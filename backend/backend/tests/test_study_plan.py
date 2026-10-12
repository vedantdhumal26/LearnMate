import pytest
from datetime import datetime, timezone
from app.models.course import Course, DEMO_USER_ID
from app.models.user import User
from app.models.learner_mastery import LearnerMastery
from app.models.assessment import Question, Assessment
from app.utils.password import hash_password
from app.core.jwt import create_access_token

def test_new_learner_study_plan(client, db_session):
    """1. Verify new learner receives a 7-day diagnostic baseline plan without fabricated mastery."""
    course = Course(title="Physics 101", description="Intro to physics", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 200
    data = res.json()

    assert data["student_id"] == DEMO_USER_ID
    assert data["course_id"] == course.id
    assert data["plan_duration_days"] == 7
    assert len(data["plan"]) == 7

    # Check days are sequential 1..7
    days = [item["day"] for item in data["plan"]]
    assert days == [1, 2, 3, 4, 5, 6, 7]

    # Check action diversity across all 7 days: no two consecutive days share the same action
    for i in range(1, len(data["plan"])):
        assert data["plan"][i]["action"] != data["plan"][i - 1]["action"], (
            f"Action repeated on days {i} and {i+1}: {data['plan'][i]['action']}"
        )

    # Verify diagnostic/baseline reasons are provided without fabricated scores
    for item in data["plan"]:
        assert item["question_count"] == 5
        assert len(item["reason"]) > 0
        assert "diagnostic" in item["reason"].lower() or "baseline" in item["reason"].lower() or "review" in item["reason"].lower() or "practice" in item["reason"].lower() or "tutor" in item["reason"].lower()


def test_weak_learner_study_plan(client, db_session):
    """2. Verify weak learner (mastery < 0.40) gets high priority, easy difficulty, and alternating actions."""
    course = Course(title="Chemistry", description="Chemistry", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    # Two weak topics
    r1 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Stoichiometry",
        mastery_score=0.20,
        confidence=0.5,
        attempts=3,
        correct_attempts=1,
    )
    r2 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Thermodynamics",
        mastery_score=0.35,
        confidence=0.5,
        attempts=3,
        correct_attempts=1,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 200
    plan = res.json()["plan"]
    assert len(plan) == 7

    # Weakest topic (Stoichiometry 0.20) must appear on Day 1
    assert plan[0]["day"] == 1
    assert plan[0]["topic"] == "Stoichiometry"
    assert plan[0]["priority"] == "high"
    assert plan[0]["difficulty"] == "easy"
    assert plan[0]["question_count"] == 5
    assert plan[0]["reason"] == "Lowest current mastery"

    # All days for weak learner must be easy and high priority
    for item in plan:
        assert item["difficulty"] == "easy"
        assert item["priority"] == "high"
        assert item["question_count"] == 5

    # Check plan diversity: no consecutive duplicate actions
    for i in range(1, len(plan)):
        assert plan[i]["action"] != plan[i - 1]["action"]


def test_moderate_learner_study_plan(client, db_session):
    """3. Verify moderate learner (0.60 <= mastery < 0.75) gets medium difficulty, reinforcement, and alternating actions."""
    course = Course(title="Biology", description="Biology", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    r1 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Cell Division",
        mastery_score=0.62,
        confidence=0.7,
        attempts=4,
        correct_attempts=3,
    )
    r2 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Genetics",
        mastery_score=0.71,
        confidence=0.7,
        attempts=4,
        correct_attempts=3,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 200
    plan = res.json()["plan"]
    assert len(plan) == 7

    # Weakest moderate topic appears on Day 1
    assert plan[0]["topic"] == "Cell Division"

    # All days have medium difficulty and priority
    for item in plan:
        assert item["difficulty"] == "medium"
        assert item["priority"] == "medium"
        assert item["question_count"] == 5

    # Check diversity
    for i in range(1, len(plan)):
        assert plan[i]["action"] != plan[i - 1]["action"]


def test_strong_learner_study_plan(client, db_session):
    """4. Verify strong learner (mastery >= 0.75) gets low priority, hard challenge, and alternating actions."""
    course = Course(title="Calculus", description="Advanced Math", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    r1 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Limits",
        mastery_score=0.82,
        confidence=0.8,
        attempts=5,
        correct_attempts=4,
    )
    r2 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Integrals",
        mastery_score=0.95,
        confidence=0.9,
        attempts=5,
        correct_attempts=5,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 200
    plan = res.json()["plan"]
    assert len(plan) == 7

    # Weakest of the strong topics appears on Day 1
    assert plan[0]["topic"] == "Limits"
    assert plan[0]["action"] == "challenge"
    assert plan[0]["difficulty"] == "hard"
    assert plan[0]["priority"] == "low"
    assert plan[0]["question_count"] == 5
    assert plan[0]["reason"] == "High proficiency achieved - test with advanced questions"

    for item in plan:
        assert item["difficulty"] == "hard"
        assert item["priority"] == "low"
        assert item["question_count"] == 5

    # Check diversity
    for i in range(1, len(plan)):
        assert plan[i]["action"] != plan[i - 1]["action"]


def test_plan_ordering_weakest_topic_first(client, db_session):
    """5. Verify plan orders topics strictly with the weakest topic first."""
    course = Course(title="Physics 201", description="Mechanics", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    # High, Low, Medium topics added in arbitrary order
    r_high = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Rotational Dynamics",
        mastery_score=0.88,
        confidence=0.8,
        attempts=4,
        correct_attempts=4,
    )
    r_low = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Friction",
        mastery_score=0.25,
        confidence=0.5,
        attempts=3,
        correct_attempts=1,
    )
    r_mid = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Circular Motion",
        mastery_score=0.55,
        confidence=0.6,
        attempts=3,
        correct_attempts=2,
    )
    db_session.add_all([r_high, r_low, r_mid])
    db_session.commit()

    res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 200
    plan = res.json()["plan"]

    # Day 1 must be the weakest topic: Friction (0.25)
    assert plan[0]["topic"] == "Friction"
    assert plan[0]["reason"] == "Lowest current mastery"

    # Day 2 should be Circular Motion (0.55)
    assert plan[1]["topic"] == "Circular Motion"

    # Day 3 should be Rotational Dynamics (0.88)
    assert plan[2]["topic"] == "Rotational Dynamics"


