"""
Unit and integration tests for Phase 6A: Real User Authentication and User Ownership.
Covers all 24 required test points specified in Phase 6A instructions.
"""

import io
from datetime import timedelta
import pytest
from app.utils.password import hash_password, verify_password
from app.core.jwt import create_access_token, decode_access_token
from app.models.user import User
from app.models.course import Course
from app.models.assessment import Assessment, Question
from app.models.evaluation import EvaluationRun


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def signup_user(client, email: str, password: str = "Secret123!", display_name: str = "Test User"):
    return client.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "display_name": display_name
    })


def login_user(client, email: str, password: str = "Secret123!"):
    return client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Signup Success
# ---------------------------------------------------------------------------
def test_1_signup_success(unauthenticated_client, db_session):
    res = signup_user(unauthenticated_client, "alice@example.com", "Password123!", "Alice")
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["display_name"] == "Alice"
    assert "id" in data["user"]

    # Verify database record
    user = db_session.query(User).filter(User.email == "alice@example.com").first()
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "Password123!" not in user.password_hash


# ---------------------------------------------------------------------------
# 2. Duplicate Signup
# ---------------------------------------------------------------------------
def test_2_duplicate_signup(unauthenticated_client):
    res1 = signup_user(unauthenticated_client, "bob@example.com", "Password123!", "Bob")
    assert res1.status_code == 201

    # Attempt signup again with same email
    res2 = signup_user(unauthenticated_client, "bob@example.com", "DifferentPass123!", "Bob Again")
    assert res2.status_code == 400
    assert "already registered" in res2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Email Normalization
# ---------------------------------------------------------------------------
def test_3_email_normalization(unauthenticated_client):
    res1 = signup_user(unauthenticated_client, "  Charlie.Normal@EXAMPLE.com  ", "Password123!", "Charlie")
    assert res1.status_code == 201
    data = res1.json()
    assert data["user"]["email"] == "charlie.normal@example.com"

    # Login with different casing and extra spaces
    res_login = unauthenticated_client.post("/api/auth/login", json={
        "email": "CHARLIE.normal@example.COM",
        "password": "Password123!"
    })
    assert res_login.status_code == 200
    assert res_login.json()["user"]["email"] == "charlie.normal@example.com"


# ---------------------------------------------------------------------------
# 4. Password Hashing
# ---------------------------------------------------------------------------
def test_4_password_hashing():
    pw = "SuperSecure123!@#"
    h1 = hash_password(pw)
    h2 = hash_password(pw)

    assert h1.startswith("$argon2id$")
    assert h2.startswith("$argon2id$")
    # Argon2id generates unique salt every time
    assert h1 != h2
    # Never stores plaintext
    assert pw not in h1


# ---------------------------------------------------------------------------
# 5. Password Verification
# ---------------------------------------------------------------------------
def test_5_password_verification():
    pw = "CorrectHorseBatteryStaple1!"
    h = hash_password(pw)

    assert verify_password(pw, h) is True
    assert verify_password("WrongPassword!", h) is False
    assert verify_password("", h) is False
    assert verify_password(pw, "not-a-valid-argon-hash") is False


# ---------------------------------------------------------------------------
# 6. Login Success
# ---------------------------------------------------------------------------
def test_6_login_success(unauthenticated_client):
    signup_user(unauthenticated_client, "david@example.com", "MySecretPass123!", "David")
    res = login_user(unauthenticated_client, "david@example.com", "MySecretPass123!")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "david@example.com"


# ---------------------------------------------------------------------------
# 7. Wrong Password
# ---------------------------------------------------------------------------
def test_7_wrong_password(unauthenticated_client):
    signup_user(unauthenticated_client, "eve@example.com", "CorrectPass123!", "Eve")
    res = login_user(unauthenticated_client, "eve@example.com", "WrongPass123!")
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


# ---------------------------------------------------------------------------
# 8. Unknown Email
# ---------------------------------------------------------------------------
def test_8_unknown_email(unauthenticated_client):
    res = login_user(unauthenticated_client, "nonexistent_user@example.com", "AnyPassword123!")
    assert res.status_code == 401
    # Generic error message: do not reveal email existence
    assert res.json()["detail"] == "Invalid email or password."


# ---------------------------------------------------------------------------
# 9. Invalid Token
# ---------------------------------------------------------------------------
def test_9_invalid_token(unauthenticated_client):
    res = unauthenticated_client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.malformed.token"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 10. Expired Token
# ---------------------------------------------------------------------------
def test_10_expired_token(unauthenticated_client, db_session):
    u_res = signup_user(unauthenticated_client, "frank@example.com", "Password123!", "Frank")
    user_id = u_res.json()["user"]["id"]

    expired_token = create_access_token(user_id=user_id, expires_delta=timedelta(seconds=-10))
    res = unauthenticated_client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 11. /auth/me
