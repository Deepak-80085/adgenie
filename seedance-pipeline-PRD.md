# PRD & Technical Specification
## Seedance 2.0 Video Generation Pipeline — FastAPI App

**Version:** 1.0  
**Date:** April 14, 2026  
**Status:** Ready for Implementation

---

## 1. Overview

A FastAPI backend that takes a plain-text scene description from a user, transforms it into a production-grade bilingual video prompt using an LLM + the Seedance Director skill, then sends that prompt to fal.ai's Seedance 2.0 model to generate a cinematic video. The app returns a job ID immediately and exposes a polling endpoint to check status and retrieve the final video URL + downloaded file.

---

## 2. User Flow (End-to-End)

```
User (POST /generate)
  │
  ├─► [Step 1] Validate input (mode, prompt, optional image URL)
  │
  ├─► [Step 2] Call OpenAI GPT API
  │     System prompt = seedance-director SKILL.md contents
  │     User message  = user's plain-text scene description
  │     Response      = JSON array: [{lang:"en", prompt:"..."}, {lang:"zh", prompt:"..."}]
  │
  ├─► [Step 3] Extract the EN prompt from the JSON response
  │
  ├─► [Step 4] Submit to fal.ai queue (Seedance 2.0)
  │     Mode: text-to-video  → endpoint: bytedance/seedance-2.0/text-to-video
  │     Mode: image-to-video → endpoint: bytedance/seedance-2.0/image-to-video
  │     Returns: fal request_id
  │
  ├─► [Step 5] Store job record in memory (or SQLite)
  │     { job_id, fal_request_id, status, created_at, generated_prompt, ... }
  │
  └─► Return to user: { job_id, status: "queued" }

User (GET /status/{job_id})
  │
  ├─► Poll fal.ai queue for fal_request_id status
  ├─► If COMPLETED:
  │     ├─ Store video URL
  │     ├─ Download MP4 to local /downloads/{job_id}.mp4
  │     └─ Return { status, video_url, local_path, generated_prompt }
  └─► If IN_PROGRESS / QUEUED: return { status, message }
```

---

## 3. API Endpoints

### 3.1 `POST /generate`

Starts a new video generation job.

**Request Body:**
```json
{
  "user_prompt": "Two fighters clash in a rain-soaked alley at midnight, 10 seconds",
  "mode": "text-to-video",           // "text-to-video" | "image-to-video"
  "image_url": null,                 // required if mode = image-to-video
  "resolution": "720p",              // "480p" | "720p"  — default: "720p"
  "duration": "auto",                // "4"–"15" (string) or "auto" — default: "auto"
  "aspect_ratio": "16:9",            // "16:9" | "9:16" | "1:1" | "4:3" | "3:4" | "21:9" | "auto"
  "generate_audio": true             // default: true
}
```

**Response `202 Accepted`:**
```json
{
  "job_id": "a3f7c82d-...",
  "status": "queued",
  "message": "Job submitted. Poll /status/{job_id} to track progress."
}
```

**Validation rules:**
- `user_prompt` — required, non-empty string
- `mode` — must be `"text-to-video"` or `"image-to-video"`
- `image_url` — required and must be a valid HTTPS URL when mode is `"image-to-video"`
- `resolution` — must be `"480p"` or `"720p"`
- `duration` — must be `"auto"` or a string integer between `"4"` and `"15"`

---

### 3.2 `GET /status/{job_id}`

Polls the status of a generation job.

**Response — while in progress:**
```json
{
  "job_id": "a3f7c82d-...",
  "status": "IN_PROGRESS",
  "message": "Video is being generated on fal.ai..."
}
```

**Response — on completion:**
```json
{
  "job_id": "a3f7c82d-...",
  "status": "COMPLETED",
  "video_url": "https://v3b.fal.media/files/.../video.mp4",
  "local_path": "downloads/a3f7c82d.mp4",
  "generated_prompt": {
    "en": "Style & Mood: ...",
    "zh": "风格与氛围：..."
  },
  "seed": 1632191255,
  "duration_seconds": 10,
  "resolution": "720p"
}
```

**Response — on failure:**
```json
{
  "job_id": "a3f7c82d-...",
  "status": "FAILED",
  "error": "fal.ai returned error: ..."
}
```

---

### 3.3 `GET /jobs`

Returns a list of all jobs (paginated).

**Query params:** `?limit=20&offset=0`

**Response:**
```json
{
  "total": 5,
  "jobs": [
    { "job_id": "...", "status": "COMPLETED", "created_at": "...", "mode": "text-to-video" },
    ...
  ]
}
```

