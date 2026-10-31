# HotelOS — Production Deployment & Infrastructure Guide
**Version:** 1.0.0-PROD  
**Target Environment:** Zero-Docker Cloud Native  
**Cloud Providers:** Vercel (Frontend), Render (Backend), Supabase (Database & Storage)  
**Primary Region:** AWS Mumbai (`ap-south-1`) for Indian Hospitality Latency Optimization

---

## 1. Production Topology & Architecture

HotelOS employs a **zero-Docker, cloud-native managed architecture** designed for high availability, zero maintenance overhead, low latency across India, and independent scaling of frontend and backend layers.

```mermaid
flowchart LR
    subgraph ClientLayer[Client Edge]
        Users[Hotel Front Desk & Mobile Staff]
    end

    subgraph VercelEdge[Vercel Global Edge Network]
        NextApp[Next.js App Router Frontend]
    end

    subgraph RenderPaaS[Render PaaS - Frankfurt / Oregon]
        FastAPI[FastAPI Python ASGI Web Service]
    end

    subgraph SupabaseCloud[Supabase Cloud - AWS Mumbai ap-south-1]
        PgBouncer[PgBouncer Connection Pooler :6543]
        Postgres[(PostgreSQL 15 Database)]
        Storage[Supabase Private Storage S3]
        AuthService[Supabase Auth Service]
    end

    Users -->|HTTPS / WSS| VercelEdge
    VercelEdge --> NextApp
    NextApp -->|REST API Calls| RenderPaaS
    FastAPI -->|Async SQLAlchemy Pool| PgBouncer
    PgBouncer --> Postgres
    FastAPI -->|Signed S3 URLs| Storage
    NextApp -->|JWT Verification| AuthService
```

---

## 2. Infrastructure Setup: Supabase (Database & Storage)

### 2.1 Project Creation & Region
1. Log in to [Supabase Dashboard](https://database.new).
2. Create a new organization and project:
   - **Project Name:** `hotelos-production`
   - **Region:** `AWS Mumbai (ap-south-1)` *(Critical: Minimizes network latency to Varanasi hotels to <25ms)*
   - **Database Password:** Generate a high-entropy 32-character password.

### 2.2 Connection String Retrieval
Navigate to **Project Settings -> Database**:
- **Direct Connection:** `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres` (Used for Alembic migrations).
- **Pooled Connection (Transaction Mode):** `postgresql://postgres.[REF]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require` (Used for FastAPI application runtime).

### 2.3 Storage Bucket Provisioning
Navigate to **Storage -> Buckets**:
1. Create private bucket: `hotelos-docs-private`
   - **Public bucket:** OFF
   - **Allowed MIME types:** `image/jpeg`, `image/png`, `application/pdf`
   - **Max file size:** 10 MB
   - Used for: Guest Aadhaar/Passport photo scans and verification documents.
2. Create public bucket: `hotelos-assets-public`
   - **Public bucket:** ON
   - Used for: Hotel logos, room gallery photos, and maintenance invoice copies.

---

## 3. Backend Deployment: Render (FastAPI Web Service)

### 3.1 Service Configuration
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New + -> Web Service** and connect your GitHub repository.
3. Configure service parameters:
   - **Name:** `hotelos-api`
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Region:** `Frankfurt` (or closest available PaaS region)
   - **Branch:** `main`
   - **Build Command:**
     ```bash
     pip install --upgrade pip && pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
     ```
   - **Health Check Path:** `/health`
   - **Auto-Deploy:** `Yes`

### 3.2 Pre-Deploy Database Migrations
In Render service settings, configure the **Pre-Deploy Command**:
```bash
alembic upgrade head
```
This guarantees all database schema migrations execute successfully before new code handles traffic.

---

## 4. Frontend Deployment: Vercel (Next.js App)

### 4.1 Project Import & Build Settings
1. Log in to [Vercel Dashboard](https://vercel.com) and import the repository.
2. Configure project settings:
   - **Framework Preset:** Next.js
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`
   - **Node.js Version:** `18.x` or `20.x`

### 4.2 Custom Domain Setup
In Vercel **Settings -> Domains**:
- Add production domain: `app.hotelos.in`
- Point DNS CNAME records to `cname.vercel-dns.com`.

---

## 5. Comprehensive Environment Variables Matrix

| Variable Name | Required By | Target Environment | Description & Sample Value |
|---|---|---|---|
| `DATABASE_URL` | Backend | Render | Async PostgreSQL connection string with asyncpg driver: `postgresql+asyncpg://postgres.[REF]:[PASS]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?ssl=require` |
| `SECRET_KEY` | Backend | Render | 64-character hex secret for local session signing: `openssl rand -hex 32` |
| `ALGORITHM` | Backend | Render | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | Render | `1440` (24 hours) |
| `SUPABASE_URL` | Backend | Render | `https://[PROJECT-REF].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend | Render | Supabase secret key with elevated storage permissions |
| `ALLOWED_ORIGINS` | Backend | Render | Comma-separated CORS origins: `https://app.hotelos.in,https://hotelos.vercel.app` |
| `WHATSAPP_API_TOKEN` | Backend | Render | Meta Cloud API Bearer Token |
| `WHATSAPP_PHONE_NUMBER_ID` | Backend | Render | Meta Phone Number ID (e.g. `1029384756`) |
| `RESEND_API_KEY` | Backend | Render | Resend API key: `re_123456789...` |
| `AI_PROVIDER` | Backend | Render | `gemini` or `openai` |
| `GEMINI_API_KEY` | Backend | Render | Google Gemini API Key |
| `OPENAI_API_KEY` | Backend | Render | OpenAI API Key (optional fallback) |
| `NEXT_PUBLIC_API_URL` | Frontend | Vercel | Base URL for FastAPI: `https://hotelos-api.onrender.com/api/v1` |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend | Vercel | Supabase URL: `https://[PROJECT-REF].supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend | Vercel | Supabase anonymous public client key |

---

## 6. Zero-Docker Production Verification Checklist

Following deployment, execute these verification steps:

- [ ] **Database Connection Pool:** Backend logs confirm successful connection to Supabase PgBouncer on port 6543.
- [ ] **Alembic Version Check:** Inspect `alembic_version` table in Supabase SQL editor to confirm current revision matches `8b509fc2873d`.
- [ ] **Health Check Endpoint:** `curl -f https://hotelos-api.onrender.com/health` returns `{"status": "healthy"}`.
- [ ] **CORS Verification:** Next.js frontend at `https://app.hotelos.in` successfully executes API requests without browser CORS errors.
- [ ] **Night Audit Automation:** APScheduler or Render cron job triggers daily at 23:59 Asia/Kolkata.
- [ ] **Aadhaar Masking:** Registering a guest masks the ID to `XXXXXXXX####` in both API response and Supabase table.
- [ ] **PDF Generation:** Calling `/api/v1/reports/daily/pdf` returns valid PDF binary without memory leaks.
- [ ] **Storage Presigned URLs:** Uploading guest document creates private file with 15-minute expiring access link.

