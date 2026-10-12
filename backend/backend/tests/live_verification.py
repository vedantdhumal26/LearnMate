
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io
import json
import pymupdf
import httpx
from app.core.database import SessionLocal
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.services.vector_store.qdrant_store import get_vector_store

BASE_URL = "http://127.0.0.1:8000"

def run_live_verification():
    print("=" * 60)
    print("STARTING LIVE BACKEND VERIFICATION PASS")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. Health Endpoint
    print("\n[1] Testing GET /health...")
    health_resp = client.get("/health")
    print(f"Status: {health_resp.status_code}")
    print(f"Body: {health_resp.json()}")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok"}
    print("--> Health check verified!")

    # 2. Docs Endpoint
    print("\n[2] Testing GET /docs...")
    docs_resp = client.get("/docs")
    print(f"Status: {docs_resp.status_code}")
    assert docs_resp.status_code == 200
    print("--> OpenAPI /docs verified!")

    # 3. Create Course A
    print("\n[3] Creating Course A (Classical Physics)...")
    res_a = client.post("/api/courses", json={"title": "Classical Physics", "description": "Newtonian Mechanics"})
    print(f"Status: {res_a.status_code}")
    course_a = res_a.json()
    course_a_id = course_a["id"]
    print(f"Course A created: ID={course_a_id}, Title={course_a['title']}")
    assert res_a.status_code == 201

    # 4. Create Course B
    print("\n[4] Creating Course B (World History)...")
    res_b = client.post("/api/courses", json={"title": "World History", "description": "Ancient civilizations"})
    print(f"Status: {res_b.status_code}")
    course_b = res_b.json()
    course_b_id = course_b["id"]
    print(f"Course B created: ID={course_b_id}, Title={course_b['title']}")
    assert res_b.status_code == 201

    # 5. Generate Real PDF with PyMuPDF
    print("\n[5] Generating real 2-page PDF document...")
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text(
        (50, 72),
        "Chapter 1: Newton's First Law of Motion\n"
        "An object at rest stays at rest and an object in motion stays in motion "
        "with the same speed and in the same direction unless acted upon by an unbalanced force. "
        "This principle is universally recognized as the law of inertia."
    )
    p2 = doc.new_page()
    p2.insert_text(
        (50, 72),
        "Chapter 2: Newton's Second Law of Motion\n"
        "The acceleration of an object is directly proportional to the net force acting upon it, "
        "in the same direction as the net force, and inversely proportional to its mass. "
        "Mathematically, this fundamental relation is expressed as F = m * a. "
        "Force is measured in Newtons."
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    print(f"Generated PDF bytes length: {len(pdf_bytes)} bytes")

    # 6. Upload PDF to Course A
    print("\n[6] Uploading PDF to Course A...")
    files = {"file": ("newton_laws_live.pdf", pdf_bytes, "application/pdf")}
    upload_resp = client.post(f"/api/courses/{course_a_id}/upload", files=files)
    print(f"Status: {upload_resp.status_code}")
    upload_data = upload_resp.json()
    print(f"Upload Response: {upload_data}")
    assert upload_resp.status_code == 201
    source_id = upload_data["source_id"]
    assert upload_data["status"] == "completed"

    # 7. Verify Files and API Status
    print("\n[7] Verifying disk storage and database records via API...")
    course_detail_resp = client.get(f"/api/courses/{course_a_id}")
    assert course_detail_resp.status_code == 200
    course_detail = course_detail_resp.json()
    print(f"Course detail from API: sources={len(course_detail['sources'])}, chunks={course_detail['chunk_count']}")
    assert course_detail["chunk_count"] >= 2
    assert len(course_detail["sources"]) == 1
    assert course_detail["sources"][0]["id"] == source_id
    assert course_detail["sources"][0]["processing_status"] == "completed"

    # Verify upload status endpoint
    upload_status_resp = client.get(f"/api/courses/{course_a_id}/uploads/{source_id}")
    assert upload_status_resp.status_code == 200
    up_status = upload_status_resp.json()
    print(f"Verified Upload status endpoint: status={up_status['processing_status']}, chunks={up_status['chunks_count']}")
    assert up_status["processing_status"] == "completed"
    assert up_status["chunks_count"] >= 2

    # Verify file saved on disk
    expected_file_path = os.path.join("uploads", course_a_id, "newton_laws_live.pdf")
    assert os.path.exists(expected_file_path)
    file_size = os.path.getsize(expected_file_path)
    print(f"Verified saved file on disk at: {expected_file_path} (size: {file_size} bytes)")
    assert file_size > 0

    # 8. Test Course Isolation (Query Course B for Course A's content)
    print("\n[8] Testing Course Isolation (Querying empty Course B for Newton's laws)...")
    chat_b_resp = client.post("/api/tutor/chat", json={
        "course_id": course_b_id,
        "message": "Explain Newton's second law"
    })
    print(f"Status: {chat_b_resp.status_code}")
    chat_b_data = chat_b_resp.json()
    print(f"Course B Chat Response: {chat_b_data}")
    assert chat_b_resp.status_code == 200
    assert chat_b_data["grounded"] is False
    assert chat_b_data["sources"] == []
    print("--> Course Isolation verified: Content from Course A was NOT accessible in Course B!")

    # 9. Test Unrelated Question Grounding Rejection
    print("\n[9] Testing Unrelated Question (Grounding rejection on Course A)...")
    unrelated_resp = client.post("/api/tutor/chat", json={
        "course_id": course_a_id,
        "message": "What is the biological function of hemoglobin in red blood cells?"
    })
    print(f"Status: {unrelated_resp.status_code}")
    unrelated_data = unrelated_resp.json()
    print(f"Unrelated Chat Response: {unrelated_data}")
    assert unrelated_resp.status_code == 200
    assert unrelated_data["grounded"] is False
    assert unrelated_data["sources"] == []
    assert "couldn't find enough information" in unrelated_data["answer"]
    print("--> Unrelated question rejection verified!")

    # 10. Test Related Question against Live Server
    print("\n[10] Testing Related Question against Course A...")
    related_resp = client.post("/api/tutor/chat", json={
        "course_id": course_a_id,
        "message": "What is Newton's second law and what is the formula?"
    })
    print(f"Status: {related_resp.status_code}")
    print(f"Response Body: {related_resp.text.encode('ascii', errors='replace').decode('ascii')}")
    print("=" * 60)
    print("LIVE VERIFICATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    run_live_verification()
