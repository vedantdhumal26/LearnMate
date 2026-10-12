import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.course import Course
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.models.assessment import Question
from app.schemas.evaluation import (
    ExpectedSource,
    EvaluationTestCase,
    EvaluationRunRequest,
    EvaluationMetricsSummary,
    LearnerSimulationResult,
)
from app.schemas.tutor import CitationItem, TutorChatResponse
from app.services.evaluation.citation_evaluator import CitationEvaluator
from app.services.evaluation.rag_evaluator import RAGEvaluator
from app.services.evaluation.assessment_evaluator import AssessmentEvaluator
from app.services.evaluation.learner_evaluator import LearnerModelEvaluator
from app.services.evaluation.evaluator import EvaluationEngine
from app.services.evaluation.fixtures import get_default_evaluation_dataset


def test_dataset_validation():
    """Verify evaluation dataset models enforce strict types and reject malformed schemas."""
    # Valid test case
    tc = EvaluationTestCase(
        id="eval-001",
        course_id="course-123",
        question="What is momentum?",
        expected_answer="Mass times velocity",
        expected_sources=[ExpectedSource(source_id="src-1", page=2, modality="pdf")],
        expected_grounded=True
    )
    assert tc.id == "eval-001"
    assert tc.expected_grounded is True
    assert len(tc.expected_sources) == 1
    assert tc.expected_sources[0].page == 2

    # Invalid: empty question
    with pytest.raises(ValidationError):
        EvaluationTestCase(
            id="eval-bad",
            course_id="course-123",
            question=""
        )


def test_metric_aggregation_without_fabrication():
    """Verify metric summary aggregates strictly calculated values and does not fabricate missing metrics."""
    summary = EvaluationMetricsSummary(
        faithfulness=0.88,
        answer_relevancy=0.82,
        context_precision=None,  # Not calculated
        context_recall=None,     # Not calculated
        citation_accuracy=1.0,
        citation_failure_count=0,
        grounding_accuracy=0.95,
        supported_questions_count=10,
        supported_questions_passed=10,
        unsupported_questions_count=5,
        unsupported_questions_passed=4,
        course_isolation_failures=0,
        course_isolation_tests_count=2,
        assessment_valid_question_rate=0.96,
        duplicate_rate=0.03,
        total_test_cases=17,
        passed_test_cases=16
    )

    assert summary.faithfulness == 0.88
    assert summary.answer_relevancy == 0.82
    assert summary.context_precision is None
    assert summary.context_recall is None
    assert summary.citation_accuracy == 1.0
    assert summary.citation_failure_count == 0
    assert summary.course_isolation_failures == 0


def test_grounding_evaluation_supported_vs_unsupported(db_session):
    """Verify evaluation engine correctly discriminates supported, unsupported, and false overclaims."""
    course = Course(title="Physics Course")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    mock_tutor = MagicMock()
    # Case 1: Supported question correctly answered
    # Case 2: Unsupported question correctly rejected
    # Case 3: Unsupported question incorrectly overclaimed
    mock_tutor.answer_question.side_effect = [
        TutorChatResponse(answer="F = ma", grounded=True, sources=[]),
        TutorChatResponse(answer="I couldn't find enough information", grounded=False, sources=[]),
        TutorChatResponse(answer="Here is a made up fact", grounded=True, sources=[]),
    ]

    engine = EvaluationEngine(tutor_service=mock_tutor)

    test_cases = [
        EvaluationTestCase(
            id="tc-sup",
            course_id=course.id,
            question="What is Newton's law?",
            expected_grounded=True,
            expected_sources=[]
        ),
        EvaluationTestCase(
            id="tc-unsup-ok",
            course_id=course.id,
            question="What is the capital of Mars?",
            expected_grounded=False,
            expected_sources=[]
        ),
        EvaluationTestCase(
            id="tc-unsup-overclaim",
            course_id=course.id,
            question="What are cricket rules?",
            expected_grounded=False,
            expected_sources=[]
        ),
    ]

    req = EvaluationRunRequest(
        name="Grounding Test",
        dataset=test_cases,
        run_learner_simulations=False,
        run_assessment_eval=False,
        sync=True
    )

    run = engine.run_evaluation(db_session, req)
    assert run.status == "completed"
    assert run.dataset_size == 3

    results = {r.test_case_id: r for r in run.results}
    assert results["tc-sup"].passed is True
    assert results["tc-unsup-ok"].passed is True
    assert results["tc-unsup-overclaim"].passed is False
    assert "Overclaim" in results["tc-unsup-overclaim"].failure_reason


