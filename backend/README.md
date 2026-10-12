# LearnSphere AI — Multimodal Intelligent Tutoring Platform

LearnSphere AI is an adaptive learning and course-grounded intelligent tutoring platform.

## Supported Course Material Formats
- **PDF Documents** (`.pdf`): Page-aware extraction, heading hierarchy detection, and exact page citations.
- **PowerPoint Slide Decks** (`.pptx`): Slide-by-slide text extraction, slide-level citations, visual/diagram extraction, and vision-model comprehension.
- **Lecture Videos** (`.mp4`): Timestamped speech-to-text transcription (Groq Whisper), contiguous transcript chunking, and exact timestamp citations (`00:04:32–00:04:49`).

## Phase 4B Features: Lecture Video + Timestamped Transcripts
- **MP4 Video Ingestion**: Validates `.mp4` format and ISO Base Media File container signatures (`ftyp` box), extracts spoken audio, and transcribes spoken lecture content.
- **Speech-to-Text Transcription**: Powered by Groq Speech-to-Text with switchable models (`whisper-large-v3-turbo` or `whisper-large-v3`) with segment-level timestamps.
- **Large Video Handling**: Files <= 25MB are transcribed directly; files exceeding the limit have audio extracted and chunked into overlapping segments via ffmpeg with global timestamp preservation.
- **Timestamped Grounded Citations**: The AI tutor provides exact video timestamp citations (e.g., `lecture1.mp4 — 00:04:32–00:04:49`) with `start_seconds`, `end_seconds`, `page: null`, `slide: null`.
- **Course Isolation**: Vector payloads in Qdrant maintain strict course boundaries preventing cross-course retrieval.
- **Backward Compatibility**: Fully preserves PDF page citations, PPTX slide citations, adaptive assessments, and learner mastery tracking.

## Environment Variables (.env)
```ini
# Vision Model Configuration (Phase 4A)
VISION_PROVIDER=groq
VISION_MODEL=qwen/qwen3.6-27b
VISION_API_KEY=your_vision_api_key_here
VISION_ENABLED=true

# Speech-to-Text Transcription Configuration (Phase 4B)
TRANSCRIPTION_PROVIDER=groq
TRANSCRIPTION_MODEL=whisper-large-v3-turbo
TRANSCRIPTION_LANGUAGE=
TRANSCRIPTION_API_KEY=your_groq_api_key_here
TRANSCRIPTION_ENABLED=true
TRANSCRIPTION_MAX_FILE_MB=25
TRANSCRIPTION_CHUNK_SECONDS=600
TRANSCRIPTION_OVERLAP_SECONDS=5
```

## Example Video Upload & Tutor Citation
### 1. Upload Video
```bash
curl -X POST http://localhost:8000/api/courses/{course_id}/upload \
  -F "file=@aerodynamics_lecture.mp4;type=video/mp4"
```
Response:
```json
{
  "source_id": "94ca03b2-745f-4392-9410-3433cc543c00",
  "file_name": "aerodynamics_lecture.mp4",
  "status": "completed"
}
```

### 2. Tutor Query & Timestamp Citation
```bash
curl -X POST http://localhost:8000/api/tutor/chat \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "76ad1087-b841-40a3-9e79-7f6922425965",
    "message": "What does Bernoulli principle state about fluid velocity and pressure?"
  }'
```
Response:
```json
{
  "answer": "According to Bernoulli's principle, when a fluid's velocity increases, its static pressure decreases simultaneously.",
  "grounded": true,
  "sources": [
    {
      "source_id": "94ca03b2-745f-4392-9410-3433cc543c00",
      "file_name": "aerodynamics_lecture.mp4",
      "page": null,
      "slide": null,
      "start_seconds": 0.0,
      "end_seconds": 5.7,
      "excerpt": "[Video 00:00:00–00:00:06]\nAccording to Bernoulli principle, when fluid velocity increases, static pressure decreases."
    }
  ]
}
```

## Running the Backend
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Swagger Documentation: `http://localhost:8000/docs`
