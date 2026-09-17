import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getIntervention, updateIntervention, transitionIntervention,
  generateBrief, measureIntervention, getInterventionOutcome,
  getSignal
} from '../services/api'
import { formatLocalDateTime } from '../utils/dateTime'

const LIFECYCLE = [
  'DETECTED', 'NEEDS_DIAGNOSIS', 'NEEDS_TRUTH_VALIDATION',
  'READY_FOR_OWNER_REVIEW', 'APPROVED_FOR_BRIEF', 'IN_CREATION',
  'IN_MLR', 'APPROVED', 'PUBLISHED', 'AWAITING_RETEST', 'MEASURED', 'CLOSED',
]

const STATUS_COLOR: Record<string, string> = {
  NEEDS_DIAGNOSIS: '#ef4444', NEEDS_TRUTH_VALIDATION: '#f97316',
  READY_FOR_OWNER_REVIEW: '#eab308', APPROVED_FOR_BRIEF: '#3b82f6',
  IN_CREATION: '#8b5cf6', IN_MLR: '#ec4899', APPROVED: '#06b6d4',
  PUBLISHED: '#22c55e', AWAITING_RETEST: '#14b8a6', MEASURED: '#6366f1',
  CLOSED: '#6b7280', REJECTED: '#9ca3af', DETECTED: '#d97706',
  INSUFFICIENT_EVIDENCE: '#9ca3af',
}

const OUTCOME_COLOR: Record<string, string> = {
  IMPROVED: '#22c55e', NO_MATERIAL_CHANGE: '#eab308',
  DETERIORATED: '#ef4444', MIXED_BY_ENGINE: '#f97316',
  INCONCLUSIVE: '#6b7280', AWAITING_MORE_RUNS: '#3b82f6',
}

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined || !Number.isFinite(Number(value))
    ? 'Not available'
    : `${(Number(value) * 100).toFixed(1)}%`
}

interface Intervention {
  intervention_id: string
  signal_instance_id: string
  brand_id: string
  market: string
  business_problem: string
  diagnosed_cause: string
  recommended_action: string
  target_prompt_id: string | null
  target_product_id: string | null
  target_claim_id: string | null
  target_page_id: string | null
  approved_evidence: string | null
  risk_route: string | null
  owner: string | null
  approver: string | null
  status: string
  priority: string
  confidence: number
  baseline_run_id: string | null
  baseline_metric: number | null
  target_metric: number | null
  planned_publish_date: string | null
  actual_publish_date: string | null
  retest_date: string | null
  created_at: string | null
  updated_at: string | null
}