def test_citation_validation_pdf(db_session):
    """Verify PDF page citation matching and rejection of wrong pages."""
    course = Course(title="Calculus Course")
    db_session.add(course)
    db_session.flush()

    source = Source(
        course_id=course.id,
        file_name="calculus.pdf",
        file_type="application/pdf",
        file_path="/tmp/calculus.pdf",
        source_type="pdf",
        processing_status="completed"
    )
    db_session.add(source)
    db_session.flush()

    chunk = DocumentChunk(
        source_id=source.id,
        course_id=course.id,
        content="Derivatives represent instantaneous rates of change.",
        page_number=3,
        chunk_index=0,
        content_hash="hash-pdf-1"
    )
    db_session.add(chunk)
    db_session.commit()

    # Citation with correct page (3)
    c_correct = CitationItem(
        source_id=source.id,
        file_name="calculus.pdf",
        page=3,
        excerpt="Derivatives represent instantaneous rates of change.",
        modality="pdf"
    )
    is_valid, _ = CitationEvaluator.evaluate_citation(
        citation=c_correct,
        expected_sources=[ExpectedSource(source_id=source.id, page=3, modality="pdf")],
        course_id=course.id,
        db=db_session
    )
    assert is_valid is True

    # Citation with wrong page (7)
    c_wrong_page = CitationItem(
        source_id=source.id,
        file_name="calculus.pdf",
        page=7,
        excerpt="Derivatives represent instantaneous rates of change.",
        modality="pdf"
    )
    is_valid_wrong, reason = CitationEvaluator.evaluate_citation(
        citation=c_wrong_page,
        expected_sources=[ExpectedSource(source_id=source.id, page=3, modality="pdf")],
        course_id=course.id,
        db=db_session
    )
    assert is_valid_wrong is False
    assert "does not match" in reason


def test_citation_validation_pptx(db_session):
    """Verify PPTX slide citation matching."""
    course = Course(title="Robotics Course")
    db_session.add(course)
    db_session.flush()

    source = Source(
        course_id=course.id,
        file_name="robotics.pptx",
        file_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_path="/tmp/robotics.pptx",
        source_type="pptx",
        processing_status="completed"
    )
    db_session.add(source)
    db_session.flush()

    chunk = DocumentChunk(
        source_id=source.id,
        course_id=course.id,
        content="Forward kinematics maps joint angles to end-effector position.",
        slide_number=5,
        modality="pptx_text",
        chunk_index=0,
        content_hash="hash-pptx-1"
    )
    db_session.add(chunk)
    db_session.commit()

    c = CitationItem(
        source_id=source.id,
        file_name="robotics.pptx",
        slide=5,
        excerpt="Forward kinematics maps joint angles to end-effector position.",
        modality="pptx"
    )
    is_valid, _ = CitationEvaluator.evaluate_citation(
        citation=c,
        expected_sources=[ExpectedSource(source_id=source.id, slide=5, modality="pptx")],
        course_id=course.id,
        db=db_session
    )
    assert is_valid is True


