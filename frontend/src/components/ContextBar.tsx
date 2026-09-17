import { useState, useEffect } from 'react';
import { getDatasetStatus, getAIHealth, getCurrentContext, startIngestion, getIngestionProgress } from '../services/api';
import { formatRunIdLocal } from '../utils/dateTime';

type Status = {
  ai_available: boolean;
  latest_run_id: string | null;
  archive_entries_discovered: number;
  physical_files_discovered: number;
  unique_payloads: number;
  duplicate_payload_references: number;
  canonical_observations: number;
  assessment_runs: number;
  schema_families: number;
};

type AIHealth = {
  llm_reachable: boolean;
  synthesis_mode: string;
};

const DEMO_INGEST_OVERRIDE_PASSWORD = 'KENVUE-DEMO-2026';

export function ContextBar() {
  const [status, setStatus] = useState<Status | null>(null);
  const [aiHealth, setAIHealth] = useState<AIHealth | null>(null);
  const [context, setContext] = useState<any>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestStage, setIngestStage] = useState(0);
  const [ingestResult, setIngestResult] = useState<any>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [ingestProgress, setIngestProgress] = useState<any>(null);
  const [overrideExisting, setOverrideExisting] = useState(false);
  const [overridePassword, setOverridePassword] = useState(DEMO_INGEST_OVERRIDE_PASSWORD);

  useEffect(() => {
    const fetchContext = async () => {
      try {
        const [s, h, c] = await Promise.all([
          getDatasetStatus().catch(() => null),
          getAIHealth().catch(() => null),
          getCurrentContext().catch(() => null)
        ]);
        setStatus(s);
        setAIHealth(h);
        setContext(c);
      } catch (e) {
        // Fallback for unexpected synchronous errors
        setStatus(null);
        setAIHealth(null);
      }
    };
    fetchContext();
    const interval = setInterval(fetchContext, 60000); // 1 min refresh
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!ingesting) return;
    const timer = setInterval(() => setIngestStage((stage) => Math.min(stage + 1, 3)), 1800);
    return () => clearInterval(timer);
  }, [ingesting]);

  const handleIngest = async () => {
    setIngesting(true);
    setIngestStage(0);
    setIngestResult(null);
    setIngestError(null);
    setIngestProgress(null);
    try {
      const job = await startIngestion({
        override_existing: overrideExisting,
        password: overrideExisting ? overridePassword : undefined,
      });
      setIngestProgress(job);
      let current = job;
      while (current.status === 'QUEUED' || current.status === 'RUNNING') {
        await new Promise((resolve) => setTimeout(resolve, 500));
        current = await getIngestionProgress(job.job_id);
        setIngestProgress(current);
      }
      if (current.status === 'FAILED') throw new Error(current.error || 'Ingestion failed');
      setIngestStage(4);
      setIngestResult(current.summary);
      const [nextStatus, nextContext] = await Promise.all([getDatasetStatus(), getCurrentContext()]);
      setStatus(nextStatus);
      setContext(nextContext);
    } catch (error) {
      setIngestError(error instanceof Error ? error.message : 'Ingestion failed');
    } finally {
      setIngesting(false);
    }
  };

  const runId = context?.assessment_run_id || (status?.latest_run_id ? formatRunIdLocal(status.latest_run_id, 'None') : 'No run detected');
  const obsCount = status?.canonical_observations?.toLocaleString() || '0';
  const fileCount = status?.physical_files_discovered?.toLocaleString() || '0';
  const aiStatus = aiHealth?.llm_reachable ? 'AI Agent Online' : 'Evidence Mode';
  const stages = ['Preparing input scan', 'Reading CSV, TSV, and ZIP files', 'Parsing and validating rows', 'Writing canonical observations', 'Ingestion complete'];
  const processedFiles = ingestProgress?.processed_files ?? 0;
  const totalFiles = ingestProgress?.total_files ?? 0;
  const percentage = Number(ingestProgress?.percentage ?? 0);

  return (
    <div className="bg-slate-800 text-white text-sm py-2 px-6 flex justify-between items-center shadow-md border-b border-slate-700">
      <div className="flex gap-6 items-center">
        <span className="font-semibold text-brand-light uppercase tracking-wide text-xs">Decision Context</span>
        <span>{context?.brand_display || context?.brand_id || 'Brand not configured'} · {context?.market || 'Market unknown'} · {context?.language || 'Language unknown'}</span>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Run:</span>
          <span className="font-medium">{runId}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Observations:</span>
          <span className="font-medium">{obsCount}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Files:</span>
          <span className="font-medium">{fileCount}</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-slate-300">{context?.source_system || 'Source unknown'} · {context?.semantic_trust_state || 'Trust unknown'}</span>
        <div className="relative">
          <label className="mr-2 inline-flex items-center gap-1 text-[10px] text-slate-300" title="Requires the hardcoded demo override password">
            <input type="checkbox" checked={overrideExisting} onChange={(event) => setOverrideExisting(event.target.checked)} />
            Demo override
          </label>
          {overrideExisting && <input type="password" aria-label="Demo override password" value={overridePassword} onChange={(event) => setOverridePassword(event.target.value)} className="mr-2 w-28 rounded bg-slate-700 px-2 py-1 text-[10px] text-white" />}
          <button
            type="button"
            onClick={handleIngest}
            disabled={ingesting}
            aria-busy={ingesting}
            className="rounded-lg bg-brand-primary px-3 py-1.5 text-xs font-bold text-white hover:bg-brand-primary/90 disabled:cursor-wait disabled:opacity-60"
          >
            {ingesting ? 'Ingesting...' : 'Ingest data'}
          </button>
          {(ingesting || ingestResult || ingestError) && (
            <div className="absolute right-0 top-10 z-50 w-80 rounded-lg border border-slate-600 bg-slate-900 p-3 shadow-xl" role="status" aria-live="polite">
              {ingesting && <>
                <div className="flex items-center justify-between text-xs font-semibold text-white"><span>{ingestProgress?.stage || stages[ingestStage]}</span><span>{processedFiles}/{totalFiles || '...'} files · {percentage.toFixed(1)}%</span></div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-700" aria-label={`${percentage.toFixed(1)}% of files processed`}>
                  <div className="h-full rounded-full bg-brand-light transition-[width] duration-300" style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }} />
                </div>
                <p className="mt-2 text-[11px] text-slate-400">Processing the complete configured input folder. The count includes parsed, duplicate, empty, and quarantined files.</p>
              </>}
              {!ingesting && ingestResult && <p className="text-xs text-emerald-300">Completed: {ingestResult.physical_files} files, {ingestResult.parsed_rows} parsed rows, {ingestResult.rejected_rows} rejected rows, {ingestResult.quarantined_files || 0} quarantined files.</p>}
              {!ingesting && ingestError && <p className="text-xs text-red-300">{ingestError}</p>}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 bg-slate-700 px-3 py-1 rounded-full">
          <div className={`w-2 h-2 rounded-full ${aiHealth?.llm_reachable ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`}></div>
          <span className="text-xs font-semibold uppercase tracking-wider">{aiStatus}</span>
        </div>
      </div>
    </div>
  );
}
