import { useEffect, useState } from 'react';
import { 
  getDatasetStatus, 
  getQuality, 
  getReferenceChecks, 
  getMetricContracts,
  getSchemaContracts,
  getAssessmentRuns,
  getSemanticBlockers,
  getVendorQuestions,
  getIngestionErrors,
} from '../services/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { formatLocalDateTime } from '../utils/dateTime';

export function DataTrust() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('contracts');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [
          status, quality, refs,
          metrics, schemas, runs, blockers, questions, ingestionErrors
        ] = await Promise.all([
          getDatasetStatus().catch(() => null),
          getQuality().catch(() => null),
          getReferenceChecks().catch(() => null),
          getMetricContracts().catch(() => []),
          getSchemaContracts().catch(() => []),
          getAssessmentRuns().catch(() => []),
          getSemanticBlockers().catch(() => []),
          getVendorQuestions().catch(() => []),
          getIngestionErrors().catch(() => [])
        ]);
        
        setData({ status, quality, refs, metrics, schemas, runs, blockers, questions, ingestionErrors });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch trust data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="p-10 animate-pulse text-slate-500">Loading Semantic Trust Center...</div>;
  if (error) return <Card className="m-8 bg-red-50 text-red-800">{error}</Card>;

  const TABS = [
    { id: 'contracts', label: 'Semantic Contracts' },
    { id: 'runs', label: 'Assessment Runs' },
    { id: 'blockers', label: 'Blockers & Vendor Qs' },
    { id: 'diagnostics', label: 'Layer-1 Diagnostics' }
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Semantic Trust Center</h1>
        <p className="text-slate-500 mt-1">Single source of truth for metric definitions, schema enforcement, and data acquisition provenance.</p>
      </div>

      <div className="flex space-x-4 border-b border-slate-200">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 font-semibold text-sm border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-brand-primary text-brand-primary'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {activeTab === 'contracts' && (
          <div className="space-y-8">
            <section>
              <h2 className="text-xl font-bold text-slate-900 mb-4">Metric Contracts ({data?.metrics?.length || 0})</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data?.metrics?.map((m: any) => (
                  <Card key={m.metric_id} className="p-5">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-bold text-slate-900 text-lg">{m.metric_name}</h3>
                      <Badge variant={m.validation_status === 'VERIFIED_VENDOR' ? 'verified' : m.validation_status === 'UNRESOLVED' ? 'blocked' : 'experimental'}>{m.validation_status || 'UNKNOWN'}</Badge>
                    </div>
                    <p className="text-sm text-slate-600 mb-3">{m.description}</p>
                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs font-mono text-slate-500 space-y-1">
                      <div>Module: {m.module}</div>
                      <div>Direction: {m.direction}</div>
                      <div>Natural grain: {m.grain}</div>
                      <div>Calculated by: {m.calculated_by}</div>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
            
            <section>
              <h2 className="text-xl font-bold text-slate-900 mb-4">Schema Contracts ({data?.schemas?.length || 0})</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data?.schemas?.map((s: any) => (
                  <Card key={s.schema_family} className="p-5">
                    <h3 className="font-bold text-slate-900 text-lg mb-2">{s.schema_family}</h3>
                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs font-mono text-slate-500 space-y-1">
                      <div>Adapter: {s.adapter_name}</div>
                      <div>Expected Columns: {JSON.stringify(s.expected_columns)}</div>
                      <div>{s.description}</div>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          </div>
        )}

        {activeTab === 'runs' && (
          <section>
            <h2 className="text-xl font-bold text-slate-900 mb-4">Assessment Runs (Provenance)</h2>
            <Card className="p-0 overflow-hidden">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3">Run ID</th>
                    <th className="px-4 py-3">Market</th>
                    <th className="px-4 py-3">Vendor</th>
                    <th className="px-4 py-3">Query</th>
                    <th className="px-4 py-3">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data?.runs?.map((r: any) => (
                    <tr key={r.run_id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono text-xs">{r.run_id}</td>
                      <td className="px-4 py-3 text-slate-900">{r.market}</td>
                      <td className="px-4 py-3 text-slate-600">{r.source_system}</td>
                      <td className="px-4 py-3 text-slate-600 italic">{r.module || 'All modules'}</td>
                      <td className="px-4 py-3 text-slate-500">{formatLocalDateTime(r.acquisition_date, '—')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </section>
        )}

        {activeTab === 'blockers' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <section>
              <h2 className="text-xl font-bold text-slate-900 mb-4">Semantic Blockers</h2>
              <div className="space-y-4">
                {data?.blockers?.map((b: any) => (
                  <Card key={b.blocker_id} className="border-red-200 bg-red-50/30">
                    <div className="flex justify-between items-start">
                      <h3 className="font-bold text-red-900">{b.description}</h3>
                      <Badge variant="critical">BLOCKED</Badge>
                    </div>
                      <p className="text-xs text-red-700 mt-2 font-mono">Affected: {b.target_entity} · {b.blocker_type}</p>
                  </Card>
                ))}
              </div>
            </section>
            <section>
              <h2 className="text-xl font-bold text-slate-900 mb-4">Vendor Questions</h2>
              <div className="space-y-4">
                {data?.questions?.map((q: any) => (
                  <Card key={q.question_id} className="border-amber-200 bg-amber-50/30">
                    <div className="flex justify-between items-start">
                      <h3 className="font-bold text-amber-900">{q.question_text}</h3>
                      <Badge variant={q.status === 'OPEN' ? 'high' : 'verified'}>{q.status}</Badge>
                    </div>
                    <p className="text-xs text-amber-700 mt-2 font-mono">Topic: {q.topic}</p>
                  </Card>
                ))}
              </div>
            </section>
          </div>
        )}

        {activeTab === 'diagnostics' && (
          <section>
            <h2 className="text-xl font-bold text-slate-900 mb-4">Layer-1 Diagnostics</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card glass>
                <h3 className="text-xs font-semibold text-slate-500 uppercase">Total Observations</h3>
                <p className="text-2xl font-black mt-1">{data?.status?.canonical_observations?.toLocaleString()}</p>
              </Card>
              <Card glass>
                <h3 className="text-xs font-semibold text-slate-500 uppercase">Unique Payloads</h3>
                <p className="text-2xl font-black mt-1">{data?.quality?.unique_payloads?.toLocaleString()}</p>
              </Card>
              <Card glass>
                <h3 className="text-xs font-semibold text-slate-500 uppercase">Files Discovered</h3>
                <p className="text-2xl font-black mt-1">{data?.quality?.physical_files_discovered?.toLocaleString()}</p>
              </Card>
              <Card glass className={data?.ingestionErrors?.length ? 'border-amber-200 bg-amber-50/50' : ''}>
                <h3 className="text-xs font-semibold text-slate-500 uppercase">Ingestion issues</h3>
                <p className="text-2xl font-black mt-1">{data?.ingestionErrors?.length || 0}</p>
                <p className="text-xs text-slate-500 mt-1">Rows/files quarantined while the run continued</p>
              </Card>
            </div>
            {data?.ingestionErrors?.length > 0 && (
              <Card className="mt-6 border-amber-200 bg-amber-50/40">
                <h2 className="text-lg font-bold text-slate-900 mb-3">Latest ingestion issues</h2>
                <div className="space-y-2">
                  {data.ingestionErrors.slice(0, 10).map((item: any, index: number) => (
                    <div key={`${item.file_id}-${item.source_row}-${index}`} className="rounded-md bg-white px-3 py-2 text-sm">
                      <div className="font-semibold text-slate-800">{item.error_type} · {item.file_id || 'file unavailable'} · row {item.source_row || 'n/a'}</div>
                      <div className="text-slate-600">{item.error_message}</div>
                    </div>
                  ))}
                </div>
                {data.ingestionErrors.length > 10 && <p className="mt-3 text-xs text-slate-500">Showing 10 of {data.ingestionErrors.length}. Use the ingestion-errors API for the complete list.</p>}
              </Card>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