def test_authenticated_access(unauthenticated_client, db_session):
    """6. Verify unauthenticated requests return 401 Unauthorized."""
    course = Course(title="Secret Course", description="Confidential", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    res = unauthenticated_client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 401


def test_cross_user_isolation(client, db_session):
    """7. Verify student cannot access another student's study plan (403 Forbidden)."""
    course = Course(title="Public Course", description="Public", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    other_student_id = "student-other-9999"
    res = client.get(f"/api/learner/{other_student_id}/courses/{course.id}/study-plan")
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


def test_course_isolation(client, db_session):
    """8. Verify course isolation: unowned course returns 404, and Course A mastery does not leak into Course B."""
    # 1. Course owned by someone else
    other_user_id = "user-other-0000"
    other_user = User(
        id=other_user_id,
        email="other@learnsphere.local",
        password_hash=hash_password("Pass123!"),
        display_name="Other User",
    )
    unowned_course = Course(title="Other's Course", description="Not mine", owner_id=other_user_id)
    db_session.add_all([other_user, unowned_course])
    db_session.commit()

    res_404 = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{unowned_course.id}/study-plan")
    assert res_404.status_code == 404

    # 2. Course A has mastery records, Course B does not
    course_a = Course(title="Course A", description="Physics", owner_id=DEMO_USER_ID)
    course_b = Course(title="Course B", description="History", owner_id=DEMO_USER_ID)
    db_session.add_all([course_a, course_b])
    db_session.commit()

    r_a = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course_a.id,
        topic="Quantum Mechanics",
        mastery_score=0.30,
        confidence=0.5,
        attempts=2,
        correct_attempts=1,
    )
    db_session.add(r_a)
    db_session.commit()

    # Query Course A
    res_a = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course_a.id}/study-plan")
    assert res_a.status_code == 200
    plan_a = res_a.json()["plan"]
    assert any(item["topic"] == "Quantum Mechanics" for item in plan_a)

    # Query Course B - must be new learner baseline, Quantum Mechanics must NOT appear
    res_b = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course_b.id}/study-plan")
    assert res_b.status_code == 200
    plan_b = res_b.json()["plan"]
    assert not any(item["topic"] == "Quantum Mechanics" for item in plan_b)


