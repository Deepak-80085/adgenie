'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { GeneratingLoader } from '@/components/create/generating-loader'
import { UploadZone } from '@/components/create/upload-zone'
import { VibeSelector } from '@/components/create/vibe-selector'
import { WizardStepper } from '@/components/create/wizard-stepper'
import { Footer } from '@/components/shared/footer'
import { PageTransition } from '@/components/shared/page-transition'
import { VideoPlayer } from '@/components/shared/video-player'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { productCategories, vibePresets } from '@/lib/mock-data'
import * as api from '@/lib/api'

const WIZARD_STEPS = ['Product', 'Style & Format', 'Result']
const DURATION_OPTIONS = [
  { label: 'Auto', value: 'auto' },
  { label: '5 s', value: '5' },
  { label: '8 s', value: '8' },
  { label: '10 s', value: '10' },
  { label: '15 s', value: '15' },
]
const GENERATION_STEPS = [
  'Analyzing your product…',
  'Crafting your video prompt…',
  'Submitting to Seedance AI…',
  'Processing video…',
  'Rendering frames…',
  'Almost there…',
  'Finalising…',
]
const POLL_LABEL_TO_STEP: Record<string, number> = {
  'Processing video…': 3,
  'Rendering frames…': 4,
  'Almost there…': 5,
  'Finalising…': 6,
}