def test_citation_validation_mp4_timestamp(db_session):
    """Verify MP4 video timestamp window overlap."""
    course = Course(title="Fluid Mechanics Course")
    db_session.add(course)
    db_session.flush()

    source = Source(
        course_id=course.id,
        file_name="bernoulli.mp4",
        file_type="video/mp4",
        file_path="/tmp/bernoulli.mp4",
        source_type="video",
        processing_status="completed"
    )
    db_session.add(source)
    db_session.flush()

    chunk = DocumentChunk(
        source_id=source.id,
        course_id=course.id,
        content="Fluid velocity increase leads to static pressure decrease.",
        start_time_seconds=60.0,
        end_time_seconds=85.0,
        modality="video_transcript",
        chunk_index=0,
        content_hash="hash-mp4-1"
    )
    db_session.add(chunk)
    db_session.commit()

    # Overlapping citation interval (65-80s)
    c_good = CitationItem(
        source_id=source.id,
        file_name="bernoulli.mp4",
        start_seconds=65.0,
        end_seconds=80.0,
        excerpt="Fluid velocity increase leads to static pressure decrease.",
        modality="video"
    )
    is_valid, _ = CitationEvaluator.evaluate_citation(
        citation=c_good,
        expected_sources=[ExpectedSource(source_id=source.id, start_seconds=60.0, end_seconds=85.0, modality="video")],
        course_id=course.id,
        db=db_session
    )
    assert is_valid is True


def test_citation_validation_youtube_timestamp(db_session):
    """Verify YouTube timestamp window matching."""
    course = Course(title="Neural Networks Course")
    db_session.add(course)
    db_session.flush()

    source = Source(
        course_id=course.id,
        file_name="3Blue1Brown Neural Networks",
        file_type="youtube",
        file_path="https://www.youtube.com/watch?v=aircAruvnKk",
        source_type="youtube",
        video_id="aircAruvnKk",
        canonical_url="https://www.youtube.com/watch?v=aircAruvnKk",
        processing_status="completed"
    )
    db_session.add(source)
    db_session.flush()

    chunk = DocumentChunk(
        source_id=source.id,
        course_id=course.id,
        content="There are 784 neurons in the input layer corresponding to pixels.",
        start_time_seconds=180.0,
        end_time_seconds=210.0,
        modality="youtube",
        video_id="aircAruvnKk",
        canonical_url="https://www.youtube.com/watch?v=aircAruvnKk",
        chunk_index=0,
        content_hash="hash-yt-1"
    )
    db_session.add(chunk)
    db_session.commit()

    c_yt = CitationItem(
        source_id=source.id,
        file_name="3Blue1Brown Neural Networks",
        start_seconds=185.0,
        end_seconds=205.0,
        excerpt="[YouTube 00:03:05–00:03:25]\nThere are 784 neurons in the input layer corresponding to pixels.",
        modality="youtube",
        video_id="aircAruvnKk"
    )
    is_valid, _ = CitationEvaluator.evaluate_citation(
        citation=c_yt,
        expected_sources=[ExpectedSource(source_id=source.id, start_seconds=180.0, end_seconds=210.0, modality="youtube")],
        course_id=course.id,
        db=db_session
    )
    assert is_valid is True


def test_citation_validation_fabricated_excerpt_rejection(db_session):
    """Verify citation whose excerpt does not exist in document_chunks is flagged as fabricated."""
    course = Course(title="Course Fabricated Test")
    db_session.add(course)
    db_session.flush()

    source = Source(
        course_id=course.id,
        file_name="doc.pdf",
        file_type="application/pdf",
        file_path="/tmp/doc.pdf",
        source_type="pdf",
        processing_status="completed"
    )
    db_session.add(source)
    db_session.flush()

    chunk = DocumentChunk(
        source_id=source.id,
        course_id=course.id,
        content="Photosynthesis converts sunlight into chemical energy.",
        page_number=1,
        chunk_index=0,
        content_hash="hash-f-1"
    )
    db_session.add(chunk)
    db_session.commit()

    # Citation with completely made up excerpt
    c_fabricated = CitationItem(
        source_id=source.id,
        file_name="doc.pdf",
        page=1,
        excerpt="Subatomic quantum entanglement induces faster than light teleportation across galaxies.",
        modality="pdf"
    )
    is_valid, reason = CitationEvaluator.evaluate_citation(
        citation=c_fabricated,
        expected_sources=[],
        course_id=course.id,
        db=db_session
    )
    assert is_valid is False
    assert "fabricated" in reason.lower()


