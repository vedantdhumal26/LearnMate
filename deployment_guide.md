# LearnMate — Production Deployment Guide

**Target Architecture:**
- **Frontend:** Vercel (Edge CDN Static Hosting)
- **Backend:** Render or Railway (Docker Container Web Service)
- **Relational Database:** Managed PostgreSQL (Supabase, Neon, or Render Postgres)
- **Vector Database:** Qdrant Cloud (Managed Vector Cluster)
- **Inference Providers:** Groq Cloud / OpenAI (LLM, Vision, Whisper STT)

---

## 1. Architecture Overview

LearnMate utilizes a high-performance split-cloud deployment model:

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
│       (LearnMate Frontend)           │           │        (Render or Railway)           │
│                                      │           │                                      │
│  - React 18 + Vite SPA               │           │  - FastAPI + Uvicorn                 │
│  - vercel.json SPA rewrites          │           │  - Docker container runtime          │
│  - VITE_API_URL configured           │           │  - Port bound to $PORT               │
│  - Zero cold starts                  │           │  - Persistent Disk: /app/uploads     │
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

---

## 2. Pre-Requisites & Cloud Accounts

Ensure you have created accounts on the following platforms:
1. **GitHub**: Repository hosting (`https://github.com/vedantdhumal26/LearnMate`)
2. **Vercel**: Frontend deployment (`https://vercel.com`)
3. **Render** (`https://render.com`) or **Railway** (`https://railway.app`): Backend Docker hosting
4. **Supabase** (`https://supabase.com`) or **Neon** (`https://neon.tech`): Managed PostgreSQL
5. **Qdrant Cloud** (`https://cloud.qdrant.io`): Managed vector database
6. **Groq Console** (`https://console.groq.com`) or **OpenAI Platform** (`https://platform.openai.com`): AI API keys

---

## 3. Step 1: Provision Cloud Data Services

### 3.1 Managed PostgreSQL Database (Neon or Supabase)
1. Log in to **Neon** (or Supabase) and create a new project named `learnmate-prod`.
2. Locate the database connection string under Project Settings / Connection Details.
3. Select the pooled connection string (with `sslmode=require`).
4. Example format:
   ```text
   postgresql+psycopg2://<user>:<password>@<host>:5432/<dbname>?sslmode=require
   ```
   *(Note: LearnMate automatically translates `postgres://` or `postgresql://` URIs to `postgresql+psycopg2://` at runtime).*

### 3.2 Qdrant Cloud Vector Database
1. Log in to **Qdrant Cloud** and create a free 1GB cluster.
2. In the cluster overview, copy the **Cluster URL** (e.g., `https://xyz-your-cluster.eu-central.aws.cloud.qdrant.io:6333`).
3. Click **Data Access Control** -> **API Keys** -> **Create API Key**.
4. Copy the API Key value.
5. LearnMate will automatically create the `learnsphere_chunks` collection with 384-dimensional cosine distance and keyword payload indexes on first run.

---

## 4. Step 2: Backend Deployment (Render or Railway)

### Option A: Deploying on Render (Recommended)

1. **Create Web Service**:
   - Go to the **Render Dashboard** -> click **New +** -> **Web Service**.
   - Connect your GitHub repository (`vedantdhumal26/LearnMate` or `vedantdhumal26/IIT-HACKATHON`).
2. **Configure Service Details**:
   - **Name**: `learnmate-api`
   - **Region**: Choose the region closest to your PostgreSQL database (e.g., Oregon or Frankfurt).
   - **Root Directory**: `backend` (if using LearnMate mono-repo) or `.` (if connecting IIT-HACKATHON).
   - **Runtime**: **Docker**.
   - **Dockerfile Path**: `Dockerfile` (or `backend/backend/Dockerfile` if building from top root).
3. **Attach Persistent Storage (Crucial for uploads)**:
   - In the service configuration, navigate to **Disks** -> click **Add Disk**.
   - **Name**: `learnmate-uploads`
   - **Mount Path**: `/app/uploads`
   - **Size**: `5 GB` (or larger depending on expected uploads).
