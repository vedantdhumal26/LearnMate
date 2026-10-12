"""
Complete Phase 4B Live Acceptance Test for LearnSphere AI.
Multimodal Ingestion: Lecture Video + Timestamped Transcripts + RAG Citations.
Executes all 14 required steps against the live running FastAPI server at http://127.0.0.1:8000.
"""

import os
import sys
import io
import time
import subprocess
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from app.services.transcription.audio_utils import get_ffmpeg_exe

BASE_URL = "http://127.0.0.1:8000"

def generate_acceptance_video(output_mp4_path: str) -> str:
    """
    Generate a small, valid MP4 lecture video containing real spoken English.
    Spoken text: 'According to Bernoulli principle, when fluid velocity increases, static pressure decreases.'
    Uses Windows SAPI for TTS audio generation and ffmpeg for MP4 container muxing.
    """
    wav_path = output_mp4_path.replace(".mp4", "_speech.wav")
    
    # 1. Generate speech WAV
    spoken_text = "According to Bernoulli principle, when fluid velocity increases, static pressure decreases."
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(wav_path, 3, False)
        speaker.AudioOutputStream = stream
        speaker.Speak(spoken_text)
        stream.Close()
    except Exception as e:
        print(f"Warning: SAPI TTS failed ({e}), falling back to lavfi sine wave.")
        wav_path = None

    ffmpeg_exe = get_ffmpeg_exe()
    assert ffmpeg_exe is not None, "ffmpeg executable must be available to generate acceptance video."

    if wav_path and os.path.exists(wav_path):
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "lavfi", "-i", "color=c=navy:s=320x240:r=1",
            "-i", wav_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            output_mp4_path
        ]
    else:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
            "-f", "lavfi", "-i", "color=c=navy:s=320x240:d=4",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            output_mp4_path
        ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate acceptance video: {res.stderr}")

    if wav_path and os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass

    return output_mp4_path


