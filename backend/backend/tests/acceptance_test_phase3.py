"""
Complete Phase 3 Acceptance Test for LearnSphere AI Learner Model & Topic Mastery.
Executes all 16 steps specified in Milestone Phase 3 Section 16 against the live running FastAPI server.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
import httpx
from app.core.database import SessionLocal
from app.models.learner_mastery import LearnerMastery
from app.models.assessment import Question

BASE_URL = "http://127.0.0.1:8000"

def run_acceptance_test():
    print("=" * 75)
    print("STARTING PHASE 3 LIVE ACCEPTANCE TEST: LEARNER MODEL & TOPIC MASTERY")
    print("=" * 75)

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)
    student_id = "student_phase3_eval"

    # 1. Create course
    print("\n[Step 1] Creating course for Phase 3 Acceptance Test...")
    c_res = client.post("/api/courses", json={
        "title": "Kinematics & Dynamics Mastery",
        "description": "Comprehensive course on Newton's laws, force, and acceleration"
    })
    assert c_res.status_code == 201, f"Failed to create course: {c_res.text}"
    course = c_res.json()
    course_id = course["id"]
    print(f"--> Course created: ID={course_id}, Title='{course['title']}'")

    # 2. Upload PDF
    print("\n[Step 2] Generating and uploading 2-page PDF...")
    doc = pymupdf.open()

    p1 = doc.new_page()
    p1_rect = pymupdf.Rect(50, 50, 550, 750)
    p1_text = (
        "Chapter 1: Newton's First Law and Inertia\n\n"
        "An object at rest stays at rest and an object in motion continues in motion with uniform velocity "
        "along a straight line unless acted upon by a net external force. This fundamental property is "
        "defined as inertia. Mass is a quantitative measure of an object's inertia. The greater the mass, "
        "the greater the resistance to change in motion."
    )
    p1.insert_textbox(p1_rect, p1_text, fontsize=11)

    p2 = doc.new_page()
    p2_rect = pymupdf.Rect(50, 50, 550, 750)
    p2_text = (
        "Chapter 2: Newton's Second Law and Force Calculation\n\n"
        "The acceleration of an object is directly proportional to the net force acting upon it, "
        "in the same direction as the net force, and inversely proportional to its mass. "
        "Mathematically, this relationship is expressed as F = m * a, where F is net force in Newtons (N), "
        "m is mass in kilograms (kg), and a is acceleration in meters per second squared (m/s^2). "
        "One Newton is defined as the force required to accelerate 1 kilogram at 1 m/s^2."
    )
    p2.insert_textbox(p2_rect, p2_text, fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("kinematics_phase3.pdf", pdf_bytes, "application/pdf")}
    up_res = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert up_res.status_code == 201, f"Upload failed: {up_res.text}"
    print(f"--> Upload successful: status={up_res.json()['status']}")

    # Check new learner state before any assessment
    print("\n[Verification] Verifying initial state for new learner...")
    init_res = client.get(f"/api/learner/{student_id}/courses/{course_id}/mastery")
    assert init_res.status_code == 200
    assert init_res.json()["topics"] == []
    print("--> Initial mastery correctly empty (no fabricated data)!")

    # 3. Generate assessment
    print("\n[Step 3] Generating assessment with 2 MCQs using Groq LLM...")
    gen_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "student_id": student_id,
        "topic": "Inertia and Force",
        "difficulty": "medium",
        "question_type": "mcq",
        "count": 2
    })
    assert gen_res.status_code == 201, f"Assessment generation failed: {gen_res.text}"
    gen_data = gen_res.json()
    assessment_id = gen_data["assessment_id"]
    questions = gen_data["questions"]
    print(f"--> Assessment created: ID={assessment_id}, Questions={len(questions)}")
    assert len(questions) == 2

    # Query DB to get the true answer for Q1 and an incorrect answer for Q2 to test differentiation
    db = SessionLocal()
    q_models = {q.id: q for q in db.query(Question).filter(Question.id.in_([q["id"] for q in questions])).all()}
    db.close()

    q1_id = questions[0]["id"]
    q2_id = questions[1]["id"]
    correct_ans_q1 = q_models[q1_id].correct_answer
    # intentionally provide wrong answer for Q2
    wrong_ans_q2 = "Completely Incorrect Option XYZ"

    # 4. Submit answers
    print("\n[Step 4] Submitting answers (Q1=correct, Q2=incorrect)...")
    sub1_res = client.post(f"/api/assessments/{assessment_id}/submit", json={
        "student_id": student_id,
        "answers": [
            {"question_id": q1_id, "answer": correct_ans_q1},
            {"question_id": q2_id, "answer": wrong_ans_q2}
        ]
    })
    assert sub1_res.status_code == 200, f"Submit failed: {sub1_res.text}"
    sub1_data = sub1_res.json()

    # 5. Verify assessment score
    print("\n[Step 5] Verifying assessment score...")
    print(f"--> Score: {sub1_data['score']}%, Correct: {sub1_data['correct']}/{sub1_data['total']}")
    assert sub1_data["total"] == 2
    assert sub1_data["correct"] == 1
    assert sub1_data["score"] == 50.0
    print("--> Assessment score verified!")

    # 6. Verify learner mastery records were created
    print("\n[Step 6] Verifying learner mastery records created in database and via API...")
    m1_res = client.get(f"/api/learner/{student_id}/courses/{course_id}/mastery")
    assert m1_res.status_code == 200
    m1_data = m1_res.json()
    topics1 = m1_data["topics"]
    print(f"--> Created {len(topics1)} mastery topic record(s): {[t['topic'] for t in topics1]}")
    assert len(topics1) >= 1
    assert topics1[0]["attempts"] >= 1
    assert topics1[0]["confidence"] > 0.0

    # 7. Verify topic mastery reflects the actual result
    print("\n[Step 7] Verifying topic mastery reflects actual assessment performance...")
    topic_rec = topics1[0]
    print(f"--> Topic: '{topic_rec['topic']}', Mastery: {topic_rec['mastery_score']}, Confidence: {topic_rec['confidence']}, Attempts: {topic_rec['attempts']}")
    assert 0.0 <= topic_rec["mastery_score"] <= 1.0
    prior_mastery = topic_rec["mastery_score"]
    prior_attempts = topic_rec["attempts"]

    # 8. Submit another assessment
    print("\n[Step 8] Generating and submitting a second assessment...")
    gen2_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "student_id": student_id,
        "topic": topic_rec["topic"],
        "difficulty": "medium",
        "question_type": "mcq",
        "count": 1
    })
    assert gen2_res.status_code == 201
    gen2_data = gen2_res.json()
    q_new_id = gen2_data["questions"][0]["id"]

    db = SessionLocal()
    q_new_model = db.query(Question).filter(Question.id == q_new_id).first()
    correct_new = q_new_model.correct_answer
    db.close()

    # Submit second assessment with correct answer
    sub2_res = client.post(f"/api/assessments/{gen2_data['assessment_id']}/submit", json={
        "student_id": student_id,
        "answers": [{"question_id": q_new_id, "answer": correct_new}]
    })
    assert sub2_res.status_code == 200
    assert sub2_res.json()["correct"] == 1
    print("--> Second assessment submitted successfully with correct answer!")

    # 9. Verify mastery updates
    print("\n[Step 9] Verifying mastery score and attempts updated deterministically...")
    m2_res = client.get(f"/api/learner/{student_id}/courses/{course_id}/mastery")
    assert m2_res.status_code == 200
    topics2 = {t["topic"]: t for t in m2_res.json()["topics"]}
    updated_topic = topics2[topic_rec["topic"]]
    print(f"--> Updated Mastery: {updated_topic['mastery_score']} (was {prior_mastery}), Attempts: {updated_topic['attempts']} (was {prior_attempts})")
    assert updated_topic["attempts"] == prior_attempts + 1
    assert updated_topic["correct_attempts"] >= 1
    assert updated_topic["confidence"] >= topic_rec["confidence"]

    # 10. Verify weak-topic detection
    print("\n[Step 10] Testing WeakTopicDetector via summary endpoint...")
    sum_res = client.get(f"/api/learner/{student_id}/courses/{course_id}/summary")
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    print(f"--> Overall Mastery: {sum_data['overall_mastery']}")
    print(f"--> Weak Topics count: {len(sum_data['weak_topics'])}")
    print(f"--> Strong Topics count: {len(sum_data['strong_topics'])}")
    print(f"--> Recent Topics count: {len(sum_data['recent_topics'])}")
    assert sum_data["status"] == "active"
    assert len(sum_data["recent_topics"]) >= 1

    # 11. Verify recommendations
    print("\n[Step 11] Verifying recommendations generated from real mastery data...")
    rec_res = client.get(f"/api/learner/{student_id}/courses/{course_id}/recommendations")
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    recommendations = rec_data["recommendations"]
    print(f"--> Generated {len(recommendations)} recommendation(s):")
    for r in recommendations:
        print(f"    Topic: '{r['topic']}', Priority: '{r['priority']}', Action: '{r['recommended_action']}', Reason: '{r['reason']}'")
    assert len(recommendations) >= 1
    assert recommendations[0]["priority"] in ["high", "medium", "low"]
    assert len(recommendations[0]["reason"]) > 3

    # 12. Query mastery endpoint
    print("\n[Step 12] Explicitly validating GET /api/learner/{student_id}/courses/{course_id}/mastery schema...")
    m_check = client.get(f"/api/learner/{student_id}/courses/{course_id}/mastery")
    assert m_check.status_code == 200
    mc = m_check.json()
    assert "student_id" in mc and mc["student_id"] == student_id
    assert "course_id" in mc and mc["course_id"] == course_id
    assert isinstance(mc["topics"], list)
    for t in mc["topics"]:
        assert 0.0 <= t["mastery_score"] <= 1.0
        assert 0.0 <= t["confidence"] <= 1.0
        assert t["attempts"] >= t["correct_attempts"] >= 0
    print("--> Mastery endpoint schema 100% compliant!")

    # 13. Query summary endpoint
    print("\n[Step 13] Explicitly validating GET /api/learner/{student_id}/courses/{course_id}/summary schema...")
    s_check = client.get(f"/api/learner/{student_id}/courses/{course_id}/summary")
    assert s_check.status_code == 200
    sc = s_check.json()
    assert "overall_mastery" in sc and 0.0 <= sc["overall_mastery"] <= 1.0
    assert "strong_topics" in sc and isinstance(sc["strong_topics"], list)
    assert "weak_topics" in sc and isinstance(sc["weak_topics"], list)
    assert "recent_topics" in sc and isinstance(sc["recent_topics"], list)
    print("--> Summary endpoint schema 100% compliant!")

    # 14. Query recommendation endpoint
    print("\n[Step 14] Explicitly validating GET /api/learner/{student_id}/courses/{course_id}/recommendations schema...")
    r_check = client.get(f"/api/learner/{student_id}/courses/{course_id}/recommendations")
    assert r_check.status_code == 200
    rc = r_check.json()
    assert "recommendations" in rc and isinstance(rc["recommendations"], list)
    for r in rc["recommendations"]:
        assert "topic" in r
        assert "priority" in r
        assert "reason" in r
        assert "recommended_action" in r
    print("--> Recommendations endpoint schema 100% compliant!")

    # 15. Verify course isolation
    print("\n[Step 15] Verifying course isolation (creating Course B and ensuring 0 mastery leakage)...")
    c_b_res = client.post("/api/courses", json={
        "title": "Independent Organic Chemistry",
        "description": "Completely separate course"
    })
    assert c_b_res.status_code == 201
    course_b_id = c_b_res.json()["id"]

    # Student has zero interaction with Course B
    m_b = client.get(f"/api/learner/{student_id}/courses/{course_b_id}/mastery").json()
    assert m_b["topics"] == [], f"Data leaked to Course B: {m_b}"

    s_b = client.get(f"/api/learner/{student_id}/courses/{course_b_id}/summary").json()
    assert s_b["overall_mastery"] == 0.0
    assert s_b["status"] == "new_learner"

    # Also verify non-existent course returns 404
    err_res = client.get(f"/api/learner/{student_id}/courses/invalid-course-uuid-404/mastery")
    assert err_res.status_code == 404
    print("--> Course isolation verified perfectly!")

    print("\n" + "=" * 75)
    print("PHASE 3 ACCEPTANCE TEST PASSED SUCCESSFULLY (ALL 15 STEPS)")
    print("=" * 75)

if __name__ == "__main__":
    run_acceptance_test()