def test_course_isolation_evaluation(db_session):
    """Verify detection of cross-course vector isolation leakage."""
    c1 = Course(title="Course A: Physics")
    c2 = Course(title="Course B: History")
    db_session.add_all([c1, c2])
    db_session.commit()

    mock_tutor = MagicMock()
    # Scenario: Query Course B for Course A's topic correctly returns grounded=False
    mock_tutor.answer_question.return_value = TutorChatResponse(
        answer="I couldn't find enough information about this topic.",
        grounded=False,
        sources=[]
    )

    engine = EvaluationEngine(tutor_service=mock_tutor)
    cases = [
        EvaluationTestCase(
            id="tc-iso-ok",
            course_id=c2.id,
            question="Explain Newton's laws from Course A",
            expected_grounded=False,
            is_course_isolation=True,
            source_course_id=c1.id
        )
    ]

    req = EvaluationRunRequest(
        name="Isolation Evaluation",
        dataset=cases,
        run_learner_simulations=False,
        run_assessment_eval=False,
        sync=True
    )
    run = engine.run_evaluation(db_session, req)
    summary = json.loads(run.summary_metrics)
    assert summary["course_isolation_failures"] == 0
    assert summary["course_isolation_tests_count"] == 1


def test_learner_simulation(db_session):
    """Verify student simulations measure baseline, gain, weak topics, and dynamic recommendation adjustments."""
    course = Course(title="Machine Learning Simulation")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    evaluator = LearnerModelEvaluator()
    sim_results = evaluator.run_simulations(
        db=db_session,
        course_id=course.id,
        topic="Neural Networks"
    )

    assert len(sim_results) == 3
    profiles = {s.student_profile: s for s in sim_results}
    assert "high_performer" in profiles
    assert "mixed_performer" in profiles
    assert "struggling" in profiles

    # High performer should have higher mastery than struggling
    assert profiles["high_performer"].mastery_after > profiles["struggling"].mastery_after
    assert profiles["high_performer"].mastery_gain > 0.0

    # Struggling performer should have weak topic flagged
    assert len(profiles["struggling"].weak_topics_detected) > 0
    assert "Neural Networks" in profiles["struggling"].weak_topics_detected


def test_rag_evaluator_metrics():
    """Verify RAGEvaluator computes cosine answer relevancy and context precision/recall."""
    rag_eval = RAGEvaluator()

    # Relevancy
    score = rag_eval.evaluate_answer_relevance(
        question="What is Newton's second law?",
        answer="Newton's second law states that force equals mass multiplied by acceleration."
    )
    assert score is not None
    assert 0.0 <= score <= 1.0
    assert score > 0.5  # High semantic relevance

    # Refusal relevancy should be 0.0
    refusal_score = rag_eval.evaluate_answer_relevance(
        question="What is quantum mechanics?",
        answer="I couldn't find enough information about this topic in the uploaded course material."
    )
    assert refusal_score == 0.0

    # Context precision & recall
    retrieved = [
        CitationItem(source_id="s1", file_name="f1.pdf", page=2, excerpt="text"),
        CitationItem(source_id="s2", file_name="f2.pdf", page=8, excerpt="text"),
    ]
    expected = [
        ExpectedSource(source_id="s1", page=2)
    ]
    prec = rag_eval.evaluate_context_precision(retrieved, expected)
    rec = rag_eval.evaluate_context_recall(retrieved, expected)
    assert prec == 0.5  # 1 of 2 retrieved was relevant
    assert rec == 1.0   # 1 of 1 expected was retrieved