---

### 3.4 `GET /download/{job_id}`

Streams the downloaded MP4 file directly as a file response.

**Response:** `FileResponse` with `Content-Type: video/mp4`  
Returns `404` if video not yet downloaded or job not found.

---

## 4. Project Structure

```
seedance-pipeline/
│
├── main.py                  # FastAPI app, router mounts
├── config.py                # Env var loading (API keys, paths)
├── models.py                # Pydantic request/response models + job store
│
├── services/
│   ├── prompt_service.py    # Calls OpenAI, injects SKILL.md as system prompt
│   ├── fal_service.py       # Submits to fal.ai queue, polls status
│   └── download_service.py  # Downloads MP4 from video_url to disk
│
├── routers/
│   ├── generate.py          # POST /generate
│   ├── status.py            # GET /status/{job_id}
│   ├── jobs.py              # GET /jobs
│   └── download.py          # GET /download/{job_id}
│
├── skill/
│   └── seedance_director.md # The Seedance Director SKILL.md (system prompt)
│
├── downloads/               # Auto-created — local MP4 storage
├── .env                     # API keys (never committed)
├── .env.example             # Template for env vars
├── requirements.txt
└── README.md
```

---

## 5. Environment Variables (`.env`)

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o            # configurable — change to whatever model you have access to
FAL_KEY=...                    # from fal.ai dashboard
DOWNLOAD_DIR=downloads         # local folder for MP4 files
MAX_POLL_ATTEMPTS=60           # max status poll attempts on /status endpoint
POLL_INTERVAL_SECONDS=5        # seconds between each fal.ai poll
```

> **Note on model:** You mentioned "gpt-5.4" — this model name does not exist in OpenAI's current API
> as of April 2026. The `OPENAI_MODEL` env var is fully configurable, so plug in whatever
> model string your API key grants access to (e.g., `gpt-4o`, `o4-mini`, etc.).
> The app will pass it through directly to the OpenAI API.

---

## 6. Service-Level Logic

### 6.1 `prompt_service.py` — LLM Prompt Generation

```
1. Load seedance_director.md from disk at startup (or per-request)
2. Build OpenAI messages:
     system: <full contents of SKILL.md>
     user:   <user_prompt from request>
3. Call openai.chat.completions.create(model=OPENAI_MODEL, messages=[...])
4. Parse response content as JSON array:
     [{"lang": "en", "prompt": "..."}, {"lang": "zh", "prompt": "..."}]
5. Extract and return both EN and ZH prompts
6. On JSON parse failure → raise HTTPException 502 with raw LLM output for debugging
```

The SKILL.md instructs the LLM to respond **only** with a JSON array — no markdown, no explanation. The service must handle edge cases where the model wraps output in backticks and strip them before parsing.

---

### 6.2 `fal_service.py` — fal.ai Submission & Polling

**Endpoints used:**

| Mode | fal.ai Endpoint |
|------|-----------------|
| text-to-video | `bytedance/seedance-2.0/text-to-video` |
| image-to-video | `bytedance/seedance-2.0/image-to-video` |

**Submit (queue):**
```
POST https://queue.fal.run/{endpoint}
Authorization: Key {FAL_KEY}
Content-Type: application/json

Body (text-to-video):
{
  "prompt": "<EN prompt from LLM>",
  "duration": "auto",
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "generate_audio": true
}

Body (image-to-video) — adds:
{
  "image_url": "<user-provided HTTPS image URL>",
  ...same fields...
}

Response: { "request_id": "...", "status": "IN_QUEUE" }
```

**Poll status:**
```
GET https://queue.fal.run/{endpoint}/requests/{request_id}/status
Authorization: Key {FAL_KEY}

Response: { "status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED" }
```

**Fetch result (only when COMPLETED):**
```
GET https://queue.fal.run/{endpoint}/requests/{request_id}
Authorization: Key {FAL_KEY}

