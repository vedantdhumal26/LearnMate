"""
Comprehensive tests for Groq 429 Quota Contention, Concurrency Gate, and Rate Pacing.
Covers all 9 required test scenarios in Step 13.
"""

import time
import json
import threading
import pytest
from unittest.mock import patch, MagicMock
from openai import RateLimitError, APITimeoutError
import httpx

from app.services.llm.concurrency_gate import (
    LLMConcurrencyGate,
    RequestPriority,
    get_llm_gate
)
from app.services.llm.llm_service import (
    OpenAILLMService,
    LLMRateLimitError,
    LLMTimeoutError,
    parse_provider_retry_after
)
from app.services.evaluation.eval_lock import get_evaluation_lock_manager
from app.models.course import Course
from app.models.document_chunk import DocumentChunk
from app.models.source import Source
from app.schemas.tutor import TutorChatResponse, CitationItem


@pytest.fixture(autouse=True)
def reset_gate_and_eval_lock():
    """Reset evaluation lock and gate rate limits before and after each test."""
    get_llm_gate().reset_rate_limit()
    get_evaluation_lock_manager().force_reset()
    yield
    get_llm_gate().reset_rate_limit()
    get_evaluation_lock_manager().force_reset()


# -------------------------------------------------------------------------
# Test 1: Two simultaneous Tutor requests: verify only 1 Groq request at a time
# -------------------------------------------------------------------------
def test_two_simultaneous_tutor_requests_serialized():
    """Verify only 1 concurrent Groq request executes at a time under the shared gate."""
    gate = LLMConcurrencyGate(max_concurrency=1, min_interval_seconds=0.05)

    active_executions = 0
    max_active_observed = 0
    lock = threading.Lock()
    execution_order = []

    def run_tutor_call(req_id: int):
        nonlocal active_executions, max_active_observed
        with gate.limit(priority=RequestPriority.TUTOR, request_type="tutor"):
            with lock:
                active_executions += 1
                if active_executions > max_active_observed:
                    max_active_observed = active_executions
            time.sleep(0.1)  # Simulate LLM generation time
            with lock:
                active_executions -= 1
                execution_order.append(req_id)

    t1 = threading.Thread(target=run_tutor_call, args=(1,))
    t2 = threading.Thread(target=run_tutor_call, args=(2,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert max_active_observed == 1, f"Concurrency exceeded 1: observed {max_active_observed}"
    assert len(execution_order) == 2


# -------------------------------------------------------------------------
# Test 2: Tutor + Evaluation simultaneously: verify Tutor gets priority
# -------------------------------------------------------------------------
def test_tutor_prioritized_over_evaluation():
    """Verify user-facing Tutor request jumps ahead of waiting Evaluation requests."""
    # Use pacing to keep slot reserved briefly
    gate = LLMConcurrencyGate(max_concurrency=1, min_interval_seconds=0.1)

    execution_order = []
    eval_started = threading.Event()
    release_initial_block = threading.Event()

    # Step 1: Hold the slot with initial job
    def blocker():
        with gate.limit(priority=RequestPriority.EVALUATION, request_type="initial_job"):
            eval_started.set()
            release_initial_block.wait(timeout=5.0)

    # Step 2: Evaluation tries to acquire (will wait in queue)
    def eval_worker():
        eval_started.wait()
        # Give blocker a moment to establish
        time.sleep(0.02)
        with gate.limit(priority=RequestPriority.EVALUATION, request_type="evaluation"):
            execution_order.append("evaluation")

    # Step 3: Tutor tries to acquire (arrives after eval, but should jump ahead)
    def tutor_worker():
        eval_started.wait()
        time.sleep(0.04)  # Arrives strictly after evaluation was enqueued
        with gate.limit(priority=RequestPriority.TUTOR, request_type="tutor"):
            execution_order.append("tutor")

    t_block = threading.Thread(target=blocker)
    t_eval = threading.Thread(target=eval_worker)
    t_tutor = threading.Thread(target=tutor_worker)

    t_block.start()
    t_eval.start()
    t_tutor.start()

    # Wait for blocker to start and threads to enqueue
    time.sleep(0.1)
    # Release initial blocker
    release_initial_block.set()

    t_block.join()
    t_eval.join()
    t_tutor.join()

    # Tutor MUST have executed before evaluation despite arriving second!
    assert execution_order == ["tutor", "evaluation"], (
        f"Priority inversion: Expected ['tutor', 'evaluation'], got {execution_order}"
    )


# -------------------------------------------------------------------------
# Test 3: Two simultaneous evaluations: verify second returns HTTP 409
# -------------------------------------------------------------------------
def test_two_simultaneous_evaluations_returns_409(client, db_session):
    """Verify starting an evaluation while another is running returns HTTP 409 Conflict."""
    course = Course(title="Eval Concurrency Course")
    db_session.add(course)
    db_session.commit()

    lock_mgr = get_evaluation_lock_manager()
    lock_mgr.force_reset()

    # Acquire lock simulating an active run
    acquired = lock_mgr.acquire("test-active-run-123", db=db_session)
    assert acquired is True

    try:
        # Attempt to start a second evaluation run
        response = client.post("/api/evaluation/run", json={
            "name": "Second Concurrent Run",
            "course_id": course.id,
            "dataset": [],
            "sync": False
        })

        assert response.status_code == 409
        data = response.json()
        assert "An evaluation is already running" in data["detail"]
    finally:
        lock_mgr.release("test-active-run-123")


# -------------------------------------------------------------------------
# Test 4: Groq 429: verify bounded handling and no long blocking sleep
# -------------------------------------------------------------------------
def test_groq_429_fails_fast_without_long_sleep():
    """Verify that when Groq asks to wait 5m20s, system fails fast without blocking."""
    # Test retry-after duration extraction
    raw_error_text = "Rate limit reached for model openai/gpt-oss-120b on TPM: Limit 8000. Please try again in 5m20s."
    mock_request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(429, request=mock_request, headers={"retry-after": "320"})
    rate_err = RateLimitError(raw_error_text, response=mock_response, body=None)

    wait_s = parse_provider_retry_after(rate_err)
    assert wait_s == 320.0 or wait_s == 320  # parsed 5m20s / 320s

    # Verify OpenAILLMService fails fast when provider wait > MAX_DELAY_PER_RETRY (3.0s)
    service = OpenAILLMService(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="gsk_dummy_test_key"
    )

    with patch.object(service.client.chat.completions, "create", side_effect=rate_err):
        start_time = time.time()
        with pytest.raises(LLMRateLimitError) as exc_info:
            service.generate(prompt="Hello", system_prompt="Test")
        duration = time.time() - start_time

        # Duration MUST be well under 3.0 seconds, proving NO 320s sleep occurred!
        assert duration < 3.0, f"Blocked for too long on 429: {duration:.2f}s"
        assert "temporarily busy" in str(exc_info.value)


# -------------------------------------------------------------------------
# Test 5: Groq timeout: verify bounded failure
# -------------------------------------------------------------------------
def test_groq_timeout_bounded_failure():
    """Verify provider timeout raises LLMTimeoutError without infinite hanging."""
    service = OpenAILLMService(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="gsk_dummy_test_key"
    )

    mock_request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    timeout_err = APITimeoutError(request=mock_request)

    with patch.object(service.client.chat.completions, "create", side_effect=timeout_err):
        with pytest.raises(LLMTimeoutError) as exc_info:
            service.generate(prompt="Explain inertia", system_prompt="Physics tutor")

        assert "timed out" in str(exc_info.value).lower()


# -------------------------------------------------------------------------
# Test 6: Normal Tutor: verify 200
# -------------------------------------------------------------------------
def test_normal_tutor_200(client, db_session):
    """Verify normal grounded tutor query returns 200 with citations."""
    course = Course(title="Physics 101")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    from app.services.vector_store.base import VectorSearchResult

    mock_answer = "Newton's second law is F = m * a as stated in physics.pdf — Page 2."
    mock_chunks = [
        VectorSearchResult(
            chunk_id="chk-1",
            course_id=course.id,
            source_id="src-1",
            file_name="physics.pdf",
            page_number=2,
            content="Newton's second law: F = ma.",
            score=0.92,
            modality="pdf"
        )
    ]

    with patch("app.services.rag.tutor_service.CourseRetriever.retrieve", return_value=mock_chunks), \
         patch("app.services.rag.tutor_service.GroundingValidator.validate_pre_retrieval", return_value=(True, "")), \
         patch("app.services.rag.tutor_service.GroundingValidator.validate_post_generation", return_value=(True, mock_answer, [CitationItem(source_id="src-1", file_name="physics.pdf", page=2, excerpt="F = ma", modality="pdf")])):

        with patch("app.services.llm.llm_service.OpenAILLMService.generate", return_value=mock_answer):
            res = client.post("/api/tutor/chat", json={
                "course_id": course.id,
                "message": "What is Newton's second law?"
            })

            assert res.status_code == 200
            data = res.json()
            assert data["grounded"] is True
            assert "F = m * a" in data["answer"]
            assert len(data["sources"]) >= 1


# -------------------------------------------------------------------------
# Test 7: Normal Assessment count=1: verify 201
# -------------------------------------------------------------------------
def test_normal_assessment_count_1_created(client, db_session):
    """Verify generating 1 assessment question returns 201 Created with bounded generation."""
    from app.services.vector_store.base import VectorSearchResult

    course = Course(title="Thermodynamics")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    mock_mcq_json = json.dumps([
        {
            "question": "What is the first law of thermodynamics?",
            "options": [
                "A) Delta U = Q - W",
                "B) F = ma",
                "C) E = mc^2",
                "D) V = IR"
            ],
            "correct_answer": "A",
            "explanation": "Delta U = Q - W relates internal energy, heat, and work.",
            "difficulty": "medium",
            "topic": "Thermodynamics"
        }
    ])

    mock_chunk = VectorSearchResult(
        chunk_id="chk-th",
        course_id=course.id,
        source_id="src-th",
        file_name="thermo.pdf",
        page_number=1,
        content="The first law of thermodynamics states Delta U = Q - W.",
        score=0.88,
        modality="pdf"
    )

    from tests.conftest import MockLLMService
    from app.api.routes.assessments import assessment_service

    old_llm = assessment_service.question_generator._llm_service
    assessment_service.question_generator._llm_service = MockLLMService(response_text=mock_mcq_json)

    try:
        with patch("app.services.assessment.question_generator.CourseRetriever.retrieve", return_value=[mock_chunk]), \
             patch("app.services.assessment.question_generator.GroundingValidator.validate_pre_retrieval", return_value=(True, "")):
            res = client.post("/api/assessments/generate", json={
                "course_id": course.id,
                "topic": "Thermodynamics",
                "question_type": "mcq",
                "count": 1,
                "difficulty": "medium"
            })

            assert res.status_code == 201
            data = res.json()
            assert len(data["questions"]) == 1
            assert data["questions"][0]["question_type"] == "mcq"
    finally:
        assessment_service.question_generator._llm_service = old_llm


# -------------------------------------------------------------------------
# Test 8: 1-case Evaluation: verify completion
# -------------------------------------------------------------------------
def test_single_case_evaluation_completion(client, db_session):
    """Verify single-case evaluation completes successfully and computes summary metrics."""
    course = Course(title="Eval Single Case Course")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    get_evaluation_lock_manager().force_reset()

    mock_tutor_response = TutorChatResponse(
        answer="Momentum is mass times velocity (p = mv) on physics.pdf — Page 4.",
        grounded=True,
        sources=[
            CitationItem(
                source_id="src-p",
                file_name="physics.pdf",
                page=4,
                excerpt="p = mv",
                modality="pdf"
            )
        ]
    )

    with patch("app.services.rag.tutor_service.TutorService.answer_question", return_value=mock_tutor_response):
        run_res = client.post("/api/evaluation/run", json={
            "name": "1-Case Evaluation Run",
            "course_id": course.id,
            "dataset": [
                {
                    "id": "eval-single-01",
                    "course_id": course.id,
                    "question": "What is momentum?",
                    "expected_grounded": True,
                    "expected_sources": []
                }
            ],
            "run_learner_simulations": False,
            "run_assessment_eval": False,
            "sync": True
        })

        assert run_res.status_code == 201
        eval_id = run_res.json()["evaluation_id"]

        # Results endpoint
        results_res = client.get(f"/api/evaluation/{eval_id}/results")
        assert results_res.status_code == 200
        data = results_res.json()
        assert data["summary"]["total_test_cases"] == 1
        assert data["summary"]["grounding_accuracy"] == 1.0


# -------------------------------------------------------------------------
# Test 9: Existing course isolation: verify unchanged
# -------------------------------------------------------------------------
def test_course_isolation_rejection_unchanged(client, db_session):
    """Verify cross-course query isolation is maintained without regression."""
    c1 = Course(title="Course 1 - Fluid Dynamics")
    c2 = Course(title="Course 2 - Medieval History")
    db_session.add_all([c1, c2])
    db_session.commit()

    # Query Course 2 (History) about Course 1 (Fluid Dynamics)
    # CourseRetriever returns empty list for unrelated course
    with patch("app.services.rag.tutor_service.CourseRetriever.retrieve", return_value=[]):
        res = client.post("/api/tutor/chat", json={
            "course_id": c2.id,
            "message": "Explain Bernoulli's equation for inviscid fluid flow"
        })

        assert res.status_code == 200
        data = res.json()
        # Must be rejected pre-retrieval
        assert data["grounded"] is False
        assert "couldn't find enough information" in data["answer"].lower()
        assert len(data["sources"]) == 0


# -------------------------------------------------------------------------
# Test 10: Quick Evaluation: verify default mode bounds cases to EVALUATION_MAX_CASES_LIVE (3)
# -------------------------------------------------------------------------
def test_quick_evaluation_bounded_to_max_cases(client, db_session):
    """Verify default/quick evaluation mode bounds benchmark cases to EVALUATION_MAX_CASES_LIVE (3 cases)."""
    course = Course(title="Quick Eval Benchmark Course")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    get_evaluation_lock_manager().force_reset()

    mock_resp = TutorChatResponse(
        answer="Grounded answer for quick evaluation test case.",
        grounded=True,
        sources=[]
    )

    with patch("app.services.rag.tutor_service.TutorService.answer_question", return_value=mock_resp):
        res = client.post("/api/evaluation/run", json={
            "name": "Quick Demo Evaluation",
            "course_id": course.id,
            "mode": "quick",
            "run_learner_simulations": False,
            "run_assessment_eval": False,
            "sync": True
        })

        assert res.status_code == 201
        eval_id = res.json()["evaluation_id"]

        results_res = client.get(f"/api/evaluation/{eval_id}/results")
        assert results_res.status_code == 200
        data = results_res.json()

        # Must be bounded to 3 cases (not the 40 cases of the full benchmark)
        assert data["summary"]["total_test_cases"] == 3
        assert len(data["results"]) == 3
        assert data["status"] == "completed"


# -------------------------------------------------------------------------
# Test 11: Full Evaluation: verify mode="full" executes all test cases
# -------------------------------------------------------------------------
def test_full_evaluation_runs_all_cases(client, db_session):
    """Verify mode='full' executes all test cases without quick bounding."""
    course = Course(title="Full Eval Course")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    get_evaluation_lock_manager().force_reset()

    # Pass 5 test cases
    custom_dataset = [
        {
            "id": f"eval-full-{i}",
            "course_id": course.id,
            "question": f"Question {i}?",
            "expected_grounded": True,
            "expected_sources": []
        }
        for i in range(5)
    ]

    mock_resp = TutorChatResponse(
        answer="Grounded answer for full evaluation case.",
        grounded=True,
        sources=[]
    )

    with patch("app.services.rag.tutor_service.TutorService.answer_question", return_value=mock_resp):
        res = client.post("/api/evaluation/run", json={
            "name": "Full Benchmark Run",
            "course_id": course.id,
            "mode": "full",
            "dataset": custom_dataset,
            "run_learner_simulations": False,
            "run_assessment_eval": False,
            "sync": True
        })

        assert res.status_code == 201
        eval_id = res.json()["evaluation_id"]

        results_res = client.get(f"/api/evaluation/{eval_id}/results")
        assert results_res.status_code == 200
        data = results_res.json()

        # All 5 cases executed
        assert data["summary"]["total_test_cases"] == 5
        assert len(data["results"]) == 5
        assert data["status"] == "completed"


# -------------------------------------------------------------------------
# Test 12: Evaluation priority yields to both Tutor (1) and Assessment (2)
# -------------------------------------------------------------------------
def test_evaluation_priority_yields_to_tutor_and_assessment():
    """Verify Evaluation (priority 3) yields to Tutor (priority 1) and Assessment (priority 2)."""
    gate = LLMConcurrencyGate(max_concurrency=1, min_interval_seconds=0.05)

    execution_order = []
    blocker_active = threading.Event()
    release_blocker = threading.Event()

    def blocker_worker():
        with gate.limit(priority=RequestPriority.EVALUATION, request_type="blocker"):
            blocker_active.set()
            release_blocker.wait(timeout=5.0)

    def eval_worker():
        blocker_active.wait()
        time.sleep(0.01)  # Arrives first
        with gate.limit(priority=RequestPriority.EVALUATION, request_type="evaluation"):
            execution_order.append("evaluation")

    def assessment_worker():
        blocker_active.wait()
        time.sleep(0.02)  # Arrives second
        with gate.limit(priority=RequestPriority.ASSESSMENT, request_type="assessment"):
            execution_order.append("assessment")

    def tutor_worker():
        blocker_active.wait()
        time.sleep(0.03)  # Arrives third
        with gate.limit(priority=RequestPriority.TUTOR, request_type="tutor"):
            execution_order.append("tutor")

    t_block = threading.Thread(target=blocker_worker)
    t_eval = threading.Thread(target=eval_worker)
    t_asmt = threading.Thread(target=assessment_worker)
    t_tutor = threading.Thread(target=tutor_worker)

    t_block.start()
    t_eval.start()
    t_asmt.start()
    t_tutor.start()

    time.sleep(0.1)  # Wait for all workers to enqueue in gate
    release_blocker.set()

    t_block.join()
    t_tutor.join()
    t_asmt.join()
    t_eval.join()

    # Priority ordering MUST be: Tutor (1), then Assessment (2), then Evaluation (3)
    assert execution_order == ["tutor", "assessment", "evaluation"], (
        f"Incorrect priority execution order: {execution_order}"
    )


# -------------------------------------------------------------------------
# Test 13: Evaluation 429 fail-fast aborts run immediately
# -------------------------------------------------------------------------
def test_evaluation_429_fail_fast_aborts_run(client, db_session):
    """Verify that when Groq returns 429 during evaluation, the run aborts immediately and records failure."""
    course = Course(title="Fail Fast Eval Course")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    get_evaluation_lock_manager().force_reset()
    get_llm_gate().reset_rate_limit()

    call_count = 0

    def mock_answer_rate_limited(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise LLMRateLimitError("AI service is temporarily busy. Please try again.")

    custom_dataset = [
        {"id": f"eval-case-{i}", "course_id": course.id, "question": f"Question {i}?", "expected_grounded": True}
        for i in range(3)
    ]

    with patch("app.services.rag.tutor_service.TutorService.answer_question", side_effect=mock_answer_rate_limited):
        res = client.post("/api/evaluation/run", json={
            "name": "Rate Limited Evaluation",
            "course_id": course.id,
            "dataset": custom_dataset,
            "run_learner_simulations": False,
            "run_assessment_eval": False,
            "sync": True
        })

        assert res.status_code == 201
        eval_id = res.json()["evaluation_id"]

        status_res = client.get(f"/api/evaluation/{eval_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["status"] == "failed"
        assert "HTTP 429" in data["failure_reason"] or "temporarily busy" in data["failure_reason"].lower()

        # Proves it failed fast on the very 1st case and didn't execute remaining cases!
        assert call_count == 1, f"Expected 1 call, but got {call_count} calls (failed to abort early)."


# -------------------------------------------------------------------------
# Test 14: Evaluation 429 before execution fast fails without calling LLM
# -------------------------------------------------------------------------
def test_evaluation_429_before_execution_fast_fails(client, db_session):
    """Verify that when provider rate limit is active on gate, evaluation fails fast before executing test cases."""
    course = Course(title="Pre-Execution 429 Course")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    get_evaluation_lock_manager().force_reset()
    gate = get_llm_gate()

    # Simulate an active rate limit recorded from a previous call
    gate.record_rate_limit(duration=2.0, reason="Provider 429 active")

    tutor_mock = MagicMock()

    try:
        with patch("app.services.rag.tutor_service.TutorService.answer_question", tutor_mock):
            res = client.post("/api/evaluation/run", json={
                "name": "Pre-check 429 Evaluation",
                "course_id": course.id,
                "dataset": [{"id": "eval-pre-01", "course_id": course.id, "question": "Q?", "expected_grounded": True}],
                "run_learner_simulations": False,
                "run_assessment_eval": False,
                "sync": True
            })

            assert res.status_code == 201
            eval_id = res.json()["evaluation_id"]

            status_res = client.get(f"/api/evaluation/{eval_id}")
            assert status_res.status_code == 200
            data = status_res.json()
            assert data["status"] == "failed"
            assert "HTTP 429" in data["failure_reason"] or "rate limit" in data["failure_reason"].lower()

            # Tutor was never invoked because evaluation failed fast beforehand!
            assert tutor_mock.call_count == 0
    finally:
        gate.reset_rate_limit()


# -------------------------------------------------------------------------
# Test 15: Evaluation no infinite retry on 429
# -------------------------------------------------------------------------
def test_evaluation_no_infinite_retry_on_429():
    """Verify evaluation LLM generation performs at most 1 attempt on 429 and does not loop."""
    service = OpenAILLMService(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="gsk_dummy_test_key"
    )

    raw_error_text = "Rate limit reached for model openai/gpt-oss-120b on TPM: Limit 8000."
    mock_request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(429, request=mock_request, headers={"retry-after": "1.0"})
    rate_err = RateLimitError(raw_error_text, response=mock_response, body=None)

    create_mock = MagicMock(side_effect=rate_err)

    with patch.object(service.client.chat.completions, "create", create_mock):
        start_time = time.time()
        with pytest.raises(LLMRateLimitError):
            service.generate(
                prompt="Explain gravity",
                system_prompt="Physics evaluator",
                request_type="evaluation",
                priority=RequestPriority.EVALUATION
            )
        duration = time.time() - start_time

        # Must execute only once (max_retries = 1 for evaluation)
        assert create_mock.call_count == 1
        assert duration < 2.0

