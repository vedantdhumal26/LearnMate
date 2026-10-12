"""
Complete Phase 4C Live Acceptance Test for LearnSphere AI.
YouTube URL Sources: URL Validation, Metadata, Captions/Transcripts, Timestamped Chunks,
Qdrant Indexing, Grounded Tutoring, and Deep-link Citations.
Executes against the live running FastAPI server at http://127.0.0.1:8000 using a real public YouTube educational video.
"""

import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

BASE_URL = "http://127.0.0.1:8000"
REAL_YOUTUBE_URL = "https://www.youtube.com/watch?v=aircAruvnKk"
EXPECTED_VIDEO_ID = "aircAruvnKk"

def run_acceptance_test():
    print("=" * 80)
    print("STARTING PHASE 4C LIVE ACCEPTANCE TEST: YOUTUBE URL SOURCES")
    print(f"Target Video: {REAL_YOUTUBE_URL} (3Blue1Brown - But what is a neural network?)")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=90.0)

    # Step 1: Create Course 1
    print("\n[Step 1] Creating Course 1 (Neural Networks & Deep Learning)...")
    c1_res = client.post("/api/courses", json={
        "title": "Neural Networks & Deep Learning",
        "description": "Foundations of artificial neural networks, activation functions, and gradient descent."
    })
    assert c1_res.status_code == 201, f"Failed to create Course 1: {c1_res.text}"
    course_1 = c1_res.json()
    course_1_id = course_1["id"]
    print(f"--> Course 1 created: ID={course_1_id}, Title='{course_1['title']}'")

    # Step 2: Add Real Public YouTube Video to Course 1
    print(f"\n[Step 2] Adding YouTube video source: {REAL_YOUTUBE_URL}...")
    yt_res = client.post(f"/api/courses/{course_1_id}/youtube", json={
        "url": REAL_YOUTUBE_URL
    })
    assert yt_res.status_code == 201, f"Failed to add YouTube source: {yt_res.text}"
    yt_data = yt_res.json()
    source_id = yt_data["source_id"]
    video_id = yt_data["video_id"]
    canonical_url = yt_data["canonical_url"]
    status = yt_data["status"]
    print(f"--> Response: source_id={source_id}, video_id={video_id}, status={status}")
    print(f"--> Title: '{yt_data.get('title')}', Canonical: {canonical_url}")
    assert video_id == EXPECTED_VIDEO_ID
    assert canonical_url == f"https://www.youtube.com/watch?v={EXPECTED_VIDEO_ID}"
    assert status in ("ready", "completed")

    # Step 3: Verify Source Status & Chunk Metadata
    print("\n[Step 3] Checking source details via GET /api/courses/{id}/uploads/{source_id}...")
    status_res = client.get(f"/api/courses/{course_1_id}/uploads/{source_id}")
    assert status_res.status_code == 200, f"Failed to get source status: {status_res.text}"
    source_info = status_res.json()
    print(f"--> Source Type: {source_info.get('source_type')}")
    print(f"--> Processing Status: {source_info.get('processing_status')}")
    print(f"--> Chunks Count: {source_info.get('chunks_count')}")
    print(f"--> Duration Seconds: {source_info.get('duration_seconds')}")
    print(f"--> Video ID: {source_info.get('video_id')}")

    assert source_info.get("source_type") == "youtube"
    assert source_info.get("processing_status") in ("completed", "ready")
    assert source_info.get("chunks_count") > 0
    assert source_info.get("video_id") == EXPECTED_VIDEO_ID
    assert source_info.get("canonical_url") == f"https://www.youtube.com/watch?v={EXPECTED_VIDEO_ID}"

    # Step 4: Verify Course Detail includes YouTube source metadata
    print("\n[Step 4] Checking course listing via GET /api/courses/{course_id}...")
    course_detail_res = client.get(f"/api/courses/{course_1_id}")
    assert course_detail_res.status_code == 200
    course_detail = course_detail_res.json()
    sources = course_detail.get("sources", [])
    assert len(sources) >= 1
    yt_src = next((s for s in sources if s["id"] == source_id), None)
    assert yt_src is not None
    assert yt_src.get("source_type") == "youtube"
    assert yt_src.get("video_id") == EXPECTED_VIDEO_ID
    print(f"--> Course has {len(sources)} source(s), including YouTube source '{yt_src.get('title')}'")

    # Step 5: Ask Grounded Question Answered in Video
    print("\n[Step 5] Asking tutor question answered in the YouTube video...")
    question = "How many pixels are in the 28 by 28 grid of a handwritten digit image, and how many neurons make up the input layer?"
    print(f"Question: '{question}'")
    chat_res = client.post("/api/tutor/chat", json={
        "course_id": course_1_id,
        "message": question
    })
    assert chat_res.status_code == 200, f"Tutor chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    print(f"--> Grounded: {chat_data.get('grounded')}")
    print(f"--> Answer: {chat_data.get('answer')[:300]}...")

    assert chat_data.get("grounded") is True, f"Expected grounded=True, got: {chat_data}"
    sources = chat_data.get("sources", [])
    assert len(sources) > 0, "Expected at least one citation"

    # Step 6: Verify YouTube Citation Format & Timestamps
    print("\n[Step 6] Verifying YouTube timestamp citation...")
    yt_citation = None
    for src in sources:
        print(f"--> Citation: modality={src.get('modality')}, file='{src.get('file_name')}', "
              f"start={src.get('start_seconds')}s, end={src.get('end_seconds')}s, "
              f"excerpt='{src.get('excerpt')[:80]}...'")
        if src.get("modality") == "youtube" or src.get("video_id") == EXPECTED_VIDEO_ID:
            yt_citation = src
            break

    assert yt_citation is not None, f"Expected YouTube citation, got {sources}"
    assert yt_citation.get("modality") == "youtube"
    assert yt_citation.get("video_id") == EXPECTED_VIDEO_ID
    assert yt_citation.get("canonical_url") == f"https://www.youtube.com/watch?v={EXPECTED_VIDEO_ID}"
    assert yt_citation.get("start_seconds") is not None
    assert yt_citation.get("end_seconds") is not None
    assert yt_citation.get("start_seconds") >= 0
    assert yt_citation.get("end_seconds") >= yt_citation.get("start_seconds")
    assert "[YouTube " in yt_citation.get("excerpt"), f"Expected [YouTube HH:MM:SS-HH:MM:SS] in excerpt, got {yt_citation.get('excerpt')}"
    print(f"--> Verified timestamp citation: {yt_citation.get('start_seconds')}s to {yt_citation.get('end_seconds')}s")

    # Step 7: Ask Unrelated Question -> Grounded Rejection
    print("\n[Step 7] Asking completely unrelated off-material question...")
    unrelated_q = "What are the rules of professional cricket and how is an LBW wicket decided?"
    print(f"Question: '{unrelated_q}'")
    unrelated_res = client.post("/api/tutor/chat", json={
        "course_id": course_1_id,
        "message": unrelated_q
    })
    assert unrelated_res.status_code == 200
    unrelated_data = unrelated_res.json()
    print(f"--> Grounded: {unrelated_data.get('grounded')}")
    print(f"--> Sources: {unrelated_data.get('sources')}")
    print(f"--> Answer: {unrelated_data.get('answer')}")

    assert unrelated_data.get("grounded") is False
    assert len(unrelated_data.get("sources", [])) == 0
    assert "couldn't find enough information" in unrelated_data.get("answer").lower() or "not" in unrelated_data.get("answer").lower()
    print("--> Verified grounded rejection for off-material question!")

    # Step 8: Course Isolation Check
    print("\n[Step 8] Verifying Course Isolation with Course 2...")
    c2_res = client.post("/api/courses", json={
        "title": "Renaissance Art & Architecture",
        "description": "Art history in 15th-century Italy."
    })
    assert c2_res.status_code == 201
    course_2_id = c2_res.json()["id"]

    c2_chat = client.post("/api/tutor/chat", json={
        "course_id": course_2_id,
        "message": "Explain what 784 neurons represent in the 28 by 28 grid from the neural network video."
    })
    assert c2_chat.status_code == 200
    c2_data = c2_chat.json()
    print(f"--> Course 2 Grounded: {c2_data.get('grounded')}")
    print(f"--> Course 2 Sources: {c2_data.get('sources')}")
    assert c2_data.get("grounded") is False
    assert len(c2_data.get("sources", [])) == 0
    print("--> Verified Course Isolation: Course 2 cannot access YouTube vectors of Course 1!")

    print("\n" + "=" * 80)
    print("PHASE 4C LIVE ACCEPTANCE TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_acceptance_test()