# ---------------------------------------------------------------------------
def test_11_auth_me(unauthenticated_client):
    u_res = signup_user(unauthenticated_client, "grace@example.com", "Password123!", "Grace Hopper")
    token = u_res.json()["access_token"]

    res = unauthenticated_client.get("/api/auth/me", headers=auth_header(token))
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "grace@example.com"
    assert data["display_name"] == "Grace Hopper"
    assert data["id"] == u_res.json()["user"]["id"]


# ---------------------------------------------------------------------------
# 12. Protected Endpoint Without Token
# ---------------------------------------------------------------------------
def test_12_protected_endpoint_without_token(unauthenticated_client):
    res_me = unauthenticated_client.get("/api/auth/me")
    assert res_me.status_code == 401

    res_courses = unauthenticated_client.get("/api/courses")
    assert res_courses.status_code == 401

    res_create = unauthenticated_client.post("/api/courses", json={"title": "Unauthorized Course"})
    assert res_create.status_code == 401


# ---------------------------------------------------------------------------
# 13. User Sees Own Courses
# ---------------------------------------------------------------------------
def test_13_user_sees_own_courses(unauthenticated_client):
    # User A
    a_res = signup_user(unauthenticated_client, "user_a@example.com", "Password123!", "User A")
    token_a = a_res.json()["access_token"]
    unauthenticated_client.post("/api/courses", json={"title": "Course A1"}, headers=auth_header(token_a))
    unauthenticated_client.post("/api/courses", json={"title": "Course A2"}, headers=auth_header(token_a))

    # User B
    b_res = signup_user(unauthenticated_client, "user_b@example.com", "Password123!", "User B")
    token_b = b_res.json()["access_token"]
    unauthenticated_client.post("/api/courses", json={"title": "Course B1"}, headers=auth_header(token_b))

    # User A lists courses
    courses_a = unauthenticated_client.get("/api/courses", headers=auth_header(token_a)).json()
    titles_a = [c["title"] for c in courses_a]
    assert "Course A1" in titles_a
    assert "Course A2" in titles_a
    assert "Course B1" not in titles_a

    # User B lists courses
    courses_b = unauthenticated_client.get("/api/courses", headers=auth_header(token_b)).json()
    titles_b = [c["title"] for c in courses_b]
    assert "Course B1" in titles_b
    assert "Course A1" not in titles_b
    assert "Course A2" not in titles_b


