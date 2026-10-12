import uuid
import pytest
from app.models.course import Course, DEMO_USER_ID
from app.models.assessment import Question, Assessment
from app.models.learner_mastery import LearnerMastery
from app.services.learner_model.mastery import update_mastery
from app.services.learner_model.weak_topics import WeakTopicDetector
from app.services.learner_model.recommendations import RecommendationEngine
from app.services.learner_model.learner_service import LearnerModelService

def test_new_learner_has_no_fabricated_mastery(client, db_session):
    """1. Verify new learner has no fabricated mastery records or statistics."""
    course = Course(title="Physics 101", description="Introductory physics")
    db_session.add(course)
    db_session.commit()

    from app.models.course import DEMO_USER_ID
    student_id = DEMO_USER_ID

    # Query mastery endpoint
    res_m = client.get(f"/api/learner/{student_id}/courses/{course.id}/mastery")
    assert res_m.status_code == 200
    data_m = res_m.json()
    assert data_m["student_id"] == student_id
    assert data_m["course_id"] == course.id
    assert data_m["topics"] == []

    # Query summary endpoint
    res_s = client.get(f"/api/learner/{student_id}/courses/{course.id}/summary")
    assert res_s.status_code == 200
    data_s = res_s.json()
    assert data_s["overall_mastery"] == 0.0
    assert data_s["strong_topics"] == []
    assert data_s["weak_topics"] == []
    assert data_s["recent_topics"] == []
    assert data_s["status"] == "new_learner"

    # Query recommendations endpoint
    res_r = client.get(f"/api/learner/{student_id}/courses/{course.id}/recommendations")
    assert res_r.status_code == 200
    data_r = res_r.json()
    assert len(data_r["recommendations"]) >= 1
    assert data_r["recommendations"][0]["recommended_action"] == "diagnostic"


def test_first_assessment_creates_mastery_record(client, db_session):
    """2. Verify that the first assessment submission creates a real mastery record."""
    course = Course(title="Nanotechnology", description="Nano course")
    db_session.add(course)
    db_session.commit()

    q = Question(
        course_id=course.id,
        topic_id="Nanoparticles",
        question_type="mcq",
        question_text="What defines a nanoparticle?",
        options=["Size 1-100 nm", "Size > 1 mm", "Liquid only", "None"],
        correct_answer="Size 1-100 nm",
        explanation="Nanoparticles are 1-100 nm.",
        difficulty="medium",
        content_hash="nano_hash_1"
    )
    db_session.add(q)
    db_session.commit()

    assessment = Assessment(
        course_id=course.id,
        title="Nano Quiz 1",
        student_id=DEMO_USER_ID,
        questions=[q.id]
    )
    db_session.add(assessment)
    db_session.commit()

    # Submit assessment
    sub_res = client.post(
        f"/api/assessments/{assessment.id}/submit",
        json={
            "student_id": DEMO_USER_ID,
            "answers": [{"question_id": q.id, "answer": "Size 1-100 nm"}]
        }
    )
    assert sub_res.status_code == 200

    # Verify mastery record created
    rec = db_session.query(LearnerMastery).filter(
        LearnerMastery.student_id == DEMO_USER_ID,
        LearnerMastery.course_id == course.id,
        LearnerMastery.topic == "Nanoparticles"
    ).first()

    assert rec is not None
    assert rec.attempts == 1
    assert rec.correct_attempts == 1
    assert rec.mastery_score > 0.50
    assert rec.confidence > 0.0

    # Query via API
    api_res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/mastery")
    assert api_res.status_code == 200
    topics = api_res.json()["topics"]
    assert len(topics) == 1
    assert topics[0]["topic"] == "Nanoparticles"
    assert topics[0]["attempts"] == 1
    assert topics[0]["correct_attempts"] == 1


def test_correct_answer_increases_mastery():
    """3. Verify correct answer deterministically increases mastery score."""
    initial_score = 0.50
    new_score, confidence = update_mastery(
        previous_mastery=initial_score,
        is_correct=True,
        difficulty="medium",
        total_attempts_prior=2,
        correct_attempts_prior=1
    )
    assert new_score > initial_score
    assert 0.0 <= new_score <= 1.0


def test_incorrect_answer_decreases_mastery():
    """4. Verify incorrect answer deterministically decreases mastery score."""
    initial_score = 0.75
    new_score, confidence = update_mastery(
        previous_mastery=initial_score,
        is_correct=False,
        difficulty="medium",
        total_attempts_prior=3,
        correct_attempts_prior=2
    )
    assert new_score < initial_score
    assert 0.0 <= new_score <= 1.0


