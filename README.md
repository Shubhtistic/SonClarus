<div align="center">

<img src="https://img.shields.io/badge/Sonclarus-Audio%20Intelligence-black?style=for-the-badge" alt="Sonclarus"/>

# Sonclarus

**Upload a two-person recording. Get back a clean, speaker-labeled transcript and AI summary.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-blue.svg?style=flat-square)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg?style=flat-square)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-Free%20Tier-orange.svg?style=flat-square)](https://aws.amazon.com/free)

[What It Does](#-what-it-does) · [How It Works](#-how-it-works) · [Architecture](#-architecture) · [Quickstart](#-quickstart) · [API](#-api-reference)

</div>

---

## The Problem

You record a podcast interview, a client call, or a research session. You get back one messy audio file with two people talking, sometimes over each other, with background noise from a café or a room with bad acoustics.

Getting a usable transcript means:
- Paying $16/month for Otter.ai
- Or manually listening and typing it yourself

**Sonclarus does it for free.** It cleans the noise, separates the two voices, transcribes each speaker independently, and returns a labeled transcript with an AI-generated summary — no subscription, no manual work.

---

## ✨ What It Does

Given a raw audio file of two people talking, Sonclarus returns this:

```
Speaker 1: So tell me about how you started the project.
Speaker 2: It came out of a problem I kept hitting at work. Every meeting
           ended with no clear record of who said what or what was decided.
Speaker 1: How long did it take you to build the first version?
Speaker 2: About three weeks for the core pipeline. The hard part was
           getting speaker separation to work on noisy recordings.

─────────────────────────────────────────────────────
SUMMARY
The conversation covered the origin of the project and the core
engineering challenges in building the audio pipeline.

ACTION ITEMS
• Speaker 2 to share the initial design document
• Follow up on deployment timeline next week
─────────────────────────────────────────────────────
```

**Works best for:** Podcast interviews · Research interviews · Client calls · Sales calls · Depositions · Lecture recordings · 1-on-1 meetings

> **Note:** Sonclarus separates exactly two speakers. It is not designed for panel discussions or group calls with three or more participants.

---

## 🔬 How It Works

Every uploaded file passes through a four-stage pipeline:

```
                    ┌─────────────────────────────────────────┐
                    │              SONCLARUS PIPELINE          │
                    └─────────────────────────────────────────┘

  Raw Audio
      │
      ▼
┌──────────────┐    DeepFilterNet removes wind, traffic,
│  1. DENOISE  │ ── static, and room echo from the recording.
└──────────────┘    The cleaned audio moves to the next stage.
      │
      ▼
┌──────────────┐    SepFormer analyses the full waveform and
│  2. SEPARATE │ ── isolates two distinct voice patterns into
└──────────────┘    two independent audio tracks.
      │
      ├── Track A ──► Whisper transcribes Speaker 1
      └── Track B ──► Whisper transcribes Speaker 2
                              │
                              ▼
                    ┌──────────────────┐
                    │   3. TRANSCRIBE  │   Whisper runs on each
                    └──────────────────┘   track independently,
                              │            with confidence scoring
                              ▼            to flag uncertain words.
                    ┌──────────────────┐
                    │   4. SUMMARIZE   │   An LLM generates a
                    └──────────────────┘   short summary and pulls
                              │            out action items.
                              ▼
                    Labeled transcript returned
```

| Stage | Model | What it produces |
| :--- | :--- | :--- |
| Denoise | DeepFilterNet | Clean audio with background noise removed |
| Separate | SepFormer (`wsj02mix`) | Two isolated voice tracks from one mixed file |
| Transcribe | OpenAI Whisper | Text per speaker with confidence scores |
| Summarize | LLM API | 5-line summary + action items |

---

## 🏗 Architecture

Sonclarus uses a decoupled cloud + local GPU setup to keep infrastructure cost at zero.

```
  Browser / API Client
          │
          │  POST /upload (audio file)
          ▼
  ┌───────────────────┐
  │   FastAPI (EC2)   │ ──► S3 (stores raw audio)
  └───────────────────┘
          │
          │  Enqueues job via ARQ
          ▼
  ┌───────────────────┐
  │  ARQ Worker (EC2) │ ──► Redis (job queue)
  └───────────────────┘
          │
          ├──► ML Server (local GPU via ngrok)
          │    ├── DeepFilterNet  →  denoised audio
          │    └── SepFormer      →  two speaker tracks
          │
          ├──► Whisper  →  transcription per track
          │
          └──► LLM API  →  summary + action items
                    │
                    ▼
          ┌──────────────────┐
          │  PostgreSQL (RDS) │  stores final transcript
          └──────────────────┘
```

### Why ARQ instead of Celery

Audio processing takes 30–90 seconds per file. The user should not wait at an open HTTP connection for that long. ARQ accepts the upload, returns a `job_id` immediately, and processes async in the background.

We moved from Celery after hitting two hard problems:
- Celery's threading model caused `asyncio` event loop conflicts with `asyncpg` — crashes at runtime with "Task attached to a different loop"
- Shared `QueuePool` between the API and worker containers caused ghost connections and database lockups

ARQ is built natively for Python's `asyncio`. Both issues went away.

### Why a local GPU instead of a cloud GPU instance

SepFormer needs a GPU to run at useful speed. A GPU EC2 instance costs $0.50–$1.00/hour — not viable for a zero-cost deployment. The ML models run on a local GPU machine and are exposed via ngrok as an internal HTTP endpoint. The EC2 worker calls it like any other API.

---

## 💸 Zero-Cost Infrastructure

| Service | Role | Free Tier Limit | Strategy |
| :--- | :--- | :--- | :--- |
| **EC2 (t3.micro)** | API + ARQ worker | 750 hrs/month | Runs 24/7 |
| **S3** | Audio file storage | 5 GB | Lifecycle rule auto-deletes files after 24 hours |
| **RDS (PostgreSQL)** | Transcript storage | 20 GB | Stores text only — audio is always deleted post-processing |
| **Redis (Docker)** | ARQ job queue | — | Runs inside EC2, no ElastiCache needed |
| **ngrok** | ML server tunnel | Free tier | Local GPU machine, no cloud GPU cost |

---

## 🚀 Quickstart

### Prerequisites

- Docker and Docker Compose
- Git
- A machine with a GPU running the ML server (see [`/ml-server/README.md`](ml-server/README.md))
- An ngrok account with a tunnel pointed at the ML server

### 1. Clone and configure

```bash
git clone https://github.com/Shubhtistic/SonClarus.git
cd SonClarus
cp .env.example .env
```

Fill in `.env`:

```env
# Database
POSTGRES_SERVER=your_rds_endpoint_here
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=sonclarus_db

# Redis
REDIS_URL=redis://redis:6379/0

# AWS
S3_BUCKET=your_bucket_name
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-south-1

# ML Server
ML_SERVER_URL=https://your-ngrok-url.ngrok-free.app

# LLM
LLM_API_KEY=your_key_here
```

### 2. Start the stack

```bash
# Development
docker compose up --build

# Production (detached)
docker compose -f compose.prod.yml up -d --build
```

Services start in dependency order automatically:

| Step | Service | Condition |
| :--- | :--- | :--- |
| 1 | `postgres` + `redis` | Start immediately in parallel |
| 2 | `migrate` | Waits for postgres health check, runs Alembic migrations, exits |
| 3 | `api` + `worker` | Start after migrations complete successfully |

---

## 📡 API Reference

### Upload audio

```bash
POST /api/v1/upload
Content-Type: multipart/form-data

curl -X POST https://your-domain.com/api/v1/upload \
  -F "file=@interview.mp3"
```

**Response:**
```json
{
  "job_id": "3f7a9c12-...",
  "status": "queued",
  "message": "Processing started. Poll /status/{job_id} for updates."
}
```

### Check status

```bash
GET /api/v1/status/{job_id}
```

```json
{
  "job_id": "3f7a9c12-...",
  "status": "processing",
  "stage": "separating_speakers"
}
```

Status flow: `queued` → `denoising` → `separating_speakers` → `transcribing` → `summarizing` → `done`

### Get result

```bash
GET /api/v1/result/{job_id}
```

```json
{
  "job_id": "3f7a9c12-...",
  "status": "done",
  "transcript": [
    { "speaker": "Speaker 1", "text": "Tell me about the project." },
    { "speaker": "Speaker 2", "text": "It started as an internal tool..." }
  ],
  "summary": "The conversation covered the origin of the project...",
  "action_items": [
    "Speaker 2 to share the design document",
    "Follow up on deployment timeline next week"
  ]
}
```

---

## 🛠 Tech Stack

| Layer | Technology |
| :--- | :--- |
| API | Python 3.10, FastAPI, Uvicorn |
| Task Queue | ARQ (asyncio-native, replaces Celery) |
| Cache / Buffer | Redis |
| ML — Denoising | DeepFilterNet |
| ML — Separation | SepFormer via SpeechBrain |
| ML — Transcription | OpenAI Whisper |
| ML — Summarization | LLM API |
| Database | PostgreSQL, SQLModel ORM, Alembic |
| Infrastructure | AWS EC2, S3, RDS |
| DevOps | Docker, Docker Compose, GitHub Actions |

---

## 📁 Project Structure

```
SonClarus/
├── api/
│   ├── main.py          # FastAPI app and route definitions
│   ├── models.py        # SQLModel database schemas
│   ├── worker.py        # ARQ background job definitions
│   └── storage.py       # S3 upload/download helpers
├── ml-server/
│   ├── server.py        # FastAPI app exposing ML endpoints
│   ├── denoise.py       # DeepFilterNet wrapper
│   ├── separate.py      # SepFormer wrapper
│   └── README.md        # ML server setup guide
├── migrations/          # Alembic migration files
├── compose.yml
├── compose.prod.yml
└── .env.example
```

---

## 🗺 Roadmap

- [ ] Web UI — drag and drop upload with live status tracking
- [ ] Speaker naming — let users label Speaker 1 and Speaker 2 after processing
- [ ] Export — download transcript as `.txt`, `.docx`, or `.srt` subtitle file
- [ ] Confidence highlighting — flag low-confidence words in the transcript
- [ ] Video support — accept `.mp4` and `.mov` and extract audio automatically

---

## 👥 The Team

- **Shubham Pawar** — Core Developer
- **Mihir Revaskar** — Core Developer

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## License

[MIT](LICENSE)