# LearnSphere AI — Personalized Tutoring & Adaptive Learning Platform (Backend)

LearnSphere AI is a source-grounded intelligent tutoring and adaptive learning backend.
Supported Course Material Formats:
- **PDF Documents** (`.pdf`): page-aware text chunking, heading detection, and exact 1-indexed page citations.
- **PowerPoint Slide Decks** (`.pptx`): slide-by-slide text extraction, slide-level citations, embedded image/diagram extraction, and optional vision-model diagram comprehension.
- **YouTube Video URLs** (`youtube`): transcript/caption extraction without downloading audiovisual media, timestamped segment normalization, chunking, and exact timestamp citations (`[YouTube 00:03:19–00:03:49]`).

---

## 1. Architecture Overview

```
[Student / Bolt.new Frontend]
             │
             ▼
     [FastAPI Endpoints]
     ├── /health
     ├── /api/courses
     ├── /api/courses/{course_id}/upload (PDF, PPTX, MP4)
     ├── /api/courses/{course_id}/youtube (YouTube URL ingestion)
     ├── /api/courses/{course_id}/uploads/{source_id}
     ├── /api/assessments/generate & /submit
     ├── /api/learner/{student_id}/courses/{course_id}/*
     ├── /api/tutor/chat
     └── /api/evaluation/run, /{id}, /{id}/results
             │
   ┌─────────┴───────────────────────────────────────────────────────┐
   │ Ingestion Pipeline:                                             │
   │   PDF: PyMuPDF Page Text Extraction ➔ Heading Detection         │
   │   PPTX: python-pptx Slide Text & Visual Diagram Extraction      │
   │   MP4: ISO Base Media Validation ➔ Groq Whisper Speech-to-Text  │
   │        ➔ ffmpeg Audio Chunking for Large Videos (>25MB)         │
   │        ➔ Timestamp Normalization & Contiguous Time Windows      │
   │   YouTube: Public Transcript/Caption Extraction (No AV Storage) │
   │        ➔ Timestamp Normalization & Contiguous Time Windows      │
   │   ➔ Deterministic SHA-256 Content Hash (Deduplication)          │
   │   ➔ Dense Semantic Embeddings (FastEmbed / OpenAI)              │
   │   ➔ Relational Store (Courses, Sources, Chunks, Video Meta)     │
   │   ➔ Qdrant Vector Collection (Strict Course-Isolated Payloads)  │
   └─────────────────────────────────────────────────────────────────┘
             │
   ┌─────────┴───────────────────────────────────────────────────────┐
   │ RAG Tutor Pipeline:                                             │
   │   Student Question ➔ Query Embedding                            │
   │   ➔ Course-Filtered Qdrant Vector Search                        │
   │   ➔ Pre-Retrieval Grounding Check (Score Threshold >= 0.55)     │
   │   ➔ Modality-Aware Prompt Builder (PDF, PPTX, Video, YouTube)   │
   │   ➔ Configurable LLM Service (Groq, OpenAI, Ollama)             │
   │   ➔ Exact Citations (Page, Slide, Video/YouTube Timestamps)     │
   │   ➔ Post-Generation Grounding Validator                         │
   └─────────────────────────────────────────────────────────────────┘
             │
   ┌─────────┴───────────────────────────────────────────────────────┐
   │ Phase 5 Evaluation Subsystem:                                   │
   │   RAG Metrics (Faithfulness, Relevancy, Precision, Recall)      │
   │   Grounding Check (Supported Acceptance, Off-Material Rejection)│
   │   Citation Verification (DB, Course, Modality, Page/Slide/Time) │
   │   Course Isolation Evaluation (Zero-Leakage Guarantee)          │
   │   Assessment Quality & Deduplication Rate Evaluation            │
   │   Simulated Learner Mastery Profiles (Beginner, Mixed, Advanced)│
   └─────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

```
backend/
├── app/
│   ├── main.py                     # FastAPI application setup, CORS, lifespan & error handlers
│   ├── core/
│   │   ├── config.py               # Pydantic v2 Settings & environment variables
│   │   ├── database.py             # PostgreSQL / SQLite SQLAlchemy engine and sessions
│   │   └── logging_config.py       # Structured logging configuration
│   ├── api/
│   │   └── routes/
│   │       ├── health.py           # GET /health
│   │       ├── courses.py          # POST/GET /api/courses & details
│   │       ├── uploads.py          # POST /api/courses/{course_id}/upload (PDF, PPTX, MP4) & /youtube
│   │       ├── assessments.py      # POST /api/assessments/generate & submit
│   │       ├── learner.py          # GET /api/learner/{student_id}/courses/{course_id}/*
│   │       ├── tutor.py            # POST /api/tutor/chat
│   │       └── evaluation.py       # POST /api/evaluation/run, GET /{id}, GET /{id}/results
│   ├── models/
│   │   ├── course.py               # Course SQL model
│   │   ├── source.py               # Source document SQL model (pdf, pptx, video, youtube)
│   │   ├── document_chunk.py       # DocumentChunk model (pages, slides, timestamps, modality)
│   │   ├── assessment.py           # Assessment and Question models
│   │   ├── learner_mastery.py      # Topic mastery tracking models
│   │   └── evaluation.py           # EvaluationRun and EvaluationResult models
│   ├── schemas/
│   │   ├── course.py               # Pydantic DTOs for courses
│   │   ├── upload.py               # Pydantic DTOs for uploads (duration_seconds, segment_count)
│   │   ├── tutor.py                # Pydantic DTOs for tutor chat & citations
│   │   ├── assessment.py           # Pydantic DTOs for adaptive assessments
│   │   ├── learner.py              # Pydantic DTOs for learner mastery
│   │   └── evaluation.py           # Pydantic DTOs for evaluation requests, results, summaries
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── pdf_processor.py    # PyMuPDF extraction, heading detection, and chunking
│   │   │   ├── pptx_processor.py   # python-pptx slide text and visual extraction
│   │   │   ├── youtube_processor.py# YouTube transcript ingestion and chunking
│   │   │   └── ingestion_service.py# Unified ingestion coordinator (PDF, PPTX, MP4, YouTube)
│   │   ├── transcription/
│   │   │   ├── audio_utils.py      # ffmpeg audio extraction, probe, and segment chunking
│   │   │   └── transcription_service.py # Groq Speech-to-Text client & chunk builder
│   │   ├── vision/
│   │   │   └── vision_service.py   # Multimodal image and diagram captioning
│   │   ├── embeddings/
│   │   │   └── embedding_service.py# Modular FastEmbed / OpenAI embedding providers
│   │   ├── vector_store/
│   │   │   ├── base.py             # Vector store abstract base interface
│   │   │   └── qdrant_store.py     # Qdrant client implementation with course filtering
│   │   ├── rag/
│   │   │   ├── retriever.py        # Course-isolated semantic retriever
│   │   │   ├── prompt_builder.py   # Modality-aware grounded tutor prompt
│   │   │   ├── grounding.py        # Pre/post retrieval grounding validator
│   │   │   ├── citation.py         # Multi-format citation extractor (Page, Slide, Timestamp)
│   │   │   └── tutor_service.py    # End-to-end tutor orchestration
│   │   ├── llm/
│   │   │   └── llm_service.py      # Provider-independent LLM service (OpenAI, Groq, Ollama)
│   │   └── evaluation/
│   │       ├── citation_evaluator.py  # Page, slide, timestamp, and excerpt authenticity validation
│   │       ├── rag_evaluator.py       # Dense cosine relevancy, faithfulness, precision, recall
│   │       ├── assessment_evaluator.py# Question validity, arithmetic check, duplicate rate
│   │       ├── learner_evaluator.py   # High, mixed, and struggling learner simulations
│   │       ├── fixtures.py            # Built-in multimodal evaluation dataset fixtures
│   │       └── evaluator.py           # Central evaluation orchestration engine
│   └── utils/
│       ├── file_utils.py           # PDF, PPTX, and MP4 format and header signature validation
│       ├── text_utils.py           # Whitespace cleanup & heading detection
│       ├── hashing.py              # SHA256 deterministic content hashing
│       └── youtube_utils.py        # YouTube URL parsing and video ID extraction
│   └── tests/
│       ├── test_health.py          # Health endpoint tests
│       ├── test_courses.py         # Course creation and listing tests
│       ├── test_upload.py          # PDF upload and processing tests
│       ├── test_pptx_ingestion.py  # PPTX ingestion, slides, visuals, and citations
│       ├── test_video_ingestion.py # MP4 ingestion, Groq Whisper, timestamps, citations
│       ├── test_youtube_source.py  # YouTube transcript extraction, timestamps, citations
│       ├── test_assessments.py     # Adaptive assessment generation, grading, safety
│       ├── test_learner_model.py   # Topic mastery, Bayesian updates, recommendations
│       ├── test_tutor.py           # Grounded chat, citations, rejection tests
│       ├── test_evaluation.py      # Phase 5 evaluation subsystem tests
│       └── acceptance_test_phase5.py # Live acceptance test for full Phase 5 evaluation
```

---

## 3. Phase 5 Evaluation Subsystem

LearnSphere AI includes a production evaluation subsystem measuring quality and safety without fabricated metrics.

### What is Being Evaluated

1. **RAG Retrieval Quality**:
   - Dense semantic **Answer Relevancy** between student question and generated answer.
   - Ground truth **Faithfulness** verifying factual statements against retrieved context.
   - **Context Precision**: Ratio of relevant retrieved documents among all retrieved.
   - **Context Recall**: Coverage of expected ground truth context by retrieved chunks.
2. **Grounding & Safety**:
   - **Supported Questions**: Grounded answers generated when covered by course material (`grounded = true`).
   - **Unsupported Questions**: Clean refusals with empty citations for off-material questions (`grounded = false`, `sources = []`).
3. **Citation Correctness**:
   - Verification that `source_id` exists in the database and belongs to the queried course.
   - Modality verification (PDF, PPTX, MP4 video, YouTube URL).
   - Location precision: exact PDF page, PPTX slide number, MP4 timestamp window, and YouTube timestamp interval overlap.
   - Excerpt authenticity: anti-hallucination verification against chunks stored in the database.
4. **Cross-Course Isolation**:
   - Zero-leakage verification: queries directed to Course B cannot retrieve or cite documents from Course A.
5. **Assessment Quality & Question Repetition**:
   - Question validity: single correct MCQ option, arithmetic consistency for numerical questions, grounded short answers.
   - Question deduplication: duplicate detection rate across repeated generation rounds.
6. **Learner Model Personalization**:
   - Deterministic simulations across three student profiles:
     - `high_performer`: mostly correct responses (mastery increases, minimal weak topics).
     - `mixed_performer`: balanced responses (moderate mastery gain).
     - `struggling`: mostly incorrect responses (detects weak topics, generates dynamic recommendations).

### Dataset Format (Provider-Independent JSON)

```json
[
  {
    "id": "eval-pdf-01",
    "course_id": "course-uuid",
    "question": "What is Newton's second law of motion and what is the formula?",
    "expected_answer": "F = m * a",
    "expected_grounded": true,
    "expected_sources": [
      {
        "source_id": "source-uuid",
        "page": 2,
        "modality": "pdf"
      }
    ]
  },
  {
    "id": "eval-pptx-01",
    "course_id": "course-uuid",
    "question": "What are the three primary components of an electric motor?",
    "expected_answer": "Stator, rotor, and commutator.",
    "expected_grounded": true,
    "expected_sources": [
      {
        "source_id": "source-uuid",
        "slide": 2,
        "modality": "pptx"
      }
    ]
  },
  {
    "id": "eval-yt-01",
    "course_id": "course-uuid",
    "question": "How many neurons make up the input layer for the 28 by 28 pixel image?",
    "expected_answer": "784 neurons",
    "expected_grounded": true,
    "expected_sources": [
      {
        "source_id": "source-uuid",
        "start_seconds": 180.0,
        "end_seconds": 240.0,
        "modality": "youtube"
      }
    ]
  },
  {
    "id": "eval-unsupported-01",
    "course_id": "course-uuid",
    "question": "What are the rules of professional cricket?",
    "expected_answer": null,
    "expected_grounded": false,
    "expected_sources": []
  },
  {
    "id": "eval-isolation-01",
    "course_id": "unrelated-course-uuid",
    "question": "Explain Newton's second law from the uploaded physics notes.",
    "expected_answer": null,
    "expected_grounded": false,
    "expected_sources": [],
    "is_course_isolation": true,
    "source_course_id": "course-uuid"
  }
]
```

### Metric Definitions

| Metric | Definition | Range |
|---|---|---|
| **Faithfulness** | Fraction of claims in the generated answer supported by retrieved chunks. | `[0.0, 1.0]` or `null` if ungrounded |
| **Answer Relevancy** | Dense cosine similarity between question and generated answer embedding. | `[-1.0, 1.0]` (typically `0.70-0.95`) |
| **Context Precision** | Proportion of retrieved chunks that match expected ground truth sources. | `[0.0, 1.0]` |
| **Context Recall** | Proportion of expected ground truth sources retrieved by the system. | `[0.0, 1.0]` |
| **Citation Accuracy** | Proportion of citations that are authentic, belong to the course, and match expected locations. | `[0.0, 1.0]` |
| **Grounding Accuracy** | Accuracy of the tutor in answering supported questions and rejecting unsupported questions. | `[0.0, 1.0]` |
| **Course Isolation Failures** | Number of times material from Course A leaked into responses for Course B. | Integer (`0` required) |
| **Duplicate Rate** | Percentage of generated questions rejected as duplicates across repeated rounds. | `[0.0, 1.0]` |

> [!IMPORTANT]
> Metrics are calculated from real test executions. If external services are unavailable or a metric cannot be evaluated, it is returned as `null` rather than fabricated.

### How to Run an Evaluation

#### Option A: Via REST API

1. **Launch Evaluation Run**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/evaluation/run \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Live RAG Evaluation",
       "course_id": "<course-id>",
       "run_learner_simulations": true,
       "run_assessment_eval": true,
       "sync": false
     }'
   ```
   **Response (`201 Created`):**
   ```json
   {
     "evaluation_id": "18064616-eaea-4f96-879f-74e9b7ad4584",
     "status": "started"
   }
   ```

