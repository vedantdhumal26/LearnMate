"""
Evaluation concurrency protection (Milestone: Groq 429 Quota Contention).
Guarantees at most ONE evaluation run at a time across the entire process.
"""

import threading
import time
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.core.logging_config import logger


class EvaluationLockManager:
    """
    Thread-safe manager ensuring only one evaluation run executes concurrently.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._active_run_id: Optional[str] = None
        self._started_at: Optional[float] = None

    def is_running(self, db: Optional[Session] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if an evaluation run is currently active in memory or in the database.
        Returns (is_active: bool, active_run_id: Optional[str]).
        """
        with self._lock:
            if self._active_run_id is not None:
                return True, self._active_run_id

        # Also check DB for active runs if db session provided
        if db is not None:
            try:
                from app.models.evaluation import EvaluationRun
                active_db_run = db.query(EvaluationRun).filter(
                    EvaluationRun.status.in_(["running", "pending", "started"])
                ).first()
                if active_db_run is not None:
                    # Sanity check: if it started more than 30 minutes ago without update, it may be orphaned
                    return True, active_db_run.id
            except Exception as e:
                logger.warning(f"Error querying active evaluation runs in DB: {e}")

        return False, None

    def acquire(self, run_id: str, db: Optional[Session] = None) -> bool:
        """
        Attempt to acquire the exclusive evaluation lock.
        Returns True if acquired, False if another evaluation is already active.
        """
        with self._lock:
            if self._active_run_id is not None:
                logger.warning(
                    f"[EVAL_LOCK] Denied acquire for run '{run_id}'. "
                    f"Run '{self._active_run_id}' is already active."
                )
                return False

            if db is not None:
                try:
                    from app.models.evaluation import EvaluationRun
                    active_db_run = db.query(EvaluationRun).filter(
                        EvaluationRun.status.in_(["running", "pending", "started"]),
                        EvaluationRun.id != run_id
                    ).first()
                    if active_db_run is not None:
                        logger.warning(
                            f"[EVAL_LOCK] Denied acquire for run '{run_id}'. "
                            f"Database run '{active_db_run.id}' has status '{active_db_run.status}'."
                        )
                        return False
                except Exception as e:
                    logger.warning(f"Error querying active evaluation runs in DB: {e}")

            self._active_run_id = run_id
            self._started_at = time.time()
            logger.info(f"[EVAL_LOCK] Acquired exclusive evaluation lock for run '{run_id}'.")
            return True

    def release(self, run_id: str) -> None:
        """Release the exclusive evaluation lock."""
        with self._lock:
            if self._active_run_id == run_id:
                duration = time.time() - (self._started_at or time.time())
                self._active_run_id = None
                self._started_at = None
                logger.info(
                    f"[EVAL_LOCK] Released exclusive evaluation lock for run '{run_id}' "
                    f"(held for {duration:.1f}s)."
                )

    def force_reset(self) -> None:
        """Force reset the lock (useful for tests)."""
        with self._lock:
            self._active_run_id = None
            self._started_at = None


# Process-wide singleton
_eval_lock_instance: Optional[EvaluationLockManager] = None
_eval_init_lock = threading.Lock()


def get_evaluation_lock_manager() -> EvaluationLockManager:
    global _eval_lock_instance
    if _eval_lock_instance is None:
        with _eval_init_lock:
            if _eval_lock_instance is None:
                _eval_lock_instance = EvaluationLockManager()
    return _eval_lock_instance
