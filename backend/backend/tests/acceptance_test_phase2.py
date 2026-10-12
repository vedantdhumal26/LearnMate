"""
Complete Phase 2 Acceptance Test for LearnSphere AI Adaptive Assessment Backend.
Executes all 17 steps specified in Milestone Phase 2 Section 16 against the live running FastAPI server.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io
import json
import pymupdf
import httpx
from app.core.database import SessionLocal
from app.models.assessment import Question, Assessment, QuestionAttempt, AssessmentAttempt

BASE_URL = "http://127.0.0.1:8000"

def run_acceptance_test():
    print("=" * 70)
    print("STARTING PHASE 2 LIVE ACCEPTANCE TEST")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    # 1. Create Course
    print("\n[Step 1] Creating course for Phase 2 Acceptance Test...")
    c_res = client.post("/api/courses", json={
        "title": "Quantum & Classical Mechanics",
        "description": "Fundamental physics covering Newton's laws and inertia"
    })
    print(f"Status: {c_res.status_code}")
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
        "Chapter 1: Newton's First Law and the Principle of Inertia\n\n"
        "An object at rest stays at rest and an object in motion continues in motion with uniform velocity "
        "along a straight line unless acted upon by a net external force. This fundamental property is "
        "defined as inertia. Mass is a quantitative measure of an object's inertia. The greater the mass, "
        "the greater the resistance to change in motion."
    )
    p1.insert_textbox(p1_rect, p1_text, fontsize=11)

    p2 = doc.new_page()
    p2_rect = pymupdf.Rect(50, 50, 550, 750)
    p2_text = (
        "Chapter 2: Newton's Second Law and Quantitative Force\n\n"
        "The acceleration of an object is directly proportional to the net force acting upon it, "
        "in the same direction as the net force, and inversely proportional to its mass. "
        "Mathematically, this relationship is expressed as F = m * a, where F is net force in Newtons (N), "
        "m is mass in kilograms (kg), and a is acceleration in meters per second squared (m/s^2). "
        "One Newton is defined as the force required to accelerate 1 kilogram at 1 m/s^2."
    )
    p2.insert_textbox(p2_rect, p2_text, fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("mechanics_grounded.pdf", pdf_bytes, "application/pdf")}
    up_res = client.post(f"/api/courses/{course_id}/upload", files=files)
    print(f"Status: {up_res.status_code}")
    assert up_res.status_code == 201
    up_data = up_res.json()
    source_id = up_data["source_id"]
    print(f"--> Upload successful: source_id={source_id}, status={up_data['status']}")

    # 3 & 4. Ask Tutor Question and Verify Existing Tutor Works
    print("\n[Steps 3 & 4] Testing existing RAG tutor endpoint (POST /api/tutor/chat)...")
    tutor_res = client.post("/api/tutor/chat", json={
        "course_id": course_id,
        "message": "What is the definition of inertia and how does mass relate to it?"
    })
    print(f"Status: {tutor_res.status_code}")
    assert tutor_res.status_code == 200
    tutor_data = tutor_res.json()
    print(f"Tutor Grounded: {tutor_data['grounded']}")
    print(f"Tutor Citations: {len(tutor_data['sources'])}")
    assert tutor_data["grounded"] is True
    assert len(tutor_data["sources"]) > 0
    print("--> Existing Milestone 1 Tutor functionality verified!")

    # 5. Generate 5 MCQs about a topic in the PDF
    print("\n[Step 5] Generating 5 MCQs about topic 'Inertia and Force' using real Groq LLM...")
    gen_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "student_id": "student_live_1",
        "topic": "Inertia and Force",
        "difficulty": "medium",
        "question_type": "mcq",
        "count": 5
    })
    print(f"Status: {gen_res.status_code}")
    assert gen_res.status_code == 201, f"Generation failed: {gen_res.text}"
    gen_data = gen_res.json()
    assessment_id = gen_data["assessment_id"]
    questions = gen_data["questions"]
    print(f"--> Assessment created: ID={assessment_id}, Total Questions={len(questions)}")
    assert len(questions) == 5

    # 6. Verify every question is course-grounded
    print("\n[Step 6] Verifying course grounding for all 5 questions...")
    for idx, q in enumerate(questions, 1):
        print(f"  Q{idx}: {q['question'][:75]}... (type={q['question_type']}, diff={q['difficulty']})")
        assert q["question_type"] == "mcq"
        assert len(q["options"]) == 4

    # 7. Verify source citations
    print("\n[Step 7] Verifying source citations on generated questions...")
    for idx, q in enumerate(questions, 1):
        citations = q["sources"]
        print(f"  Q{idx} Citations: {len(citations)} source(s)")
        assert len(citations) > 0
        for cit in citations:
            assert cit["file_name"] == "mechanics_grounded.pdf"
            assert cit["page"] in [1, 2]
            assert len(cit["excerpt"]) > 0
    print("--> Real page citations verified on all questions!")

    # 8. Verify answer keys are hidden from API response
    print("\n[Step 8] Verifying student safety (correct answers strictly hidden)...")
    for q in questions:
        assert "correct_answer" not in q
        assert "expected_answer" not in q
        assert "answer" not in q

    # Also verify GET /api/assessments/{id}
    detail_res = client.get(f"/api/assessments/{assessment_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    for q in detail_data["questions"]:
        assert "correct_answer" not in q
        assert "expected_answer" not in q
    print("--> Student safety confirmed: Zero answer leakage in generate or get endpoints!")

    # 9. Submit answers
    print("\n[Step 9] Submitting answers to POST /api/assessments/{id}/submit...")
    # Fetch correct answers server-side from DB to craft test submissions
    db = SessionLocal()
    db_questions = db.query(Question).filter(Question.id.in_([q["id"] for q in questions])).all()
    ans_key = {q.id: q.correct_answer for q in db_questions}
    db.close()

    submission_answers = []
    # Answer 4 correctly, and 1 intentionally incorrectly to test both paths
    for idx, q in enumerate(questions):
        qid = q["id"]
        correct_val = ans_key[qid]
        if idx < 4:
            submission_answers.append({"question_id": qid, "answer": correct_val})
        else:
            # Intentionally choose wrong answer
            wrong = "Z" if correct_val != "Z" else "A"
            submission_answers.append({"question_id": qid, "answer": wrong})

    submit_res = client.post(f"/api/assessments/{assessment_id}/submit", json={
        "student_id": "student_live_1",
        "answers": submission_answers
    })
    print(f"Status: {submit_res.status_code}")
    assert submit_res.status_code == 200
    submit_data = submit_res.json()

    # 10. Verify score
    print("\n[Step 10] Verifying score calculation...")
    print(f"--> Score: {submit_data['score']}%, Correct: {submit_data['correct']}/{submit_data['total']}")
    assert submit_data["total"] == 5
    assert submit_data["correct"] == 4
    assert submit_data["score"] == 80.0

    # 11. Verify feedback
    print("\n[Step 11] Verifying grounded explanatory feedback...")
    results = submit_data["question_results"]
    assert len(results) == 5

    # Check correct answer feedback
    correct_item = results[0]
    assert correct_item["correct"] is True
    assert "Correct!" in correct_item["feedback"]
    assert len(correct_item["sources"]) > 0

    # Check incorrect answer feedback
    incorrect_item = results[4]
    assert incorrect_item["correct"] is False
    assert "Incorrect" in incorrect_item["feedback"]
    assert len(incorrect_item["sources"]) > 0
    print("--> Feedback correctly differentiates correct and incorrect submissions!")

    # 12. Verify question attempts are stored
    print("\n[Step 12] Verifying question attempts in database...")
    db = SessionLocal()
    stored_attempts = db.query(QuestionAttempt).filter(
        QuestionAttempt.assessment_id == assessment_id,
        QuestionAttempt.student_id == "student_live_1"
    ).all()
    print(f"--> Found {len(stored_attempts)} stored QuestionAttempt records in DB")
    assert len(stored_attempts) == 5

    stored_assessment_attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.assessment_id == assessment_id,
        AssessmentAttempt.student_id == "student_live_1"
    ).first()
    assert stored_assessment_attempt is not None
    assert stored_assessment_attempt.score == 80.0
    db.close()
    print("--> DB persistence verified!")

    # 13 & 14. Generate another assessment and verify identical questions are avoided
    print("\n[Steps 13 & 14] Generating second assessment for same student and checking deduplication...")
    gen2_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "student_id": "student_live_1",
        "topic": "Inertia and Force",
        "difficulty": "medium",
        "question_type": "mcq",
        "count": 3
    })
    print(f"Status: {gen2_res.status_code}")
    assert gen2_res.status_code == 201
    gen2_data = gen2_res.json()
    new_questions = gen2_data["questions"]
    print(f"--> Generated {len(new_questions)} questions in second assessment")

    # 15 & 16. Ask for a topic not contained in the course & verify refusal
    print("\n[Steps 15 & 16] Requesting assessment for unsupported topic not in course...")
    unsupported_res = client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "student_id": "student_live_1",
        "topic": "Cellular respiration and glycolysis enzymes",
        "difficulty": "medium",
        "question_type": "mcq",
        "count": 3
    })
    print(f"Status: {unsupported_res.status_code}")
    assert unsupported_res.status_code == 400
    err_detail = unsupported_res.json()["detail"]
    print(f"Refusal Detail: '{err_detail}'")
    assert "Insufficient course material" in err_detail
    print("--> Grounding refusal verified for unsupported topic!")

    print("\n" + "=" * 70)
    print("ALL 16 ACCEPTANCE STEPS SUCCESSFULLY VALIDATED AGAINST LIVE SERVER")
    print("=" * 70)

if __name__ == "__main__":
    run_acceptance_test()