def test_more_evidence_changes_confidence():
    """5. Verify confidence grows with higher attempt count and evidence volume."""
    _, conf_1 = update_mastery(None, True, "medium", 0, 0)
    _, conf_3 = update_mastery(0.70, True, "medium", 2, 2)
    _, conf_8 = update_mastery(0.85, True, "medium", 7, 7)

    assert conf_1 < conf_3 < conf_8
    assert conf_8 <= 1.0


def test_attempts_increase_correctly(client, db_session):
    """6. Verify attempts and correct_attempts counters update accurately."""
    course = Course(title="Kinematics", description="Motion")
    db_session.add(course)
    db_session.commit()

    q1 = Question(
        course_id=course.id,
        topic_id="Velocity",
        question_type="mcq",
        question_text="Velocity is vector?",
        options=["Yes", "No"],
        correct_answer="Yes",
        explanation="Velocity has direction.",
        difficulty="easy",
        content_hash="vel_1"
    )
    q2 = Question(
        course_id=course.id,
        topic_id="Velocity",
        question_type="mcq",
        question_text="Acceleration is rate of change of?",
        options=["Velocity", "Position"],
        correct_answer="Velocity",
        explanation="dv/dt = a.",
        difficulty="medium",
        content_hash="vel_2"
    )
    db_session.add_all([q1, q2])
    db_session.commit()

    a1 = Assessment(course_id=course.id, title="Test 1", questions=[q1.id])
    a2 = Assessment(course_id=course.id, title="Test 2", questions=[q2.id])
    db_session.add_all([a1, a2])
    db_session.commit()

    # Submit a1 correctly
    client.post(
        f"/api/assessments/{a1.id}/submit",
        json={"student_id": DEMO_USER_ID, "answers": [{"question_id": q1.id, "answer": "Yes"}]}
    )

    rec1 = db_session.query(LearnerMastery).filter_by(student_id=DEMO_USER_ID, topic="Velocity").first()
    assert rec1.attempts == 1
    assert rec1.correct_attempts == 1

    # Submit a2 incorrectly
    client.post(
        f"/api/assessments/{a2.id}/submit",
        json={"student_id": DEMO_USER_ID, "answers": [{"question_id": q2.id, "answer": "Position"}]}
    )
    db_session.refresh(rec1)
    assert rec1.attempts == 2
    assert rec1.correct_attempts == 1


def test_course_isolation(client, db_session):
    """7. Verify student mastery in Course A does not leak into Course B."""
    course_a = Course(title="Biology", description="Bio")
    course_b = Course(title="Chemistry", description="Chem")
    db_session.add_all([course_a, course_b])
    db_session.commit()

    q = Question(
        course_id=course_a.id,
        topic_id="Cells",
        question_type="mcq",
        question_text="Cell powerhouse?",
        options=["Mitochondria", "Nucleus"],
        correct_answer="Mitochondria",
        explanation="Powerhouse.",
        difficulty="easy",
        content_hash="bio_1"
    )
    db_session.add(q)
    db_session.commit()

    ass = Assessment(course_id=course_a.id, title="Bio Quiz", questions=[q.id])
    db_session.add(ass)
    db_session.commit()

    student_id = DEMO_USER_ID

    # Submit on Course A
    client.post(
        f"/api/assessments/{ass.id}/submit",
        json={"student_id": student_id, "answers": [{"question_id": q.id, "answer": "Mitochondria"}]}
    )

    # Check Course A has 1 topic
    res_a = client.get(f"/api/learner/{student_id}/courses/{course_a.id}/mastery")
    assert len(res_a.json()["topics"]) == 1

    # Check Course B has 0 topics
    res_b = client.get(f"/api/learner/{student_id}/courses/{course_b.id}/mastery")
    assert len(res_b.json()["topics"]) == 0

    # Summary for Course B is new learner
    sum_b = client.get(f"/api/learner/{student_id}/courses/{course_b.id}/summary").json()
    assert sum_b["status"] == "new_learner"
    assert sum_b["overall_mastery"] == 0.0


