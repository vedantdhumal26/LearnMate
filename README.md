# LearnMate

> **Multimodal, grounded AI learning platform for personalized tutoring, adaptive assessment, and learner progress.**

LearnMate turns course material into an interactive learning experience. Students can add **PDFs, PowerPoint decks, MP4 videos, and YouTube lectures**, then ask questions in an AI Tutor that retrieves course-specific context and returns **source-aware citations**. The platform also generates assessments, tracks topic mastery, recommends what to study next, builds study plans, and provides an evaluation suite for grounding, citation correctness, course isolation, assessment quality, and learner personalization.

## Why LearnMate?

Traditional study tools often separate notes, videos, question banks, and progress tracking. LearnMate connects those pieces into one loop:

**Upload → Retrieve → Ask → Verify → Test → Improve**

The key design principle is that the tutor should answer from the learner's selected course material rather than freely inventing an answer.

---

## Highlights

- 📄 **PDF ingestion** with page-aware extraction and citations
- 📊 **PPTX ingestion** with slide-level text and embedded visual extraction
- 🎥 **MP4 ingestion** with speech-to-text transcription and timestamped chunks
- ▶️ **YouTube ingestion** using public transcript/caption data and timestamped citations
- 🔎 **Course-isolated semantic retrieval** using Qdrant
- 🤖 **Grounded AI Tutor** with pre- and post-generation grounding checks
- 📚 **Adaptive assessments** with grading and question verification/deduplication
- 🧠 **Learner model** for mastery, weak-topic detection, recommendations, and study plans
- 📈 **Grounding evaluation** covering RAG quality, citation correctness, unsupported-question rejection, and cross-course isolation
- 🔐 **JWT authentication** and protected course/learning APIs
- ⚡ **Provider-flexible LLM layer** supporting OpenAI, Groq, and Ollama-compatible endpoints
- 🧩 **Local FastEmbed embeddings** by default, with optional OpenAI embeddings
- 🐳 **Docker Compose** setup for PostgreSQL, Qdrant, and the backend

---

## Product Flow

```text
                    ┌──────────────────┐
                    │  Course Material │
                    │ PDF / PPTX / MP4 │
                    │    / YouTube     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Multimodal       │
                    │ Ingestion        │
                    │ + Chunking       │
                    └────────┬─────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
          PostgreSQL metadata     Qdrant vectors
                  │                     │
                  └──────────┬──────────┘
                             ▼
                    ┌──────────────────┐
                    │ Course-filtered  │
                    │ Semantic Search   │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ Grounded AI      │
                    │ Tutor + Citations│
                    └────────┬─────────┘
                             │
             ┌───────────────┼────────────────┐
             ▼               ▼                ▼
        Assessments     Mastery Model    Study Plan /
                                           Recommendations
```

---

## How the Grounded Tutor Works

When a learner asks a course question:

1. The backend validates the selected course.
2. The question is embedded using the configured embedding provider.
3. Qdrant performs semantic retrieval with a **strict `course_id` filter**.
4. A grounding threshold is applied before generation.
5. A modality-aware prompt is constructed from the retrieved chunks.
6. The configured LLM generates the answer.
7. LearnMate builds citations from the retrieved source metadata.
8. A post-generation grounding validator checks the response.
9. The API returns the answer, grounding status, and citations.

Citations preserve the relevant location:

- PDF → page number
- PPTX → slide number
- MP4 → timestamp range
- YouTube → timestamp range

Unsupported questions can be rejected instead of being answered from unrelated knowledge.

---

## Multimodal Ingestion

### PDF

PDFs are processed with PyMuPDF. The pipeline extracts page-aware text, detects headings, chunks content, hashes chunks for deterministic identity, generates embeddings, stores metadata in PostgreSQL, and indexes vectors in Qdrant.

### PowerPoint

PPTX files are processed slide-by-slide using `python-pptx`. LearnMate extracts:

- slide text
- tables
- embedded images/diagrams
- slide-level metadata

When enabled, extracted visuals can be passed to the configured vision model for additional understanding.

### MP4 Video

Video ingestion validates the media, extracts/transcribes speech, normalizes timestamped transcript segments, and creates contiguous time-window chunks.

For files larger than the configured direct transcription limit, LearnMate can use FFmpeg to extract audio and process it in chunks with overlap.

### YouTube

