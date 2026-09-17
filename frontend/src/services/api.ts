// Production is served from IIS with the API reverse-proxied under /api.
// VITE_API_BASE_URL remains available for local development overrides.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

async function apiFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `API error ${res.status}: ${path}`)
  }
  return res.json()
}

export async function getDatasetStatus() {
  return apiFetch('/dataset-status')
}

export async function getQuality() {
  return apiFetch('/quality')
}

export async function runIngestion() {
  return apiFetch('/ingest', { method: 'POST' })
}

export async function startIngestion(payload?: { override_existing?: boolean; password?: string }) {
  return apiFetch('/ingest/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  })
}

export async function getIngestionProgress(jobId: string) {
  return apiFetch(`/ingest/progress/${encodeURIComponent(jobId)}`)
}

export async function getIngestionErrors(runId?: string) {
  const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
  return apiFetch(`/ingestion-errors${suffix}`)
}

export async function getIngestionOverview() {
  return apiFetch('/ingestion/overview')
}

export async function getSignalCoverage(runId?: string) {
  const suffix = runId ? `?assessment_run_id=${encodeURIComponent(runId)}` : ''
  return apiFetch(`/signal-coverage${suffix}`)
}

export async function getReferenceChecks() {
  return apiFetch('/reference-checks')
}

export async function getSchemaSummary() {
  return apiFetch('/schema-summary')
}

export async function getManifest(status?: string, limit = 25, offset = 0, query?: string) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) params.set('status', status)
  if (query) params.set('query', query)
  const suffix = `?${params.toString()}`
  return apiFetch(`/manifest${suffix}`)
}

export async function generateActivations() {
  return apiFetch('/activations/generate', { method: 'POST' })
}

export async function getActivations() {
  return apiFetch('/activations')
}

export async function askLeadershipChat(question: string) {
  return apiFetch('/leadership-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export async function askLeadershipChatAdvanced(payload: {
  question: string
  signal_instance_id?: string
  mode: 'EXECUTIVE' | 'ANALYST'
  history_enabled: boolean
  history: Array<{ role: 'user' | 'assistant'; content: string }>
  context?: Record<string, unknown>
}) {
  return apiFetch('/leadership-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function evaluateSignals() {
  return apiFetch('/signals/evaluate', { method: 'POST' })
}

export async function getSignals(filters?: {
  severity?: string
  signal_type?: string
  workflow_status?: string
  business_priority?: string
  governance_status?: string
  assessment_run_id?: string
  module?: string
  truth_validation_status?: string
}) {
  const params = new URLSearchParams()
  if (filters?.severity) params.set('severity', filters.severity)
  if (filters?.signal_type) params.set('signal_type', filters.signal_type)
  if (filters?.workflow_status) params.set('workflow_status', filters.workflow_status)
  if (filters?.business_priority) params.set('business_priority', filters.business_priority)
  if (filters?.governance_status) params.set('governance_status', filters.governance_status)
  if (filters?.assessment_run_id) params.set('assessment_run_id', filters.assessment_run_id)
  if (filters?.module) params.set('module', filters.module)
  if (filters?.truth_validation_status) params.set('truth_validation_status', filters.truth_validation_status)
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiFetch(`/signals${suffix}`)
}

export async function getSignal(id: string) {
  return apiFetch(`/signals/${encodeURIComponent(id)}`)
}

export async function getSignalEvidence(id: string) {
  return apiFetch(`/signals/${encodeURIComponent(id)}/evidence`)
}

export async function getSignalHistory(id: string) {
  return apiFetch(`/signals/${encodeURIComponent(id)}/history`)
}

export async function getSignalComparisons(id: string) {
  return apiFetch(`/signals/${encodeURIComponent(id)}/comparisons`)
}

// ── Interventions ─────────────────────────────────────────────────────────────

export async function getInterventions(params?: { brand_id?: string; status?: string; signal_instance_id?: string }) {
  const q = new URLSearchParams()
  if (params?.brand_id) q.set('brand_id', params.brand_id)
  if (params?.status) q.set('status', params.status)
  if (params?.signal_instance_id) q.set('signal_instance_id', params.signal_instance_id)
  const suffix = q.toString() ? `?${q.toString()}` : ''
  return apiFetch(`/interventions${suffix}`)
}

export async function getIntervention(id: string) {
  return apiFetch(`/interventions/${encodeURIComponent(id)}`)
}

export async function createIntervention(payload: object) {
  return apiFetch('/interventions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function updateIntervention(id: string, payload: object) {
  return apiFetch(`/interventions/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function transitionIntervention(id: string, target_status: string) {
  return apiFetch(`/interventions/${encodeURIComponent(id)}/transition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_status }),
  })
}

export async function generateBrief(id: string) {
  return apiFetch(`/interventions/${encodeURIComponent(id)}/generate-brief`, {
    method: 'POST',
  })
}

export async function measureIntervention(id: string, post_change_run_id: string) {
  return apiFetch(`/interventions/${encodeURIComponent(id)}/measure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ post_change_run_id }),
  })
}

export async function getInterventionOutcome(id: string) {
  return apiFetch(`/interventions/${encodeURIComponent(id)}/outcome`)
}

// ── Outcomes ──────────────────────────────────────────────────────────────────

export async function getOutcomes() {
  return apiFetch('/outcomes')
}

// ── Truth registry ────────────────────────────────────────────────────────────

export async function getClaims(brand_id?: string) {
  const suffix = brand_id ? `?brand_id=${encodeURIComponent(brand_id)}` : ''
  return apiFetch(`/truth/claims${suffix}`)
}

export async function getContentAssets(brand_id?: string) {
  const suffix = brand_id ? `?brand_id=${encodeURIComponent(brand_id)}` : ''
  return apiFetch(`/truth/content-assets${suffix}`)
}

export async function getPromptPriorities(brand_id?: string) {
  const suffix = brand_id ? `?brand_id=${encodeURIComponent(brand_id)}` : ''
  return apiFetch(`/truth/prompts${suffix}`)
}

export async function seedFixtures() {
  return apiFetch('/seed-fixtures', { method: 'POST' })
}

// ── Signal rules & governance ─────────────────────────────────────────────────

export async function getSignalRules() {
  return apiFetch('/signal-rules')
}

// ── Metric contracts ──────────────────────────────────────────────────────────

export async function getMetricContracts() {
  return apiFetch('/metric-contracts')
}

export async function getSchemaContracts() {
  return apiFetch('/schema-contracts')
}

export async function getAssessmentRuns() {
  return apiFetch('/assessment-runs')
}

export async function getSemanticBlockers() {
  return apiFetch('/semantic-blockers')
}

export async function getVendorQuestions() {
  return apiFetch('/vendor-questions')
}

// ── AI Health ─────────────────────────────────────────────────────────────────

export async function getAIHealth() {
  return apiFetch('/health/ai')
}

export async function getCurrentContext() {
  return apiFetch('/context/current')
}

export async function getEvidence(params?: {
  query?: string
  evidence_type?: string
  assessment_run_id?: string
  signal_instance_id?: string
  limit?: number
  offset?: number
}) {
  const q = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== '') q.set(key, String(value))
  })
  return apiFetch(`/evidence${q.toString() ? `?${q.toString()}` : ''}`)
}