4. **Environment Variables**:
   Add the following environment variables in the Render dashboard:
   - `ENVIRONMENT` = `production`
   - `DATABASE_URL` = `<your-postgresql-connection-string>`
   - `JWT_SECRET_KEY` = `<secure-32-char-random-string>` (Generate with `openssl rand -hex 32`)
   - `JWT_ALGORITHM` = `HS256`
   - `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` = `60`
   - `FRONTEND_URL` = `https://<your-vercel-app-name>.vercel.app` (Can temporarily set to `*` or update after Step 3)
   - `CORS_ORIGINS` = `https://<your-vercel-app-name>.vercel.app`
   - `QDRANT_URL` = `<your-qdrant-cluster-url>`
   - `QDRANT_API_KEY` = `<your-qdrant-api-key>`
   - `QDRANT_COLLECTION` = `learnsphere_chunks`
   - `LLM_PROVIDER` = `groq` (or `openai`)
   - `LLM_MODEL` = `llama-3.3-70b-versatile` (or `gpt-4o-mini`)
   - `LLM_API_KEY` = `<your-groq-or-openai-api-key>`
   - `VISION_PROVIDER` = `groq`
   - `VISION_MODEL` = `qwen/qwen3.6-27b`
   - `VISION_API_KEY` = `<your-groq-api-key>`
   - `TRANSCRIPTION_PROVIDER` = `groq`
   - `TRANSCRIPTION_MODEL` = `whisper-large-v3-turbo`
   - `TRANSCRIPTION_API_KEY` = `<your-groq-api-key>`
   - `EMBEDDING_PROVIDER` = `fastembed`
   - `EMBEDDING_MODEL` = `BAAI/bge-small-en-v1.5`
   - `UPLOAD_DIR` = `/app/uploads`
   - `MAX_UPLOAD_SIZE_MB` = `50`
5. **Deploy**:
   - Click **Create Web Service**.
   - Render will build the Docker container and start Uvicorn, dynamically binding to `$PORT`.
   - Once deployed, note your service URL: `https://learnmate-api.onrender.com`.

---

### Option B: Deploying on Railway

1. In the **Railway Dashboard**, click **New Project** -> **Deploy from GitHub repo**.
2. Select repository and set **Root Directory** to `backend` (with Dockerfile).
3. In **Settings** -> **Volumes**, click **Add Volume**:
   - Mount path: `/app/uploads`.
4. In **Variables**, add the identical environment variables as listed above in the Render section.
5. Railway automatically generates an HTTPS domain and supplies the `$PORT` environment variable.

---

## 5. Step 3: Frontend Deployment (Vercel)

The LearnMate frontend is a React 18 + Vite SPA configured for Vercel Edge CDN distribution.