YouTube URLs are validated and canonicalized. LearnMate retrieves public video metadata/transcript information without storing the audiovisual file, then converts transcript segments into timestamped searchable chunks.

---

## Adaptive Learning

LearnMate goes beyond a chatbot.

### Assessments

The assessment subsystem supports generated assessments, submission, grading, question verification, and deduplication. The evaluation layer can also measure question validity and duplicate rates.

### Learner Model

The learner model tracks topic-level performance and supports:

- mastery estimation
- weak-topic detection
- recommendations
- study-plan generation

The implementation includes thresholds for weak and strong mastery and evaluator simulations for high-performing, mixed, and struggling learners.

---

## Evaluation & Safety

LearnMate contains a dedicated evaluation subsystem rather than relying only on subjective demo results.

It evaluates:

### RAG quality

- Answer relevancy
- Faithfulness
- Context precision
- Context recall

### Grounding behavior

- Supported questions should produce grounded answers.
- Unsupported/off-material questions should be rejected cleanly.
- Citations should be empty for rejected off-material questions.

### Citation correctness

Citations are checked for:

- source existence
- course ownership
- modality
- page/slide/timestamp location
- excerpt authenticity

### Course isolation

Retrieval is filtered by `course_id`, and the evaluation suite includes cross-course isolation tests to detect information leakage between courses.

### Assessment quality

The evaluation suite checks question validity, numerical consistency where applicable, grounded short answers, and duplicate-question rates.

### Learner personalization

The evaluator can simulate different learner profiles and verify that mastery and recommendations respond to different performance patterns.

> **Important:** The repository contains an evaluation framework and benchmark data. Any numerical results shown in a hackathon submission should be generated from an actual evaluation run rather than copied as static claims.

---

## Architecture

```text
Frontend
React + TypeScript + Vite
        │
        │ HTTP / JSON / multipart uploads
        ▼
FastAPI Backend
        │
        ├── Authentication / JWT
        ├── Course & source management
        ├── Multimodal ingestion
        ├── Grounded RAG tutor
        ├── Assessments
        ├── Learner model
        └── Evaluation engine
        │
        ├───────────────┐
        ▼               ▼
 PostgreSQL          Qdrant
 metadata            vector search
        │
        └───────────────┐
                        ▼
              LLM / Vision / STT
              OpenAI / Groq /
              Ollama-compatible
```

### Main backend modules

```text
backend/backend/app/
├── api/routes/
│   ├── auth.py
│   ├── courses.py
│   ├── uploads.py
│   ├── tutor.py
│   ├── assessments.py
│   ├── learner.py
│   ├── evaluation.py
│   └── health.py
│
├── models/
│   ├── course.py
│   ├── source.py
│   ├── document_chunk.py
│   ├── assessment.py
│   ├── learner_mastery.py
│   └── evaluation.py
│
└── services/
    ├── ingestion/
    ├── transcription/
    ├── youtube/
    ├── embeddings/
    ├── vector_store/
    ├── rag/
    ├── llm/
    ├── assessment/
    ├── learner_model/
    └── evaluation/
```

---

## Tech Stack

### Frontend

- React 18
- TypeScript
- Vite
- React Router
- Tailwind CSS
- React Markdown
- KaTeX / Markdown math
- Lucide React

### Backend

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic / Pydantic Settings
- SQLAlchemy
- PostgreSQL / SQLite fallback for local execution
- JWT authentication
- Argon2 password hashing

### AI / Retrieval

- OpenAI-compatible LLM interface
- OpenAI
- Groq
- Ollama-compatible endpoints
- FastEmbed
- `BAAI/bge-small-en-v1.5`
- Qdrant
- Configurable vision model
- Groq Whisper-compatible speech-to-text

### Multimodal processing

- PyMuPDF
- python-pptx
- FFmpeg / imageio-ffmpeg
- YouTube transcript/metadata retrieval

---

## Repository Structure

```text
LearnMate-main/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── .env.example
│
├── backend/
│   └── backend/
│       ├── app/
│       ├── tests/
│       ├── uploads/
│       ├── requirements.txt
│       ├── Dockerfile
│       ├── docker-compose.yml
│       └── .env.example
│
└── deployment_guide.md
```

---

# Getting Started

## Prerequisites

Install:

- Node.js 18+ recommended
- npm
- Python 3.12 recommended
- Git
- PostgreSQL, or use the included Docker Compose setup
- Qdrant, or use the included Docker Compose setup
- An LLM API key if using OpenAI/Groq
- FFmpeg if processing large video files

For the simplest full local setup, Docker Desktop is recommended.

---

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd LearnMate-main
```

---

## 2. Start PostgreSQL, Qdrant, and the backend with Docker

The repository includes a Compose configuration in:

```text
backend/backend/docker-compose.yml
```

Run:

```bash
cd backend/backend
docker compose up --build
```

The Compose setup starts:

- PostgreSQL on `localhost:5432`
- Qdrant on `localhost:6333`
- LearnMate API on `localhost:8000`

The backend container uses FastEmbed embeddings by default.

---

## 3. Configure the backend manually

If you prefer running FastAPI outside Docker:

```bash
cd backend/backend

python -m venv .venv
```

Activate the environment.

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

On Windows, copy `.env.example` to `.env` manually if `cp` is unavailable.

At minimum, configure:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/learnsphere

JWT_SECRET_KEY=replace_with_a_secure_secret_at_least_32_characters

QDRANT_URL=http://localhost:6333

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your_api_key

FRONTEND_URL=http://localhost:5173
```

The default embedding configuration uses FastEmbed and does not require an embedding API key:

```env
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

API documentation will be available at:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/health
```

---

## 4. Start the frontend

Open a second terminal:

```bash
cd frontend
npm install
```

Create the frontend environment file:

```bash
cp .env.example .env
```

The default value is:

```env
VITE_API_URL=http://localhost:8000
```

Start Vite:

```bash
npm run dev
```

Then open:

```text
http://localhost:5173
```

---

# Environment Variables

## Frontend

| Variable | Required | Example |
|---|---|---|
| `VITE_API_URL` | Yes | `http://localhost:8000` |

## Backend

| Variable | Required | Default / Example |
|---|---|---|
| `ENVIRONMENT` | No | `development` |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Yes in production | 32+ character secret |
| `JWT_ALGORITHM` | No | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` |
| `QDRANT_URL` | No | `http://localhost:6333` |
| `QDRANT_API_KEY` | No | Cloud Qdrant key |
| `QDRANT_COLLECTION` | No | `learnsphere_chunks` |
| `QDRANT_STORAGE_PATH` | No | `./qdrant_storage` |
| `LLM_PROVIDER` | No | `openai`, `groq`, or `ollama` |
| `LLM_MODEL` | No | `gpt-4o-mini` |
| `LLM_API_KEY` | Required for OpenAI/Groq | provider key |
| `LLM_BASE_URL` | No | custom OpenAI-compatible endpoint |
| `EMBEDDING_PROVIDER` | No | `fastembed` |
| `EMBEDDING_MODEL` | No | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_API_KEY` | Only for OpenAI embeddings | provider key |
| `FRONTEND_URL` | No | `http://localhost:5173` |
| `CORS_ORIGINS` | No | comma-separated origins |
| `UPLOAD_DIR` | No | `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | No | `50` |
| `RAG_TOP_K` | No | `5` |
| `RAG_SCORE_THRESHOLD` | No | `0.55` |
| `VISION_PROVIDER` | No | `groq` |
| `VISION_MODEL` | No | configured vision model |
| `VISION_API_KEY` | No | vision provider key |
| `VISION_ENABLED` | No | `true` |
| `TRANSCRIPTION_PROVIDER` | No | `groq` |
| `TRANSCRIPTION_MODEL` | No | `whisper-large-v3-turbo` |
| `TRANSCRIPTION_API_KEY` | No | transcription key |
| `TRANSCRIPTION_ENABLED` | No | `true` |

See `backend/backend/.env.example` for the complete configuration surface.

**Never commit real API keys, database passwords, JWT secrets, or other credentials.**

---

# API Overview

The backend exposes FastAPI routes under `/api`:

### Authentication

```text
POST   /api/auth/signup
POST   /api/auth/login
GET    /api/auth/me
PATCH  /api/auth/me
```

### Courses and sources

```text
GET    /api/courses
POST   /api/courses
GET    /api/courses/{course_id}
PATCH  /api/courses/{course_id}
PUT    /api/courses/{course_id}
DELETE /api/courses/{course_id}