Response:
{
  "video": { "url": "https://...", "file_name": "video.mp4", "file_size": 3393408 },
  "seed": 1632191255
}
```

---

### 6.3 `download_service.py` — Video Download

```
1. Receive video_url (from fal result)
2. Stream GET request to video_url
3. Save to DOWNLOAD_DIR/{job_id}.mp4
4. Return local path string
```

---

## 7. Job Store

For this version, an **in-memory dict** is sufficient (resets on server restart). A SQLite option is described for persistence.

**Job record schema:**
```python
{
  "job_id": str,              # UUID4
  "status": str,              # "queued" | "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED"
  "fal_request_id": str,
  "fal_endpoint": str,
  "mode": str,
  "resolution": str,
  "duration": str,
  "aspect_ratio": str,
  "generate_audio": bool,
  "generated_prompt": {       # from LLM
    "en": str,
    "zh": str
  },
  "video_url": str | None,
  "local_path": str | None,
  "seed": int | None,
  "error": str | None,
  "created_at": str,          # ISO 8601
  "completed_at": str | None
}
```

**Optional SQLite upgrade:** use `aiosqlite` + a single `jobs` table with the same columns as JSON. Swap the in-memory dict for DB calls inside `models.py` without touching any router or service code.

---

## 8. Dependencies (`requirements.txt`)

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0          # async HTTP for fal.ai calls
openai>=1.30.0         # OpenAI Python SDK
python-dotenv>=1.0.0
aiofiles>=23.0.0       # async file download
pydantic>=2.0.0
uuid                   # stdlib
```

---

## 9. Error Handling

| Scenario | HTTP Status | Detail |
|----------|-------------|--------|
| Missing required field | `422` | FastAPI Pydantic validation |
| `image_url` missing for image-to-video | `400` | Custom validator |
| OpenAI API error | `502` | Message + raw LLM output |
| LLM response not valid JSON | `502` | Raw LLM text included for debug |
| fal.ai submission error | `502` | fal error message forwarded |
| fal.ai job FAILED | `200` (job status FAILED) | Error stored in job record |
| job_id not found | `404` | — |
| Video not yet downloaded | `404` on `/download` | — |

---

## 10. Startup & Running

```bash
# 1. Clone / create project
cd seedance-pipeline

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env template and fill in keys
cp .env.example .env
# Edit .env: add OPENAI_API_KEY and FAL_KEY

# 4. Place your SKILL.md in skill/seedance_director.md

# 5. Run
uvicorn main:app --reload --port 8000

# 6. Interactive API docs
open http://localhost:8000/docs
```

---

## 11. Sequence Diagram

```
Client          FastAPI         OpenAI GPT       fal.ai Queue
  │                │                │                 │
  │──POST /gen────►│                │                 │
  │                │──[SKILL.md +]──►                 │
  │                │   user_prompt  │                 │
  │                │◄──JSON prompt──│                 │
  │                │                                  │
  │                │──POST queue.fal.run/submit───────►│
  │                │◄──{ request_id }─────────────────│
  │                │                                  │
  │◄──{ job_id }───│                                  │
  │                │                                  │
  │──GET /status──►│                                  │
  │                │──GET queue.fal.run/status────────►│
  │                │◄──{ IN_PROGRESS }────────────────│
  │◄──IN_PROGRESS──│                                  │
  │                │                                  │
  │──GET /status──►│                                  │
  │                │──GET queue.fal.run/status────────►│
  │                │◄──{ COMPLETED }──────────────────│
  │                │──GET queue.fal.run/result────────►│
  │                │◄──{ video_url, seed }────────────│
  │                │──download MP4 to disk             │
  │◄──COMPLETED────│                                  │
  │  video_url     │                                  │
  │  local_path    │                                  │
  │                │                                  │
  │──GET /download/{job_id}                           │
  │◄──MP4 stream───│                                  │
```

---

## 12. Key Decisions & Notes

| Decision | Choice | Reason |
|----------|--------|--------|
| Prompt language sent to fal | English only (EN from bilingual output) | Seedance 2.0 is optimized for EN prompts; ZH stored for reference |
| Job persistence | In-memory (SQLite as upgrade path) | Simple to start; easy to upgrade |
| fal.ai SDK vs REST | Raw HTTP (httpx) | No extra SDK dependency; full control |
| Async polling | Client-driven (poll /status) | Avoids server-side background tasks for simplicity; easy to upgrade to WebSocket |
| SKILL.md loading | Load once at startup, cache in memory | Avoid disk reads per request |
| Download on completion | Triggered inside /status when COMPLETED detected for first time | Keeps download logic server-side, transparent to client |

---

## 13. Future Upgrades (Out of Scope for v1)

- **WebSocket endpoint** `/ws/{job_id}` — push status updates instead of polling
- **SQLite or PostgreSQL** job store for persistence across restarts
- **Reference-to-video mode** — multimodal input (images + video + audio refs)
- **Rate limiting** per API key
- **Simple HTML frontend** — form to submit prompt, shows video player on completion
- **Webhook support** — fal.ai can POST result to your server instead of polling

---

*End of PRD — ready to hand off to a developer or use as build instructions.*
