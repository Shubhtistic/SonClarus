<div align="center">

# Sonclarus
### Intelligence in Every Wave.

![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Architecture](https://img.shields.io/badge/Architecture-Hybrid_Cloud-blue?style=for-the-badge)
![Cost](https://img.shields.io/badge/Cost-Free_Tier_Optimized-brightgreen?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-v1.0.0-orange?style=for-the-badge)

**Sonclarus** is an open-source, event-driven audio intelligence platform. It automates the forensic separation of overlapping speakers and contextual transcription using a **Hybrid Microservices Architecture** optimized specifically for the AWS Free Tier.

[View Architecture](#-hybrid-cloud-architecture) • [Zero-Cost Strategy](#-the-zero-cost-strategy) • [The Team](#-the-team)

</div>

---

## The Mission
In high-stakes intelligence analysis, clarity is everything. Analysts often face **"Data Overload"**—hundreds of hours of noisy recordings where overlapping voices (cocktail party effect) make manual review impossible.

**Sonclarus** acts as a high-speed triage engine. It employs a **Stateful/Stateless Hybrid Model** to ingest raw audio, clean it using Deep Learning, separate speakers into distinct tracks, and index the content—all without incurring cloud infrastructure costs.

---

## Core Intelligence

| Module | Function | Technology |
| :--- | :--- | :--- |
| **Forensic Denoising** | Removes non-stationary noise (wind, traffic, static) to enhance signal clarity. | **DeepFilterNet** (Lambda) |
| **Blind Source Separation** | Disentangles two speakers talking simultaneously into distinct, isolated tracks. | **SepFormer** (EC2) |
| **Contextual Transcription** | Converts speech to text with token-level confidence scoring to flag AI uncertainty. | **OpenAI Whisper** (Lambda) |
| **Asynchronous Triage** | Handles heavy evidence files (up to 150MB) without blocking the user interface. | **Celery & Redis** |

---

## Hybrid Cloud Architecture

Sonclarus utilizes a **Decoupled Architecture** to bypass the RAM limitations of the AWS Free Tier (`t3.micro`). We split the system into **The Manager** (Stateful) and **The Specialists** (Stateless).



### The Data Flow
1.  **Ingestion:** User uploads audio via **FastAPI** (EC2). The file is validated and stored in **S3**.
2.  **Burst Clean (Stateless):** **AWS Lambda** triggers immediately to run *DeepFilterNet*, cleaning the audio in parallel.
3.  **The Heavy Lift (Stateful):** **Celery** (EC2) pulls the clean file. It utilizes a **4GB Swap Memory** partition to load the heavy *SepFormer* model on a 1GB RAM instance, splitting the speakers.
4.  **Indexing (Stateless):** **AWS Lambda** triggers again to transcribe the separated tracks using *Whisper Tiny*.
5.  **Persistence:** Results are committed to **PostgreSQL** (RDS) and presented via the dashboard.

---

## The Zero-Cost Strategy
How Sonclarus delivers military-grade results on **$0.00 infrastructure**.

| Service | Role | Free Tier Limit | Optimization Strategy |
| :--- | :--- | :--- | :--- |
| **EC2 (t3.micro)** | Manager | 750 Hrs/Month | Runs 24/7. Uses **Swap Memory** to act as "Fake RAM" for heavy AI models. |
| **AWS Lambda** | Specialists | 400k GB-Seconds | Runs lightweight models (Denoise/Whisper) to offload CPU from the main server. |
| **S3 Storage** | Data Lake | 5 GB | **Lifecycle Rule:** Auto-deletes evidence files after 24 hours. |
| **ECR Public** | Container Registry | 50 GB | Public repositories avoid the 500MB storage limit of private ECR. |

---

## Technology Stack

* **Backend:** Python 3.10, FastAPI, Uvicorn
* **Orchestration:** Celery, Redis
* **Infrastructure:** AWS (EC2, Lambda, S3, RDS, ECR)
* **Machine Learning:** PyTorch, SpeechBrain, Torchaudio
* **Database:** PostgreSQL (SQLModel ORM)
* **DevOps:** Docker, GitHub Actions

---

## The Team

Sonclarus is built with precision by:

* **Shubham Pawar** - *Core Developer*
* **Mihir Revaskar** - *Core Developer*

---

## Citation

If you use Sonclarus in your research, please cite the team:

```yaml
cff-version: 1.2.0
title: "Sonclarus: Hybrid Cloud Audio Intelligence Platform"
authors:
  - name: "Sonclarus Team"
date-released: 2026-01-18
url: "https://github.com/Shubhtistic/SonClarus"