POST   /api/courses/{course_id}/upload
POST   /api/courses/{course_id}/youtube
GET    /api/courses/{course_id}/uploads/{source_id}
```

### Tutor

```text
POST /api/tutor/chat
```

### Assessments

```text
POST /api/assessments/generate
GET  /api/assessments/{assessment_id}
POST /api/assessments/{assessment_id}/submit
```

### Learner model

```text
/api/learner/{student_id}/courses/{course_id}/...
```

The learner API provides mastery, summary, recommendations, weak-topic, and study-plan functionality.

### Evaluation

```text
POST /api/evaluation/run
GET  /api/evaluation/{evaluation_id}
GET  /api/evaluation/{evaluation_id}/results
```

### Health

```text
GET /health
```

Interactive API documentation is available through FastAPI at `/docs`.

---

# Testing

The backend contains unit, integration, acceptance, ingestion, tutor, assessment, learner-model, and evaluation tests.

From `backend/backend`:

```bash
pytest
```

Useful targeted tests include:

```bash
pytest tests/test_health.py
pytest tests/test_auth.py
pytest tests/test_courses.py
pytest tests/test_upload.py
pytest tests/test_pptx_ingestion.py
pytest tests/test_video_ingestion.py
pytest tests/test_youtube_source.py
pytest tests/test_tutor.py
pytest tests/test_assessments.py
pytest tests/test_learner_model.py
pytest tests/test_evaluation.py
```

The repository also includes live verification/demo-oriented scripts for checking the running backend and evaluation workflow.

---

# Running the Grounding Evaluation

The evaluation API can run in **quick** or **full** mode.

Quick mode is intentionally bounded to protect LLM quota during live/demo use. The default configuration limits live evaluation to three representative cases.

The evaluation engine can assess:

- supported questions
- unsupported questions
- course-isolation cases
- retrieval quality
- citation validity
- assessment quality
- learner-model simulations

Use the frontend's **Grounding Evaluation** workflow or call the evaluation API directly through `/docs`.

---

# Deployment

The repository includes `deployment_guide.md` with deployment instructions for:

- backend deployment on Render or Railway
- PostgreSQL configuration
- Qdrant Cloud
- persistent upload storage
- frontend deployment on Vercel
- production CORS configuration

A typical production architecture is:

```text
Vercel
  │
  │ HTTPS
  ▼
LearnMate FastAPI
  ├── Managed PostgreSQL
  ├── Qdrant Cloud
  ├── LLM Provider
  ├── Vision Provider
  └── Speech-to-Text Provider
```

For production, use a strong randomly generated `JWT_SECRET_KEY`, persistent storage for uploaded files, and restrictive CORS origins.

---

# Demo Flow

For a hackathon demo, the recommended story is:

1. **Create/open a course**
2. **Upload a PDF/PPTX or add a YouTube source**
3. Wait for processing to complete
4. Open **AI Tutor**
5. Ask a course-specific question
6. Show the answer and its page/slide/timestamp citation
7. Ask an off-material question and show grounded rejection
8. Generate an assessment
9. Submit answers and show grading/mastery
10. Open **My Learning** to show recommendations/study plan
11. Run **Grounding Evaluation** and show the evaluation results

The central message:

> **LearnMate doesn't just answer questions — it connects course material, grounded tutoring, assessment, and personalized learning into one feedback loop.**

---

# Hackathon Submission Checklist

Before submitting:

- [ ] Public GitHub repository is accessible
- [ ] README explains setup and architecture
- [ ] `.env.example` files are present
- [ ] No real API keys or secrets are committed
- [ ] Backend starts successfully
- [ ] Frontend starts successfully
- [ ] Demo course/materials are ready
- [ ] AI Tutor can answer with citations
- [ ] Assessment flow works
- [ ] My Learning flow works
- [ ] Grounding evaluation can be demonstrated
- [ ] YouTube demo is 3–10 minutes
- [ ] YouTube video is public or unlisted, not private
- [ ] English audio or English subtitles are included
- [ ] All team members are added to the Devpost project

---

# Project Status

LearnMate is an active hackathon project. Some components depend on external services and credentials, including the configured LLM, vision, transcription, PostgreSQL, and Qdrant deployments.

The repository is designed so that core retrieval embeddings can run locally with FastEmbed, while generation and multimodal services can be configured independently.

---

---

## Built for learning, not just answering

**LearnMate — Upload → Ask → Verify → Test → Improve.**