2. **Poll Status**:
   ```bash
   curl -X GET http://127.0.0.1:8000/api/evaluation/18064616-eaea-4f96-879f-74e9b7ad4584
   ```
   **Response (`200 OK`):**
   ```json
   {
     "evaluation_id": "18064616-eaea-4f96-879f-74e9b7ad4584",
     "status": "completed",
     "dataset_size": 4,
     "started_at": "2026-10-03T14:17:26.759437Z",
     "completed_at": "2026-10-03T14:17:45.240701Z",
     "failure_reason": null
   }
   ```

3. **Retrieve Full Results & Metrics Summary**:
   ```bash
   curl -X GET http://127.0.0.1:8000/api/evaluation/18064616-eaea-4f96-879f-74e9b7ad4584/results
   ```

#### Option B: Via Acceptance Test CLI

Run the end-to-end acceptance script that builds a live multimodal course, uploads PDF, PPTX, MP4, executes the evaluation, and verifies all metrics:
```bash
python tests/acceptance_test_phase5.py
```

---

## 4. Actual Measured Evaluation Results vs. Example Result

### Actual Measured Execution (Run ID: `18064616-eaea-4f96-879f-74e9b7ad4584`)

The following metrics were measured during live execution against the running backend with uploaded PDF, PPTX, MP4, and Groq LLM:

```
================================================================================
LEARN SPHERE AI — EVALUATION REPORT (ACTUAL MEASURED EXECUTION)
================================================================================
Run ID: 18064616-eaea-4f96-879f-74e9b7ad4584
Status: COMPLETED
Dataset Size: 4 test cases

RAG METRICS:
  Answer Relevancy: 0.860 (Calculated via FastEmbed dense cosine similarity)
  Faithfulness:     0.750 (Calculated via factual claim grounding)
  Context Precision:0.250
  Context Recall:   1.000

GROUNDING & SAFETY:
  Grounding Accuracy:            100.0%
  Supported Questions Answered:  2/2
  Unsupported Questions Rejected:1/1
  Course Isolation Failures:     0/1 (Strict course isolation verified)

CITATIONS:
  Citation Accuracy:             100.0%
  Citation Failure Count:        0

LEARNER PROFILES SIMULATION:
  [HIGH_PERFORMER] Before: 0.00 -> After: 1.00 (Gain: +1.00), Recommendations: 1
  [MIXED_PERFORMER] Before: 0.00 -> After: 0.65 (Gain: +0.65), Recommendations: 1
  [STRUGGLING]     Before: 0.00 -> After: 0.26 (Gain: +0.26), Weak Topics: ['Neural Networks']
================================================================================
```