export default function CreatePage() {
  const router = useRouter()

  // ── step 1: product ───────────────────────────────────────────────────────
  const [uploadedPreviewUrl, setUploadedPreviewUrl] = useState<string | null>(null)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [productName, setProductName] = useState('')
  const [productCategory, setProductCategory] = useState('Fashion')
  const [productBrief, setProductBrief] = useState('')

  // ── step 2: style & format ────────────────────────────────────────────────
  const [vibeId, setVibeId] = useState(vibePresets[0].id)
  const [targetAudience, setTargetAudience] = useState('')
  const [ctaText, setCtaText] = useState('Shop Now')
  const [resolution, setResolution] = useState<'480p' | '720p'>('720p')
  const [aspectRatio, setAspectRatio] = useState('16:9')
  const [duration, setDuration] = useState('auto')
  const [generateAudio, setGenerateAudio] = useState(true)

  // ── wizard ────────────────────────────────────────────────────────────────
  const [currentStep, setCurrentStep] = useState(1)

  // ── generation state ──────────────────────────────────────────────────────
  const [generationStepIdx, setGenerationStepIdx] = useState(0)
  const [isGenerating, setIsGenerating] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [resultVideoUrl, setResultVideoUrl] = useState<string | null>(null)

  const abortRef = useRef(false)

  const onUploadImage = (file: File | null) => {
    if (uploadedPreviewUrl?.startsWith('blob:')) URL.revokeObjectURL(uploadedPreviewUrl)
    if (!file) { setUploadedPreviewUrl(null); setUploadedFile(null); return }
    setUploadedPreviewUrl(URL.createObjectURL(file))
    setUploadedFile(file)
  }

  useEffect(() => {
    return () => { if (uploadedPreviewUrl?.startsWith('blob:')) URL.revokeObjectURL(uploadedPreviewUrl) }
  }, [uploadedPreviewUrl])

  const selectedVibe = useMemo(
    () => vibePresets.find(v => v.id === vibeId) ?? vibePresets[0],
    [vibeId]
  )

  function buildBrief(overrideVibeId?: string) {
    const vibe = overrideVibeId
      ? (vibePresets.find(v => v.id === overrideVibeId) ?? selectedVibe)
      : selectedVibe
    const parts = [
      productBrief.trim() ? productBrief.trim() : null,
      `Product: ${productName}${productCategory ? ` (${productCategory})` : ''}`,
      `Style: ${vibe.name} — ${vibe.description}`,
      targetAudience ? `Target audience: ${targetAudience}` : null,
      ctaText ? `Call to action: "${ctaText}"` : null,
    ].filter(Boolean)
    return parts.join('\n')
  }

  const runGeneration = async (overrideVibeId?: string) => {
    abortRef.current = false
    setIsGenerating(true)
    setGenerationStepIdx(0)

    try {
      const fd = new FormData()
      fd.append('brief', buildBrief(overrideVibeId))
      if (uploadedFile) fd.append('product_images', uploadedFile, uploadedFile.name)
      const { session_id } = await api.startChat(fd)

      if (abortRef.current) return
      setGenerationStepIdx(1)

      const preview = await api.confirmChat({
        session_id,
        mode: uploadedFile ? 'image-to-video' : 'text-to-video',
        resolution,
        duration,
        aspect_ratio: aspectRatio,
        generate_audio: generateAudio,
      })

      if (abortRef.current) return
      setGenerationStepIdx(2)

      const { job_id } = await api.generateVideo({ preview_id: preview.preview_id })
      setJobId(job_id)

      if (abortRef.current) return

      const job = await api.pollUntilComplete(job_id, (label) => {
        setGenerationStepIdx(POLL_LABEL_TO_STEP[label] ?? 3)
      })

      setResultVideoUrl(job.video_url ?? api.downloadUrl(job_id))
      setCurrentStep(3)
      setIsGenerating(false)
      toast.success('Your video is ready.')
    } catch (err) {
      if (abortRef.current) return
      setIsGenerating(false)
      toast.error(err instanceof Error ? err.message : 'Generation failed')
    }
  }

  const onNext = () => {
    if (currentStep === 1) {
      if (!uploadedFile) { toast.error('Upload a product image to continue.'); return }
      if (!productName.trim()) { toast.error('Enter a product name.'); return }
      setCurrentStep(2); return
    }
    if (currentStep === 2) {
      if (!ctaText.trim()) { toast.error('Call to action is required.'); return }
      void runGeneration()
    }
  }

  const onBack = () => {
    if (currentStep === 2) setCurrentStep(1)
  }

  const resetFlow = () => {
    abortRef.current = true
    setIsGenerating(false)
    if (uploadedPreviewUrl?.startsWith('blob:')) URL.revokeObjectURL(uploadedPreviewUrl)
    setUploadedPreviewUrl(null); setUploadedFile(null)
    setProductName(''); setProductCategory('Fashion'); setProductBrief('')
    setTargetAudience(''); setCtaText('Shop Now')
    setResolution('720p'); setAspectRatio('16:9'); setDuration('auto'); setGenerateAudio(true)
    setVibeId(vibePresets[0].id)
    setJobId(null); setResultVideoUrl(null)
    setCurrentStep(1)
  }

  // ── display step for stepper: during generation show step 2 with loader overlay
  const stepperStep = isGenerating ? 2 : currentStep

  return (
    <PageTransition>
      <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8 sm:px-6 sm:py-12">

        <div className="space-y-1">
          <p data-meta>Create</p>
          <h1 className="text-[32px] tracking-tight sm:text-[42px]">New Video Ad</h1>
        </div>

        <WizardStepper steps={WIZARD_STEPS} currentStep={stepperStep} />

        {/* ── Generating overlay (shown on top of step 2 during generation) ── */}
        {isGenerating && (
          <GeneratingLoader currentIndex={generationStepIdx} steps={GENERATION_STEPS} />
        )}

        {/* ── Step 1: Product ── */}
        {currentStep === 1 && !isGenerating && (
          <Card>
            <CardHeader>
              <CardTitle>Your product</CardTitle>
              <p className="text-sm text-[var(--muted-foreground)]">
                Upload a clean image of your product and tell us what it is.
              </p>
            </CardHeader>
            <CardContent className="space-y-6">
              <UploadZone previewUrl={uploadedPreviewUrl} onFileChange={onUploadImage} />

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="product-name">Product Name <span className="text-red-500">*</span></Label>
                  <Input
                    id="product-name"
                    value={productName}
                    onChange={e => setProductName(e.target.value)}
                    placeholder="e.g. Titon Watch"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="category">Category</Label>
                  <select
                    id="category"
                    value={productCategory}
                    onChange={e => setProductCategory(e.target.value)}
                    className="h-11 w-full rounded-sm border border-[var(--border)] bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--foreground)]"
                  >
                    {productCategories.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="brief">
                  Product Brief
                  <span className="ml-1 text-[var(--muted-foreground)] font-normal text-xs">(optional but recommended)</span>
                </Label>
                <textarea
                  id="brief"
                  value={productBrief}
                  onChange={e => setProductBrief(e.target.value)}
                  rows={3}
                  placeholder="What makes this product special? Who is it for? What story do you want to tell?"
                  className="w-full resize-none rounded-sm border border-[var(--border)] bg-transparent px-3 py-2.5 text-sm leading-relaxed focus:outline-none focus:ring-1 focus:ring-[var(--foreground)]"
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Step 2: Style & Format ── */}
        {currentStep === 2 && !isGenerating && (
          <Card>
            <CardHeader>
              <CardTitle>Style & format</CardTitle>
              <p className="text-sm text-[var(--muted-foreground)]">
                Choose the mood of your video and configure output settings.
              </p>
            </CardHeader>
            <CardContent className="space-y-8">

              {/* Vibe */}
              <div className="space-y-2">
                <Label>Vibe</Label>
                <VibeSelector vibes={vibePresets} selectedId={vibeId} onSelect={setVibeId} />
              </div>

              {/* Audience + CTA */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="audience">Target Audience <span className="font-normal text-xs text-[var(--muted-foreground)]">(optional)</span></Label>
                  <Input
                    id="audience"
                    value={targetAudience}
                    onChange={e => setTargetAudience(e.target.value)}
                    placeholder="e.g. Young professionals"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cta">Call to Action <span className="text-red-500">*</span></Label>
                  <Input
                    id="cta"
                    value={ctaText}
                    onChange={e => setCtaText(e.target.value)}
                    placeholder="e.g. Shop Now"
                  />
                </div>
              </div>

              {/* Format controls */}
              <div className="space-y-4 border-t border-[var(--border)] pt-6">
                <p className="text-sm font-medium">Video format</p>

                <div className="grid gap-6 sm:grid-cols-2">
                  {/* Resolution */}
                  <div className="space-y-2">
                    <Label>Resolution</Label>
                    <div className="flex gap-2">
                      {(['480p', '720p'] as const).map(r => (
                        <button
                          key={r}
                          type="button"
                          onClick={() => setResolution(r)}
                          className={`flex-1 border py-2 text-sm font-medium transition-colors ${resolution === r ? 'border-[var(--foreground)] bg-[var(--foreground)] text-[var(--background)]' : 'border-[var(--border)] hover:border-[var(--foreground)]'}`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Duration */}
                  <div className="space-y-2">
                    <Label>Duration</Label>
                    <div className="flex flex-wrap gap-2">
                      {DURATION_OPTIONS.map(opt => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setDuration(opt.value)}
                          className={`border px-3 py-2 text-sm font-medium transition-colors ${duration === opt.value ? 'border-[var(--foreground)] bg-[var(--foreground)] text-[var(--background)]' : 'border-[var(--border)] hover:border-[var(--foreground)]'}`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Aspect ratio */}
                <div className="space-y-2">
                  <Label>Aspect Ratio</Label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: '16:9  Landscape', value: '16:9' },
                      { label: '9:16  Portrait', value: '9:16' },
                      { label: '1:1  Square', value: '1:1' },
                    ].map(ar => (
                      <button
                        key={ar.value}
                        type="button"
                        onClick={() => setAspectRatio(ar.value)}
                        className={`border px-3 py-2 text-sm font-medium transition-colors ${aspectRatio === ar.value ? 'border-[var(--foreground)] bg-[var(--foreground)] text-[var(--background)]' : 'border-[var(--border)] hover:border-[var(--foreground)]'}`}
                      >
                        {ar.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Audio toggle */}
                <div className="flex items-center justify-between rounded-sm border border-[var(--border)] px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">AI-generated audio</p>
                    <p className="text-xs text-[var(--muted-foreground)]">Seedance will compose synchronized sound for the video</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={generateAudio}
                    onClick={() => setGenerateAudio(v => !v)}
                    className={`relative inline-flex h-6 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--foreground)] focus:ring-offset-2 ${generateAudio ? 'bg-[var(--foreground)]' : 'bg-[var(--border)]'}`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-[var(--background)] shadow ring-0 transition duration-200 ease-in-out ${generateAudio ? 'translate-x-4' : 'translate-x-0'}`}
                    />
                  </button>
                </div>
              </div>

            </CardContent>
          </Card>
        )}

        {/* ── Step 3: Result ── */}
        {currentStep === 3 && resultVideoUrl && !isGenerating && (
          <div className="space-y-6">
            <Card>
              <CardHeader><CardTitle>Your video is ready</CardTitle></CardHeader>
              <CardContent className="space-y-5">
                <VideoPlayer src={resultVideoUrl} title={productName} />

                <div className="flex flex-wrap gap-2 sm:gap-3">
                  <Button asChild>
                    <a href={jobId ? `/api/download/${jobId}` : resultVideoUrl} download={`${productName}.mp4`}>
                      Download
                    </a>
                  </Button>
                  <Button variant="outline" onClick={() => { void navigator.clipboard.writeText(window.location.href); toast.success('Link copied.') }}>
                    Share
                  </Button>
                  <Button variant="outline" onClick={() => void runGeneration()}>
                    Regenerate
                  </Button>
                  <Button variant="secondary" onClick={resetFlow}>
                    New Video
                  </Button>
                  {jobId && (
                    <Button variant="ghost" onClick={() => router.push('/dashboard')}>
                      View in Library
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Quick re-style panel */}
            <div className="space-y-3 border border-[var(--border)] p-4">
              <p className="text-sm font-medium">Try a different vibe</p>
              <div className="flex flex-wrap gap-2">
                {vibePresets.map(vibe => (
                  <button
                    key={vibe.id}
                    type="button"
                    onClick={() => { setVibeId(vibe.id); void runGeneration(vibe.id) }}
                    className={`border px-3 py-1.5 text-xs transition-colors ${vibe.id === vibeId ? 'border-[var(--foreground)] bg-[var(--surface)]' : 'border-[var(--border)] hover:border-[var(--foreground)]'}`}
                  >
                    {vibe.name}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Nav buttons ── */}
        {!isGenerating && currentStep < 3 && (
          <div className="flex items-center justify-between gap-3">
            <Button variant="outline" onClick={onBack} disabled={currentStep === 1}>
              Back
            </Button>
            <Button onClick={onNext}>
              {currentStep === 2 ? 'Generate Video' : 'Continue'}
            </Button>
          </div>
        )}

      </div>
      <Footer />
    </PageTransition>
  )
}
