"""
Process-wide LLM Concurrency Gate and Priority Pacer (Milestone: Groq 429 Quota Contention).

Features:
- Single process-wide limiter (default: 1 concurrent Groq request).
- Priority ordering:
    1. Tutor (user-facing, highest priority)
    2. Assessment generation (user-facing, high priority)
    3. Evaluation / background jobs (lowest priority)
- Global rate pacing (minimum spacing LLM_MIN_INTERVAL_SECONDS between requests).
- Evaluation yielding: background evaluations immediately yield when user-facing requests arrive.
- Safe bounded wait with fail-fast timeouts on quota congestion.
"""

import time
import heapq
import threading
from enum import IntEnum
from typing import Optional, List, Tuple, Any
from contextvars import ContextVar
from contextlib import contextmanager

from app.core.config import settings
from app.core.logging_config import logger


class RequestPriority(IntEnum):
    TUTOR = 1
    ASSESSMENT = 2
    EVALUATION = 3


# Context variables for caller tracing
current_request_priority: ContextVar[int] = ContextVar(
    "current_request_priority", default=RequestPriority.TUTOR
)
current_request_type: ContextVar[str] = ContextVar(
    "current_request_type", default="tutor"
)


def get_priority_for_type(request_type: str) -> int:
    req_norm = request_type.lower().strip()
    if req_norm in ("tutor", "chat"):
        return RequestPriority.TUTOR
    elif req_norm in ("assessment", "question_generation", "grader"):
        return RequestPriority.ASSESSMENT
    elif req_norm in ("evaluation", "eval", "background"):
        return RequestPriority.EVALUATION
    return RequestPriority.TUTOR