def test_evaluation_api_endpoints(client, db_session):
    """Test POST /api/evaluation/run, GET /api/evaluation/{id}, and GET /api/evaluation/{id}/results."""
    course_res = client.post("/api/courses", json={"title": "Eval API Course"})
    assert course_res.status_code == 201
    course_id = course_res.json()["id"]

    mock_tutor_resp = TutorChatResponse(
        answer="Neural network activations are calculated via weights and biases.",
        grounded=True,
        sources=[]
    )

    with patch("app.services.rag.tutor_service.TutorService.answer_question", return_value=mock_tutor_resp):
        # 1. Start evaluation run
        run_res = client.post("/api/evaluation/run", json={
            "name": "Integration Test Run",
            "course_id": course_id,
            "dataset": [
                {
                    "id": "eval-api-01",
                    "course_id": course_id,
                    "question": "How are activations calculated?",
                    "expected_grounded": True,
                    "expected_sources": []
                }
            ],
            "run_learner_simulations": True,
            "run_assessment_eval": False,
            "sync": True
        })
        assert run_res.status_code == 201
        eval_id = run_res.json()["evaluation_id"]

        # 2. Check status
        status_res = client.get(f"/api/evaluation/{eval_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] == "completed"
        assert status_data["dataset_size"] == 1

        # 3. Check results
        results_res = client.get(f"/api/evaluation/{eval_id}/results")
        assert results_res.status_code == 200
        res_data = results_res.json()
        assert "summary" in res_data
        assert res_data["summary"]["grounding_accuracy"] == 1.0
        assert len(res_data["learner_simulations"]) == 3
        assert len(res_data["results"]) == 1


def test_evaluation_api_not_found(client):
    """GET /api/evaluation/{nonexistent} returns 404."""
    res = client.get("/api/evaluation/non-existent-id-12345")
    assert res.status_code == 404


def test_failed_evaluation_handling(client, db_session):
    """Verify failed evaluation records failure reason and returns safe error without leaking secrets."""
    course_res = client.post("/api/courses", json={"title": "Crash Course"})
    course_id = course_res.json()["id"]

    with patch("app.services.rag.tutor_service.TutorService.answer_question", side_effect=RuntimeError("Simulated DB connection drop")):
        run_res = client.post("/api/evaluation/run", json={
            "name": "Crashing Evaluation",
            "course_id": course_id,
            "dataset": [
                {
                    "id": "eval-crash-01",
                    "course_id": course_id,
                    "question": "Will this crash?",
                    "expected_grounded": True
                }
            ],
            "run_learner_simulations": False,
            "run_assessment_eval": False,
            "sync": True
        })
        eval_id = run_res.json()["evaluation_id"]

        # Status check should report completed run with recorded failure for the case
        status_res = client.get(f"/api/evaluation/{eval_id}")
        assert status_res.status_code == 200

        results_res = client.get(f"/api/evaluation/{eval_id}/results")
        assert results_res.status_code == 200
        data = results_res.json()
        assert len(data["failures"]) >= 1
        assert "Simulated DB connection drop" in data["failures"][0]["failure_reason"]


def test_assessment_question_validity_evaluation(db_session):
    """
    Verify QuestionVerifier and AssessmentEvaluator correctly count valid questions,
    reject malformed questions, and calculate exact validity rates without fabrication.
    """
    course = Course(title="Assessment Validation Course")
    db_session.add(course)
    db_session.commit()

    evaluator = AssessmentEvaluator()

    # 1. Valid questions of different types
    valid_mcq = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="mcq",
        question_text="According to Newton's First Law, what state does an object maintain without net force?",
        options=["A) Constant velocity", "B) Infinite acceleration", "C) Zero mass", "D) Random motion"],
        correct_answer="A",
        explanation="Newton's First Law states that an object remains at rest or in uniform motion unless acted upon by a net force.",
        content_hash="hash-valid-1"
    )
    valid_mcq_text_ans = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="mcq",
        question_text="Which physical quantity is a quantitative measure of an object's inertia?",
        options=["A) Velocity", "B) Mass", "C) Weight", "D) Momentum"],
        correct_answer="Mass",
        explanation="Mass is the quantitative measure of an object's inertia, resisting acceleration under force.",
        content_hash="hash-valid-2"
    )
    valid_numerical = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="numerical",
        question_text="A force of 30 N accelerates a mass. If mass is 6 kg, calculate the acceleration in m/s^2.",
        options=None,
        correct_answer="5.0 m/s^2",
        explanation="Using Newton's Second Law: a = F / m = 30 / 6 = 5.0 m/s^2.",
        content_hash="hash-valid-3"
    )
    valid_short = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="short_answer",
        question_text="Briefly explain what is meant by an inertial frame of reference.",
        options=None,
        correct_answer="A reference frame in which Newton's first law of motion holds true.",
        explanation="In an inertial frame, an object with zero net force moves with constant velocity.",
        content_hash="hash-valid-4"
    )

    # 2. Invalid questions testing distinct failure modes
    invalid_mcq_wrong_count = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="mcq",
        question_text="What is the unit of force in SI system?",
        options=["A) Newton", "B) Joule"],  # Only 2 options instead of 4
        correct_answer="A",
        explanation="Force is measured in Newtons in the SI system.",
        content_hash="hash-inv-1"
    )
    invalid_mcq_blank_option = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="mcq",
        question_text="What is the SI unit of electrical resistance?",
        options=["A) Ohm", "B) Volt", "C) Ampere", ""],  # Blank option
        correct_answer="A",
        explanation="Resistance is measured in Ohms in the SI system.",
        content_hash="hash-inv-2"
    )
    invalid_mcq_duplicate_options = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="mcq",
        question_text="What is the formula for kinetic energy of a mass m?",
        options=["A) 1/2 m v^2", "B) 1/2 m v^2", "C) m g h", "D) F * d"],  # Non-distinct options
        correct_answer="A",
        explanation="Kinetic energy is given by half the mass times velocity squared.",
        content_hash="hash-inv-3"
    )
    invalid_mcq_unmatched_answer = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="mcq",
        question_text="Which law explains the conservation of momentum?",
        options=["A) Newton's 1st Law", "B) Newton's 2nd Law", "C) Newton's 3rd Law", "D) Hooke's Law"],
        correct_answer="Z",  # Answer key 'Z' matches none of the options
        explanation="Newton's Third Law explains the conservation of momentum.",
        content_hash="hash-inv-4"
    )
    invalid_numerical_arithmetic = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="numerical",
        question_text="Calculate the force required to accelerate a 5 kg mass at 4 m/s^2.",
        options=None,
        correct_answer="20 N",
        explanation="Using F = m * a: 5 * 4 = 35 N.",  # Inconsistent arithmetic: 5 * 4 != 35
        content_hash="hash-inv-5"
    )
    invalid_refusal_string = Question(
        course_id=course.id,
        topic_id="Classical Mechanics",
        question_type="short_answer",
        question_text="I couldn't find enough information about this topic in the uploaded materials.",
        options=None,
        correct_answer="No answer available",
        explanation="No explanation because model refused to generate question.",
        content_hash="hash-inv-6"
    )

    db_session.add_all([
        valid_mcq, valid_mcq_text_ans, valid_numerical, valid_short,
        invalid_mcq_wrong_count, invalid_mcq_blank_option, invalid_mcq_duplicate_options,
        invalid_mcq_unmatched_answer, invalid_numerical_arithmetic, invalid_refusal_string
    ])
    db_session.commit()

    # Test all 4 valid questions
    valid_result = evaluator.evaluate_questions_quality(
        questions=[valid_mcq, valid_mcq_text_ans, valid_numerical, valid_short],
        db=db_session
    )
    assert valid_result["total_evaluated"] == 4
    assert valid_result["valid_count"] == 4
    assert valid_result["invalid_count"] == 0
    assert valid_result["validity_rate"] == 1.0

    # Test all 6 invalid questions
    invalid_result = evaluator.evaluate_questions_quality(
        questions=[
            invalid_mcq_wrong_count, invalid_mcq_blank_option, invalid_mcq_duplicate_options,
            invalid_mcq_unmatched_answer, invalid_numerical_arithmetic, invalid_refusal_string
        ],
        db=db_session
    )
    assert invalid_result["total_evaluated"] == 6
    assert invalid_result["valid_count"] == 0
    assert invalid_result["invalid_count"] == 6
    assert invalid_result["validity_rate"] == 0.0
    assert len(invalid_result["failures"]) == 6

    # Test mixed batch: 4 valid + 1 invalid = 80% validity
    mixed_result = evaluator.evaluate_questions_quality(
        questions=[valid_mcq, valid_mcq_text_ans, valid_numerical, valid_short, invalid_mcq_wrong_count],
        db=db_session
    )
    assert mixed_result["total_evaluated"] == 5
    assert mixed_result["valid_count"] == 4
    assert mixed_result["invalid_count"] == 1
    assert mixed_result["validity_rate"] == 0.8