def test_mastery_records_not_duplicated(client, db_session):
    """8. Verify repeated assessments on the same topic update the same record rather than duplicating."""
    course = Course(title="Calculus", description="Math")
    db_session.add(course)
    db_session.commit()

    q1 = Question(
        course_id=course.id,
        topic_id="Derivatives",
        question_type="mcq",
        question_text="d/dx of x^2?",
        options=["2x", "x"],
        correct_answer="2x",
        explanation="Power rule",
        difficulty="easy",
        content_hash="der_1"
    )
    q2 = Question(
        course_id=course.id,
        topic_id="Derivatives",
        question_type="mcq",
        question_text="d/dx of sin(x)?",
        options=["cos(x)", "-cos(x)"],
        correct_answer="cos(x)",
        explanation="Derivative of sin",
        difficulty="medium",
        content_hash="der_2"
    )
    db_session.add_all([q1, q2])
    db_session.commit()

    ass = Assessment(course_id=course.id, title="Derivatives Test", questions=[q1.id, q2.id])
    db_session.add(ass)
    db_session.commit()

    # Submit assessment with 2 questions on same topic
    client.post(
        f"/api/assessments/{ass.id}/submit",
        json={
            "student_id": DEMO_USER_ID,
            "answers": [
                {"question_id": q1.id, "answer": "2x"},
                {"question_id": q2.id, "answer": "cos(x)"}
            ]
        }
    )

    records = db_session.query(LearnerMastery).filter_by(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Derivatives"
    ).all()

    assert len(records) == 1
    assert records[0].attempts == 2
    assert records[0].correct_attempts == 2


def test_weak_topics_detected_from_real_data(client, db_session):
    """9. Verify WeakTopicDetector detects weak topics and returns actionable explanations."""
    course = Course(title="Robotics", description="Robotics course")
    db_session.add(course)
    db_session.commit()

    student_id = DEMO_USER_ID

    # Create weak record directly (mastery 0.32, 3 attempts, 1 correct)
    weak_rec = LearnerMastery(
        student_id=student_id,
        course_id=course.id,
        topic="Inverse Kinematics",
        mastery_score=0.32,
        confidence=0.60,
        attempts=3,
        correct_attempts=1
    )
    # Create strong record (mastery 0.88, 4 attempts, 4 correct)
    strong_rec = LearnerMastery(
        student_id=student_id,
        course_id=course.id,
        topic="DC Motors",
        mastery_score=0.88,
        confidence=0.75,
        attempts=4,
        correct_attempts=4
    )
    db_session.add_all([weak_rec, strong_rec])
    db_session.commit()

    res = client.get(f"/api/learner/{student_id}/courses/{course.id}/summary")
    assert res.status_code == 200
    data = res.json()

    # Check weak topics
    assert len(data["weak_topics"]) == 1
    wt = data["weak_topics"][0]
    assert wt["topic"] == "Inverse Kinematics"
    assert wt["mastery_score"] == 0.32
    assert len(wt["reason"]) > 5

    # Check strong topics
    assert len(data["strong_topics"]) == 1
    st = data["strong_topics"][0]
    assert st["topic"] == "DC Motors"
    assert st["mastery_score"] == 0.88

    # Overall mastery average: (0.32 + 0.88) / 2 = 0.60
    assert data["overall_mastery"] == 0.60


def test_recommendations_use_actual_mastery(client, db_session):
    """10. Verify recommendations prioritize lowest mastery topic and suggest appropriate difficulty."""
    course = Course(title="Circuits", description="Electronics")
    db_session.add(course)
    db_session.commit()

    student_id = DEMO_USER_ID

    # Weak topic
    r1 = LearnerMastery(
        student_id=student_id,
        course_id=course.id,
        topic="Op-Amps",
        mastery_score=0.30,
        confidence=0.50,
        attempts=3,
        correct_attempts=1
    )
    # Moderate topic
    r2 = LearnerMastery(
        student_id=student_id,
        course_id=course.id,
        topic="Resistors",
        mastery_score=0.68,
        confidence=0.60,
        attempts=3,
        correct_attempts=2
    )
    # Strong topic
    r3 = LearnerMastery(
        student_id=student_id,
        course_id=course.id,
        topic="Ohm's Law",
        mastery_score=0.92,
        confidence=0.80,
        attempts=4,
        correct_attempts=4
    )
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    res = client.get(f"/api/learner/{student_id}/courses/{course.id}/recommendations")
    assert res.status_code == 200
    recs = res.json()["recommendations"]

    assert len(recs) >= 1
    # Top recommendation must be Op-Amps with high priority
    top = recs[0]
    assert top["topic"] == "Op-Amps"
    assert top["priority"] == "high"
    assert top["recommended_action"] == "practice"
    assert top["recommended_difficulty"] in ["easy", "medium"]
    assert top["recommended_question_count"] == 5



def test_learner_model_service_tutor_interaction_stub(db_session):
    """11. Verify tutor interaction interface does not blindly update mastery without evidence."""
    service = LearnerModelService()
    res = service.record_tutor_interaction(
        db=db_session,
        student_id="student_chat",
        course_id="c_1",
        topic="Thermodynamics",
        interaction_evidence=None
    )
    assert res is None