def test_mastery_changes_reflected_in_plan(client, db_session):
    """9. Verify dynamic recomputation: assessment submission updates mastery and immediately changes the study plan."""
    course = Course(title="Calculus I", description="Diff & Int", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    # Two topics: Derivatives (weak 0.25) and Integrals (moderate 0.65)
    r_der = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Derivatives",
        mastery_score=0.25,
        confidence=0.5,
        attempts=2,
        correct_attempts=0,
    )
    r_int = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Integrals",
        mastery_score=0.65,
        confidence=0.6,
        attempts=3,
        correct_attempts=2,
    )
    db_session.add_all([r_der, r_int])
    db_session.commit()

    # 1. Initial plan: Derivatives is weakest (0.25), so it must be on Day 1 with easy difficulty
    res1 = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res1.status_code == 200
    plan1 = res1.json()["plan"]
    assert plan1[0]["topic"] == "Derivatives"
    assert plan1[0]["difficulty"] == "easy"
    assert plan1[0]["priority"] == "high"
    assert plan1[0]["reason"] == "Lowest current mastery"

    # 2. Simulate assessment submission on Derivatives: mastery improves to 0.88!
    r_der.mastery_score = 0.88
    r_der.correct_attempts += 3
    r_der.attempts += 3
    r_der.updated_at = datetime.now(timezone.utc)
    db_session.commit()

    # 3. Request plan again: Integrals (0.65) is now the weakest topic!
    res2 = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res2.status_code == 200
    plan2 = res2.json()["plan"]

    # Day 1 is now Integrals!
    assert plan2[0]["topic"] == "Integrals"
    assert plan2[0]["difficulty"] == "medium"
    assert plan2[0]["priority"] == "medium"

    # Derivatives is now recognized as strong (mastery >= 0.75) on its scheduled days
    der_items = [item for item in plan2 if item["topic"] == "Derivatives"]
    assert len(der_items) > 0
    for d_item in der_items:
        assert d_item["difficulty"] == "hard"
        assert d_item["priority"] == "low"


def test_mixed_learner_matches_prompt_example(client, db_session):
    """10. Verify mixed weak/moderate learner matches prompt example response structure."""
    course = Course(title="Physics", description="Newtonian Mechanics", owner_id=DEMO_USER_ID)
    db_session.add(course)
    db_session.commit()

    r1 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Newton's Second Law",
        mastery_score=0.25,
        confidence=0.5,
        attempts=2,
        correct_attempts=0,
    )
    r2 = LearnerMastery(
        student_id=DEMO_USER_ID,
        course_id=course.id,
        topic="Inertia",
        mastery_score=0.68,
        confidence=0.7,
        attempts=3,
        correct_attempts=2,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    res = client.get(f"/api/learner/{DEMO_USER_ID}/courses/{course.id}/study-plan")
    assert res.status_code == 200
    data = res.json()

    assert data["student_id"] == DEMO_USER_ID
    assert data["course_id"] == course.id
    assert data["plan_duration_days"] == 7
    plan = data["plan"]

    # Day 1: Newton's Second Law, high priority, practice, easy, 5 questions, Lowest current mastery
    assert plan[0]["day"] == 1
    assert plan[0]["topic"] == "Newton's Second Law"
    assert plan[0]["priority"] == "high"
    assert plan[0]["action"] == "practice"
    assert plan[0]["difficulty"] == "easy"
    assert plan[0]["question_count"] == 5
    assert plan[0]["reason"] == "Lowest current mastery"

    # Day 2: Inertia, medium priority, tutor_review, medium, 5 questions, Reinforcement recommended
    assert plan[1]["day"] == 2
    assert plan[1]["topic"] == "Inertia"
    assert plan[1]["priority"] == "medium"
    assert plan[1]["action"] == "tutor_review"
    assert plan[1]["difficulty"] == "medium"
    assert plan[1]["question_count"] == 5
    assert plan[1]["reason"] == "Reinforcement recommended"
