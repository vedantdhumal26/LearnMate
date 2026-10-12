# LearnMate — Vercel Deployment Compatibility Audit

**Project:** LearnMate (Full-Stack AI Learning Companion)  
**Date:** October 12, 2026  
**Auditor:** Senior Full-Stack Deployment & Cloud Architecture Engineer  
**Scope:** Frontend (`frontend/`), Backend (`backend/`), Databases, Vector Search, AI Ingestion & Inference Workloads  
**Status:** Pre-Deployment Audit Complete (Report Only — No Code/Data Modifications Applied)

---

## 1. Executive Summary

LearnMate is a comprehensive AI-powered learning companion comprising:
- A **React 18 + TypeScript + Vite SPA** with client-side routing, KaTeX mathematical typesetting, dark mode, and an interactive study dashboard.
- A **FastAPI Python backend** with JWT authentication, multi-modal ingestion (PDF text/visual extraction, PowerPoint slide processing, MP4 video speech-to-text transcription via ffmpeg, YouTube transcript fetching), FastEmbed ONNX embedding generation, Qdrant vector similarity search, grounded AI tutoring with citation verification, adaptive assessment generation, learner mastery tracking, and evaluation benchmarking.

This audit evaluated whether the full-stack system can be deployed on Vercel without breaking existing functionality.

### Core Verdict Summary

| Component | Verdict | Summary |
|---|:---:|---|
| **Frontend (`frontend/`)** | **READY WITH CHANGES** | Vite SPA builds cleanly to `dist/`. Requires a `vercel.json` SPA rewrite rule to prevent 404s on deep links/refreshes, plus setting `VITE_API_URL` to point to the production backend. |
| **Backend (`backend/`) on Vercel Serverless Functions** | **NOT RECOMMENDED** | **Architecturally incompatible** with Vercel Serverless Functions. Exceeds Vercel's 250 MB uncompressed function size limit (~400 MB dependencies), violates Vercel's 4.5 MB request payload limit (LearnMate supports up to 50 MB PDFs/PPTX/MP4s), breaches execution timeouts (10s Hobby / 15s-60s Pro during heavy ingestion), lacks persistent disk for uploaded files, and suffers from cold-start model download penalties. |
| **Recommended Overall Architecture** | **SPLIT DEPLOYMENT** | **Frontend on Vercel** (Global Edge CDN, instantaneous builds, automated preview URLs) + **Backend on a dedicated Python Container Host** (Render, Railway, Fly.io, or AWS App Runner) using the existing `Dockerfile` with managed PostgreSQL and persistent Qdrant Cloud. |

---

## 2. Vercel Compatibility Verdict for the Frontend

### Verdict: **READY WITH CHANGES**

### Verification Details

1. **Build Tool & Output Directory**:
   - `package.json` defines standard scripts: `"build": "vite build"`, `"typecheck": "tsc --noEmit -p tsconfig.app.json"`, `"lint": "eslint ."`.
   - Production bundle output is `frontend/dist/` (verified: 1,893 modules transformed, 828 kB JS, 100 kB CSS, fonts, and assets generated in 9.1s without errors).
   - Vercel natively detects Vite and executes `npm run build` with output directory `dist`.

2. **Client-Side SPA Routing Requirement (Blocker if omitted)**:
   - LearnMate uses `react-router-dom` with `BrowserRouter` across deep paths (`/dashboard`, `/courses/:id`, `/courses/:id/tutor`, `/courses/:id/assessments`, `/courses/:id/learning`, `/evaluation`).
   - By default, Vercel attempts to resolve direct browser requests (e.g., reloading `https://learnmate.vercel.app/dashboard`) against static HTML files on disk, resulting in `404: NOT_FOUND`.
   - **Required Change**: Create `frontend/vercel.json` with an SPA rewrite mapping all routes to `/index.html`:
     ```json
     {
       "rewrites": [
         { "source": "/(.*)", "destination": "/" }
       ]
     }
     ```

