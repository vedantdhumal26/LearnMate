import json
import urllib.request
import urllib.error
import pymupdf
import io
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.course import DEMO_USER_ID
from app.core.jwt import create_access_token
from app.services.rag.small_talk import (
    GREETING_RESPONSE,
    THANKS_RESPONSE,
    FAREWELL_RESPONSE,
)

BASE_URL = "http://127.0.0.1:8000"

def get_auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def create_sample_physics_pdf() -> bytes:
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 72), "Chapter 1: Newton's First Law\nAn object at rest stays at rest.", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((50, 72), "Chapter 2: Newton's Second Law\nForce equals mass times acceleration (F = m * a).", fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b

def run_live_tests():
    token = create_access_token(user_id=DEMO_USER_ID)
    auth_headers = get_auth_headers(token)

    print("--- 1. Health check ---")
    req = urllib.request.Request(f"{BASE_URL}/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        print("Health OK:", resp.read().decode())

    print("\n--- 2. Setting up Course for DEMO user ---")
    course_payload = json.dumps({"title": "Live Test Physics Course"}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/courses", data=course_payload, headers=auth_headers)
    with urllib.request.urlopen(req) as resp:
        course = json.loads(resp.read().decode())
        course_id = course["id"]
        print(f"Created Course ID: {course_id}")

    # Upload PDF
    pdf_bytes = create_sample_physics_pdf()
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="physics.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + pdf_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = urllib.request.Request(f"{BASE_URL}/api/courses/{course_id}/upload", data=body, headers=upload_headers)
    with urllib.request.urlopen(req) as resp:
        print("Uploaded PDF Status:", resp.status)

    # Helper function to send chat message
    def send_chat(msg: str, custom_headers=None, target_course=None):
        cid = target_course or course_id
        payload = json.dumps({"course_id": cid, "message": msg}).encode("utf-8")
        headers = custom_headers if custom_headers is not None else auth_headers
        req = urllib.request.Request(f"{BASE_URL}/api/tutor/chat", data=payload, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())

    print("\n--- Test A: 'Hi' ---")
    status, data = send_chat("Hi")
    print("Status:", status)
    print("Response:", json.dumps(data, indent=2))
    assert status == 200
    assert data["answer"] == GREETING_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")
    print(">> Test A PASSED: 'Hi' returned small-talk response, sources=[], grounded=False.")

    print("\n--- Test B: 'Hello!' ---")
    status, data = send_chat("Hello!")
    print("Status:", status)
    print("Response:", json.dumps(data, indent=2))
    assert status == 200
    assert data["answer"] == GREETING_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")
    print(">> Test B PASSED: 'Hello!' returned small-talk response, sources=[], grounded=False.")

    print("\n--- Test C: 'Thank you' ---")
    status, data = send_chat("Thank you")
    print("Status:", status)
    print("Response:", json.dumps(data, indent=2))
    assert status == 200
    assert data["answer"] == THANKS_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")
    print(">> Test C PASSED: 'Thank you' returned thanks response, sources=[], grounded=False.")

    print("\n--- Test D: 'Bye' ---")
    status, data = send_chat("Bye")
    print("Status:", status)
    print("Response:", json.dumps(data, indent=2))
    assert status == 200
    assert data["answer"] == FAREWELL_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")
    print(">> Test D PASSED: 'Bye' returned farewell response, sources=[], grounded=False.")

    print("\n--- Test E: 'Hi, explain Newton's second law.' (Mixed Academic Query) ---")
    status, data = send_chat("Hi, explain Newton's second law.")
    print("Status:", status)
    print("Response snippet:", data["answer"][:120], "...")
    print("Grounded:", data["grounded"])
    print("Sources count:", len(data["sources"]))
    print("Response type:", data.get("response_type"))
    assert status == 200
    # Must NOT be the small talk greeting template
    assert data["answer"] != GREETING_RESPONSE
    assert data.get("response_type") == "academic"
    assert len(data["sources"]) > 0
    assert data["grounded"] is True
    print(">> Test E PASSED: Mixed academic query followed full RAG pipeline.")

    print("\n--- Test F: Unsupported academic question ---")
    status, data = send_chat("How does chlorophyll absorb light during plant photosynthesis?")
    print("Status:", status)
    print("Response:", data["answer"])
    print("Grounded:", data["grounded"])
    print("Sources count:", len(data["sources"]))
    assert status == 200
    assert data["grounded"] is False
    assert data["sources"] == []
    assert "couldn't find enough information" in data["answer"].lower()
    assert data.get("response_type") == "academic"
    print(">> Test F PASSED: Unsupported query rejected by grounding safeguards.")

    print("\n--- Authorization Tests ---")
    # 1. Unauthenticated request
    unauth_headers = {"Content-Type": "application/json"}
    try:
        send_chat("Hi", custom_headers=unauth_headers)
        assert False, "Should have failed with 401"
    except urllib.error.HTTPError as e:
        assert e.code == 401
        print(">> Unauthenticated greeting correctly rejected with 401.")

    # 2. Non-existent course ID
    try:
        send_chat("Hi", target_course="non-existent-course-id-12345")
        assert False, "Should have failed with 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404
        print(">> Greeting to non-existent course correctly rejected with 404.")

    print("\nALL LIVE RUNNING SERVER TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_live_tests()
