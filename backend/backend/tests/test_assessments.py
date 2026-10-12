import io
import json
import pytest
from app.api.routes.assessments import assessment_service
from app.services.assessment.question_verifier import QuestionVerifier
from app.services.assessment.deduplication import QuestionDeduplicator, compute_content_hash, normalize_text
from app.services.vector_store.base import VectorSearchResult
from app.models.assessment import Question, Assessment, QuestionAttempt, AssessmentAttempt
from tests.conftest import MockLLMService

def test_mcq_verifier_structure_and_single_correct_option():
    """Verify QuestionVerifier enforces exactly 4 distinct options and single valid correct answer."""
    chunks = [
        VectorSearchResult(
            chunk_id="c1",
            course_id="crs1",
            source_id="src1",
            content="Newton's second law: Force equals mass times acceleration (F = m * a). Force is measured in Newtons.",
            file_name="physics.pdf",
            page_number=2,
            score=0.9
        )
    ]

    # Valid MCQ
    valid_mcq = {
        "question": "According to Newton's second law, what is the formula for force?",
        "options": ["A) F = m / a", "B) F = m * a", "C) F = m + a", "D) F = a / m"],
        "correct_answer": "B",
        "explanation": "Newton's second law states that Force equals mass times acceleration (F = m * a).",
        "sources": [{"source_id": "src1", "file_name": "physics.pdf", "page": 2, "excerpt": "F = m * a"}]
    }
    is_valid, reason = QuestionVerifier.verify_question(valid_mcq, "mcq", "Newton's Laws", chunks)
    assert is_valid is True, f"Failed on valid MCQ: {reason}"

    # Invalid: Only 3 options
    invalid_opts = dict(valid_mcq, options=["A) opt1", "B) opt2", "C) opt3"])
    is_valid, reason = QuestionVerifier.verify_question(invalid_opts, "mcq", "Newton's Laws", chunks)
    assert is_valid is False
    assert "4 options" in reason

    # Invalid: Duplicate options
    duplicate_opts = dict(valid_mcq, options=["A) opt1", "A) opt1", "C) opt3", "D) opt4"])
    is_valid, reason = QuestionVerifier.verify_question(duplicate_opts, "mcq", "Newton's Laws", chunks)
    assert is_valid is False
    assert "distinct" in reason

    # Invalid: Correct answer does not match any option
    invalid_ans = dict(valid_mcq, correct_answer="Z")
    is_valid, reason = QuestionVerifier.verify_question(invalid_ans, "mcq", "Newton's Laws", chunks)
    assert is_valid is False
    assert "does not match" in reason


def test_numerical_verifier_arithmetic_consistency():
    """Verify QuestionVerifier rejects mathematically inconsistent numerical questions."""
    chunks = [
        VectorSearchResult(
            chunk_id="c1",
            course_id="crs1",
            source_id="src1",
            content="Force is mass times acceleration. A 5 kg object accelerating at 2 m/s^2 experiences force.",
            file_name="physics.pdf",
            page_number=2,
            score=0.85
        )
    ]

    # Inconsistent arithmetic: 5 * 2 = 15 is false
    inconsistent_q = {
        "question": "Calculate the force on a 5 kg mass with acceleration of 2 m/s^2.",
        "correct_answer": "15 N",
        "explanation": "Using F = m * a, we have 5 * 2 = 15 Newtons.",
        "sources": []
    }
    is_valid, reason = QuestionVerifier.verify_question(inconsistent_q, "numerical", "Force", chunks)
    assert is_valid is False
    assert "Mathematical inconsistency" in reason

    # Consistent arithmetic: 5 * 2 = 10 is true
    consistent_q = {
        "question": "Calculate the force on a 5 kg mass with acceleration of 2 m/s^2.",
        "correct_answer": "10 N",
        "explanation": "Using F = m * a, we calculate 5 * 2 = 10 Newtons.",
        "sources": []
    }
    is_valid, reason = QuestionVerifier.verify_question(consistent_q, "numerical", "Force", chunks)
    assert is_valid is True, f"Failed on consistent question: {reason}"