export function InterventionDetail() {
  const { id: interventionId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [iv, setIv] = useState<Intervention | null>(null)
  const [signal, setSignal] = useState<any>(null)
  const [outcome, setOutcome] = useState<any>(null)
  const [brief, setBrief] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [transitioning, setTransitioning] = useState(false)
  const [owner, setOwner] = useState('')
  const [postRunId, setPostRunId] = useState('')
  const [showMeasureForm, setShowMeasureForm] = useState(false)

  useEffect(() => {
    if (!interventionId) return
    setLoading(true)
    getIntervention(interventionId)
      .then((data: Intervention) => {
        setIv(data)
        setOwner(data.owner || '')
        return getSignal(data.signal_instance_id).catch(() => null)
      })
      .then((sig: any) => { if (sig) setSignal(sig) })
      .catch(() => setError('Could not load intervention'))
      .finally(() => setLoading(false))

    getInterventionOutcome(interventionId).then(setOutcome).catch(() => null)
  }, [interventionId])

  async function handleTransition(target: string) {
    if (!interventionId) return
    if (!confirm(`Transition to "${target.replace(/_/g, ' ')}"?`)) return
    setTransitioning(true)
    try {
      const updated = await transitionIntervention(interventionId, target)
      setIv(updated)
      setSuccessMsg(`Status updated to ${target.replace(/_/g, ' ')}`)
      if (target === 'AWAITING_RETEST') setShowMeasureForm(true)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setTransitioning(false)
    }
  }

  async function handleSaveOwner() {
    if (!interventionId) return
    try {
      const updated = await updateIntervention(interventionId, { owner })
      setIv(updated)
      setSuccessMsg('Owner saved')
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function handleGenerateBrief() {
    if (!interventionId) return
    try {
      const b = await generateBrief(interventionId)
      setBrief(b)
      setSuccessMsg('Brief generated')
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function handleMeasure() {
    if (!interventionId || !postRunId.trim()) return
    try {
      const o = await measureIntervention(interventionId, postRunId.trim())
      setOutcome(o)
      setShowMeasureForm(false)
      setSuccessMsg('Outcome recorded')
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (loading) return <div className="page-loading">Loading intervention…</div>
  if (!iv) return <div className="page-container"><div className="alert alert-error">Intervention not found</div></div>

  const currentIdx = LIFECYCLE.indexOf(iv.status)
  const statusColor = STATUS_COLOR[iv.status] || '#6b7280'

  const NEXT_TRANSITIONS: Record<string, string[]> = {
    DETECTED: ['NEEDS_DIAGNOSIS', 'REJECTED'],
    NEEDS_DIAGNOSIS: ['NEEDS_TRUTH_VALIDATION', 'REJECTED', 'INSUFFICIENT_EVIDENCE'],
    NEEDS_TRUTH_VALIDATION: ['READY_FOR_OWNER_REVIEW', 'NEEDS_DIAGNOSIS', 'REJECTED'],
    READY_FOR_OWNER_REVIEW: ['APPROVED_FOR_BRIEF', 'REJECTED'],
    APPROVED_FOR_BRIEF: ['IN_CREATION', 'REJECTED'],
    IN_CREATION: ['IN_MLR', 'APPROVED', 'REJECTED'],
    IN_MLR: ['APPROVED', 'IN_CREATION', 'REJECTED'],
    APPROVED: ['PUBLISHED', 'REJECTED'],
    PUBLISHED: ['AWAITING_RETEST'],
    AWAITING_RETEST: ['MEASURED', 'PUBLISHED'],
    MEASURED: ['CLOSED'],
  }

  const nextActions = NEXT_TRANSITIONS[iv.status] || []

  return (
    <div className="page-container">
      <div className="breadcrumb">
        <button className="link-btn" onClick={() => navigate('/interventions')}>Interventions</button>
        <span> / </span>
        <span>Detail</span>
      </div>

      {error && <div className="alert alert-error">{error} <button onClick={() => setError(null)}>✕</button></div>}
      {successMsg && <div className="alert alert-success">{successMsg} <button onClick={() => setSuccessMsg(null)}>✕</button></div>}

      {/* Header */}
      <div className="page-header intervention-header">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-primary">Intervention workspace · business action from a signal</p>
          <h1 className="page-title">{iv.business_problem && iv.business_problem.length > 100 ? iv.business_problem.slice(0, 100) + '...' : iv.business_problem || 'Untitled intervention'}</h1>
          <div className="header-meta">
            <span className="status-chip" style={{ background: statusColor + '22', color: statusColor, border: `1px solid ${statusColor}` }}>
              {iv.status.replace(/_/g, ' ')}
            </span>
            <span className={`priority-badge priority-${iv.priority.toLowerCase()}`}>{iv.priority}</span>
            <span className="muted">{iv.brand_id.toUpperCase()} · {iv.market}</span>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-outline" onClick={handleGenerateBrief}>Generate brief</button>
        </div>
      </div>

      <div className="mb-7 rounded-2xl border border-teal-100 bg-teal-50/70 p-5 text-sm text-slate-700 md:p-6">
        <h2 className="font-extrabold text-slate-900">What is this?</h2>
        <p className="mt-1 max-w-4xl leading-6">An intervention is a tracked business action created from an evidence-backed signal. This page records the problem, diagnosis, approved action, owner, workflow approvals, and—after a comparable retest—the measurable outcome.</p>
      </div>

      {/* Lifecycle stepper */}
      <div className="lifecycle-stepper">
        {LIFECYCLE.map((step, i) => (
          <div
            key={step}
            className={`lifecycle-step ${i < currentIdx ? 'done' : i === currentIdx ? 'active' : 'future'}`}
          >
            <div className="step-dot" />
            <div className="step-label">{step.replace(/_/g, ' ')}</div>
          </div>
        ))}
      </div>

      {/* Main content grid */}
      <div className="detail-grid">
        {/* Left column */}
        <div className="detail-main">
          <div className="card">
            <h3 className="card-title">Business problem</h3>
            <p>{iv.business_problem}</p>
          </div>

          <div className="card">
            <h3 className="card-title">Diagnosed cause</h3>
            <p>{iv.diagnosed_cause || <span className="muted">Pending diagnosis</span>}</p>
          </div>

          <div className="card">
            <h3 className="card-title">Recommended action</h3>
            <p>{iv.recommended_action || <span className="muted">Not yet specified</span>}</p>
          </div>

          {signal && (
            <div className="card">
              <h3 className="card-title">
                Source signal
                <button className="link-btn ml-2" onClick={() => navigate(`/signals/${iv.signal_instance_id}`)}>
                  View signal ↗
                </button>
              </h3>
              <div className="signal-summary">
                <div><strong>{signal.title}</strong></div>
                <div className="mt-1 muted">{signal.description}</div>
                <div className="metric-row mt-2">
                  <div className="mini-metric">
                    <span className="severity-badge" style={{ background: { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308' }[signal.severity as string] || '#6b7280' }}>
                      {signal.severity}
                    </span>
                  </div>
                  <div className="mini-metric">
                    <span className="muted">Score: </span>
                    <strong>{formatPercent(signal.current_value)}</strong>
                  </div>
                  <div className="mini-metric">
                    <span className="muted">Evidence: </span>
                    <strong>{signal.evidence_count} rows</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {brief && (
            <div className="card">
              <h3 className="card-title">Generated brief</h3>
              <div className="brief-block">
                <div className="brief-row"><strong>Type:</strong> {brief.brief_type}</div>
                <div className="brief-row"><strong>Approved claim:</strong> {brief.approved_claim?.claim_text || '—'} <span className="muted">({brief.approved_claim?.approval_status || 'unknown'})</span></div>
                <div className="brief-row"><strong>Target page:</strong> {brief.target_page?.url || '—'}</div>
                <div className="brief-row"><strong>Risk route:</strong> {brief.risk_route || '—'}</div>
                <div className="brief-row"><strong>Baseline:</strong> {brief.baseline_metric ?? '—'} → Target: {brief.target_metric ?? '—'}</div>
                <div className="brief-row muted small">{brief.note}</div>
              </div>
            </div>
          )}

          <div className="card">
            <h3 className="card-title">Outcome measurement</h3>
            {!outcome ? (
              <div className="outcome-pending">
                {['PUBLISHED', 'AWAITING_RETEST'].includes(iv.status)
                  ? 'No outcome recorded yet. Use "Record outcome" in the sidebar after the retest window passes.'
                  : 'Outcome available after intervention is published and retested.'}
              </div>
            ) : (
              <div className="outcome-summary">
                <span
                  className="outcome-badge"
                  style={{ background: (OUTCOME_COLOR[outcome.outcome_status] || '#6b7280') + '22', color: OUTCOME_COLOR[outcome.outcome_status] || '#6b7280', border: `1px solid ${OUTCOME_COLOR[outcome.outcome_status] || '#6b7280'}` }}
                >
                  {outcome.outcome_status.replace(/_/g, ' ')}
                </span>
                <div className="metric-row mt-2">
                  <div className="mini-metric"><span className="muted">Baseline:</span> <strong>{formatPercent(outcome.baseline_value)}</strong></div>
                  <div className="mini-metric"><span className="muted">Post-change:</span> <strong>{formatPercent(outcome.post_change_value)}</strong></div>
                  <div className="mini-metric"><span className="muted">Delta:</span> <strong style={{ color: (outcome.absolute_delta ?? 0) >= 0 ? '#22c55e' : '#ef4444' }}>{outcome.absolute_delta === null || outcome.absolute_delta === undefined ? 'Not available' : `${outcome.absolute_delta >= 0 ? '+' : ''}${(outcome.absolute_delta * 100).toFixed(1)}%`}</strong></div>
                  <div className="mini-metric"><span className="muted">Confidence:</span> <strong>{formatPercent(outcome.confidence)}</strong></div>
                </div>
                <div className="limitations-note mt-2">
                  <strong>Limitations:</strong> {outcome.comparison_limitations}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right sidebar */}
        <div className="detail-sidebar">
          <div className="card">
            <h3 className="card-title">Next actions</h3>
            {nextActions.length > 0 ? (
              <div className="action-list">
                {nextActions.map(action => (
                  <button
                    key={action}
                    className={`btn btn-block ${action === 'REJECTED' ? 'btn-danger' : 'btn-primary'} mb-1`}
                    disabled={transitioning}
                    onClick={() => handleTransition(action)}
                  >
                    {action.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted small">No further transitions available.</p>
            )}
          </div>

          <div className="card">
            <h3 className="card-title">Owner</h3>
            <div className="owner-form">
              <input
                className="form-input"
                value={owner}
                onChange={e => setOwner(e.target.value)}
                placeholder="Assign owner…"
              />
              <button className="btn btn-sm btn-primary mt-1" onClick={handleSaveOwner}>Save</button>
            </div>
            {iv.approver && <div className="mt-1 muted small">Approver: {iv.approver}</div>}
          </div>

          <div className="card">
            <h3 className="card-title">Targets</h3>
            <div className="small">
              <div><span className="muted">Claim: </span>{iv.target_claim_id || '—'}</div>
              <div><span className="muted">Page: </span>{iv.target_page_id || '—'}</div>
              <div><span className="muted">Prompt: </span>{iv.target_prompt_id || '—'}</div>
              <div><span className="muted">Risk route: </span>{iv.risk_route || '—'}</div>
            </div>
          </div>

          <div className="card">
            <h3 className="card-title">Baseline & retest</h3>
            <div className="small">
              <div><span className="muted">Baseline metric: </span>{iv.baseline_metric ?? '—'}</div>
              <div><span className="muted">Target metric: </span>{iv.target_metric ?? '—'}</div>
              <div><span className="muted">Publish date: </span>{formatLocalDateTime(iv.planned_publish_date, '—')}</div>
              <div><span className="muted">Retest date: </span>{formatLocalDateTime(iv.retest_date, '—')}</div>
            </div>
          </div>

          {(iv.status === 'AWAITING_RETEST' || showMeasureForm) && !outcome && (
            <div className="card">
              <h3 className="card-title">Measure outcome</h3>
              <p className="muted small mb-1">Enter the post-change assessment run ID to compare against baseline.</p>
              <input
                className="form-input"
                value={postRunId}
                onChange={e => setPostRunId(e.target.value)}
                placeholder="Post-change run ID…"
              />
              <button className="btn btn-sm btn-primary mt-1" onClick={handleMeasure} disabled={!postRunId.trim()}>
                Record outcome
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