class LLMConcurrencyGate:
    """
    Thread-safe Priority Concurrency Gate with Global Rate Pacing.
    Guarantees user-facing requests jump ahead of background evaluation tasks.
    """
    def __init__(
        self,
        max_concurrency: Optional[int] = None,
        min_interval_seconds: Optional[float] = None,
    ):
        self.max_concurrency = (
            max_concurrency
            if max_concurrency is not None
            else getattr(settings, "LLM_MAX_CONCURRENCY", 1)
        )
        self.min_interval_seconds = (
            min_interval_seconds
            if min_interval_seconds is not None
            else getattr(settings, "LLM_MIN_INTERVAL_SECONDS", 2.0)
        )
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._active_count = 0
        self._last_finish_time = 0.0
        self._provider_rate_limited_until = 0.0
        # Waiters heap entries: (priority, seq, item_id)
        self._waiters: List[Tuple[int, int, int]] = []
        self._seq = 0
        self._total_requests_served = 0

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active_count

    @property
    def waiting_count(self) -> int:
        with self._lock:
            return len(self._waiters)

    def record_rate_limit(self, duration: float = 5.0, reason: str = "") -> None:
        """Record an active rate limit from provider to fail-fast background evaluation jobs."""
        with self._lock:
            self._provider_rate_limited_until = max(
                self._provider_rate_limited_until,
                time.monotonic() + duration
            )
            logger.warning(
                f"[GATE_RATE_LIMIT] Provider rate limit active for {duration:.1f}s: {reason}"
            )

    def is_rate_limited(self) -> bool:
        """Check whether the provider is currently in a known rate-limit cooldown."""
        with self._lock:
            return time.monotonic() < self._provider_rate_limited_until

    def reset_rate_limit(self) -> None:
        """Reset rate limit cooldown (useful for testing)."""
        with self._lock:
            self._provider_rate_limited_until = 0.0

    def acquire(
        self,
        priority: int = RequestPriority.TUTOR,
        request_type: str = "tutor",
        timeout: Optional[float] = None
    ) -> None:
        """
        Acquire a slot in the concurrency gate respecting priority and pacing.
        Raises LLMRateLimitError if timeout expires before slot is acquired.
        """
        from app.services.llm.llm_service import LLMRateLimitError

        deadline = (time.monotonic() + timeout) if timeout is not None else None
        item_id = id(object())

        with self._condition:
            # Step 6: Fail-fast before enqueuing if provider is already in a rate-limit cooldown
            if priority == RequestPriority.EVALUATION and time.monotonic() < self._provider_rate_limited_until:
                remaining = self._provider_rate_limited_until - time.monotonic()
                logger.warning(
                    f"[GATE_EVAL_YIELD] Fast-failing evaluation request: provider quota is currently rate-limited "
                    f"({remaining:.1f}s cooldown remaining)."
                )
                raise LLMRateLimitError(
                    "AI service is temporarily busy (HTTP 429 rate limit active). Evaluation yielding."
                )

            self._seq += 1
            my_seq = self._seq
            my_entry = (int(priority), my_seq, item_id)
            heapq.heappush(self._waiters, my_entry)

            logger.debug(
                f"[GATE_QUEUE] Enqueued request_type='{request_type}' priority={priority} "
                f"seq={my_seq}. Total waiters={len(self._waiters)}, active={self._active_count}"
            )

            try:
                while True:
                    # Check if provider became rate-limited while waiting
                    if priority == RequestPriority.EVALUATION and time.monotonic() < self._provider_rate_limited_until:
                        logger.warning(
                            f"[GATE_EVAL_YIELD] Fast-failing waiting evaluation request: provider rate limit active."
                        )
                        raise LLMRateLimitError(
                            "AI service is temporarily busy (HTTP 429 rate limit active). Evaluation yielding."
                        )

                    # Check timeout
                    if deadline is not None:
                        remaining_timeout = deadline - time.monotonic()
                        if remaining_timeout <= 0:
                            logger.warning(
                                f"[GATE_TIMEOUT] Request '{request_type}' (priority={priority}) "
                                f"timed out waiting for LLM gate slot after {timeout:.1f}s."
                            )
                            raise LLMRateLimitError(
                                "AI service is temporarily busy. Please try again."
                            )
                    else:
                        remaining_timeout = None

                    # Can we run? Must be top waiter and active_count < max_concurrency
                    if (
                        self._waiters
                        and self._waiters[0] == my_entry
                        and self._active_count < self.max_concurrency
                    ):
                        now = time.monotonic()
                        elapsed_since_last = now - self._last_finish_time
                        remaining_pacing = self.min_interval_seconds - elapsed_since_last

                        if remaining_pacing <= 0:
                            # Pacing satisfied! Pop and acquire slot.
                            heapq.heappop(self._waiters)
                            self._active_count += 1
                            logger.debug(
                                f"[GATE_ACQUIRE] Acquired slot for '{request_type}' priority={priority} "
                                f"seq={my_seq}. Active={self._active_count}"
                            )
                            return
                        else:
                            # Must wait for remaining pacing duration.
                            wait_duration = (
                                min(remaining_pacing, remaining_timeout)
                                if remaining_timeout is not None
                                else remaining_pacing
                            )
                            # Wait releases lock and re-checks conditions upon wake
                            self._condition.wait(timeout=wait_duration)
                    else:
                        # Not our turn or capacity reached. Wait for wake up or timeout.
                        self._condition.wait(timeout=remaining_timeout)

            except Exception:
                # Cleanup if timed out or interrupted
                if my_entry in self._waiters:
                    self._waiters.remove(my_entry)
                    heapq.heapify(self._waiters)
                self._condition.notify_all()
                raise

    def release(self) -> None:
        """Release the acquired slot and trigger pacing timer."""
        with self._condition:
            if self._active_count > 0:
                self._active_count -= 1
            self._last_finish_time = time.monotonic()
            self._total_requests_served += 1
            logger.debug(
                f"[GATE_RELEASE] Released slot. Active={self._active_count}, "
                f"Waiters={len(self._waiters)}"
            )
            # Wake up all waiting threads to evaluate next highest priority
            self._condition.notify_all()

    @contextmanager
    def limit(
        self,
        priority: Optional[int] = None,
        request_type: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """Context manager to safely acquire and release gate slot."""
        eff_type = request_type or current_request_type.get()
        eff_priority = (
            priority
            if priority is not None
            else current_request_priority.get()
            if current_request_priority.get() != RequestPriority.TUTOR
            else get_priority_for_type(eff_type)
        )

        # User requests fail-fast after 25s if queue is jammed; evaluation can wait longer
        if timeout is None:
            timeout = 25.0 if eff_priority <= RequestPriority.ASSESSMENT else 120.0

        self.acquire(priority=eff_priority, request_type=eff_type, timeout=timeout)
        try:
            yield
        finally:
            self.release()


# Process-wide singleton
_process_gate_instance: Optional[LLMConcurrencyGate] = None
_gate_init_lock = threading.Lock()


def get_llm_gate() -> LLMConcurrencyGate:
    """Retrieve the process-wide shared LLM concurrency gate."""
    global _process_gate_instance
    if _process_gate_instance is None:
        with _gate_init_lock:
            if _process_gate_instance is None:
                _process_gate_instance = LLMConcurrencyGate()
    return _process_gate_instance