def test_question_deduplicator(db_session):
    """Verify deduplication detects identical hashes, text similarity, and student attempts."""
    dedup = QuestionDeduplicator(similarity_threshold=0.8)

    q1 = Question(
        course_id="c_test",
        question_type="mcq",
        question_text="What is Newton's First Law of Motion?",
        correct_answer="Law of inertia",
        explanation="An object stays at rest unless acted on by force.",
        content_hash=compute_content_hash("What is Newton's First Law of Motion?"),
    )
    db_session.add(q1)
    db_session.commit()

    # Exact duplicate
    assert dedup.is_duplicate(db_session, "c_test", "What is Newton's First Law of Motion?") is True

    # Case / whitespace variation of same text
    assert dedup.is_duplicate(db_session, "c_test", "what is newton's   first law of motion? ") is True

    # Near duplicate (high similarity)
    assert dedup.is_duplicate(db_session, "c_test", "State Newton's first law of motion") is True

    # Different question
    assert dedup.is_duplicate(db_session, "c_test", "Explain thermodynamics second law") is False

    # Student-aware deduplication
    q2 = Question(
        course_id="c_test",
        question_type="mcq",
        question_text="Define acceleration in classical mechanics.",
        correct_answer="Rate of change of velocity",
        explanation="a = dv/dt",
        content_hash=compute_content_hash("Define acceleration in classical mechanics."),
    )
    db_session.add(q2)
    db_session.commit()

    # Before student attempt
    assert dedup.is_duplicate(db_session, "c_test", "Define acceleration in classical mechanics.", student_id="student_1") is True  # Already exists for course

    # Add attempt for student
    attempt = QuestionAttempt(
        assessment_id="a1",
        question_id=q2.id,
        student_id="student_1",
        submitted_answer="rate of velocity",
        is_correct=True,
    )
    db_session.add(attempt)
    db_session.commit()

    # Check student previous attempt rejection
    assert dedup.is_duplicate(db_session, "c_other", "Define acceleration in classical mechanics.", student_id="student_1") is True


def test_assessment_generation_mcq_and_student_safety(client, sample_physics_pdf):
    """
    Test assessment generation:
    - Generates 2 MCQs using course context.
    - Verifies student-safe response (answers strictly omitted).
    - Verifies 4 options per MCQ.
    - Verifies source citations present.
    """
    # 1. Setup course and upload
    c_res = client.post("/api/courses", json={"title": "Mechanics 101"})
    course_id = c_res.json()["id"]

    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up_res = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert up_res.status_code == 201

    # Mock LLM to return valid MCQ JSON
    mock_mcq_json = json.dumps([
        {
            "question": "What is the universal law of inertia also known as?",
            "options": ["A) Newton's Third Law", "B) Newton's First Law of Motion", "C) Newton's Second Law", "D) Law of Conservation of Energy"],
            "correct_answer": "B",
            "explanation": "Chapter 1 states that Newton's First Law of Motion is also known as the law of inertia.",
            "difficulty": "medium",
            "topic": "Inertia"
        },
        {
            "question": "According to Chapter 2, how is the acceleration of an object related to net force?",
            "options": [
                "A) Inversely proportional to net force",
                "B) Directly proportional to net force",
                "C) Independent of net force",
                "D) Exponentially proportional to net force"
            ],
            "correct_answer": "B",
            "explanation": "Acceleration is directly proportional to the magnitude of the net force acting upon it.",
            "difficulty": "medium",
            "topic": "Inertia"
        }
    ])
    mock_llm = MockLLMService(response_text=mock_mcq_json)
    assessment_service.question_generator._llm_service = mock_llm

    # 2. Call generate endpoint
    gen_payload = {
        "course_id": course_id,
        "student_id": "student_alpha",
        "topic": "Inertia",
        "difficulty": "medium",
        "question_type": "mcq",
        "count": 2
    }
    response = client.post("/api/assessments/generate", json=gen_payload)
    assert response.status_code == 201

    data = response.json()
    assert "assessment_id" in data
    assert len(data["questions"]) == 2

    for q in data["questions"]:
        # Verify student-safety: NO correct_answer or expected_answer
        assert "correct_answer" not in q
        assert "expected_answer" not in q
        assert "options" in q
        assert len(q["options"]) == 4
        assert len(q["sources"]) > 0
        assert q["sources"][0]["file_name"] == "physics.pdf"
        assert q["sources"][0]["page"] in [1, 2]