### Example Illustrative Output (For Reference Only)

```
LEARN SPHERE AI EVALUATION (ILLUSTRATIVE EXAMPLE)
RAG: Faithfulness: 91%, Answer Relevancy: 88%, Context Precision: 86%, Context Recall: 90%
Grounding: Supported: 95/100, Unsupported Rejected: 97/100
Citations: Correct Citations: 94/100
Assessments: Valid Questions: 98/100, Duplicate Rate: 4%
Learner Simulation: Beginner: +17%, Intermediate: +11%, Struggling: +13%
```

---

## 5. System Limitations

1. **RAGAS Integration**: RAGAS is replaced by a native, documented equivalent evaluation path using local FastEmbed embeddings and claim verification to prevent heavy dependency conflicts.
2. **YouTube Transcripts**: In offline test environments or when YouTube rate limits Innertube requests, YouTube test cases cleanly report `modality unavailable` rather than failing or fabricating captions.
3. **Local Vector Storage**: Embedded local Qdrant is used by default when server Qdrant is unavailable on port 6333.
4. **LLM Rate Limits**: Groq API rate limits (HTTP 429) are gracefully handled using exponential backoff with retry.

---

## 6. Full Regression Test Suite

All 86 tests pass cleanly with zero regressions:
```bash
python -m pytest tests/ -v
# 86 passed in 28.08s
```
- `test_health.py`: 1 passed
- `test_courses.py`: 5 passed
- `test_upload.py`: 5 passed
- `test_pptx_ingestion.py`: 12 passed
- `test_video_ingestion.py`: 14 passed
- `test_youtube_source.py`: 10 passed
- `test_assessments.py`: 9 passed
- `test_learner_model.py`: 11 passed
- `test_tutor.py`: 5 passed
- `test_evaluation.py`: 14 passed
```

---

## 3. Configuration & Environment Variables

Key settings in `.env`:

```ini
# Database & Vector DB
DATABASE_URL=sqlite:///./learnsphere.db
QDRANT_URL=http://localhost:6333
QDRANT_STORAGE_PATH=./qdrant_storage