def run_acceptance_test():
    print("=" * 80)
    print("STARTING PHASE 4B LIVE ACCEPTANCE TEST: LECTURE VIDEO INGESTION & CITATIONS")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=90.0)

    # Step 1: Create Course 1
    print("\n[Step 1] Creating Course 1...")
    c1_res = client.post("/api/courses", json={
        "title": "Fluid Dynamics and Aerodynamics Lecture Series",
        "description": "Comprehensive lectures on Bernoulli's principle, fluid flow, and dynamic pressure."
    })
    assert c1_res.status_code == 201, f"Failed to create Course 1: {c1_res.text}"
    course_1 = c1_res.json()
    course_1_id = course_1["id"]
    print(f"--> Course 1 created: ID={course_1_id}, Title='{course_1['title']}'")

    # Step 2: Create/upload a real small MP4
    mp4_filename = "lecture_fluid_mechanics.mp4"
    temp_mp4_path = os.path.join(os.path.dirname(__file__), mp4_filename)
    print(f"\n[Step 2] Generating real small MP4 with spoken lecture content: '{temp_mp4_path}'...")
    generate_acceptance_video(temp_mp4_path)
    file_size = os.path.getsize(temp_mp4_path)
    print(f"--> Generated MP4 file size: {file_size} bytes")

    print("\n[Step 3] Uploading MP4 to Course 1...")
    with open(temp_mp4_path, "rb") as f:
        files = {
            "file": (
                mp4_filename,
                f,
                "video/mp4"
            )
        }
        upload_res = client.post(f"/api/courses/{course_1_id}/upload", files=files)

    # Clean up local generated mp4 file
    if os.path.exists(temp_mp4_path):
        try:
            os.remove(temp_mp4_path)
        except Exception:
            pass

    assert upload_res.status_code == 201, f"Failed to upload MP4: {upload_res.text}"
    upload_data = upload_res.json()
    source_id = upload_data["source_id"]
    file_name = upload_data["file_name"]
    print(f"--> Upload successful: source_id={source_id}, file_name='{file_name}', status='{upload_data.get('status')}'")

    # Step 4: Verify processing_status = completed
    print("\n[Step 4] Checking ingestion status...")
    status_res = client.get(f"/api/courses/{course_1_id}/uploads/{source_id}")
    assert status_res.status_code == 200, f"Failed to get source status: {status_res.text}"
    source_info = status_res.json()
    assert source_info["processing_status"] == "completed", f"Status is {source_info['processing_status']}"
    print(f"--> Source processing_status: {source_info['processing_status']}")

    # Step 5: Verify transcript chunks exist
    print("\n[Step 5] Verifying transcript chunks exist...")
    chunks_count = source_info.get("chunks_count", 0)
    print(f"--> Document chunks count: {chunks_count}")
    assert chunks_count >= 1, f"Expected at least 1 chunk, got {chunks_count}"

    # Step 6: Verify start/end timestamps exist
    print("\n[Step 6] Verifying start/end timestamps and video metadata exist...")
    duration_seconds = source_info.get("duration_seconds")
    segment_count = source_info.get("segment_count")
    print(f"--> Duration seconds: {duration_seconds}, Segment count: {segment_count}")
    assert duration_seconds is not None and duration_seconds > 0.0, f"Expected positive duration, got {duration_seconds}"
    assert segment_count is not None and segment_count >= 1, f"Expected at least 1 segment, got {segment_count}"

    # Step 7: Ask tutor question whose answer exists in a known transcript segment
    print("\n[Step 7] Asking tutor question answered in the video transcript...")
    q1 = "According to Bernoulli's principle, what happens to the static pressure of a fluid when its velocity increases?"
    chat_res = client.post("/api/tutor/chat", json={
        "course_id": course_1_id,
        "message": q1
    })
    assert chat_res.status_code == 200, f"Tutor chat failed: {chat_res.text}"
    chat_data = chat_res.json()

    # Step 8: Verify grounded = true, source_id correct, file_name correct, start_seconds populated, end_seconds populated
    print("\n[Step 8] Verifying grounded=True and exact video citation metadata...")
    print(f"--> Grounded: {chat_data['grounded']}")
    print(f"--> Answer: {chat_data['answer']}")
    assert chat_data["grounded"] is True, f"Expected tutor answer to be grounded, got {chat_data}"
    assert len(chat_data["sources"]) > 0, "Expected at least one citation source"

    video_citation = None
    for src in chat_data["sources"]:
        print(f"--> Citation: file='{src['file_name']}', start={src.get('start_seconds')}, end={src.get('end_seconds')}")
        if src.get("file_name") == mp4_filename or src.get("start_seconds") is not None:
            video_citation = src
            break

    assert video_citation is not None, f"Expected video citation, got: {chat_data['sources']}"
    assert video_citation["source_id"] == source_id, f"Expected source_id={source_id}, got {video_citation['source_id']}"
    assert video_citation["file_name"] == mp4_filename
    assert video_citation["page"] is None, f"Expected page=None for video, got {video_citation['page']}"
    assert video_citation["slide"] is None, f"Expected slide=None for video, got {video_citation['slide']}"
    assert video_citation["start_seconds"] is not None, "Expected start_seconds to be populated"
    assert video_citation["end_seconds"] is not None, "Expected end_seconds to be populated"
    assert video_citation["start_seconds"] >= 0.0, f"Invalid start_seconds: {video_citation['start_seconds']}"
    assert video_citation["end_seconds"] >= video_citation["start_seconds"], f"Invalid end_seconds: {video_citation['end_seconds']}"
    print(f"--> PASS: Verified video citation: {video_citation['file_name']} — start: {video_citation['start_seconds']}s, end: {video_citation['end_seconds']}s")

    # Step 9: Verify returned citation corresponds to expected time window
    print("\n[Step 9] Verifying returned citation corresponds to expected time window...")
    # The speech in the acceptance video is roughly 5.7 seconds long
    assert video_citation["start_seconds"] <= 10.0, f"Expected start_seconds <= 10.0, got {video_citation['start_seconds']}"
    assert video_citation["end_seconds"] <= 30.0, f"Expected end_seconds <= 30.0, got {video_citation['end_seconds']}"
    print(f"--> PASS: Timestamp citation {video_citation['start_seconds']}s–{video_citation['end_seconds']}s matches the expected time window.")

    # Step 10: Ask unrelated question
    print("\n[Step 10] Asking completely unrelated off-material question...")
    q_unrelated = "What is the capital of ancient Mesopotamia and what were the laws of Hammurabi?"
    chat_unrelated = client.post("/api/tutor/chat", json={
        "course_id": course_1_id,
        "message": q_unrelated
    })
    assert chat_unrelated.status_code == 200
    unrelated_data = chat_unrelated.json()

    # Step 11: Verify grounded = false, sources = []
    print("\n[Step 11] Verifying rejection for off-material question...")
    print(f"--> Grounded: {unrelated_data['grounded']}")
    print(f"--> Sources: {unrelated_data['sources']}")
    print(f"--> Answer: {unrelated_data['answer']}")
    assert unrelated_data["grounded"] is False, "Expected grounded=False for off-material topic"
    assert unrelated_data["sources"] == [], "Expected empty sources for off-material topic"
    print("--> PASS: Off-material question correctly rejected with grounded=False and sources=[]")

    # Step 12: Create Course 2
    print("\n[Step 12] Creating Course 2 to test cross-course video isolation...")
    c2_res = client.post("/api/courses", json={
        "title": "Stellar Astrophysics and Cosmology",
        "description": "Lifecycle of stars, white dwarfs, neutron stars, and black holes."
    })
    assert c2_res.status_code == 201
    course_2 = c2_res.json()
    course_2_id = course_2["id"]
    print(f"--> Course 2 created: ID={course_2_id}, Title='{course_2['title']}'")

    # Step 13: Ask Course 2 about Course 1's video content
    print("\n[Step 13] Asking Course 2 about Course 1's video lecture content...")
    cross_res = client.post("/api/tutor/chat", json={
        "course_id": course_2_id,
        "message": "Explain Bernoulli's principle and the relationship between velocity and pressure from the lecture video."
    })
    assert cross_res.status_code == 200
    cross_data = cross_res.json()
    print(f"--> Course 2 Query Grounded: {cross_data['grounded']}")
    print(f"--> Course 2 Query Sources: {cross_data['sources']}")

    # Step 14: Verify Course 2 cannot retrieve Course 1 content
    print("\n[Step 14] Verifying Course 2 cannot retrieve Course 1 video content...")
    assert cross_data["grounded"] is False, "Course 1 video content must NOT be retrievable from Course 2"
    assert cross_data["sources"] == [], "No sources should be returned across course boundary"
    print("--> PASS: Strict Course Isolation verified. Course 2 returned grounded=False and sources=[].")

    print("\n" + "=" * 80)
    print("ALL 14 STEPS OF PHASE 4B LIVE ACCEPTANCE TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_acceptance_test()
