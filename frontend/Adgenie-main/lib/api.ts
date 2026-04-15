import { createClient } from '@/lib/supabase/client'

// All /api/* calls go through Next.js rewrites → FastAPI at localhost:8000
const BASE = ''

export type JobRecord = {
  job_id: string
  status: string
  user_prompt: string
  mode: string
  resolution: string
  duration: string
  aspect_ratio: string
  generate_audio: boolean
  video_url: string | null
  local_path: string | null
  submitted_prompt: string | null
  submitted_prompt_language: 'en' | 'zh' | null
  generated_prompt?: { en: string; zh: string }
  seed: number | null
  error: string | null
  created_at: string
  completed_at: string | null
}

type JobsListResponse = {
  jobs: JobRecord[]
  total: number
  limit: number
  offset: number
}

async function authHeaders(): Promise<Record<string, string>> {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  return user ? { 'X-User-ID': user.id } : {}
}

export async function startChat(formData: FormData) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/chat/start`, { method: 'POST', headers, body: formData })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to start chat')
  }
  return res.json() as Promise<{ session_id: string; message: string; image_count: number }>
}

export async function confirmChat(body: {
  session_id: string
  mode: 'text-to-video' | 'image-to-video'
  resolution: string
  duration: string
  aspect_ratio: string
  generate_audio: boolean
  end_user_id?: string
}) {
  const headers = { ...(await authHeaders()), 'Content-Type': 'application/json' }
  const res = await fetch(`${BASE}/api/chat/confirm`, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to generate prompt')
  }
  return res.json() as Promise<{ preview_id: string }>
}

export async function generateVideo(body: { preview_id: string }) {
  const headers = { ...(await authHeaders()), 'Content-Type': 'application/json' }
  const res = await fetch(`${BASE}/api/generate`, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to submit generation')
  }
  return res.json() as Promise<{ job_id: string; status: string; prompt_language: string }>
}

export async function getJobStatus(jobId: string): Promise<JobRecord> {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/status/${jobId}`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to get job status')
  }
  return res.json()
}

export async function listJobs(limit = 50): Promise<JobRecord[]> {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/jobs?limit=${limit}`, { headers })
  if (!res.ok) return []
  const data: JobsListResponse = await res.json()
  return data.jobs ?? []
}

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'MOCK_PROMPT_ONLY'])

export async function pollUntilComplete(
  jobId: string,
  onLabel?: (label: string) => void
): Promise<JobRecord> {
  const labels = ['Processing video…', 'Rendering frames…', 'Almost there…', 'Finalising…']
  let labelIdx = 0

  for (let attempt = 0; attempt < 120; attempt++) {
    await new Promise(r => setTimeout(r, 4000))
    const job = await getJobStatus(jobId)

    if (job.status === 'IN_PROGRESS' || job.status === 'IN_QUEUE') {
      onLabel?.(labels[labelIdx % labels.length])
      labelIdx++
    }

    if (TERMINAL.has(job.status)) {
      if (job.status === 'FAILED') {
        throw new Error(job.error ?? 'Video generation failed')
      }
      return job
    }
  }
  throw new Error('Generation timed out — check the dashboard for updates.')
}

export function downloadUrl(jobId: string) {
  return `${BASE}/api/download/${jobId}`
}
