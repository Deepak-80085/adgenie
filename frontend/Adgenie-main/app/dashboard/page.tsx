'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { EmptyState } from '@/components/shared/empty-state'
import { Footer } from '@/components/shared/footer'
import { PageTransition } from '@/components/shared/page-transition'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { listJobs, downloadUrl, type JobRecord } from '@/lib/api'

const STATUS_LABEL: Record<string, string> = {
  IN_QUEUE: 'Queued',
  IN_PROGRESS: 'Generating',
  COMPLETED: 'Done',
  FAILED: 'Failed',
  MOCK_PROMPT_ONLY: 'Preview only',
}

const STATUS_CLASS: Record<string, string> = {
  IN_QUEUE: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  IN_PROGRESS: 'bg-blue-50 text-blue-700 border-blue-200',
  COMPLETED: 'bg-green-50 text-green-700 border-green-200',
  FAILED: 'bg-red-50 text-red-700 border-red-200',
  MOCK_PROMPT_ONLY: 'bg-gray-50 text-gray-600 border-gray-200',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${STATUS_CLASS[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

function JobCard({ job }: { job: JobRecord }) {
  const date = new Date(job.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
  const title = job.user_prompt.slice(0, 60) + (job.user_prompt.length > 60 ? '…' : '')

  return (
    <Card className="overflow-hidden">
      {/* Video or placeholder */}
      <div className="relative aspect-video w-full overflow-hidden bg-[var(--secondary)]">
        {job.status === 'COMPLETED' && job.video_url ? (
          <video
            src={job.video_url}
            className="h-full w-full object-cover"
            controls
            playsInline
            preload="metadata"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <StatusBadge status={job.status} />
          </div>
        )}
      </div>

      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="line-clamp-2 font-[var(--font-instrument-serif)] text-[18px] leading-tight">{title}</p>
          <StatusBadge status={job.status} />
        </div>

        <p data-meta className="text-[11px] uppercase tracking-wide">
          {job.resolution} · {job.aspect_ratio} · {date}
        </p>

        {job.status === 'FAILED' && job.error && (
          <p className="text-xs text-red-600 border border-red-200 bg-red-50 px-2 py-1.5">{job.error}</p>
        )}

        {job.status === 'COMPLETED' && (
          <div className="flex gap-2">
            <Button asChild size="sm" variant="default">
              <a href={downloadUrl(job.job_id)} download={`${job.job_id}.mp4`}>Download</a>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listJobs(50).then(j => { setJobs(j); setLoading(false) })

    // Auto-refresh every 10 s so in-progress jobs update
    const id = setInterval(() => listJobs(50).then(setJobs), 10_000)
    return () => clearInterval(id)
  }, [])

  const TERMINAL = new Set(['COMPLETED', 'FAILED', 'MOCK_PROMPT_ONLY'])
  const completed = jobs.filter(j => j.status === 'COMPLETED')
  const mock = jobs.filter(j => j.status === 'MOCK_PROMPT_ONLY')
  const active = jobs.filter(j => !TERMINAL.has(j.status))
  const failed = jobs.filter(j => j.status === 'FAILED')
  const ordered = [...active, ...completed, ...mock, ...failed]

  return (
    <PageTransition>
      <div className="mx-auto w-full max-w-[1200px] space-y-12 px-5 py-12 md:px-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <p data-meta>Archive</p>
            <h1 className="text-[36px] tracking-tight sm:text-[48px]">Your generated videos</h1>
          </div>
          <Button asChild variant="default">
            <Link href="/create">Create ad</Link>
          </Button>
        </div>

        {loading ? (
          <p data-meta>Loading archive…</p>
        ) : ordered.length ? (
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-2">
            {ordered.map(job => (
              <JobCard key={job.job_id} job={job} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No videos yet"
            description="Start a new generation to build your archive."
            cta="Create ad"
          />
        )}
      </div>
      <Footer />
    </PageTransition>
  )
}
