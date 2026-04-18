// ── Supabase client ────────────────────────────────────────────────────────
let _supabase = null;
function getSupabase() {
  if (!_supabase && window.supabase && window.SUPABASE_URL && window.SUPABASE_ANON_KEY) {
    _supabase = window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_ANON_KEY);
  }
  return _supabase;
}

// ── Auth helpers ───────────────────────────────────────────────────────────
async function authHeaders() {
  const sb = getSupabase();
  if (!sb) return {};
  const { data: { session } } = await sb.auth.getSession();
  if (!session?.user) return {};
  return { 'X-User-ID': session.user.id };
}

// ── API functions ──────────────────────────────────────────────────────────
async function _apiFetch(path, options = {}) {
  const headers = await authHeaders();
  const res = await fetch(path, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || j.message || detail; } catch (_) {}
    if (Array.isArray(detail)) detail = detail.map(e => e.msg || JSON.stringify(e)).join('; ');
    throw new Error(detail);
  }
  return res.json();
}

window.apiStartChat = async function(formData) {
  const headers = await authHeaders();
  const res = await fetch('/api/chat/start', { method: 'POST', headers, body: formData });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
};

window.apiConfirmChat = function(body) {
  return _apiFetch('/api/chat/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
};

window.apiChatMessage = function(body) {
  return _apiFetch('/api/chat/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
};

window.apiGenerateVideo = function(body) {
  return _apiFetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
};

window.apiGetJobStatus = function(jobId) {
  return _apiFetch(`/api/status/${jobId}`);
};

window.apiListJobs = async function(limit = 50) {
  try {
    const data = await _apiFetch(`/api/jobs?limit=${limit}`);
    return data.jobs || [];
  } catch (_) {
    return [];
  }
};

const _TERMINAL = new Set(['COMPLETED', 'FAILED', 'MOCK_PROMPT_ONLY']);

window.apiPollUntilComplete = async function(jobId, onLabel) {
  const labels = ['Processing video…', 'Rendering frames…', 'Almost there…', 'Finalising…'];
  let labelIdx = 0;
  for (let attempt = 0; attempt < 120; attempt++) {
    await new Promise(r => setTimeout(r, 4000));
    const job = await window.apiGetJobStatus(jobId);
    if (job.status === 'IN_PROGRESS' || job.status === 'IN_QUEUE') {
      if (onLabel) onLabel(labels[labelIdx % labels.length]);
      labelIdx++;
    }
    if (_TERMINAL.has(job.status)) {
      if (job.status === 'FAILED') throw new Error(job.error || 'Video generation failed');
      return job;
    }
  }
  throw new Error('Generation timed out — check the dashboard for updates.');
};

window.downloadUrl = function(jobId) {
  return `/api/download/${jobId}`;
};

// ── Alpine.js stores & components ─────────────────────────────────────────
document.addEventListener('alpine:init', () => {

  // Toast store
  Alpine.store('toasts', {
    items: [],
    _id: 0,
    add(message, type) {
      const id = ++this._id;
      this.items.push({ id, message, type, visible: true });
      setTimeout(() => {
        const t = this.items.find(t => t.id === id);
        if (t) t.visible = false;
        setTimeout(() => { this.items = this.items.filter(t => t.id !== id); }, 300);
      }, 4000);
    },
    success(msg) { this.add(msg, 'success'); },
    error(msg) { this.add(msg, 'error'); },
  });

  window.toastSuccess = msg => Alpine.store('toasts').success(msg);
  window.toastError = msg => Alpine.store('toasts').error(msg);

  // Auth store
  Alpine.store('auth', {
    user: null,
    loading: true,

    get initials() {
      if (!this.user) return '?';
      const name = this.user.user_metadata?.full_name;
      if (name) return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
      return (this.user.email || '?').slice(0, 2).toUpperCase();
    },

    async init() {
      const sb = getSupabase();
      if (!sb) { this.loading = false; return; }
      const { data: { session } } = await sb.auth.getSession();
      this.user = session?.user || null;
      this.loading = false;
      sb.auth.onAuthStateChange((_event, session) => {
        this.user = session?.user || null;
      });
    },

    async signOut() {
      const sb = getSupabase();
      if (sb) await sb.auth.signOut();
      window.location.href = '/login';
    },
  });

});

// ── Page components ────────────────────────────────────────────────────────

// Navigate to /create, redirecting to login if not authenticated
window.createIfAuth = function() {
  const go = (user) => {
    window.location.href = user ? '/create' : '/login?next=/create';
  };
  const auth = Alpine.store('auth');
  if (!auth.loading) { go(auth.user); return; }
  const id = setInterval(() => {
    const a = Alpine.store('auth');
    if (!a.loading) { clearInterval(id); go(a.user); }
  }, 50);
};

window.loginPage = function() {
  return {
    tab: 'signin',
    email: '',
    password: '',
    fullName: '',
    loading: false,
    error: null,
    message: null,

    async submit() {
      this.loading = true;
      this.error = null;
      this.message = null;
      const sb = getSupabase();
      if (!sb) { this.error = 'Auth not configured.'; this.loading = false; return; }

      if (this.tab === 'signin') {
        const { error } = await sb.auth.signInWithPassword({ email: this.email, password: this.password });
        if (error) { this.error = error.message; }
        else {
          const params = new URLSearchParams(window.location.search);
          window.location.href = params.get('next') || '/';
        }
      } else {
        const { error } = await sb.auth.signUp({
          email: this.email,
          password: this.password,
          options: { data: { full_name: this.fullName } },
        });
        if (error) { this.error = error.message; }
        else { this.message = 'Check your email to confirm your account, then sign in.'; this.tab = 'signin'; }
      }
      this.loading = false;
    },
  };
};

const VIBES = [
  { id: 'energetic', name: 'Energetic', description: 'Fast cuts, bold typography, and punchy transitions.' },
  { id: 'luxury', name: 'Luxury', description: 'Premium tones, soft camera moves, polished pacing.' },
  { id: 'playful', name: 'Playful', description: 'Bright visuals and upbeat storytelling for social.' },
  { id: 'minimalist', name: 'Minimalist', description: 'Clean composition, calm rhythm, modern aesthetic.' },
  { id: 'cinematic', name: 'Cinematic', description: 'Dramatic reveals with immersive scene progression.' },
];

const CATEGORIES = ['Fashion', 'Electronics', 'Beauty', 'Food', 'Home', 'Other'];

const WIZARD_STEPS = ['Product', 'Style & Format', 'Result'];

const GENERATION_STEPS = [
  'Analyzing your product…',
  'Crafting your video prompt…',
  'Submitting to Seedance AI…',
  'Processing video…',
  'Rendering frames…',
  'Almost there…',
  'Finalising…',
];

const POLL_LABEL_TO_STEP = {
  'Processing video…': 3,
  'Rendering frames…': 4,
  'Almost there…': 5,
  'Finalising…': 6,
};

window.createWizard = function() {
  return {
    step: 1,
    generating: false,
    generationStepIdx: 0,
    aborted: false,

    // ── Step 1: product inputs ──
    uploadedFile: null,
    uploadedPreviewUrl: null,
    productName: '',
    productBrief: '',
    dragOver: false,

    // ── Step 1: AI chat state ──
    sessionId: null,
    chatMessages: [],   // [{role:'user'|'assistant', content:''}]
    chatInput: '',
    chatLoading: false,
    chatStarted: false,

    // ── Step 2: style ──
    vibes: VIBES,
    vibeId: 'energetic',
    targetAudience: '',
    ctaText: 'Shop Now',
    resolution: '720p',
    aspectRatio: '16:9',
    duration: 'auto',
    generateAudio: true,

    durationOptions: [
      { label: 'Auto', value: 'auto' },
      { label: '5 s', value: '5' },
      { label: '8 s', value: '8' },
      { label: '10 s', value: '10' },
      { label: '15 s', value: '15' },
    ],

    generationSteps: GENERATION_STEPS,
    wizardSteps: WIZARD_STEPS,

    // ── Step 3 ──
    jobId: null,
    resultVideoUrl: null,

    init() {
      const guard = () => {
        if (!Alpine.store('auth').user) window.location.href = '/login?next=/create';
      };
      if (!Alpine.store('auth').loading) { guard(); return; }
      const id = setInterval(() => {
        if (!Alpine.store('auth').loading) { clearInterval(id); guard(); }
      }, 50);
    },

    get currentVibe() {
      return this.vibes.find(v => v.id === this.vibeId) || this.vibes[0];
    },

    get stepperStep() {
      return this.generating ? 2 : this.step;
    },

    // ── File handling ─────────────────────────────────────────────────────
    onFileChange(event) {
      const file = event.target.files[0];
      if (file) this._setFile(file);
    },

    onDrop(event) {
      this.dragOver = false;
      const file = event.dataTransfer.files[0];
      if (!file || !file.type.startsWith('image/')) { window.toastError('Please drop an image file.'); return; }
      this._setFile(file);
    },

    _setFile(file) {
      if (this.uploadedPreviewUrl?.startsWith('blob:')) URL.revokeObjectURL(this.uploadedPreviewUrl);
      this.uploadedFile = file;
      this.uploadedPreviewUrl = URL.createObjectURL(file);
    },

    clearFile() {
      if (this.uploadedPreviewUrl?.startsWith('blob:')) URL.revokeObjectURL(this.uploadedPreviewUrl);
      this.uploadedFile = null;
      this.uploadedPreviewUrl = null;
    },

    // ── AI Chat ──────────────────────────────────────────────────────────
    async startAnalysis() {
      if (!this.uploadedFile) { window.toastError('Upload a product image first.'); return; }
      if (!this.productName.trim()) { window.toastError('Enter a product name.'); return; }
      if (!this.productBrief.trim()) { window.toastError('Add a brief description of your product.'); return; }

      this.chatLoading = true;
      const brief = `Product: ${this.productName}\n${this.productBrief.trim()}`;
      try {
        const fd = new FormData();
        fd.append('brief', brief);
        fd.append('product_images', this.uploadedFile, this.uploadedFile.name);
        const res = await window.apiStartChat(fd);
        this.sessionId = res.session_id;
        this.chatMessages = [
          { role: 'user', content: brief },
          { role: 'assistant', content: res.message },
        ];
        this.chatStarted = true;
        this.$nextTick(() => this._scrollChat());
      } catch (err) {
        window.toastError(err.message || 'Analysis failed.');
      } finally {
        this.chatLoading = false;
      }
    },

    async sendChatMessage() {
      const text = this.chatInput.trim();
      if (!text || this.chatLoading) return;
      this.chatInput = '';
      this.chatMessages.push({ role: 'user', content: text });
      this.$nextTick(() => this._scrollChat());
      this.chatLoading = true;
      try {
        const res = await window.apiChatMessage({ session_id: this.sessionId, message: text });
        this.chatMessages.push({ role: 'assistant', content: res.message });
        this.$nextTick(() => this._scrollChat());
      } catch (err) {
        window.toastError(err.message || 'Message failed.');
      } finally {
        this.chatLoading = false;
      }
    },

    _scrollChat() {
      const el = document.getElementById('chat-messages');
      if (el) el.scrollTop = el.scrollHeight;
    },

    resetChat() {
      this.sessionId = null;
      this.chatMessages = [];
      this.chatInput = '';
      this.chatStarted = false;
      this.chatLoading = false;
    },

    // ── Video generation ─────────────────────────────────────────────────
    async runGeneration(overrideVibeId) {
      this.aborted = false;
      this.generating = true;
      this.generationStepIdx = 0;

      try {
        // sessionId exists when user went through chat; build one on-the-fly for re-generate
        let sid = this.sessionId;
        if (!sid) {
          const vibe = overrideVibeId
            ? (this.vibes.find(v => v.id === overrideVibeId) || this.currentVibe)
            : this.currentVibe;
          const brief = [
            `Product: ${this.productName}`,
            this.productBrief.trim() || null,
            `Style: ${vibe.name} — ${vibe.description}`,
            this.targetAudience ? `Target audience: ${this.targetAudience}` : null,
            this.ctaText ? `Call to action: "${this.ctaText}"` : null,
          ].filter(Boolean).join('\n');
          const fd = new FormData();
          fd.append('brief', brief);
          if (this.uploadedFile) fd.append('product_images', this.uploadedFile, this.uploadedFile.name);
          const startRes = await window.apiStartChat(fd);
          sid = startRes.session_id;
          this.sessionId = sid;
        }
        if (this.aborted) return;
        this.generationStepIdx = 1;

        const preview = await window.apiConfirmChat({
          session_id: sid,
          mode: this.uploadedFile ? 'image-to-video' : 'text-to-video',
          resolution: this.resolution,
          duration: this.duration,
          aspect_ratio: this.aspectRatio,
          generate_audio: this.generateAudio,
        });
        if (this.aborted) return;
        this.generationStepIdx = 2;

        const { job_id } = await window.apiGenerateVideo({ preview_id: preview.preview_id });
        this.jobId = job_id;
        if (this.aborted) return;

        const job = await window.apiPollUntilComplete(job_id, (label) => {
          this.generationStepIdx = POLL_LABEL_TO_STEP[label] ?? 3;
        });

        this.resultVideoUrl = job.video_url || window.downloadUrl(job_id);
        this.step = 3;
        this.generating = false;
        window.toastSuccess('Your video is ready.');
      } catch (err) {
        if (this.aborted) return;
        this.generating = false;
        window.toastError(err.message || 'Generation failed');
      }
    },

    onNext() {
      if (this.step === 1) {
        if (!this.chatStarted) { this.startAnalysis(); return; }
        this.step = 2;
        return;
      }
      if (this.step === 2) {
        if (!this.ctaText.trim()) { window.toastError('Call to action is required.'); return; }
        this.runGeneration();
      }
    },

    onBack() {
      if (this.step === 2) this.step = 1;
    },

    reset() {
      this.aborted = true;
      this.generating = false;
      this.clearFile();
      this.productName = '';
      this.productBrief = '';
      this.resetChat();
      this.targetAudience = '';
      this.ctaText = 'Shop Now';
      this.resolution = '720p';
      this.aspectRatio = '16:9';
      this.duration = 'auto';
      this.generateAudio = true;
      this.vibeId = this.vibes[0].id;
      this.jobId = null;
      this.resultVideoUrl = null;
      this.step = 1;
    },
  };
};

window.dashboardPage = function() {
  return {
    jobs: [],
    loading: true,

    STATUS_LABEL: {
      IN_QUEUE: 'Queued',
      IN_PROGRESS: 'Generating',
      COMPLETED: 'Done',
      FAILED: 'Failed',
      MOCK_PROMPT_ONLY: 'Preview only',
    },
    STATUS_CSS: {
      IN_QUEUE: 'status-queued',
      IN_PROGRESS: 'status-progress',
      COMPLETED: 'status-done',
      FAILED: 'status-failed',
      MOCK_PROMPT_ONLY: 'status-mock',
    },
    TERMINAL: ['COMPLETED', 'FAILED', 'MOCK_PROMPT_ONLY'],

    get ordered() {
      const terminal = this.TERMINAL;
      const active = this.jobs.filter(j => !terminal.includes(j.status));
      const completed = this.jobs.filter(j => j.status === 'COMPLETED');
      const mock = this.jobs.filter(j => j.status === 'MOCK_PROMPT_ONLY');
      const failed = this.jobs.filter(j => j.status === 'FAILED');
      return [...active, ...completed, ...mock, ...failed];
    },

    statusLabel(s) { return this.STATUS_LABEL[s] || s; },
    statusCss(s) { return this.STATUS_CSS[s] || 'status-mock'; },

    formatDate(d) {
      return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

    shortPrompt(p) { return p.slice(0, 60) + (p.length > 60 ? '…' : ''); },
    downloadUrl(id) { return window.downloadUrl(id); },

    init() {
      this.loadJobs();
      const id = setInterval(() => this.loadJobs(), 10000);
      return () => clearInterval(id);
    },

    async loadJobs() {
      this.jobs = await window.apiListJobs(50);
      this.loading = false;
    },
  };
};

window.profilePage = function() {
  return {
    user: null,
    loading: true,

    async init() {
      const sb = getSupabase();
      if (!sb) { this.loading = false; return; }
      const { data: { user } } = await sb.auth.getUser();
      this.user = user;
      this.loading = false;
    },

    get displayName() {
      if (!this.user) return '';
      return this.user.user_metadata?.full_name || this.user.email || '';
    },

    get initials() {
      if (!this.user) return '?';
      const name = this.user.user_metadata?.full_name;
      if (name) return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
      return (this.user.email || '?').slice(0, 2).toUpperCase();
    },
  };
};
