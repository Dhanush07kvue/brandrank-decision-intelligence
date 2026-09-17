import { useEffect, useState } from 'react'
import { getIngestionOverview, getManifest, getSchemaContracts, getSignalCoverage } from '../services/api'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

const PAGE_SIZE = 25

type Tab = 'files' | 'schemas' | 'ontology' | 'coverage'

function number(value: number | undefined) {
  return (value || 0).toLocaleString()
}

function statusVariant(status: string) {
  if (status === 'SUPPORTED' || status === 'CANONICALIZED') return 'verified'
  if (status.includes('QUARANTINED') || status.includes('UNSUPPORTED')) return 'blocked'
  return 'provisional'
}

export function IngestionOntology() {
  const [overview, setOverview] = useState<any>(null)
  const [contracts, setContracts] = useState<any[]>([])
  const [coverage, setCoverage] = useState<any>(null)
  const [files, setFiles] = useState<any[]>([])
  const [tab, setTab] = useState<Tab>('files')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filesLoading, setFilesLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getIngestionOverview(), getSchemaContracts()])
      .then(async ([nextOverview, nextContracts]) => {
        setOverview(nextOverview)
        setContracts(nextContracts)
        setCoverage(await getSignalCoverage(nextOverview.run_id))
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load ingestion overview'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!overview) return
    setFilesLoading(true)
    getManifest(status || undefined, PAGE_SIZE, page * PAGE_SIZE, query.trim() || undefined)
      .then(setFiles)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load file inventory'))
      .finally(() => setFilesLoading(false))
  }, [overview, status, page, query])

  if (loading) return <div className="p-10 animate-pulse text-slate-500">Loading ingestion lineage...</div>
  if (error && !overview) return <Card className="m-8 bg-red-50 text-red-800">{error}</Card>

  const funnel = [
    ['Physical files', overview?.physical_files, 'Every file occurrence discovered'],
    ['Unique payloads', overview?.unique_payloads, 'Content fingerprints after duplicate detection'],
    ['Parsed files', overview?.parsed_files, 'Files that reached parsing'],
    ['Source rows', overview?.source_rows, 'Rows found across physical files'],
    ['Canonical observations', overview?.canonical_observations, 'Rows available to evidence and rules'],
    ['Rule-eligible rows', overview?.rule_eligible_observations, 'Rows matching current rule input shapes'],
    ['Findings', overview?.evaluated_signals, `${overview?.blocked_evaluations || 0} blocked evaluation(s)`],
  ]

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Ingestion &amp; Ontology</h1>
        <p className="text-slate-500 mt-1">See what arrived, how it was converted, and what each canonical field means.</p>
        <p className="text-xs text-slate-500 mt-2">Current ingestion run: <span className="font-mono font-semibold">{overview?.run_id || 'No run detected'}</span></p>
      </div>

      <Card className="bg-slate-800 text-white">
        <p className="text-xs uppercase tracking-wider text-slate-300 font-bold">How the data moves</p>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-3 items-center">
          {['Source files', 'Schema adapter', 'Canonical observations', 'Evidence & rules', 'Business findings'].map((step, index) => (
            <div key={step} className="flex items-center gap-2">
              <div className="rounded-lg bg-slate-700 px-3 py-3 text-sm font-bold">{step}</div>
              {index < 4 && <span className="hidden md:block text-brand-light">→</span>}
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-slate-300">A file can be retained as a duplicate or quarantined without producing canonical observations. A finding is an aggregated pattern, so files and findings will not have a one-to-one count.</p>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
        {funnel.map(([label, value, detail]) => (
          <Card key={String(label)} className="p-4">
            <p className="text-[11px] uppercase tracking-wide font-bold text-slate-500">{label}</p>
            <p className="text-2xl font-black text-slate-900 mt-1">{number(value as number)}</p>
            <p className="text-[11px] text-slate-500 mt-1 leading-4">{detail}</p>
          </Card>
        ))}
      </div>

      {(overview?.quarantined_files || overview?.empty_files || overview?.duplicate_references) > 0 && (
        <Card className="border-amber-200 bg-amber-50/60">
          <p className="font-bold text-slate-900">Ingestion quality notes</p>
          <p className="text-sm text-slate-700 mt-1">{number(overview?.duplicate_references)} duplicate file reference(s), {number(overview?.quarantined_files)} quarantined file(s), and {number(overview?.empty_files)} empty file(s) were retained in the audit trail. They are not silently discarded.</p>
        </Card>
      )}

      <div className="flex space-x-1 border-b border-slate-200">
        {([['files', 'File inventory'], ['schemas', 'Schemas & conversions'], ['ontology', 'Canonical ontology'], ['coverage', 'Signal coverage']] as [Tab, string][]).map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={`px-4 py-2 font-semibold text-sm border-b-2 ${tab === id ? 'border-brand-primary text-brand-primary' : 'border-transparent text-slate-500'}`}>{label}</button>
        ))}
      </div>

      {tab === 'files' && (
        <Card>
          <div className="flex flex-wrap gap-3 items-center justify-between mb-4">
            <div><h2 className="text-xl font-bold text-slate-900">Files ingested</h2><p className="text-sm text-slate-500 mt-1">Each row is a physical source-file occurrence and its canonical conversion result.</p></div>
            <div className="flex gap-2">
              <input value={query} onChange={(event) => { setPage(0); setQuery(event.target.value) }} placeholder="Find filename" aria-label="Find filename" className="border rounded-lg px-3 py-2 text-sm" />
              <select value={status} onChange={(event) => { setPage(0); setStatus(event.target.value) }} aria-label="Ingestion status" className="border rounded-lg px-3 py-2 text-sm">
                <option value="">All statuses</option><option value="SUPPORTED">Supported</option><option value="QUARANTINED_UNSUPPORTED">Unsupported</option><option value="QUARANTINED_PARSE_ERROR">Parse error</option><option value="EMPTY_UNSUPPORTED">Empty</option>
              </select>
            </div>
          </div>
          {filesLoading ? <p className="text-slate-500 animate-pulse">Loading files...</p> : files.length === 0 ? <p className="text-slate-500 py-8 text-center">No files match this filter.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200"><tr><th className="px-3 py-3">File</th><th className="px-3 py-3">Schema / adapter</th><th className="px-3 py-3">Rows</th><th className="px-3 py-3">Canonical rows</th><th className="px-3 py-3">Result</th><th className="px-3 py-3">Source columns</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {files.map((file) => <tr key={file.file_id} className="hover:bg-slate-50 align-top"><td className="px-3 py-3"><div className="font-semibold text-slate-900 max-w-64 break-words">{file.original_filename}</div><div className="text-[11px] text-slate-500 font-mono mt-1">{file.file_id}</div></td><td className="px-3 py-3"><div className="font-mono text-xs text-slate-700">{file.schema_contract_id || 'unclassified'}</div><div className="text-xs text-slate-500 mt-1">{file.adapter_name} {file.adapter_version}</div></td><td className="px-3 py-3">{number(file.row_count)}<div className="text-xs text-slate-500">{number(file.rejected_row_count)} rejected</div></td><td className="px-3 py-3 font-semibold">{number(file.canonical_row_count)}</td><td className="px-3 py-3"><Badge variant={statusVariant(file.ingestion_status) as any}>{file.ingestion_status}</Badge>{file.duplicate_of_file_id && <div className="text-[11px] text-slate-500 mt-1">duplicate reference</div>}</td><td className="px-3 py-3 text-xs text-slate-500 max-w-72 break-words">{file.source_columns?.join(', ') || 'No parsed header'}</td></tr>)}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex justify-between items-center mt-4 text-sm"><span className="text-slate-500">Page {page + 1} · showing up to {PAGE_SIZE} files</span><div className="flex gap-2"><button type="button" disabled={page === 0 || filesLoading} onClick={() => setPage((current) => current - 1)} className="border rounded-lg px-3 py-1 disabled:opacity-40">Previous</button><button type="button" disabled={files.length < PAGE_SIZE || filesLoading} onClick={() => setPage((current) => current + 1)} className="border rounded-lg px-3 py-1 disabled:opacity-40">Next</button></div></div>
        </Card>
      )}

      {tab === 'schemas' && <div className="space-y-6"><Card><h2 className="text-xl font-bold text-slate-900">Observed schema conversions</h2><p className="text-sm text-slate-500 mt-1">This is the measured conversion result for the current run.</p><div className="overflow-x-auto mt-4"><table className="w-full text-sm text-left"><thead className="bg-slate-50 border-b"><tr><th className="px-3 py-3">Schema family</th><th className="px-3 py-3">File occurrences</th><th className="px-3 py-3">Unique payloads</th><th className="px-3 py-3">Source rows</th><th className="px-3 py-3">Canonical observations</th><th className="px-3 py-3">Disposition</th></tr></thead><tbody className="divide-y">{overview?.schemas?.map((schema: any) => <tr key={schema.schema_family}><td className="px-3 py-3 font-mono">{schema.schema_family}</td><td className="px-3 py-3">{number(schema.file_count)}</td><td className="px-3 py-3">{number(schema.unique_payloads)}</td><td className="px-3 py-3">{number(schema.source_rows)}</td><td className="px-3 py-3 font-semibold">{number(schema.canonical_observations)}</td><td className="px-3 py-3"><Badge variant={statusVariant(schema.disposition) as any}>{schema.disposition}</Badge></td></tr>)}</tbody></table></div></Card><Card><h2 className="text-xl font-bold text-slate-900">Schema contracts</h2><p className="text-sm text-slate-500 mt-1">Expected source columns and the adapter description used to classify incoming files.</p><div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">{contracts.map((contract) => <div key={contract.schema_family} className="rounded-lg border border-slate-200 p-4"><div className="flex justify-between gap-3"><h3 className="font-bold text-slate-900">{contract.schema_family}</h3><span className="font-mono text-xs text-slate-500">{contract.adapter_name}</span></div><p className="text-sm text-slate-600 mt-2">{contract.description}</p><div className="mt-3 flex flex-wrap gap-1">{contract.expected_columns?.map((column: string) => <span key={column} className="rounded bg-slate-100 px-2 py-1 text-[11px] font-mono text-slate-600">{column}</span>)}</div></div>)}</div></Card></div>}

      {tab === 'coverage' && <div className="space-y-6"><Card><h2 className="text-xl font-bold text-slate-900">Why the finding count is small</h2><p className="text-sm text-slate-600 mt-1">The audit uses the same row-shape and threshold logic as signal evaluation. Rows outside a rule’s governed input shape remain canonical evidence but do not become findings.</p><div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">{Object.entries(coverage?.funnel || {}).map(([key, value]) => <div key={key} className="rounded-lg bg-slate-50 p-3"><p className="text-[11px] uppercase font-bold text-slate-500">{key.replaceAll('_', ' ')}</p><p className="text-xl font-black text-slate-900 mt-1">{number(value as number)}</p></div>)}</div></Card><Card><h2 className="text-xl font-bold text-slate-900">Rule evaluation audit</h2><div className="overflow-x-auto mt-4"><table className="w-full text-sm text-left"><thead className="bg-slate-50 border-b"><tr><th className="px-3 py-3">Rule</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Input</th><th className="px-3 py-3">Eligible rows</th><th className="px-3 py-3">Groups</th><th className="px-3 py-3">Fired</th><th className="px-3 py-3">Suppressed</th><th className="px-3 py-3">Blocked</th><th className="px-3 py-3">Reason</th></tr></thead><tbody className="divide-y">{coverage?.rules?.map((rule: any) => <tr key={rule.rule_id} className="align-top"><td className="px-3 py-3 font-semibold text-slate-900">{rule.name}<div className="font-mono text-[11px] text-slate-500 mt-1">{rule.rule_id}</div></td><td className="px-3 py-3"><Badge variant={statusVariant(rule.status) as any}>{rule.status}</Badge></td><td className="px-3 py-3 text-slate-600">{rule.input_observation_type}</td><td className="px-3 py-3">{number(rule.eligible_rows)}</td><td className="px-3 py-3">{number(rule.groups_evaluated)}</td><td className="px-3 py-3 font-semibold">{number(rule.signals_fired)}</td><td className="px-3 py-3">{number(rule.signals_suppressed)}</td><td className="px-3 py-3">{number(rule.signals_blocked)}</td><td className="px-3 py-3 text-slate-600 min-w-64">{rule.reason}</td></tr>)}</tbody></table></div></Card></div>}

      {tab === 'ontology' && <div className="space-y-6"><Card><h2 className="text-xl font-bold text-slate-900">Canonical ontology</h2><p className="text-sm text-slate-500 mt-1">The common language used after ingestion. Raw source rows stay available in qualifiers for auditability.</p></Card>{overview?.ontology?.map((entity: any) => <Card key={entity.entity}><div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-bold text-slate-900">{entity.entity}</h2><p className="text-sm text-slate-600 mt-1">{entity.purpose}</p></div><span className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-mono text-slate-600">{entity.table}</span></div><div className="overflow-x-auto mt-4"><table className="w-full text-sm text-left"><thead className="bg-slate-50 border-b"><tr><th className="px-3 py-3">Column</th><th className="px-3 py-3">Type</th><th className="px-3 py-3">Meaning</th><th className="px-3 py-3">Role</th><th className="px-3 py-3">Populated from</th></tr></thead><tbody className="divide-y">{entity.fields.map((field: any) => <tr key={field.name} className="align-top"><td className="px-3 py-3 font-mono font-semibold text-slate-900">{field.name}</td><td className="px-3 py-3 text-slate-500">{field.data_type}</td><td className="px-3 py-3 text-slate-700">{field.meaning}</td><td className="px-3 py-3 text-slate-600">{field.role}</td><td className="px-3 py-3 text-slate-500">{field.populated_from}</td></tr>)}</tbody></table></div></Card>)}</div>}
    </div>
  )
}