1. **Import Repository**:
   - Go to [vercel.com](https://vercel.com) and log in.
   - Click **Add New...** -> **Project**.
   - Import `vedantdhumal26/LearnMate`.
2. **Project Settings**:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend` *(Click Edit and choose `frontend`)*
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`
3. **Environment Variables**:
   Under **Environment Variables**, configure:
   - `VITE_API_URL` = `https://<your-backend-service-url>` (e.g. `https://learnmate-api.onrender.com`).
   *(Ensure there is NO trailing slash).*
4. **Deploy**:
   - Click **Deploy**.
   - Vercel will install dependencies, execute `npm run build`, and publish the assets to its global Edge network.
   - The included `frontend/vercel.json` ensures all SPA routes (`/dashboard`, `/courses/:id`, `/courses/:id/tutor`, etc.) route cleanly to `/index.html`.

---

## 6. Step 4: Final Network & CORS Alignment

After Vercel assigns your production URL (e.g., `https://learnmate-ai.vercel.app`):
1. Open your backend hosting dashboard (Render or Railway).
2. Update the environment variables:
   - `FRONTEND_URL` = `https://learnmate-ai.vercel.app`
   - `CORS_ORIGINS` = `https://learnmate-ai.vercel.app`
3. Trigger a manual redeploy of the backend service (takes ~30 seconds) to ensure CORS filters strictly allow only your production Vercel domain.

---

## 7. Required Environment Variables Reference

### Frontend Environment Variables (Vercel)

| Variable Name | Required | Example / Description |
|---|:---:|---|
| `VITE_API_URL` | **Yes** | `https://learnmate-api.onrender.com` (Backend API root URL, no trailing slash). Public value. |

### Backend Environment Variables (Render / Railway)

| Variable Name | Required | Default | Description |
|---|:---:|:---:|---|
| `ENVIRONMENT` | **Yes** | `production` | Set to `production` in live environment to enforce strict CORS and secret checks. |
| `DATABASE_URL` | **Yes** | — | Managed PostgreSQL URI (`postgresql+psycopg2://...`). |
| `JWT_SECRET_KEY` | **Yes** | — | Cryptographically random string (min 32 chars) for signing access tokens. |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Token validity duration in minutes. |
| `FRONTEND_URL` | **Yes** | — | Allowed production frontend origin for CORS. |
| `CORS_ORIGINS` | No | — | Optional comma-separated list of additional origins (e.g., custom domains or preview URLs). |
| `QDRANT_URL` | **Yes** | — | Managed Qdrant Cloud cluster endpoint (`https://...:6333`). |
| `QDRANT_API_KEY` | **Yes** | — | Qdrant Cloud cluster API key. |
| `QDRANT_COLLECTION` | No | `learnsphere_chunks` | Collection name for vector embeddings. |
| `LLM_PROVIDER` | No | `groq` | Chosen LLM provider (`groq` or `openai`). |
| `LLM_MODEL` | No | `llama-3.3-70b-versatile` | Model identifier. |
| `LLM_API_KEY` | **Yes** | — | Provider API key. |
| `VISION_PROVIDER` | No | `groq` | Vision model provider (`groq` or `openai`). |
| `VISION_MODEL` | No | `qwen/qwen3.6-27b` | Vision model for slide/figure understanding. |
| `VISION_API_KEY` | No | — | Vision API key (defaults to `LLM_API_KEY`). |
| `TRANSCRIPTION_PROVIDER` | No | `groq` | Speech-to-text provider (`groq`). |
| `TRANSCRIPTION_MODEL` | No | `whisper-large-v3-turbo`| Whisper model identifier. |
| `TRANSCRIPTION_API_KEY` | No | — | Transcription API key (defaults to `LLM_API_KEY`). |
| `EMBEDDING_PROVIDER` | No | `fastembed` | Embedding provider (`fastembed` requires 0 API keys). |
| `EMBEDDING_MODEL` | No | `BAAI/bge-small-en-v1.5`| Model name. |
| `UPLOAD_DIR` | No | `/app/uploads` | Path to persistent disk volume mount. |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Maximum file upload limit in megabytes. |

---

## 8. Health-Check & Connectivity Verification

### Step 1: Backend Health Check
Run in terminal or browser:
```bash
curl -i https://<your-backend-url>/health
```
**Expected Response:**
```json
HTTP/2 200
content-type: application/json

{"status":"ok"}
```

### Step 2: CORS Verification
Simulate an allowed cross-origin request from your Vercel frontend:
```bash
curl -i -X OPTIONS https://<your-backend-url>/api/courses \
  -H "Origin: https://<your-frontend-url>.vercel.app" \
  -H "Access-Control-Request-Method: GET"
```
**Expected Response:**
```text
HTTP/2 200 OK
access-control-allow-origin: https://<your-frontend-url>.vercel.app
access-control-allow-credentials: true
```

---

## 9. Post-Deployment Smoke-Test Checklist

Perform these checks in order on the live production frontend:

- [ ] **1. Landing Page**: Navigate to `https://<your-frontend-url>.vercel.app/` — renders clean branding, navigation links, and theme toggle.
- [ ] **2. SPA Route Reload**: Directly refresh the browser on `/login` and `/signup` — confirms `vercel.json` SPA rewrite prevents 404 errors.
- [ ] **3. User Registration**: Complete registration on `/signup` with a new test account — user record is securely created with Argon2id hash in PostgreSQL.
- [ ] **4. User Authentication**: Log in on `/login` — JWT token is saved to localStorage and redirects to `/dashboard`.
- [ ] **5. Course Creation**: Click **New Course**, create "Computer Science 101" — course is saved with the user's `owner_id`.
- [ ] **6. Document Ingestion**: Upload a sample PDF (or PPTX/MP4) — backend receives file, stores it on `/app/uploads`, chunks text, generates embeddings via FastEmbed, and indexes vectors into Qdrant Cloud.
- [ ] **7. Grounded AI Tutor**: Open AI Tutor for the course and ask a question directly answered by the document — verify the answer contains valid numbered citations referencing the uploaded file.
- [ ] **8. Small Talk & Greetings**: Send "hello" to the tutor — tutor replies with a friendly conversational greeting without hallucinating document sources.
- [ ] **9. Out-of-Scope Rejection**: Ask a completely unrelated question — tutor safely declines grounded answer without hallucinating.
- [ ] **10. Assessment Generation**: Generate a 2-question quiz — questions render with choices.
- [ ] **11. Quiz Submission**: Submit answers — assessment results and score percentages calculate properly.
- [ ] **12. Learner Mastery Model**: Navigate to `/learning` — mastery bar and topic recommendations render.
- [ ] **13. Evaluation Page**: Visit `/evaluation` — metrics render "Not measured" where appropriate (never 0% for missing data).
- [ ] **14. User Isolation**: Open an incognito browser window, register a second user, and verify they cannot see or access the first user's courses, uploads, or assessments.
- [ ] **15. Logout & Protection**: Click Logout; try navigating directly to `/dashboard` — verify immediate redirect to `/login`.

---

## 10. Rollback Instructions

### 10.1 Frontend Rollback (Vercel)
Vercel keeps immutable deployment builds for every commit:
1. Go to **Vercel Dashboard** -> select the project -> click **Deployments**.
2. Find the last known working deployment.
3. Click the three dots `...` -> **Promote to Production**.
4. The rollback takes effect globally in under **5 seconds** without rebuilding.

### 10.2 Backend Rollback (Render / Railway)
1. In the **Render Dashboard**, go to your Web Service -> **Events** or **Deploys**.
2. Select the previous successful deployment and click **Rollback to this deploy**.
3. Alternatively, revert the Git commit:
   ```bash
   git revert HEAD
   git push origin main
   ```
   Render/Railway will automatically rebuild and redeploy the previous state.

### 10.3 Database Rollback
- Neon and Supabase support Point-In-Time Recovery (PITR) and automatic daily backups.
- Before major releases, take a manual snapshot in the database dashboard.

---

## 11. Repository Hygiene & Remediation Plan

### Local Artifacts Tracked in Git
The audit identified that the following local files were previously tracked in version control:
- `frontend/learnsphere.db`
- `frontend/qdrant_storage/`
- `frontend/uploads/`
- `frontend/vite.config.ts.timestamp-*.mjs`

### Safe Remediation Commands (Run by Developer)
To untrack these files from Git without deleting your local copies:
```bash
# In the root LearnMate repository:
git rm --cached frontend/learnsphere.db
git rm -r --cached frontend/qdrant_storage
git rm -r --cached frontend/uploads
git rm frontend/vite.config.ts.timestamp-*.mjs 2>nul || true
git commit -m "chore: untrack local databases and storage from git"
git push origin main
```
*Note: A root `.gitignore` has now been created to permanently prevent these files from ever being staged or committed again.*

---

## 12. Estimated Cost Categories (Planning Estimates)

*The estimates below are categorized based on standard free/hobby tiers suitable for hackathon demonstrations, staging evaluation, and initial user rollout.*

| Service | Recommended Provider | Tier / Plan | Estimated Monthly Cost | Included Capabilities |
|---|---|---|:---:|---|
| **Frontend CDN** | Vercel | Hobby (Free) | **$0.00** | Unlimited builds, global Edge network, SSL certificates |
| **Backend API Host** | Render / Railway | Starter Container | **$5.00 – $7.00** | 1 vCPU, 1 GB RAM, persistent disk support, no cold starts |
| **Relational Database** | Neon or Supabase | Free Tier | **$0.00** | 500 MB PostgreSQL storage, automated backups, pooling |
| **Vector Database** | Qdrant Cloud | Free Tier | **$0.00** | 1 GB managed vector cluster (~250,000 document vectors) |
| **Inference (LLM/STT)** | Groq Cloud | Free / Pay-as-you-go | **$0.00 – $2.00** | Generous free rate limits for LLaMA 3.3, Whisper, and Qwen vision |
| **Estimated Total** | — | — | **~$5.00 – $7.00 / month** | Full-featured, production-ready environment |

---

## 13. Known Limitations & Production Best Practices

1. **Persistent Upload Disk**:
   Always attach a persistent volume (mount path: `/app/uploads`) on your container host. Do not rely on ephemeral container storage, as container restarts or redeploys will destroy uploaded lecture notes.
2. **Synchronous Ingestion Limits**:
   File uploads execute synchronous chunking, OCR/vision descriptions, and embedding generation. For documents exceeding 30 pages or 10-minute videos, ensure your container host HTTP timeout is set to at least 120 seconds.
3. **LLM Rate-Limit Retries**:
   The backend includes built-in concurrency gates and exponential backoff retry logic (`LLM_MAX_RETRIES=2`) to handle Groq rate limits smoothly during concurrent student requests.
4. **HTTPS Everywhere**:
   Both Vercel and container hosts automatically provision TLS/SSL certificates. Never downgrade `FRONTEND_URL` or `VITE_API_URL` to `http://` in production.
