# Seedance Pipeline

Simple FastAPI app for a two-step Seedance flow:

1. Upload real product images and write a short business brief.
2. Preview refined bilingual prompts from Azure OpenAI with image-aware analysis.
3. Click **Generate Video** to send the selected prompt to fal.ai.
4. Track multiple jobs from the same page.
5. Preview and download the completed video.

## What is implemented

- Prompt preview before video generation
- English + Chinese prompt generation using `Seedance_2_Skill.txt`
- Product-image aware prompt generation
- Live image upload to fal.ai before `image-to-video` submission
- `text-to-video` and `image-to-video`
- In-memory job store
- Safe mock mode for fal so you can test the app without spending credits
- Prompt-only mock jobs that show what would have been sent to Seedance
- Simple FastAPI UI with job list, prompt display, preview player, and download action

## Environment setup

1. Copy `.env.example` to `.env`
2. Fill in:
   - `AZURE_OPENAI_RESPONSES_URL`
   - `AZURE_OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `FAL_KEY` only when you are ready for the final live test
   - `UPLOAD_DIR` if you want uploads somewhere other than `uploads`
3. Keep `FAL_MOCK_MODE=true` until the last step

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`

## Main routes

- `GET /` UI
- `POST /api/prompt-preview`
- `POST /api/generate`
- `GET /api/status/{job_id}`
- `GET /api/jobs`
- `GET /api/download/{job_id}`

## Recommended testing order

1. Test prompt preview with Azure OpenAI
2. Test uploaded image validation for both modes
3. Test multiple concurrent prompt-only jobs with fal mock mode on
4. Test UI refresh, prompt display, and download buttons
5. Put in the real `FAL_KEY`
6. Set `FAL_MOCK_MODE=false`
7. Run a single low-cost fal test at the end