def test_empty_or_missing_assessment_samples():
    """Verify empty or missing question samples return None (unmeasured), not hardcoded 100% or 0%."""
    evaluator = AssessmentEvaluator()

    # Empty question list for validity evaluation
    empty_validity = evaluator.evaluate_questions_quality(questions=[])
    assert empty_validity["total_evaluated"] == 0
    assert empty_validity["valid_count"] == 0
    assert empty_validity["validity_rate"] is None  # Unmeasured, NOT 1.0 or 0.0

    # Empty question list for duplicate evaluation
    empty_dup = evaluator.evaluate_duplicate_rate_from_questions(questions=[])
    assert empty_dup["total_questions"] == 0
    assert empty_dup["duplicate_rate"] is None  # Unmeasured, NOT 0.0

    # Single question (cannot measure duplication across generations)
    single_q = Question(
        course_id="c1",
        question_type="mcq",
        question_text="What is kinetic energy?",
        options=["A) 1", "B) 2", "C) 3", "D) 4"],
        correct_answer="A",
        explanation="Kinetic energy is energy of motion.",
        content_hash="h1"
    )
    single_dup = evaluator.evaluate_duplicate_rate_from_questions(questions=[single_q])
    assert single_dup["total_questions"] == 1
    assert single_dup["duplicate_rate"] is None


