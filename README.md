# Isometric MTO Generator

> **AI-powered Material Take-Off from piping isometric drawings** — Upload a PDF or image of any isometric drawing and get a structured, exportable Bill of Materials in seconds.

![Isometric MTO Generator](./samples/iso_sample_1.pdf)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation &amp; Setup](#installation--setup)
- [Running the App](#running-the-app)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [How to Verify Results](#how-to-verify-results)
- [Running Tests](#running-tests)
- [Docker Deployment](#docker-deployment)
- [Project Structure](#project-structure)
- [Known Limitations](#known-limitations)

---

## Overview

The **Isometric MTO Generator** automates the tedious, error-prone task of manually reading piping isometric drawings and counting materials.

A piping engineer traditionally spends hours counting elbows, flanges, pipe lengths, and deriving bolt sets from a single isometric drawing. This tool uses **Google Gemini Vision AI** in a two-pass extraction pipeline to do the same job in under 10 seconds.

**Input:** PNG / JPG / PDF of a piping isometric drawing
**Output:** Structured MTO table with drawing metadata, quantities, material specs, bounding boxes, and a confidence score — downloadable as CSV or Excel.

---

## ✨ Features

| Feature                                | Description                                                                                        |
| -------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 🤖**AI Extraction (Pass A)**     | Full-image Gemini Vision scan for pipes, fittings, flanges, valves, and elbows with bounding boxes |
| 📋**BOM Recognition (Pass B)**   | Dedicated crop of the BOM table region with structured row extraction                              |
| 🔗**Smart Reconciliation**       | Fuzzy-match merge of Pass A + Pass B results; flags quantity mismatches                            |
| ⚙️**Auto-Derived Consumables** | Gaskets and bolt sets are automatically computed from flange/valve counts                          |
| 🖼️**Interactive SVG Overlay**  | Hover over any extracted item to highlight its bounding box on the drawing image                   |
| 📥**CSV & Excel Export**         | One-click download of the full MTO in CSV or`.xlsx` format                                       |
| ⚡**Transparent Rate Limiting**  | Clear, user-friendly messages when AI quota is reached — no silent failures                       |
| 🐋**Docker Support**             | Full`docker-compose` setup for production deployment                                             |

---

## 🛠️ Tech Stack

### Backend

- **Python 3.12** + **FastAPI** — async REST API
- **Google Gemini Vision API** (`gemini-3.1-flash-lite`) — two-pass AI extraction
- **Pillow** + **pdf2image** + **Poppler** — PDF/image preprocessing
- **Tesseract OCR** — title block metadata extraction
- **Pydantic v2** — strict data validation and serialization
- **Pytest** — 27 unit + integration tests

### Frontend

- **Next.js 14** (App Router) + **TypeScript**
- **Vanilla CSS** — custom design system, glassmorphism UI
- **SVG Overlay** — real-time bounding box visualization

---

## 🏗️ Architecture

```
User Upload (PNG/JPG/PDF)
         │
         ▼
┌─────────────────────┐
│   Image Preprocess  │  pdf2image + Pillow resize + contrast enhance
└─────────┬───────────┘
          │
    ┌─────┴──────┐
    │            │
    ▼            ▼
┌───────┐   ┌────────┐
│Pass A │   │ Pass B │  Two parallel Gemini Vision calls
│Full   │   │  BOM   │  (full image + cropped BOM region)
│Image  │   │ Region │
└───┬───┘   └───┬────┘
    │            │
    └─────┬──────┘
          ▼
┌─────────────────────┐
│   Reconciliation    │  Fuzzy merge + consumable derivation
│   Layer             │  + Pydantic validation
└─────────┬───────────┘
          ▼
   JSON Job Result
   (served via REST API)
          │
          ▼
┌─────────────────────┐
│   Next.js Frontend  │  SVG overlay + table + CSV/Excel export
└─────────────────────┘
```

**Job Flow:**

1. `POST /api/upload` → file saved to disk, background job created, `job_id` returned immediately
2. Frontend polls `GET /api/mto/{job_id}` every 2 seconds
3. Pipeline runs in background: preprocess → OCR → Gemini Pass A → Gemini Pass B → Reconcile
4. `GET /api/mto/{job_id}/image` serves the pre-processed PNG for the SVG overlay

---

## 📦 Prerequisites

### Required

- **Node.js 18+** and **npm**
- **Python 3.12+**
- **Poppler** (for PDF-to-image conversion)
- **Tesseract OCR**
- **Google Gemini API Key** (free tier at [aistudio.google.com](https://aistudio.google.com))

### Install System Dependencies (macOS)

```bash
# Install Poppler (PDF processing)
brew install poppler

# Install Tesseract OCR
brew install tesseract
```

### Install System Dependencies (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr
```

---

## 🚀 Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/Imchaitanya0/isometric-mto.git
cd isometric-mto
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3.12 -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy the example env file
cp ../.env.example .env

# Edit .env and add your Gemini API key
nano .env
```

Your `.env` file should look like:

```env
GEMINI_API_KEY=AIza...your_key_here
MAX_FILE_SIZE_MB=20
```

> **Get your free API key:** Go to [https://aistudio.google.com](https://aistudio.google.com) → Get API Key → Create API Key in new project.

### 4. Frontend Setup

```bash
cd ../frontend
npm install
```

---

## ▶️ Running the App

### Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`
Interactive API docs: `http://localhost:8000/docs`

### Start the Frontend

```bash
cd frontend
npm run dev
```

The app will open at `http://localhost:3000`

---

## 📖 Usage Guide

1. **Open** `http://localhost:3000` in your browser
2. **Upload** a piping isometric drawing (PNG, JPG, or PDF, max 20MB)
3. **Wait** 8–15 seconds for the AI pipeline to complete (the progress bar shows live status)
4. **Review Results:**
   - Left panel: the processed drawing image with **interactive SVG bounding boxes** — hover over any row in the table to highlight it on the drawing
   - Right panel: the full structured MTO table with item categories, quantities, specs, and confidence scores
5. **Export:** Click **Download CSV** or **Download Excel** to save the MTO

### Rate Limit Guidance (Free Tier)

The Google Gemini free tier allows **5 requests per minute** and **varied requests per day** per model(**example : gemini 3.1 flash lite will be having 500 requests per day**). Each drawing upload uses **2 API calls** (Pass A + Pass B).

| Error Message                 | Meaning                         | Action                           |
| ----------------------------- | ------------------------------- | -------------------------------- |
| "Please wait 1 minute…"      | Minute quota hit                | Wait 60 seconds, try again       |
| "Please try again tomorrow…" | Daily quota exhausted           | Wait until midnight PT for reset |
| "The AI model timed out…"    | Server overload (no quota used) | Retry immediately                |

---

## 🔌 API Reference

All endpoints are prefixed with `/api`.

### `POST /api/upload`

Upload a drawing file and start the extraction pipeline.

**Request:** `multipart/form-data` with field `file` (PNG/JPG/PDF, max 20MB)

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "iso_sample_1.pdf",
  "size_mb": 0.63
}
```

---

### `GET /api/mto/{job_id}`

Poll the job status and retrieve the result when complete.

**Response (completed):**

```json
{
  "job_id": "550e8400...",
  "status": "completed",
  "result": {
    "source": "ai",
    "drawing_meta": {
      "drawing_no": "XTPL/F 17",
      "revision": "0",
      "line_number": "loop-3",
      "nps": "2in",
      "material_class": "CS",
      "confidence": 0.85
    },
    "items": [
      {
        "item_no": 1,
        "category": "PIPE",
        "description": "Pipe, Seamless, BE, ASME B36.10",
        "size_nps": "2in",
        "schedule_rating": "SCH 40",
        "material_spec": "ASTM A106 Gr.B",
        "quantity": 1,
        "unit": "M",
        "length_m": 24.5,
        "confidence": 0.8,
        "bbox": { "x": 0.15, "y": 0.2, "width": 0.7, "height": 0.65 }
      }
    ],
    "summary": {
      "total_pipe_length_m": 27.7,
      "fittings": 12,
      "flanges": 8,
      "valves": 4,
      "gaskets": 8,
      "bolt_sets": 8,
      "field_welds": 14
    }
  }
}
```

**Status values:** `processing` | `completed` | `failed`

---

### `GET /api/mto/{job_id}/image`

Returns the pre-processed PNG of the uploaded drawing (used by the frontend for the SVG overlay).

---

### `GET /api/mto/{job_id}/csv`

Download the MTO as a CSV file.

---

### `GET /api/mto/{job_id}/xlsx`

Download the MTO as an Excel (`.xlsx`) file with formatted headers.

---

### `GET /api/health`

Health check endpoint.

**Response:** `{"status": "ok", "timestamp": "...", "service": "isometric-mto-backend", "version": "1.0.0"}`

---

## ✅ How to Verify Results

To independently verify whether the AI extraction is correct:

### Method 1: Check the Raw AI Output Log

While the backend is running, the raw JSON returned by each Gemini call is appended to:

```bash
cat /tmp/gemini_raw_out.log
```

This shows you exactly what the AI returned — unfiltered by the reconciliation layer.

### Method 2: Manual Cross-Check Against the Drawing

For each drawing, manually verify:

| What to Check             | How                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------- |
| **Elbows count**    | Count every direction change (corner) in the pipe run on the drawing                  |
| **Tees count**      | Count every T-junction or branch connection                                           |
| **Flange count**    | Count the flange symbols (double vertical lines)                                      |
| **Gaskets & Bolts** | Should equal the number of flanged joints (automatically derived, 100% code-computed) |
| **Pipe length**     | Sum all dimension callouts on the drawing                                             |

### Method 3: Download & Compare in Excel

Click **Download Excel**, open in Excel/Numbers, and compare each row against the drawing line-by-line. This is the most rigorous check.

---

## 🧪 Running Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

**Current test suite:** 27 tests across 3 files

| Test File                  | Coverage                                                      |
| -------------------------- | ------------------------------------------------------------- |
| `test_schema.py`         | Pydantic model validation, boundary conditions                |
| `test_reconciliation.py` | Fuzzy merge logic, consumable derivation, full reconcile flow |
| `test_mock_pipeline.py`  | Upload endpoint, health check, polling, mock pipeline         |

---

## 🐋 Docker Deployment

For production deployment, use the included Docker Compose setup:

### Prerequisites

- Docker Desktop installed and running

### Steps

```bash
# 1. Set your API key in .env file
echo "GEMINI_API_KEY=AIza...your_key" > .env

# 2. Build and start all services
docker-compose up --build

# 3. The app is now running at:
#    Frontend: http://localhost:3000
#    Backend API: http://localhost:8000
#    API Docs: http://localhost:8000/docs

# 4. To stop
docker-compose down
```

The `docker-compose.yml` starts both the FastAPI backend and Next.js frontend in isolated containers with automatic health checks and restart policies.

---

## 📁 Project Structure

```
isometric-mto/
├── backend/
│   ├── core/
│   │   ├── config.py          # Settings (API key, file size limit)
│   │   ├── exceptions.py      # Custom exception classes
│   │   └── job_store.py       # Thread-safe in-memory job store
│   ├── models/
│   │   └── mto.py             # Pydantic schemas (MTOItem, DrawingMeta, etc.)
│   ├── prompts/
│   │   ├── extraction_prompt.md  # Pass A prompt (full image)
│   │   └── bom_prompt.md         # Pass B prompt (BOM crop)
│   ├── routes/
│   │   ├── health.py          # GET /api/health
│   │   ├── mto.py             # GET /api/mto/{id}, /csv, /xlsx, /image
│   │   └── upload.py          # POST /api/upload
│   ├── services/
│   │   ├── gemini_client.py   # Gemini API wrapper (two-pass extraction)
│   │   ├── image_preprocess.py # PDF→PNG, resize, contrast enhance
│   │   ├── line_parser.py     # ISO line number parser
│   │   ├── mock_pipeline.py   # Deterministic mock for testing
│   │   ├── ocr_title.py       # Tesseract OCR for title block
│   │   ├── pipeline.py        # Main orchestrator
│   │   └── reconciliation.py  # Pass A + B merge + consumable derivation
│   ├── tests/
│   │   ├── test_mock_pipeline.py
│   │   ├── test_reconciliation.py
│   │   └── test_schema.py
│   ├── main.py                # FastAPI app entry point
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx           # Main application page
│   │   ├── layout.tsx         # Root layout with metadata
│   │   └── globals.css        # Design system + styles
│   ├── lib/
│   │   └── api.ts             # API client (upload, poll, download)
│   └── package.json
├── samples/
│   └── iso_sample_1.pdf       # Sample isometric drawing for testing
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚠️ Known Limitations

| Limitation                        | Details                                                                                                                       |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Pipe length accuracy**    | AI estimates lengths from dimension annotations. Expect ±10–15% tolerance.                                                  |
| **Free tier quota**         | 5 requests/minute, 50 requests/day per model on the free tier                                                                 |
| **Complex multi-page PDFs** | Only the first page is processed                                                                                              |
| **Hand-drawn drawings**     | OCR and AI accuracy drops significantly on hand-sketched isos                                                                 |
| **Pass B BOM extraction**   | Drawings without a tabular BOM in the bottom-right corner will return 0 BOM rows (Pass A items are still extracted correctly) |
| **In-memory job store**     | Jobs are lost if the backend restarts; no persistence to disk                                                                 |

---

## 📄 License

This project is part of the **Pathnovo** suite. All rights reserved.

---

*Built with ❤️ using Google Gemini Vision API, FastAPI, and Next.js*