# LLM Provider Configuration
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
LLM_API_KEY=your_groq_api_key

# FastEmbed Embeddings (Local, 0 API keys required)
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Vision Model (Phase 4A)
VISION_PROVIDER=groq
VISION_MODEL=qwen/qwen3.6-27b
VISION_ENABLED=true

# Speech-to-Text Transcription (Phase 4B)
TRANSCRIPTION_PROVIDER=groq
TRANSCRIPTION_MODEL=whisper-large-v3-turbo
TRANSCRIPTION_LANGUAGE=
TRANSCRIPTION_ENABLED=true
TRANSCRIPTION_MAX_FILE_MB=25
TRANSCRIPTION_CHUNK_SECONDS=600
TRANSCRIPTION_OVERLAP_SECONDS=5

# RAG & Grounding
RAG_TOP_K=4
RAG_SCORE_THRESHOLD=0.55
```

---

## 4. API Endpoints & Usage

### Uploading Course Material (PDF, PPTX, MP4)

Endpoint: `POST /api/courses/{course_id}/upload`

#### A. Video Upload (.mp4):
```bash
curl -X POST http://localhost:8000/api/courses/{course_id}/upload \
  -F "file=@lecture_fluid_mechanics.mp4;type=video/mp4"
```
**Response:**
```json
{
  "source_id": "94ca03b2-745f-4392-9410-3433cc543c00",
  "file_name": "lecture_fluid_mechanics.mp4",
  "status": "completed"
}
```

#### B. Check Ingestion Status:
```bash
curl -X GET http://localhost:8000/api/courses/{course_id}/uploads/94ca03b2-745f-4392-9410-3433cc543c00
```
**Response:**
```json
{
  "source_id": "94ca03b2-745f-4392-9410-3433cc543c00",
  "course_id": "76ad1087-b841-40a3-9e79-7f6922425965",
  "file_name": "lecture_fluid_mechanics.mp4",
  "file_type": "video/mp4",
  "processing_status": "completed",
  "chunks_count": 1,
  "duration_seconds": 5.7,
  "segment_count": 1,
  "created_at": "2026-10-02T18:30:00Z"
}
```

### Grounded Tutor Chat with Multimodal Citations

Endpoint: `POST /api/tutor/chat`

#### A. Lecture Video Query (Timestamp Citation):
```bash
curl -X POST http://localhost:8000/api/tutor/chat \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "76ad1087-b841-40a3-9e79-7f6922425965",
    "message": "What happens to fluid pressure when velocity increases?"
  }'