def test_assessment_retrieval_does_not_expose_answers(client, sample_physics_pdf):
    """Verify GET /api/assessments/{id} never exposes correct answer keys."""
    # 1. Setup course
    c_res = client.post("/api/courses", json={"title": "Physics 201"})
    course_id = c_res.json()["id"]

    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    mock_json = json.dumps([
        {
            "question": "An object at rest stays at rest according to which principle?",
            "options": ["A) Law of Gravity", "B) Law of Inertia", "C) Law of Friction", "D) Hooke's Law"],
            "correct_answer": "B",
            "explanation": "The law of inertia states that an object at rest stays at rest.",
            "difficulty": "easy",
            "topic": "Newton's First Law"
        }
    ])
    assessment_service.question_generator._llm_service = MockLLMService(response_text=mock_json)

    gen_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "topic": "Newton's First Law",
        "difficulty": "easy",
        "question_type": "mcq",
        "count": 1
    })
    assert gen_res.status_code == 201
    assessment_id = gen_res.json()["assessment_id"]

    # Retrieve assessment
    get_res = client.get(f"/api/assessments/{assessment_id}")
    assert get_res.status_code == 200

    det = get_res.json()
    assert det["assessment_id"] == assessment_id
    assert len(det["questions"]) == 1
    retrieved_q = det["questions"][0]

    assert "correct_answer" not in retrieved_q
    assert "expected_answer" not in retrieved_q
    assert "options" in retrieved_q


def test_assessment_submission_scoring_and_grounded_feedback(client, sample_physics_pdf, db_session):
    """
    Test assessment submission:
    - 1 correct answer and 1 incorrect answer submitted.
    - Score calculated (50%).
    - Feedback explains why selected answer is incorrect/correct.
    - Citations included.
    - QuestionAttempt records stored.
    """
    c_res = client.post("/api/courses", json={"title": "Physics Lab"})
    course_id = c_res.json()["id"]

    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    mock_json = json.dumps([
        {
            "question": "What is Newton's First Law commonly recognized as?",
            "options": ["A) Law of friction", "B) Law of inertia", "C) Law of momentum", "D) Law of action-reaction"],
            "correct_answer": "B",
            "explanation": "Newton's First Law is universally recognized as the law of inertia.",
            "difficulty": "medium",
            "topic": "Inertia"
        },
        {
            "question": "In the relation F = m * a, what is force measured in?",
            "options": ["A) Joules", "B) Watts", "C) Newtons", "D) Pascals"],
            "correct_answer": "C",
            "explanation": "According to Chapter 2, force is measured in Newtons.",
            "difficulty": "medium",
            "topic": "Force"
        }
    ])
    assessment_service.question_generator._llm_service = MockLLMService(response_text=mock_json)

    gen_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "topic": "Newton's Laws",
        "count": 2
    })
    data = gen_res.json()
    a_id = data["assessment_id"]
    q1_id = data["questions"][0]["id"]
    q2_id = data["questions"][1]["id"]

    # Submit answers: Q1 correct ("B"), Q2 incorrect ("A")
    submit_payload = {
        "student_id": "student_test_1",
        "answers": [
            {"question_id": q1_id, "answer": "B"},
            {"question_id": q2_id, "answer": "A"}  # Wrong (correct is C)
        ]
    }
    sub_res = client.post(f"/api/assessments/{a_id}/submit", json=submit_payload)
    assert sub_res.status_code == 200

    sub_data = sub_res.json()
    assert sub_data["score"] == 50.0
    assert sub_data["correct"] == 1
    assert sub_data["total"] == 2

    # Check question results
    results_map = {r["question_id"]: r for r in sub_data["question_results"]}
    assert results_map[q1_id]["correct"] is True
    assert "Correct!" in results_map[q1_id]["feedback"]
    assert len(results_map[q1_id]["sources"]) > 0

    assert results_map[q2_id]["correct"] is False
    assert "Incorrect" in results_map[q2_id]["feedback"]
    assert "Newtons" in results_map[q2_id]["feedback"] or "C" in results_map[q2_id]["feedback"]
    assert len(results_map[q2_id]["sources"]) > 0

    # Topic performance
    assert len(sub_data["topic_performance"]) >= 1

    # Verify attempts stored in database (student identity derives from authenticated user)
    from app.models.course import DEMO_USER_ID
    attempts = db_session.query(QuestionAttempt).filter(QuestionAttempt.student_id.in_([DEMO_USER_ID, "student_test_1"])).all()
    assert len(attempts) == 2