3. **API Base URL Configuration**:
   - In `frontend/src/lib/api.ts`:
     ```ts
     const envApiUrl = import.meta.env.VITE_API_URL;
     const API_BASE = (envApiUrl !== undefined && envApiUrl !== null && envApiUrl !== '' ? envApiUrl : '').replace(/\/+$/, '');
     ```
   - In local development, `API_BASE` is empty (`""`) and Vite's dev server proxies `/api` and `/health` to `http://127.0.0.1:8000`.
   - In production on Vercel, `VITE_API_URL` must be configured in Vercel Project Settings to the production backend URL (e.g., `https://api.learnmate.example.com`).

4. **Client-Side Authentication & CORS**:
   - The frontend stores JWTs in browser `localStorage` (`learnsphere_auth_token`) and delivers them via the standard `Authorization: Bearer <token>` HTTP header.
   - It does not rely on cross-site third-party cookies, allowing clean cross-origin requests between Vercel (`https://learnmate.vercel.app`) and the backend API host, provided the backend allows the Vercel domain in CORS headers.

5. **Static Assets & Branding**:
   - Verified: [`public/LearnMate.png`](file:///d:/LearnMate/frontend/public/LearnMate.png), `public/favicon.svg`, and KaTeX webfonts are referenced via root-relative paths (`/LearnMate.png`, `/favicon.svg`, `/assets/...`) and copy cleanly into `dist/`.

6. **Environment Variable Exposure Audit**:
   - Verified: Only `VITE_API_URL` is referenced via `import.meta.env.VITE_*`.
   - Zero private API keys, JWT secrets, or backend credentials exist in the frontend source code or bundle.

---

## 3. Vercel Compatibility Verdict for the Backend

### Verdict: **NOT RECOMMENDED**

Attempting to host the existing FastAPI backend as a Vercel Serverless Function (`api/index.py`) introduces critical architectural failure points that will break existing production workflows.

### Detailed Technical Blockers

#### 1. Function Package Size Limit Violation (CRITICAL BLOCKER)
- **Vercel Platform Limit**: AWS Lambda / Vercel Serverless Functions enforce a **250 MB uncompressed** (and 50 MB compressed) bundle size limit.
- **LearnMate Dependency Size**: LearnMate's Python dependencies measured in `.venv` total **399.6 MB**:
  - `fastembed` + `onnxruntime` + `tokenizers`: ~180 MB
  - `pymupdf` (MuPDF compiled C++ binaries): ~55 MB
  - `imageio-ffmpeg` (bundled static ffmpeg binary): ~70 MB
  - `psycopg2-binary`, `qdrant-client`, `argon2-cffi`, `scipy`/`numpy`: ~95 MB
- **Impact**: Deployment will fail during Vercel's function packaging phase with `Error: The Serverless Function size (399.6 MB) exceeds the maximum allowed size of 250 MB`.

#### 2. Request Body Payload Limit Violation (CRITICAL BLOCKER)
- **Vercel Platform Limit**: Vercel Serverless Functions enforce a strict **4.5 MB request body limit** at the edge gateway (`FUNCTION_PAYLOAD_TOO_LARGE` / HTTP 413).
- **LearnMate Requirement**:
  - Textbook & lecture PDF uploads: typically 5 MB – 35 MB.
  - PowerPoint presentations (.pptx): typically 10 MB – 45 MB.
  - Video lecture uploads (.mp4): configured up to 50 MB (`MAX_UPLOAD_SIZE_MB = 50`).
- **Impact**: Any file larger than 4.5 MB will be rejected at Vercel's edge with an immediate `413 Payload Too Large`. The backend upload route will never even be called.

#### 3. Execution Timeout Violations (CRITICAL BLOCKER)
- **Vercel Platform Limit**: Vercel Hobby plan has a hard **10-second timeout**; Pro plan has a default 15-second timeout (max 300s).
- **LearnMate Workload Execution Time**:
  - `POST /api/courses/{course_id}/upload` executes synchronous ingestion: parsing pages/slides, generating visual descriptions via vision models, chunking text, computing SHA-256 hashes, generating FastEmbed ONNX embeddings, and indexing vectors in Qdrant. A 25-page PDF requires **15 – 45 seconds**.
  - Video ingestion extracts audio with ffmpeg, chunks audio, transcribes each segment via Whisper, and embeds text chunks. This requires **30 – 120 seconds**.
  - Evaluation benchmarking (`POST /api/evaluation/run`) executes extensive multi-case RAG groundings and learner simulations, requiring **30 – 60 seconds**.
- **Impact**: Operations will terminate abruptly with `504 Gateway Timeout` (`FUNCTION_INVOCATION_TIMEOUT`), leaving partial document chunks and corrupted database records.

#### 4. Stateless Ephemeral Filesystem (HIGH SEVERITY BLOCKER)
- **Vercel Platform Limit**: Serverless execution environments have an ephemeral, read-only filesystem (only `/tmp` is writable, up to 512 MB).
- **LearnMate Behavior**: The backend writes uploaded documents to `settings.UPLOAD_DIR = "./uploads"`.
- **Impact**:
  - Writing to `./uploads` fails with `EROFS: Read-only file system`.
  - Even if redirected to `/tmp`, serverless container recycling destroys files after each invocation. When an AI Tutor citation points to an uploaded document or a user attempts to inspect source material, the physical file is lost.

#### 5. Local SQLite & Local Qdrant Incompatibility (HIGH SEVERITY BLOCKER)
- In local development, the backend defaults to `sqlite:///./learnsphere.db` and `./qdrant_storage`.
- In a serverless architecture, each concurrent invocation runs in an isolated microVM. SQLite cannot handle concurrent writes across serverless instances and loses all state when containers terminate. Persistent cloud databases (PostgreSQL and remote Qdrant) are mandatory.

#### 6. Cold-Start Model Download Penalties (HIGH SEVERITY BLOCKER)
- `FastEmbed` downloads the `BAAI/bge-small-en-v1.5` ONNX model (~130 MB) to disk cache on first use.
- In serverless functions, cold starts would repeatedly download 130 MB over the network, introducing 20–30 second cold-start latencies and rapidly consuming bandwidth.

---

## 4. Required External Services

To transition LearnMate from local development to production, the following managed cloud services must be provisioned:

| Service | Local Configuration | Required Production Configuration | Compatible with Vercel Serverless? | Persistence / Infrastructure Requirements |
|---|---|---|:---:|---|
| **SQL Database** | SQLite (`sqlite:///./learnsphere.db`) or local PostgreSQL | Managed **PostgreSQL 15+** (e.g., Supabase, Neon, AWS RDS, or Render Postgres) | **No for SQLite**; Yes for Postgres with connection pooler | Persistent managed storage with connection pooling (PgBouncer) |
| **Vector Database** | Local embedded Qdrant (`./qdrant_storage`) | Managed **Qdrant Cloud** cluster (free 1GB cluster available) or hosted Qdrant container | **No for embedded**; Yes for Qdrant Cloud | Persistent cloud vector database with API key authentication |
| **LLM Provider** | OpenAI (`gpt-4o-mini`) or Groq (`llama-3.3-70b-versatile`) | Groq API or OpenAI API | Yes (HTTP REST) | Production API key, quota monitoring, rate-limit retries |
| **Vision Model** | Groq (`qwen/qwen3.6-27b`) or OpenAI | Groq API or OpenAI API | Yes (HTTP REST) | Production API key for diagram & slide visual interpretation |
| **Speech-to-Text** | Groq Whisper (`whisper-large-v3-turbo`) with ffmpeg | Groq Whisper API | Partial (API is fine, but local ffmpeg audio extraction is not) | ffmpeg system binary required for audio segment extraction |
| **File / Media Storage** | Local directory (`./uploads`) | **Persistent Volume** mounted at `/app/uploads` (on container host) OR **S3-compatible Object Storage** (AWS S3 / Cloudflare R2 / Supabase Storage) | **No** (Vercel has no persistent file storage) | Persistent disk volume or S3 bucket with signed download URLs |

---

## 5. Critical Blockers and Severity Levels

| ID | Issue | Severity | Affected Host | Impact on LearnMate |
|---|---|:---:|:---:|---|
| **BLK-01** | Python function bundle exceeds 250 MB limit (399.6 MB measured) | **BLOCKER** | Vercel Serverless | Build fails; backend cannot be deployed on Vercel Functions. |
| **BLK-02** | 4.5 MB request body limit blocks PDF/PPTX/video uploads | **BLOCKER** | Vercel Serverless | HTTP 413 error for any file upload > 4.5 MB. |
| **BLK-03** | Serverless function timeout (10s Hobby / 15s-60s Pro) during ingestion | **BLOCKER** | Vercel Serverless | Ingestion, video transcription, and evaluations abort with HTTP 504. |
| **BLK-04** | Ephemeral filesystem destroys uploaded files in `./uploads` | **BLOCKER** | Vercel Serverless | Uploaded files disappear after function execution ends. |
| **BLK-05** | Missing SPA rewrite rule in `frontend/vercel.json` | **HIGH** | Vercel Frontend | Direct page refresh on `/dashboard`, `/courses/:id`, etc. returns HTTP 404. |
| **BLK-06** | Local SQLite (`learnsphere.db`) cannot be used in serverless / multi-instance | **HIGH** | Production Backend | Concurrency corruption, data loss across serverless container lifecycles. |
| **BLK-07** | `learnsphere.db` is currently tracked in the git repository | **MEDIUM** | Git / Security | Local database file tracked in version control; should be untracked before release. |

---

## 6. Exact Files Requiring Changes

### For Frontend Deployment on Vercel:
1. `frontend/vercel.json` (New File):
   - Add SPA fallback rewrite rule to route all paths to `/index.html`.
2. `frontend/.env.production` (New File or set via Vercel Project Settings):
   - Set `VITE_API_URL` to the production backend URL.

### For Backend Production Deployment:
1. `backend/backend/app/core/config.py`:
   - Ensure `cors_origins` includes the production Vercel domain (e.g., `https://learnmate.vercel.app`).
2. `backend/backend/Dockerfile`:
   - Already fully configured (`python:3.12-slim`, installs `libpq-dev`, `build-essential`, `curl`, and runs Uvicorn on port 8000). Ready for deployment to any container platform.
3. `.gitignore` (Root and `backend/backend/.gitignore`):
   - Untrack `learnsphere.db` from version control (`git rm --cached learnsphere.db`).

---

## 7. Proposed Production Architecture

### Recommended Architecture: Split Deployment

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLIENT / WEB BROWSER                            │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
           ┌─────────────────────────┴────────────────────────┐
           │                                                  │
           ▼ (HTTPS Static Assets)                            ▼ (HTTPS REST API / Bearer Token)
┌──────────────────────────────────────┐           ┌──────────────────────────────────────┐
│           VERCEL EDGE CDN            │           │       PYTHON CONTAINER HOST          │
│       (LearnMate Frontend)           │           │   (Render / Railway / AWS App Runner)│
│                                      │           │                                      │
│  - React 18 + Vite SPA               │           │  - FastAPI + Uvicorn (Port 8000)     │
│  - Global Edge Caching               │           │  - Full Python 3.12 Runtime          │
│  - Single-Page App Rewrites          │           │  - PyMuPDF + python-pptx             │
│  - Automated PR Previews             │           │  - imageio-ffmpeg for Video Audio    │
│  - Fast Global DNS & SSL             │           │  - FastEmbed Model Cache             │
│  - VITE_API_URL configured           │           │  - Persistent Disk: /app/uploads     │
└──────────────────────────────────────┘           └──────────────────┬───────────────────┘
                                                                      │
                         ┌────────────────────────────────────────────┼────────────────────────┐
                         │                                            │                        │
                         ▼                                            ▼                        ▼
           ┌───────────────────────────┐                ┌───────────────────────────┐    ┌───────────────────────────┐
           │     MANAGED POSTGRES      │                │       QDRANT CLOUD        │    │       AI PROVIDERS        │
           │ (Supabase / Neon / Render)│                │  (Managed Vector Cluster) │    │      (Groq & OpenAI)      │
           │                           │                │                           │    │                           │
           │  - Users & Passwords      │                │  - Multimodal Embeddings  │    │  - Groq LLaMA 3.3 / Qwen  │
           │  - Courses & Sources      │                │  - Document Chunk Vectors │    │  - Groq Whisper Audio     │
           │  - Assessments & Results  │                │  - Cosine Distance Metric │    │  - OpenAI GPT-4o-mini     │
           │  - Learner Mastery Model  │                │  - Fast Cosine Retrieval  │    │  - FastEmbed ONNX local   │
           └───────────────────────────┘                └───────────────────────────┘    └───────────────────────────┘
```

### Why this is the Safest and Simplest Solution:
1. **Frontend leverages Vercel's greatest strengths**: Instant global deployment, zero cold starts, automatic SSL, edge caching, and effortless git push integrations.
2. **Backend avoids all Vercel serverless limitations**:
   - Zero bundle size restrictions (container image has no 250 MB ceiling).
   - Zero request size limits (handles 50 MB PDFs and MP4 video uploads effortlessly).
   - Zero execution duration limits (multi-minute ingestion and evaluation runs execute reliably).
   - Native system ffmpeg support for video audio extraction.
   - Persistent volume for uploaded file storage.
   - Local model caching for FastEmbed without network re-downloads on every request.

---

## 8. Environment Variables Specification

*Note: Per security guidelines, only variable names, descriptions, and required deployment scopes are documented below. No secret values are exposed.*

### Frontend Environment Variables (Vercel Project Settings)

| Variable Name | Required | Scope | Description |
|---|:---:|---|---|
| `VITE_API_URL` | **Yes** | Production & Preview | The public HTTPS URL of the deployed FastAPI backend (e.g., `https://api.learnmate.example.com`). Must not have a trailing slash. |

### Backend Environment Variables (Container Host Settings)

| Variable Name | Required | Scope | Description |
|---|:---:|---|---|
| `DATABASE_URL` | **Yes** | Production | PostgreSQL connection string (`postgresql+psycopg2://user:pass@host:5432/dbname`). |
| `JWT_SECRET_KEY` | **Yes** | Production | Cryptographically secure random 32+ character secret for signing user authentication tokens. |
| `JWT_ALGORITHM` | No | Production | Signing algorithm (defaults to `HS256`). |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | Production | Token lifetime in minutes (defaults to `60`). |
| `FRONTEND_URL` | **Yes** | Production | Primary origin allowed for CORS (e.g., `https://learnmate.vercel.app`). |
| `CORS_ORIGINS` | No | Production | Comma-separated list of additional allowed CORS origins (e.g., `https://learnmate.vercel.app,https://*.vercel.app`). |
| `QDRANT_URL` | **Yes** | Production | URL of the managed Qdrant Cloud cluster (e.g., `https://<cluster-id>.<region>.gcp.cloud.qdrant.io:6333`). |
| `QDRANT_API_KEY` | **Yes** | Production | API Key for Qdrant Cloud authentication. |
| `QDRANT_COLLECTION` | No | Production | Name of the collection in Qdrant (defaults to `learnsphere_chunks`). |
| `LLM_PROVIDER` | No | Production | LLM provider identifier (`groq` or `openai`; defaults to `openai`). |
| `LLM_MODEL` | No | Production | Model name (e.g., `llama-3.3-70b-versatile` or `gpt-4o-mini`). |
| `LLM_API_KEY` | **Yes** | Production | API key for the chosen LLM provider (Groq or OpenAI). |
| `VISION_PROVIDER` | No | Production | Vision provider identifier (`groq` or `openai`; defaults to `groq`). |
| `VISION_MODEL` | No | Production | Vision model for slide/diagram descriptions (e.g., `qwen/qwen3.6-27b`). |
| `VISION_API_KEY` | No | Production | Vision API key (falls back to `LLM_API_KEY` if omitted). |
| `TRANSCRIPTION_PROVIDER` | No | Production | Speech-to-text provider (`groq`; defaults to `groq`). |
| `TRANSCRIPTION_MODEL` | No | Production | Whisper model identifier (e.g., `whisper-large-v3-turbo`). |
| `TRANSCRIPTION_API_KEY`| No | Production | Transcription API key (falls back to `LLM_API_KEY` if omitted). |
| `EMBEDDING_PROVIDER` | No | Production | Embedding generator (`fastembed` or `openai`; defaults to `fastembed`). |
| `EMBEDDING_MODEL` | No | Production | Embedding model name (defaults to `BAAI/bge-small-en-v1.5`). |
| `UPLOAD_DIR` | No | Production | Path on disk for file uploads (defaults to `./uploads`). |
| `MAX_UPLOAD_SIZE_MB` | No | Production | Max upload size limit (defaults to `50`). |

---

## 9. Estimated Complexity and Cost Considerations

*All figures below are realistic planning estimates based on standard free/hobby tiers suitable for hackathon demonstrations and initial production rollout.*

### Infrastructure Options & Estimated Costs

| Component | Recommended Provider | Tier / Plan | Estimated Monthly Cost | Notes |
|---|---|---|:---:|---|
| **Frontend** | Vercel | Hobby Tier | **$0.00** | Generous bandwidth, SSL, and unlimited deployments included free. |
| **Backend API** | Render / Railway | Starter Container | **$5.00 – $7.00** | 1 vCPU, 1 GB RAM, persistent disk support. Zero cold starts when running as a web service. |
| **Database** | Supabase or Neon | Free Tier | **$0.00** | 500 MB storage included free on Supabase/Neon. |
| **Vector DB** | Qdrant Cloud | Free Tier | **$0.00** | 1 GB cluster (holds ~250,000 document vectors) included free forever. |
| **LLM & Inference** | Groq Cloud | Free / Pay-as-you-go | **$0.00 – $2.00** | Groq provides generous free rate limits for LLaMA 3.3, Whisper, and Qwen vision. |
| **Total Estimated Cost** | — | — | **~$5.00 – $7.00 / mo** | Cost-effective for hackathon demos and early production users. |

### Implementation Complexity: **Low (1–2 hours)**
- The frontend is already production-ready with Vite and requires only a 6-line `vercel.json` file.
- The backend already contains a production `Dockerfile` ready to deploy to Render or Railway with a single click.

---

## 10. Step-by-Step Deployment Plan

### Step 1: Managed Database & Vector Store Provisioning
1. **Provision PostgreSQL**:
   - Create a free project on Supabase or Neon.
   - Obtain the connection URI (e.g., `postgresql+psycopg2://user:pass@ep-xyz.us-east-1.aws.neon.tech/neondb?sslmode=require`).
2. **Provision Qdrant Cloud**:
   - Create a free 1GB cluster on Qdrant Cloud.
   - Copy the cluster URL and API key.

### Step 2: Deploy Backend to Container Host (e.g., Render / Railway)
1. In the container host dashboard, create a new **Web Service** connected to the repository.
2. Specify the build configuration:
   - **Root Directory**: `backend` (or project root with Dockerfile in `backend/backend`).
   - **Build Command / Type**: Docker (use existing `backend/backend/Dockerfile`).
3. Attach a **Persistent Disk** (size: 5 GB) mounted at `/app/uploads`.
4. Configure backend environment variables in the host dashboard:
   - `DATABASE_URL`, `JWT_SECRET_KEY`, `FRONTEND_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `LLM_API_KEY`, `LLM_PROVIDER`, `EMBEDDING_PROVIDER`.
5. Deploy and verify that `GET https://<your-backend-domain>/health` returns `{"status":"ok"}`.

### Step 3: Deploy Frontend to Vercel
1. Add `frontend/vercel.json` to the frontend directory:
   ```json
   {
     "rewrites": [
       { "source": "/(.*)", "destination": "/" }
     ]
   }
   ```
2. In the Vercel Dashboard, click **Add New Project** and import the repository.
3. Configure the project:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. In **Environment Variables**, add:
   - `VITE_API_URL` = `https://<your-backend-domain>`
5. Click **Deploy**.

### Step 4: Final Domain & CORS Alignment
1. Note the assigned Vercel URL (e.g., `https://learnmate.vercel.app`).
2. Update the backend environment variable `FRONTEND_URL` on the container host to match the Vercel production URL.
3. Redeploy the backend service to apply the updated CORS configuration.

---

## 11. Post-Deployment Smoke-Test Checklist

Verify each of the following flows on the live production URL:

- [ ] **Frontend Root**: `https://<frontend-domain>/` loads the landing page with LearnMate logo and branding.
- [ ] **SPA Direct Deep Navigation**: Directly loading `https://<frontend-domain>/login`, `/signup`, or `/dashboard` loads without a 404 error.
- [ ] **User Registration**: Register a new user on `/signup` — user record created in PostgreSQL with Argon2id hash.
- [ ] **Login & JWT Storage**: Authenticate on `/login` — JWT successfully stored and redirects to `/dashboard`.
- [ ] **Course Creation**: Create a course on `/courses/new` — course appears on the dashboard.
- [ ] **Document Upload**: Upload a sample PDF note (> 5 MB) — file saves to `/app/uploads`, text/visuals are extracted, and Qdrant chunks are created.
- [ ] **Post-Upload UI**: Upload zone transitions to "Ready"; note appears immediately without a blank screen or browser refresh.
- [ ] **AI Tutor Grounded Question**: Ask a course question — tutor responds with verified citations referencing the uploaded PDF.
- [ ] **AI Tutor Small Talk**: Send "hi" — tutor replies with a friendly conversational greeting.
- [ ] **AI Tutor Out-of-Scope**: Ask an unrelated question — tutor declines grounded answer safely without hallucination.
- [ ] **Assessment Generation**: Generate a 2-question assessment — questions render with choices.
- [ ] **Assessment Submission & Scoring**: Submit the assessment — results and score percentage display correctly.
- [ ] **Learning Dashboard**: View `/learning` — mastery progress bar and recommendations render.
- [ ] **Evaluation Page**: View `/evaluation` — metrics display "Not measured" where appropriate (never 0% for missing data).
- [ ] **Course Deletion**: Delete the course — cascades and cleans up database records, Qdrant vectors, and physical upload files.
- [ ] **Logout & Route Guard**: Click Logout; verify that accessing `/dashboard` immediately redirects to `/login`.

---

## 12. Final Recommendation

1. **Deploy Frontend to Vercel**:
   - Vercel is the optimal platform for the React/Vite SPA. Add `frontend/vercel.json` for SPA rewrites and supply `VITE_API_URL`.
2. **Deploy Backend to a Container Host (Render / Railway / Fly.io)**:
   - Do **NOT** attempt to deploy the FastAPI backend on Vercel Serverless Functions. The 250 MB function size limit, 4.5 MB upload limit, 10-second timeout, and ephemeral filesystem are incompatible with LearnMate's multi-modal AI ingestion architecture.
   - The existing `Dockerfile` will deploy cleanly to any modern container host with zero modifications to application logic.
3. **Provision Managed PostgreSQL and Qdrant Cloud**:
   - Both services offer robust free tiers suitable for immediate deployment and demo presentation.
4. **Action Required Before Implementation**:
   - **No code or file changes have been made during this audit.**
   - Awaiting user approval before creating `frontend/vercel.json` or initiating cloud provisioning steps.