```
**Response:**
```json
{
  "answer": "According to Bernoulli's principle, when a fluid's velocity increases, its static pressure decreases simultaneously.",
  "grounded": true,
  "sources": [
    {
      "source_id": "94ca03b2-745f-4392-9410-3433cc543c00",
      "file_name": "lecture_fluid_mechanics.mp4",
      "page": null,
      "slide": null,
      "start_seconds": 0.0,
      "end_seconds": 5.7,
      "excerpt": "[Video 00:00:00–00:00:06]\nAccording to Bernoulli principle, when fluid velocity increases, static pressure decreases."
    }
  ]
}
```

#### B. PowerPoint Presentation Query (Slide Citation):
```json
{
  "answer": "The change in internal energy is given by Delta U = Q - W.",
  "grounded": true,
  "sources": [
    {
      "source_id": "2372ed5e-2cd2-4c53-a66b-dce9f56aa376",
      "file_name": "aerodynamics_lecture.pptx",
      "page": null,
      "slide": 2,
      "start_seconds": null,
      "end_seconds": null,
      "excerpt": "[Slide 2] First Law of Thermodynamics..."
    }
  ]
}
```

#### C. PDF Textbook Query (Page Citation):
```json
{
  "answer": "Newton's second law is mathematically expressed as F = m * a.",
  "grounded": true,
  "sources": [
    {
      "source_id": "8f8b65e1-884d-4952-ba74-d4b998cfb284",
      "file_name": "physics_lecture.pdf",
      "page": 2,
      "slide": null,
      "start_seconds": null,
      "end_seconds": null,
      "excerpt": "Chapter 2: Newton's Second Law of Motion..."
    }
  ]
}
```

#### D. Unrelated / Off-Material Rejection:
```json
{
  "answer": "I couldn't find enough information about this topic in the uploaded course material.",
  "grounded": false,
  "sources": []
}
```

---

## 5. Running Tests

Run the full pytest suite (120+ tests across all phases):
```bash
python -m pytest -v
```

Run Live Acceptance Tests:
- Phase 4A (PPTX & Slides): `python tests/acceptance_test_phase4a.py`
- Phase 4B (Video & Timestamps): `python tests/acceptance_test_phase4b.py`
- Phase 5 (Evaluation & Metrics): `python tests/acceptance_test_phase5.py`
- Phase 6A (Real User Authentication & Ownership): `python -m pytest -v tests/acceptance_test_phase6a.py`

---

## 6. Phase 6A: Real User Authentication & Frontend Contract

All protected endpoints require the HTTP header:
```http
Authorization: Bearer <token>
```

### 1. User Signup
**Endpoint:** `POST /api/auth/signup`  
**Description:** Registers a new user, hashes password with Argon2id, creates user profile, and returns an access token.  
**Status Codes:**
- `201 Created` — Registration successful.
- `400 Bad Request` — Duplicate email or validation error.

**Request Body:**
```json
{
  "email": "student@example.com",
  "password": "strong-password",
  "display_name": "Student"
}
```

**Response Body (201 Created):**
```json
{
  "user": {
    "id": "23416be9-0a88-47f4-8ac6-ae0c6698ee68",
    "email": "student@example.com",
    "display_name": "Student"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### 2. User Login
**Endpoint:** `POST /api/auth/login`  
**Description:** Authenticates user credentials via Argon2id verification and returns a signed JWT access token.  
**Status Codes:**
- `200 OK` — Authentication successful.
- `401 Unauthorized` — Invalid email or password (generic message; does not leak email existence).

**Request Body:**
```json
{
  "email": "student@example.com",
  "password": "strong-password"
}
```

**Response Body (200 OK):**
```json
{
  "user": {
    "id": "23416be9-0a88-47f4-8ac6-ae0c6698ee68",
    "email": "student@example.com",
    "display_name": "Student"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Response (401 Unauthorized):**
```json
{
  "detail": "Invalid email or password."
}
```

---

### 3. Current User Profile
**Endpoint:** `GET /api/auth/me`  
**Description:** Returns the authenticated user's profile based on the supplied JWT.  
**Header Required:**
```http
Authorization: Bearer <access_token>
```
**Status Codes:**
- `200 OK` — Token valid, profile returned.
- `401 Unauthorized` — Missing, malformed, or expired token.

**Response Body (200 OK):**
```json
{
  "id": "23416be9-0a88-47f4-8ac6-ae0c6698ee68",
  "email": "student@example.com",
  "display_name": "Student"
}
```

---

### 4. Authenticated Course & Resource Ownership Rules
- `POST /api/courses` sets `owner_id = current_user.id` automatically.
- `GET /api/courses` returns only courses owned by the authenticated user.
- `GET /api/courses/{course_id}` returns `404 Not Found` if the course does not belong to the user.
- `POST /api/courses/{course_id}/upload` & `/youtube` return `404 Not Found` if the course is not owned by the user.
- `POST /api/tutor/chat` verifies ownership before retrieval and returns `404 Not Found` for unauthorized courses.
- `POST /api/assessments/generate`, `GET /api/assessments/{id}`, `POST /api/assessments/{id}/submit` enforce ownership and derive student identity from the authenticated user.
- `GET /api/learner/{student_id}/courses/{course_id}/*` returns `403 Forbidden` if `student_id != current_user.id` or `404 Not Found` if the course is not owned by the user.
- `POST /api/evaluation/run`, `GET /api/evaluation/{id}`, `GET /api/evaluation/{id}/results` strictly isolate evaluation runs per authenticated user.