def test_assessment_course_isolation_and_unsupported_topic(client, sample_physics_pdf):
    """
    Test that an empty course or an unsupported topic correctly refuses assessment generation.
    """
    # Empty course B
    c_res = client.post("/api/courses", json={"title": "Empty History"})
    course_b_id = c_res.json()["id"]

    # Generating questions on course B should refuse with 400 Bad Request
    res_b = client.post("/api/assessments/generate", json={
        "course_id": course_b_id,
        "topic": "Newton's Second Law",
        "count": 2
    })
    assert res_b.status_code == 400
    assert "Insufficient course material" in res_b.json()["detail"]

    # Course A with Physics PDF
    c_a_res = client.post("/api/courses", json={"title": "Physics Course"})
    course_a_id = c_a_res.json()["id"]
    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_a_id}/upload", files=files)

    # Asking for an unsupported topic on Physics course
    res_unsupported = client.post("/api/assessments/generate", json={
        "course_id": course_a_id,
        "topic": "Chlorophyll and plant photosynthesis",
        "count": 2
    })
    assert res_unsupported.status_code == 400
    assert "Insufficient course material" in res_unsupported.json()["detail"]


def test_numerical_assessment_flow(client, sample_physics_pdf):
    """Test generating and submitting numerical questions with arithmetic verification."""
    c_res = client.post("/api/courses", json={"title": "Numerical Physics"})
    course_id = c_res.json()["id"]

    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    mock_num_json = json.dumps([
        {
            "question": "If a net force causes a 5 kg mass to accelerate at 2 m/s^2, what is the force?",
            "options": None,
            "correct_answer": "10 N",
            "explanation": "Using Newton's Second Law F = m * a, 5 * 2 = 10 Newtons.",
            "difficulty": "medium",
            "topic": "Second Law"
        }
    ])
    assessment_service.question_generator._llm_service = MockLLMService(response_text=mock_num_json)

    gen_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "topic": "Newton's Second Law",
        "question_type": "numerical",
        "count": 1
    })
    assert gen_res.status_code == 201
    data = gen_res.json()
    q_id = data["questions"][0]["id"]
    a_id = data["assessment_id"]

    # Submit correct numerical answer
    sub_res = client.post(f"/api/assessments/{a_id}/submit", json={
        "student_id": "num_student",
        "answers": [{"question_id": q_id, "answer": "10 N"}]
    })
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["score"] == 100.0
    assert sub_data["question_results"][0]["correct"] is True


def test_short_answer_assessment_flow(client, sample_physics_pdf):
    """Test generating and submitting short answer questions evaluated by LLM."""
    c_res = client.post("/api/courses", json={"title": "Conceptual Physics"})
    course_id = c_res.json()["id"]

    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    mock_sa_json = json.dumps([
        {
            "question": "State the principle known as the law of inertia from Chapter 1.",
            "options": None,
            "correct_answer": "An object at rest stays at rest and an object in motion stays in motion with constant velocity unless acted upon by an unbalanced force.",
            "explanation": "Chapter 1 explains that inertia is the tendency of an object to resist changes to its state of motion.",
            "difficulty": "easy",
            "topic": "Inertia"
        }
    ])
    assessment_service.question_generator._llm_service = MockLLMService(response_text=mock_sa_json)

    gen_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "topic": "Newton's First Law",
        "question_type": "short_answer",
        "count": 1
    })
    assert gen_res.status_code == 201
    q_id = gen_res.json()["questions"][0]["id"]
    a_id = gen_res.json()["assessment_id"]

    # Mock grader LLM to return evaluation
    eval_json = json.dumps({
        "is_correct": True,
        "feedback": "Excellent explanation capturing the law of inertia accurately from course material."
    })
    assessment_service.grader._llm_service = MockLLMService(response_text=eval_json)

    sub_res = client.post(f"/api/assessments/{a_id}/submit", json={
        "student_id": "sa_student",
        "answers": [{"question_id": q_id, "answer": "An object stays at rest or continues moving at constant speed unless an external force acts."}]
    })
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["score"] == 100.0
    assert sub_data["question_results"][0]["correct"] is True