def test_duplicate_detection_normalization_and_accuracy():
    """
    Verify duplicate detection normalizes text consistently, correctly identifies
    genuine duplicates, and does NOT falsely flag distinct conceptual questions.
    """
    from app.services.assessment.deduplication import normalize_text, compute_content_hash, calculate_jaccard_similarity

    # 1. Normalization consistency
    t1 = "What is Newton's Second Law of Motion?"
    t2 = "what is newton s second law of motion  "
    t3 = "What is Newton's Second Law of Motion?!"
    assert normalize_text(t1) == normalize_text(t2) == normalize_text(t3)
    assert compute_content_hash(t1) == compute_content_hash(t2) == compute_content_hash(t3)

    # 2. Regression check on calculate_jaccard_similarity:
    # A short subset question must NOT be flagged as duplicate of an unrelated/longer question
    q_short = "Which statement best describes inertia?"
    q_long = "Which statement best describes Newton's First Law of Motion as presented in the source material?"
    sim = calculate_jaccard_similarity(q_short, q_long)
    assert sim < 0.80, f"False duplicate detected: similarity {sim} should be < 0.80"

    q_mass_inertia = "Which statement best describes the relationship between mass and inertia?"
    sim2 = calculate_jaccard_similarity(q_short, q_mass_inertia)
    assert sim2 < 0.80, f"False duplicate detected: similarity {sim2} should be < 0.80"

    # 3. Genuine near-duplicate questions should have high similarity >= 0.80
    q_near1 = "According to Newton's First Law of Motion, which of the following statements is true?"
    q_near2 = "According to Newton's First Law of Motion, which of the following statements is correct?"
    sim_genuine = calculate_jaccard_similarity(q_near1, q_near2)
    assert sim_genuine >= 0.80, f"Genuine duplicate missed: similarity {sim_genuine} should be >= 0.80"

    # 4. Duplicate rate evaluation across questions
    evaluator = AssessmentEvaluator()
    q_a1 = Question(course_id="c1", question_type="mcq", question_text=q_near1, options=["A", "B", "C", "D"], correct_answer="A", explanation="exp1", content_hash=compute_content_hash(q_near1))
    q_a2 = Question(course_id="c1", question_type="mcq", question_text=q_near2, options=["A", "B", "C", "D"], correct_answer="A", explanation="exp2", content_hash=compute_content_hash(q_near2))
    q_distinct1 = Question(course_id="c1", question_type="mcq", question_text="What is the unit of force in SI?", options=["A", "B", "C", "D"], correct_answer="A", explanation="exp3", content_hash=compute_content_hash("What is the unit of force in SI?"))
    q_distinct2 = Question(course_id="c1", question_type="mcq", question_text="How is momentum related to mass and velocity?", options=["A", "B", "C", "D"], correct_answer="A", explanation="exp4", content_hash=compute_content_hash("How is momentum related to mass and velocity?"))

    # 4 questions with 1 duplicate (q_a2 is duplicate of q_a1) -> duplicate_rate = 1 / 4 = 0.25
    dup_res = evaluator.evaluate_duplicate_rate_from_questions([q_a1, q_a2, q_distinct1, q_distinct2])
    assert dup_res["total_questions"] == 4
    assert dup_res["unique_questions"] == 3
    assert dup_res["duplicate_questions"] == 1
    assert dup_res["duplicate_rate"] == 0.25

    # 3 distinct questions -> duplicate_rate = 0.0
    zero_dup_res = evaluator.evaluate_duplicate_rate_from_questions([q_a1, q_distinct1, q_distinct2])
    assert zero_dup_res["total_questions"] == 3
    assert zero_dup_res["unique_questions"] == 3
    assert zero_dup_res["duplicate_questions"] == 0
    assert zero_dup_res["duplicate_rate"] == 0.0


