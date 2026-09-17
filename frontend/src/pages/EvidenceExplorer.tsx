import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getEvidence } from '../services/api'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

type EvidenceItem = {
  evidence_ref: string
  evidence_type: string
  record_id: string | null
  file_id: string | null
  source_row: number | null
  assessment_run_id: string | null
  title: string
  detail: string
  payload_sha256: string | null
  qualifiers: Record<string, unknown>
}

export function EvidenceExplorer() {
  const [searchParams] = useSearchParams()
  const [items, setItems] = useState<EvidenceItem[]>([])
  const [query, setQuery] = useState(searchParams.get('query') || '')
  const [fixtureOnly, setFixtureOnly] = useState(false)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async (nextOffset = offset) => {
    setLoading(true)
    setError(null)
    try {
      const response = await getEvidence({ query, evidence_type: fixtureOnly ? 'DEMO_FIXTURE' : undefined, limit: 25, offset: nextOffset })
      setItems(response.items || [])
      setTotal(response.total_count || 0)
      setOffset(nextOffset)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load evidence')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(0) }, [fixtureOnly])

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Evidence Explorer</h1>
        <p className="text-slate-500 mt-2 text-lg">Trace observations back to source rows, payloads, and assessment runs.</p>
      </div>
      <Card>
        <div className="flex gap-3 flex-wrap">
          <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load(0)} placeholder="Search prompt, claim, metric, or raw context" className="flex-1 min-w-[260px] border border-slate-200 rounded-lg px-3 py-2" />
          <button onClick={() => load(0)} className="px-4 py-2 rounded-lg bg-brand-primary text-white font-semibold">Search</button>
          <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={fixtureOnly} onChange={(e) => setFixtureOnly(e.target.checked)} /> Demo fixtures only</label>
        </div>
      </Card>
      {error && <Card className="bg-red-50 text-red-800">{error}</Card>}
      {loading ? <div className="text-slate-500 animate-pulse">Loading evidence…</div> : items.length === 0 ? <Card><p className="text-slate-500">No evidence matches the current filters.</p></Card> : (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={`${item.evidence_ref}-${item.record_id}`}>
              <div className="flex justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2"><span className="font-mono text-xs text-slate-500">{item.evidence_ref}</span><Badge variant={item.evidence_type === 'DEMO_FIXTURE' ? 'experimental' : 'verified'}>{item.evidence_type}</Badge></div>
                  <h2 className="font-bold text-slate-900 mt-2">{item.title}</h2>
                  <p className="text-slate-600 mt-1">{item.detail}</p>
                </div>
                <div className="text-right text-xs text-slate-500 space-y-1 min-w-[180px]">
                  <div>Run: {item.assessment_run_id || '—'}</div>
                  <div>File: {item.file_id || '—'}</div>
                  <div>Row: {item.source_row ?? '—'}</div>
                  <div>Record: {item.record_id || '—'}</div>
                </div>
              </div>
              <details className="mt-3 text-xs text-slate-500"><summary className="cursor-pointer font-semibold">Raw context</summary><pre className="mt-2 overflow-auto bg-slate-50 p-3 rounded-lg">{JSON.stringify(item.qualifiers, null, 2)}</pre></details>
            </Card>
          ))}
        </div>
      )}
      <div className="flex justify-between items-center text-sm text-slate-500">
        <span>{total.toLocaleString()} total evidence items</span>
        <div className="flex gap-2"><button disabled={offset === 0} onClick={() => load(Math.max(0, offset - 25))} className="border rounded px-3 py-1 disabled:opacity-40">Previous</button><button disabled={offset + items.length >= total} onClick={() => load(offset + 25)} className="border rounded px-3 py-1 disabled:opacity-40">Next</button></div>
      </div>
    </div>
  )
}
