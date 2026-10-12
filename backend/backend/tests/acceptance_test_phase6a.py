"""
Phase 6A Acceptance Test: Real User Authentication + User Ownership.
Executes all 18 steps specified in Milestone Phase 6A Section 18.

Can be run:
1. Directly via python: python tests/acceptance_test_phase6a.py
2. Via pytest: pytest tests/acceptance_test_phase6a.py
"""

import io
import os
import sys
import uuid
import pymupdf
import httpx
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get("LEARNSPHERE_BASE_URL", "http://127.0.0.1:8000")


def generate_sample_pdf() -> bytes:
    """Generate a clean 2-page physics PDF for acceptance testing."""
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text(
        (50, 72),
        "Chapter 1: Principles of Classical Mechanics\n\n"
        "An object at rest will remain at rest unless an unbalanced external force acts upon it. "
        "This fundamental law of inertia dictates how particles maintain linear motion in a frictionless vacuum.\n"
        "Mass is the scalar measure of an object's inertia.",
        fontsize=12
    )

    p2 = doc.new_page()
    p2.insert_text(
        (50, 72),
        "Chapter 2: Force, Mass, and Dynamics\n\n"
        "Newton's Second Law describes the quantitative relation between force, mass, and acceleration.\n"
        "The net force vector equals mass times acceleration: F = m * a.\n"
        "Force is expressed in Newtons (N), where 1 Newton equals 1 kg * m / s^2.\n"
        "Momentum is defined as the product of mass and velocity: p = m * v.",
        fontsize=12
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def run_phase6a_acceptance(client: httpx.Client):
    print("\n" + "=" * 75)
    print("STARTING PHASE 6A ACCEPTANCE TEST: REAL USER AUTHENTICATION & OWNERSHIP")
    print("=" * 75)

    unique_suffix = str(uuid.uuid4())[:8]
    email_a = f"alice_{unique_suffix}@learnsphere.test"
    password_a = "AlphaPass#2026!"
    name_a = f"Alice Test-{unique_suffix}"

    email_b = f"bob_{unique_suffix}@learnsphere.test"
    password_b = "BetaPass#2026!"
    name_b = f"Bob Test-{unique_suffix}"

    # -------------------------------------------------------------------------
    # Step 1: Signup User A
    # -------------------------------------------------------------------------
    print("\n[Step 1] Signing up User A (Alice)...")
    res1 = client.post("/api/auth/signup", json={
        "email": email_a,
        "password": password_a,
        "display_name": name_a
    })
    assert res1.status_code == 201, f"Signup User A failed: {res1.status_code} - {res1.text}"
    data1 = res1.json()
    assert "access_token" in data1
    token_a = data1["access_token"]
    user_a_id = data1["user"]["id"]
    assert data1["user"]["email"] == email_a
    assert data1["user"]["display_name"] == name_a
    print(f"--> User A registered: id={user_a_id}, email={email_a}")

    # -------------------------------------------------------------------------
    # Step 2: Login User A
    # -------------------------------------------------------------------------
    print("\n[Step 2] Logging in User A (Alice)...")
    res2 = client.post("/api/auth/login", json={
        "email": email_a,
        "password": password_a
    })
    assert res2.status_code == 200, f"Login User A failed: {res2.status_code} - {res2.text}"
    data2 = res2.json()
    assert "access_token" in data2
    token_a = data2["access_token"]
    print("--> User A logged in successfully. Received valid JWT token.")

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # -------------------------------------------------------------------------
    # Step 3: Verify /auth/me
    # -------------------------------------------------------------------------
    print("\n[Step 3] Verifying /auth/me for User A...")
    res3 = client.get("/api/auth/me", headers=headers_a)
    assert res3.status_code == 200, f"/auth/me failed: {res3.status_code} - {res3.text}"
    data3 = res3.json()
    assert data3["id"] == user_a_id
    assert data3["email"] == email_a
    assert data3["display_name"] == name_a
    print(f"--> /auth/me verified: {data3['display_name']} ({data3['email']})")

    # -------------------------------------------------------------------------
    # Step 4: Create Course A
    # -------------------------------------------------------------------------
    print("\n[Step 4] Creating Course A under User A ownership...")
    res4 = client.post("/api/courses", json={
        "title": f"Phase 6A Dynamics & Kinematics - {unique_suffix}",
        "description": "Authenticated course owned strictly by User A"
    }, headers=headers_a)
    assert res4.status_code == 201, f"Create course failed: {res4.status_code} - {res4.text}"
    course_a = res4.json()
    course_a_id = course_a["id"]
    assert course_a.get("owner_id") == user_a_id
    print(f"--> Course A created: id={course_a_id}, owner_id={course_a.get('owner_id')}")

    # -------------------------------------------------------------------------
    # Step 5: Upload course material
    # -------------------------------------------------------------------------
    print("\n[Step 5] Uploading course material to Course A...")
    pdf_bytes = generate_sample_pdf()
    files = {"file": ("dynamics_principles.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res5 = client.post(f"/api/courses/{course_a_id}/upload", files=files, headers=headers_a)
    assert res5.status_code == 201, f"Upload to Course A failed: {res5.status_code} - {res5.text}"
    upload_data = res5.json()
    source_id = upload_data["source_id"]
    print(f"--> Document uploaded: source_id={source_id}, status={upload_data['status']}")

    # -------------------------------------------------------------------------
    # Step 6: Ask Tutor as User A
    # -------------------------------------------------------------------------
    print("\n[Step 6] Asking Tutor question as User A...")
    tutor_payload = {
        "course_id": course_a_id,
        "message": "What is Newton's Second Law and the formula for force?"
    }
    res6 = client.post("/api/tutor/chat", json=tutor_payload, headers=headers_a)
    assert res6.status_code == 200, f"Tutor chat failed: {res6.status_code} - {res6.text}"
    tutor_data = res6.json()
    assert "answer" in tutor_data
    assert len(tutor_data["answer"]) > 0
    print(f"--> Tutor responded successfully (grounded={tutor_data.get('grounded')})")

    # -------------------------------------------------------------------------
    # Step 7: Generate assessment as User A
    # -------------------------------------------------------------------------
    print("\n[Step 7] Generating assessment for Course A as User A...")
    gen_payload = {
        "course_id": course_a_id,
        "topic": "Classical Mechanics",
        "count": 2
    }
    res7 = client.post("/api/assessments/generate", json=gen_payload, headers=headers_a)
    assert res7.status_code == 201, f"Generate assessment failed: {res7.status_code} - {res7.text}"
    gen_data = res7.json()
    assessment_id = gen_data["assessment_id"]
    questions = gen_data["questions"]
    assert len(questions) >= 1
    # Verify student-safe format (answers hidden)
    for q in questions:
        assert "correct_answer" not in q
    print(f"--> Assessment generated: id={assessment_id} with {len(questions)} student-safe questions")

    # -------------------------------------------------------------------------
    # Step 8: Submit assessment
    # -------------------------------------------------------------------------
    print("\n[Step 8] Submitting assessment answers as User A...")
    first_q_id = questions[0]["id"]
    sub_payload = {
        "student_id": user_a_id,
        "answers": [
            {"question_id": first_q_id, "answer": "B"}
        ]
    }
    res8 = client.post(f"/api/assessments/{assessment_id}/submit", json=sub_payload, headers=headers_a)
    assert res8.status_code == 200, f"Submit assessment failed: {res8.status_code} - {res8.text}"
    sub_data = res8.json()
    assert "score" in sub_data
    assert "question_results" in sub_data
    print(f"--> Assessment submitted and graded: score={sub_data['score']}%")

    # -------------------------------------------------------------------------
    # Step 9: Verify User A mastery
    # -------------------------------------------------------------------------
    print("\n[Step 9] Verifying User A topic mastery profile...")
    res9 = client.get(f"/api/learner/{user_a_id}/courses/{course_a_id}/mastery", headers=headers_a)
    assert res9.status_code == 200, f"Mastery query failed: {res9.status_code} - {res9.text}"
    mastery_data = res9.json()
    assert mastery_data["student_id"] == user_a_id
    assert mastery_data["course_id"] == course_a_id
    print(f"--> User A mastery records verified: {len(mastery_data['topics'])} topics updated.")

    # -------------------------------------------------------------------------
    # Step 10: Signup User B
    # -------------------------------------------------------------------------
    print("\n[Step 10] Signing up User B (Bob)...")
    res10 = client.post("/api/auth/signup", json={
        "email": email_b,
        "password": password_b,
        "display_name": name_b
    })
    assert res10.status_code == 201, f"Signup User B failed: {res10.status_code} - {res10.text}"
    data10 = res10.json()
    token_b = data10["access_token"]
    user_b_id = data10["user"]["id"]
    assert user_b_id != user_a_id
    print(f"--> User B registered: id={user_b_id}, email={email_b}")

    # -------------------------------------------------------------------------
    # Step 11: Login User B
    # -------------------------------------------------------------------------
    print("\n[Step 11] Logging in User B (Bob)...")
    res11 = client.post("/api/auth/login", json={
        "email": email_b,
        "password": password_b
    })
    assert res11.status_code == 200, f"Login User B failed: {res11.status_code} - {res11.text}"
    token_b = res11.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print("--> User B logged in successfully with distinct credentials.")

    # -------------------------------------------------------------------------
    # Step 12: Verify User B cannot access Course A
    # -------------------------------------------------------------------------
    print("\n[Step 12] Verifying User B CANNOT access Course A...")
    res12 = client.get(f"/api/courses/{course_a_id}", headers=headers_b)
    assert res12.status_code == 404, f"Security violation: User B accessed Course A! Status={res12.status_code}"
    print("--> Access denied (404 Not Found): Zero leakage of Course A existence.")

    # -------------------------------------------------------------------------
    # Step 13: Verify User B cannot upload to Course A
    # -------------------------------------------------------------------------
    print("\n[Step 13] Verifying User B CANNOT upload documents or YouTube to Course A...")
    res13_file = client.post(
        f"/api/courses/{course_a_id}/upload",
        files={"file": ("intruder.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers_b
    )
    assert res13_file.status_code == 404, f"Security violation: User B uploaded to Course A! Status={res13_file.status_code}"

    res13_yt = client.post(
        f"/api/courses/{course_a_id}/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        headers=headers_b
    )
    assert res13_yt.status_code == 404, f"Security violation: User B added YouTube to Course A! Status={res13_yt.status_code}"
    print("--> Upload rejected (404 Not Found): Course A upload endpoints protected.")

    # -------------------------------------------------------------------------
    # Step 14: Verify User B cannot query Course A Tutor
    # -------------------------------------------------------------------------
    print("\n[Step 14] Verifying User B CANNOT query Course A Tutor...")
    res14 = client.post("/api/tutor/chat", json={
        "course_id": course_a_id,
        "message": "Extract secret course notes"
    }, headers=headers_b)
    assert res14.status_code == 404, f"Security violation: User B queried Course A Tutor! Status={res14.status_code}"
    print("--> Tutor query rejected (404 Not Found): Course ownership verified before retrieval.")

    # -------------------------------------------------------------------------
    # Step 15: Verify User B cannot access User A assessment
    # -------------------------------------------------------------------------
    print("\n[Step 15] Verifying User B CANNOT access or submit User A's assessment...")
    res15_get = client.get(f"/api/assessments/{assessment_id}", headers=headers_b)
    assert res15_get.status_code == 404, f"Security violation: User B retrieved assessment! Status={res15_get.status_code}"

    res15_sub = client.post(f"/api/assessments/{assessment_id}/submit", json={
        "student_id": user_b_id,
        "answers": [{"question_id": first_q_id, "answer": "B"}]
    }, headers=headers_b)
    assert res15_sub.status_code == 404, f"Security violation: User B submitted assessment! Status={res15_sub.status_code}"
    print("--> Assessment access rejected (404 Not Found): Assessment isolated.")

    # -------------------------------------------------------------------------
    # Step 16: Verify User B cannot access User A learner profile
    # -------------------------------------------------------------------------
    print("\n[Step 16] Verifying User B CANNOT access User A's learner records...")
    res16_m = client.get(f"/api/learner/{user_a_id}/courses/{course_a_id}/mastery", headers=headers_b)
    assert res16_m.status_code in (403, 404), f"Security violation: User B accessed User A mastery! Status={res16_m.status_code}"

    res16_s = client.get(f"/api/learner/{user_a_id}/courses/{course_a_id}/summary", headers=headers_b)
    assert res16_s.status_code in (403, 404), f"Security violation: User B accessed User A summary! Status={res16_s.status_code}"

    res16_r = client.get(f"/api/learner/{user_a_id}/courses/{course_a_id}/recommendations", headers=headers_b)
    assert res16_r.status_code in (403, 404), f"Security violation: User B accessed User A recommendations! Status={res16_r.status_code}"
    print(f"--> Learner record access rejected (Status: {res16_m.status_code}): Student identity strictly enforced.")

    # -------------------------------------------------------------------------
    # Step 17: Verify User A still has full access
    # -------------------------------------------------------------------------
    print("\n[Step 17] Verifying User A STILL has full access to Course A and all assets...")
    res17_c = client.get(f"/api/courses/{course_a_id}", headers=headers_a)
    assert res17_c.status_code == 200, "User A lost access to own course!"

    res17_a = client.get(f"/api/assessments/{assessment_id}", headers=headers_a)
    assert res17_a.status_code == 200, "User A lost access to own assessment!"

    res17_m = client.get(f"/api/learner/{user_a_id}/courses/{course_a_id}/mastery", headers=headers_a)
    assert res17_m.status_code == 200, "User A lost access to own mastery!"
    print("--> User A retain complete ownership and full access to all personal resources.")

    # -------------------------------------------------------------------------
    # Step 18: Verify no cross-user leakage
    # -------------------------------------------------------------------------
    print("\n[Step 18] Verifying no cross-user leakage in course listings...")
    courses_b = client.get("/api/courses", headers=headers_b).json()
    b_course_ids = [c["id"] for c in courses_b]
    assert course_a_id not in b_course_ids, f"Leakage detected: User B can see Course A in listing!"

    # User B creates Course B
    res_cb = client.post("/api/courses", json={"title": f"Course B - {unique_suffix}"}, headers=headers_b)
    course_b_id = res_cb.json()["id"]

    # User A cannot see Course B
    courses_a = client.get("/api/courses", headers=headers_a).json()
    a_course_ids = [c["id"] for c in courses_a]
    assert course_b_id not in a_course_ids, "Leakage detected: User A can see Course B in listing!"

    print("--> Zero cross-user leakage confirmed: Strict multi-tenant isolation enforced.")
    print("\n" + "=" * 75)
    print("PHASE 6A ACCEPTANCE TEST: ALL 18 STEPS PASSED SUCCESSFULLY!")
    print("=" * 75 + "\n")
    return True


# Pytest test hook
def test_acceptance_phase6a_live():
    """Pytest test case for Phase 6A acceptance test using live server or TestClient."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
            res = client.get("/health")
            if res.status_code == 200:
                assert run_phase6a_acceptance(client) is True
                return
    except Exception:
        pass

    # Fallback to TestClient if standalone server not reachable
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as test_client:
        assert run_phase6a_acceptance(test_client) is True


if __name__ == "__main__":
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        run_phase6a_acceptance(client)