def test_evaluation_api_assessment_quality_metrics_response(client, db_session):
    """
    Verify POST /api/evaluation/run and GET /api/evaluation/{id}/results return
    populated assessment quality metrics, sample counts, and numerators/denominators.
    """
    course_res = client.post("/api/courses", json={"title": "Assessment Quality API Course"})
    assert course_res.status_code == 201
    course_id = course_res.json()["id"]

    # Seed 3 valid questions into the course
    q1 = Question(
        course_id=course_id,
        topic_id="Thermodynamics",
        question_type="mcq",
        question_text="What does the first law of thermodynamics state regarding energy?",
        options=["A) Energy cannot be created or destroyed", "B) Energy increases over time", "C) Energy decreases to zero", "D) Entropy always decreases"],
        correct_answer="A",
        explanation="The first law states the conservation of energy: energy can change forms but cannot be created or destroyed.",
        content_hash="q-api-hash-1"
    )
    q2 = Question(
        course_id=course_id,
        topic_id="Thermodynamics",
        question_type="mcq",
        question_text="What does the second law of thermodynamics state about entropy?",
        options=["A) Entropy of an isolated system always increases", "B) Entropy always decreases", "C) Entropy remains zero at all times", "D) Entropy is independent of temperature"],
        correct_answer="A",
        explanation="The second law states that entropy of an isolated system never decreases over time.",
        content_hash="q-api-hash-2"
    )
    q3 = Question(
        course_id=course_id,
        topic_id="Thermodynamics",
        question_type="numerical",
        question_text="Calculate the work done when a force of 10 N moves an object 5 meters in its direction.",
        options=None,
        correct_answer="50 J",
        explanation="Work done W = F * d = 10 * 5 = 50 J.",
        content_hash="q-api-hash-3"
    )
    db_session.add_all([q1, q2, q3])
    db_session.commit()

    mock_tutor_resp = TutorChatResponse(
        answer="Thermodynamics principles govern heat and work transformations.",
        grounded=True,
        sources=[]
    )

    with patch("app.services.rag.tutor_service.TutorService.answer_question", return_value=mock_tutor_resp):
        run_res = client.post("/api/evaluation/run", json={
            "name": "Assessment Quality Metric Test",
            "course_id": course_id,
            "dataset": [
                {
                    "id": "eval-thermo-01",
                    "course_id": course_id,
                    "question": "What is the first law of thermodynamics?",
                    "expected_grounded": True,
                    "expected_sources": []
                }
            ],
            "run_learner_simulations": False,
            "run_assessment_eval": True,
            "sync": True
        })
        assert run_res.status_code == 201
        eval_id = run_res.json()["evaluation_id"]

        results_res = client.get(f"/api/evaluation/{eval_id}/results")
        assert results_res.status_code == 200
        summary = results_res.json()["summary"]

        # Verify assessment validity rate is populated and accurate (3/3 valid = 1.0)
        assert summary["assessment_valid_question_rate"] == 1.0
        assert summary["assessment_questions_evaluated"] == 3
        assert summary["assessment_questions_valid"] == 3

        # Verify duplicate rate is populated and accurate (0/3 duplicates = 0.0)
        assert summary["duplicate_rate"] == 0.0
        assert summary["duplicate_questions_evaluated"] == 3
        assert summary["duplicate_questions_detected"] == 0