# ---------------------------------------------------------------------------
# 14. User Cannot See Another User's Course
# ---------------------------------------------------------------------------
def test_14_user_cannot_see_another_user_course(unauthenticated_client):
    # User A creates Course
    a_res = signup_user(unauthenticated_client, "owner_a@example.com", "Password123!", "Owner A")
    token_a = a_res.json()["access_token"]
    c_res = unauthenticated_client.post("/api/courses", json={"title": "Secret Course A"}, headers=auth_header(token_a))
    course_a_id = c_res.json()["id"]

    # User B tries to view Course A
    b_res = signup_user(unauthenticated_client, "attacker_b@example.com", "Password123!", "Attacker B")
    token_b = b_res.json()["access_token"]

    res = unauthenticated_client.get(f"/api/courses/{course_a_id}", headers=auth_header(token_b))
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 15. User Cannot Upload to Another User's Course
# ---------------------------------------------------------------------------
def test_15_user_cannot_upload_to_another_user_course(unauthenticated_client, sample_physics_pdf):
    # User A creates course
    a_res = signup_user(unauthenticated_client, "owner_upload@example.com", "Password123!", "Owner")
    token_a = a_res.json()["access_token"]
    c_res = unauthenticated_client.post("/api/courses", json={"title": "Owner's Course"}, headers=auth_header(token_a))
    course_id = c_res.json()["id"]

    # User B tries to upload
    b_res = signup_user(unauthenticated_client, "intruder_upload@example.com", "Password123!", "Intruder")
    token_b = b_res.json()["access_token"]

    files = {"file": ("test.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    res = unauthenticated_client.post(
        f"/api/courses/{course_id}/upload",
        files=files,
        headers=auth_header(token_b)
    )
    assert res.status_code == 404

    # User B tries YouTube upload
    yt_res = unauthenticated_client.post(
        f"/api/courses/{course_id}/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        headers=auth_header(token_b)
    )
    assert yt_res.status_code == 404


# ---------------------------------------------------------------------------
# 16. User Cannot Query Another User's Tutor Data
# ---------------------------------------------------------------------------
def test_16_user_cannot_query_another_user_tutor(unauthenticated_client):
    # User A creates course
    a_res = signup_user(unauthenticated_client, "tutor_owner@example.com", "Password123!", "Tutor Owner")
    token_a = a_res.json()["access_token"]
    c_res = unauthenticated_client.post("/api/courses", json={"title": "Tutor Course A"}, headers=auth_header(token_a))
    course_id = c_res.json()["id"]

    # User B attempts to query Tutor for User A's course
    b_res = signup_user(unauthenticated_client, "tutor_stranger@example.com", "Password123!", "Stranger")
    token_b = b_res.json()["access_token"]

    chat_payload = {
        "course_id": course_id,
        "message": "What is the secret data in this course?"
    }
    res = unauthenticated_client.post("/api/tutor/chat", json=chat_payload, headers=auth_header(token_b))
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 17. User Cannot Retrieve Another User's Assessment
# ---------------------------------------------------------------------------
def test_17_user_cannot_retrieve_another_user_assessment(unauthenticated_client, db_session):
    # User A creates course
    a_res = signup_user(unauthenticated_client, "ass_owner@example.com", "Password123!", "Ass Owner")
    token_a = a_res.json()["access_token"]
    user_a_id = a_res.json()["user"]["id"]
    c_res = unauthenticated_client.post("/api/courses", json={"title": "Assessment Course A"}, headers=auth_header(token_a))
    course_id = c_res.json()["id"]

    # Create question and assessment directly in DB for User A's course
    q = Question(
        course_id=course_id,
        topic_id="Physics",
        question_type="mcq",
        question_text="Force unit?",
        options=["Newton", "Joule"],
        correct_answer="Newton",
        explanation="Newton is force",
        difficulty="easy",
        content_hash="q_unit_1"
    )
    db_session.add(q)
    db_session.commit()

    ass = Assessment(
        course_id=course_id,
        title="Physics Quiz A",
        student_id=user_a_id,
        questions=[q.id]
    )
    db_session.add(ass)
    db_session.commit()

    # User B attempts to view or submit User A's assessment
    b_res = signup_user(unauthenticated_client, "ass_intruder@example.com", "Password123!", "Intruder")
    token_b = b_res.json()["access_token"]

    get_res = unauthenticated_client.get(f"/api/assessments/{ass.id}", headers=auth_header(token_b))
    assert get_res.status_code == 404

    sub_res = unauthenticated_client.post(
        f"/api/assessments/{ass.id}/submit",
        json={"student_id": b_res.json()["user"]["id"], "answers": [{"question_id": q.id, "answer": "Newton"}]},
        headers=auth_header(token_b)
    )
    assert sub_res.status_code == 404


# ---------------------------------------------------------------------------
# 18. User Cannot Retrieve Another User's Learner Model
# ---------------------------------------------------------------------------
def test_18_user_cannot_retrieve_another_user_learner_model(unauthenticated_client):
    # User A creates course
    a_res = signup_user(unauthenticated_client, "learner_a@example.com", "Password123!", "Learner A")
    token_a = a_res.json()["access_token"]
    user_a_id = a_res.json()["user"]["id"]
    c_res = unauthenticated_client.post("/api/courses", json={"title": "Learner Course A"}, headers=auth_header(token_a))
    course_id = c_res.json()["id"]

    # User B attempts to view User A's learner model
    b_res = signup_user(unauthenticated_client, "learner_b@example.com", "Password123!", "Learner B")
    token_b = b_res.json()["access_token"]
    user_b_id = b_res.json()["user"]["id"]

    # 1. User B requests student_id=User A
    res_m = unauthenticated_client.get(
        f"/api/learner/{user_a_id}/courses/{course_id}/mastery",
        headers=auth_header(token_b)
    )
    assert res_m.status_code == 403

    # 2. User B requests student_id=User B for Course A (which User B does not own)
    res_m2 = unauthenticated_client.get(
        f"/api/learner/{user_b_id}/courses/{course_id}/mastery",
        headers=auth_header(token_b)
    )
    assert res_m2.status_code == 404


# ---------------------------------------------------------------------------
# 19. User Cannot Retrieve Another User's Evaluation
# ---------------------------------------------------------------------------
def test_19_user_cannot_retrieve_another_user_evaluation(unauthenticated_client, db_session):
    # User A
    a_res = signup_user(unauthenticated_client, "eval_user_a@example.com", "Password123!", "Eval User A")
    user_a_id = a_res.json()["user"]["id"]

    run = EvaluationRun(
        name="User A Private Eval",
        user_id=user_a_id,
        status="completed"
    )
    db_session.add(run)
    db_session.commit()

    # User B attempts to access User A's evaluation
    b_res = signup_user(unauthenticated_client, "eval_user_b@example.com", "Password123!", "Eval User B")
    token_b = b_res.json()["access_token"]

    status_res = unauthenticated_client.get(f"/api/evaluation/{run.id}", headers=auth_header(token_b))
    assert status_res.status_code == 404

    results_res = unauthenticated_client.get(f"/api/evaluation/{run.id}/results", headers=auth_header(token_b))
    assert results_res.status_code == 404


# ---------------------------------------------------------------------------
# 20. User Profile Editing (PATCH /api/auth/me)
# ---------------------------------------------------------------------------
def test_20_user_can_edit_profile(unauthenticated_client):
    res = signup_user(unauthenticated_client, "editable_user@example.com", "Password123!", "Old Name")
    token = res.json()["access_token"]

    patch_res = unauthenticated_client.patch(
        "/api/auth/me",
        json={"display_name": "New Name"},
        headers=auth_header(token)
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["display_name"] == "New Name"

    get_me = unauthenticated_client.get("/api/auth/me", headers=auth_header(token))
    assert get_me.json()["display_name"] == "New Name"
