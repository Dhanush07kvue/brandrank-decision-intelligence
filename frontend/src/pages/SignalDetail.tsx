import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { askLeadershipChatAdvanced, getSignal, getSignalComparisons, getSignalEvidence, getSignalHistory } from '../services/api';
import { formatLocalDateTime } from '../utils/dateTime';
import { renderMarkdown } from '../utils/markdown';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';

type SignalInstance = {
  signal_instance_id: string;
  signal_rule_id: string;
  signal_rule_version: number;
  brand_id: string;
  market: string;
  assessment_run_id: string;
  signal_type: string;
  group_key: string;
  title: string;
  description: string;
  current_value: number;
  baseline_value: number | null;
  delta: number | null;
  runs_affected: number;
  engines_affected: number;
  business_priority: string;
  severity: string;
  confidence: number;
  evidence_count: number;
  diagnosis_status: string;
  truth_validation_status: string;
  workflow_status: string;
  governance_status?: string;
  business_title?: string;
  business_summary?: string;
  business_meaning?: string;
  business_impact?: string;
  recommended_next_step?: string;
  do_not_conclude?: string;
  status_label?: string;
  confidence_label?: string;
  evidence_summary?: string;
  technical_metric?: string;
  technical_threshold?: number;
  technical_rule?: string;
};

type EvidenceRow = {
  record_id: string;
  file_id: string;
  source_row: number;
  evidence_role: string;
  original_filename: string;
  metric_name: string | null;
  metric_value: number | null;
  text_value: string | null;
  qualifiers: Record<string, unknown>;
  engine?: string | null;
};

type HistoryPoint = {
  assessment_run_id: string;
  current_value: number;
  severity: string;
  confidence: number;
  workflow_status: string;
  created_at: string;
};

type Comparisons = {
  engine_comparison_basis: string;
  engine_comparison: Array<{ label: string; value: number | null; sample_count?: number | null }>;
  competitor_comparison_basis: string;
  competitor_comparison: Array<{ label: string; value: number | null; sample_count?: number | null }>;
};

type SignalSolution = {
  answer: string;
  fallback_used?: boolean;
  limitations?: string[];
  citations?: Array<{ citation_text: string; record_id: string }>;
};

const SIGNAL_TYPE_GUIDANCE: Record<string, { label: string; meaning: string; action: string }> = {
  CROSS_LLM_INCONSISTENCY: {
    label: 'AI answer consistency',
    meaning: 'Different AI engines are giving materially different answers about the same claim. This is an instability signal, not proof that Aveeno has low visibility.',
    action: 'Compare engine-level evidence and validate the claim before changing content.',
  },
  CLAIM_AGREEMENT_INVESTIGATION: {
    label: 'Claim agreement risk',
    meaning: 'The engines agree with the claim less often than the configured agreement floor.',
    action: 'Complete Kenvue truth validation before acting on the claim.',
  },
  VISIBILITY_GAP: {
    label: 'AI visibility gap',
    meaning: 'A priority prompt may be underrepresented in the available ranking data, but the evaluation is blocked until BrandRank confirms the rank direction.',
    action: 'Resolve the vendor rank-definition question before using this as a performance recommendation.',
  },
  READINESS_DETERIORATION: {
    label: 'Content readiness gap',
    meaning: 'A content-readiness factor is below the configured activation floor.',
    action: 'Review the factor evidence and vendor scoring definition before changing content.',
  },
  EVIDENCE_ACCESSIBILITY_DEFICIT: {
    label: 'Evidence accessibility gap',
    meaning: 'AI engines are citing too few sources that appear to be owned or attributable to the brand.',
    action: 'Check source ownership and machine-readable evidence coverage.',
  },
  COMPETITIVE_PLAYBOOK_GAP: {
    label: 'Competitive content opportunity',
    meaning: 'A source playbook identifies a prompt where a competitor or authoritative source has a reported advantage and suggests remediation actions.',
    action: 'Open the source row, validate the claimed advantage, and route any response through Kenvue truth and MLR review.',
  },
  BRAND_ATTRIBUTE_BENCHMARK: {
    label: 'Competitor brand-attribute lead',
    meaning: 'A competitor has a higher source-reported score than Aveeno on a brand attribute such as safety, innovation, or promise clarity.',
    action: 'Review the scorecard and per-engine rationale before deciding whether a positioning or evidence response is warranted.',
  },
};

function displayEngineName(label: string) {
  return label.replaceAll('_', ' ').replace(/\bmeta ai\b/i, 'Meta AI').replace(/\bopen ai\b/i, 'OpenAI').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayScore(value: number | null) {
  return value === null || !Number.isFinite(value) ? 'Not available' : `${(value * 100).toFixed(0)}%`;
}

function scoreWidth(value: number | null) {
  return value === null || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(100, value * 100));
}

function rawEvidence(row: EvidenceRow) {
  return (row.qualifiers?.row || {}) as Record<string, unknown>;
}

function evidenceSubject(row: EvidenceRow) {
  const raw = rawEvidence(row);
  const value = row.text_value || raw.statementText || raw.searchTerm || raw.question || raw.groupName || raw.pageLabel || row.metric_name || 'Source observation';
  return String(value);
}

function evidencePrompt(row: EvidenceRow) {
  const raw = rawEvidence(row);
  const value = raw.searchTerm || raw.statementText || raw.question || null;
  return value === null ? null : String(value);
}

function evidenceContext(row: EvidenceRow) {
  const raw = rawEvidence(row);
  const value = raw.pageLabel || raw.pageUrl || raw.groupName || null;
  return value === null ? null : String(value);
}

export function SignalDetail() {
  const { id } = useParams();
  const [signal, setSignal] = useState<SignalInstance | null>(null);
  const [evidence, setEvidence] = useState<EvidenceRow[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [comparisons, setComparisons] = useState<Comparisons | null>(null);
  const [solution, setSolution] = useState<SignalSolution | null>(null);
  const [solutionLoading, setSolutionLoading] = useState(false);
  const [solutionError, setSolutionError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    Promise.all([getSignal(id), getSignalEvidence(id), getSignalHistory(id), getSignalComparisons(id)])
      .then(([s, e, h, c]) => {
        setSignal(s);
        setEvidence(e);
        setHistory(h);
        setComparisons(c);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load signal'))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleAskSolution() {
    if (!signal) return;
    setSolutionLoading(true);
    setSolutionError(null);
    try {
      const response = await askLeadershipChatAdvanced({
        question: `Create a specific remediation solution for the selected signal. Explain the likely issue, the exact next actions, required Kenvue truth and MLR gates, source-content improvements only when supported, and a matched retest plan.`,
        signal_instance_id: signal.signal_instance_id,
        mode: 'ANALYST',
        history_enabled: false,
        history: [],
        context: { source: 'signal_detail', signal_type: signal.signal_type, group_key: signal.group_key },
      });
      setSolution(response);
    } catch (err) {
      setSolutionError(err instanceof Error ? err.message : 'Could not generate a solution');
    } finally {
      setSolutionLoading(false);
    }
  }

  if (loading) return <div className="p-10 text-slate-500 animate-pulse">Loading signal...</div>;
  if (error) return <Card className="m-8 bg-red-50 text-red-800">{error}</Card>;
  if (!signal) return <Card className="m-8">Signal not found.</Card>;

  const guidance = SIGNAL_TYPE_GUIDANCE[signal.signal_type] || {
    label: signal.signal_type.replaceAll('_', ' ').toLowerCase(),
    meaning: 'A rule-based observation requiring review.',
    action: 'Open the evidence and confirm the business interpretation before acting.',
  };
  const groupedEvidence = Object.values(evidence.reduce<Record<string, { engine: string; rows: EvidenceRow[]; value: number | null }>>((groups, row) => {
    const engine = row.engine || String((row.qualifiers?.row as Record<string, unknown> | undefined)?.llm || (row.qualifiers?.row as Record<string, unknown> | undefined)?.llmSource || 'Source evidence');
    const group = groups[engine] || { engine, rows: [], value: row.metric_value };
    group.rows.push(row);
    groups[engine] = group;
    return groups;
  }, {}));
  const engineRows = comparisons?.engine_comparison.filter((item) => item.value !== null) || [];
  const strongestEngine = engineRows.reduce<typeof engineRows[number] | null>((best, item) => !best || (item.value ?? -Infinity) > (best.value ?? -Infinity) ? item : best, null);
  const weakestEngine = engineRows.reduce<typeof engineRows[number] | null>((worst, item) => !worst || (item.value ?? Infinity) < (worst.value ?? Infinity) ? item : worst, null);
  const scoreSpread = strongestEngine && weakestEngine ? (strongestEngine.value ?? 0) - (weakestEngine.value ?? 0) : null;
  const primaryEvidence = evidence[0] || null;
  const primaryPrompt = primaryEvidence ? evidencePrompt(primaryEvidence) : null;
  const primaryContext = primaryEvidence ? evidenceContext(primaryEvidence) : null;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header Section */}
      <div>
        <Link to="/signals" className="text-sm font-semibold text-brand-primary hover:underline mb-4 inline-block">&larr; Back to Signals</Link>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">{signal.business_title || signal.title}</h1>
              <Badge variant={signal.severity.toLowerCase() as any}>{signal.severity}</Badge>
              {signal.governance_status && (
                <Badge variant={signal.governance_status.toLowerCase() as any}>{signal.governance_status}</Badge>
              )}
            </div>
            <p className="text-lg text-slate-600">{signal.business_summary || signal.description}</p>
            <Card className="mt-4 bg-slate-50">
              <p className="text-sm font-bold text-slate-900">In plain English: {guidance.label}</p>
              <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">What it means: </span>{signal.business_meaning || guidance.meaning}</p>
              <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">Why it matters: </span>{signal.business_impact || 'This finding may affect how the brand is represented in AI answers.'}</p>
              <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">What to do next: </span>{signal.recommended_next_step || guidance.action}</p>
              <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">What this does not prove: </span>{signal.do_not_conclude || 'The finding is not, by itself, proof of causation or claim truth.'}</p>
            </Card>
          </div>
          <button type="button" onClick={handleAskSolution} disabled={solutionLoading} className="shrink-0 rounded-xl bg-brand-primary px-4 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-brand-secondary disabled:cursor-wait disabled:opacity-60">
            {solutionLoading ? 'Generating solution...' : 'Ask AI for a solution'}
          </button>
        </div>
      </div>

      {/* Hero Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card glass className="bg-slate-800 text-white border-slate-700">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Raw metric (technical)</h3>
          <p className="text-xl font-black mt-2">{signal.current_value.toFixed(3)}</p>
          {signal.delta !== null && (
            <p className={`text-sm mt-2 ${signal.delta > 0 ? 'text-emerald-400' : signal.delta < 0 ? 'text-red-400' : 'text-slate-400'}`}>
              {signal.delta > 0 ? '↑' : signal.delta < 0 ? '↓' : ''} {Math.abs(signal.delta).toFixed(3)} from baseline
            </p>
          )}
        </Card>
        <Card glass>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Finding strength</h3>
          <p className="text-xl font-black mt-2 text-slate-800">{signal.confidence_label || 'Evidence strength is provisional'}</p>
          <p className="text-sm text-slate-500 mt-2">{signal.evidence_summary || `${signal.evidence_count} linked evidence rows`}</p>
        </Card>
        <Card glass>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Business attention</h3>
          <p className="text-xl font-bold mt-2 text-slate-800">{signal.business_priority}</p>
          <p className="text-sm text-slate-500 mt-2">Experimental attention tier from the rule</p>
        </Card>
        <Card glass>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</h3>
          <p className="text-xl font-bold mt-2 text-slate-800">{signal.status_label || signal.workflow_status.replaceAll('_', ' ')}</p>
          <p className="text-sm text-slate-500 mt-2">Technical status: {signal.workflow_status}</p>
        </Card>
      </div>

      <details className="rounded-xl border border-slate-200 bg-white p-5">
        <summary className="cursor-pointer font-bold text-slate-900">Technical details and raw metric</summary>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4 text-sm text-slate-600">
          <div><span className="block text-xs text-slate-400">Metric</span>{signal.technical_metric || 'Rule value'}</div>
          <div><span className="block text-xs text-slate-400">Raw value</span>{signal.current_value.toFixed(3)}</div>
          <div><span className="block text-xs text-slate-400">Threshold</span>{signal.technical_threshold === undefined ? '—' : signal.technical_threshold.toFixed(3)}</div>
          <div><span className="block text-xs text-slate-400">Rule</span>{signal.technical_rule || `${signal.signal_rule_id} v${signal.signal_rule_version}`}</div>
          <div><span className="block text-xs text-slate-400">Evidence rows</span>{signal.evidence_count}</div>
        </div>
      </details>

      {primaryEvidence && (
        <Card className="border-teal-100 bg-teal-50/60">
          <h2 className="text-base font-extrabold text-slate-900">What content or prompt does this refer to?</h2>
          <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <div><span className="block text-xs font-bold uppercase tracking-wide text-slate-500">Evidence subject</span><span className="mt-1 block font-semibold text-slate-900">{evidenceSubject(primaryEvidence)}</span></div>
            <div><span className="block text-xs font-bold uppercase tracking-wide text-slate-500">Content or page context</span><span className="mt-1 block text-slate-700">{primaryContext || 'Not present in this source row'}</span></div>
            <div><span className="block text-xs font-bold uppercase tracking-wide text-slate-500">Prompt / claim</span><span className="mt-1 block text-slate-700">{primaryPrompt || 'No prompt was recorded. This is a content-readiness summary, not a prompt-level score.'}</span></div>
            <div><span className="block text-xs font-bold uppercase tracking-wide text-slate-500">Source lineage</span><span className="mt-1 block font-mono text-xs text-slate-700">{primaryEvidence.original_filename} · row {primaryEvidence.source_row}</span></div>
          </div>
          <p className="mt-4 text-xs leading-5 text-slate-600">This signal is about the source row shown above. It does not identify a single page or prompt unless that field exists in the original CSV.</p>
        </Card>
      )}

      {solutionError && (
        <Card className="border-red-200 bg-red-50 text-red-800">
          <p className="font-bold">Could not generate a solution</p>
          <p className="mt-1 text-sm">{solutionError}</p>
        </Card>
      )}

      {solution && (
        <Card className="border-brand-primary/30 bg-white shadow-md">
          <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-xl font-extrabold text-slate-900">AI remediation solution</h2>
              <p className="mt-1 text-sm text-slate-600">A specific action plan generated from this signal’s source evidence, governance state, and current assessment context.</p>
            </div>
            <Badge variant={solution.fallback_used ? 'provisional' : 'verified'}>
              {solution.fallback_used ? 'Evidence-backed fallback' : 'AI-generated · evidence checked'}
            </Badge>
          </div>
          <div className="mt-5 rounded-xl bg-slate-50 p-5 text-slate-800">
            <div className="signal-solution-markdown">{renderMarkdown(solution.answer)}</div>
          </div>
          {solution.citations && solution.citations.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">Evidence used</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {solution.citations.slice(0, 12).map((citation, index) => (
                  <Link
                    key={`${citation.record_id}-${index}`}
                    to={`/evidence?query=${encodeURIComponent(citation.record_id)}`}
                    className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-brand-primary hover:bg-teal-100"
                  >
                    E{index + 1}: {citation.citation_text}
                  </Link>
                ))}
              </div>
            </div>
          )}
          {solution.limitations && solution.limitations.length > 0 && (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <h3 className="font-bold">Boundaries for this recommendation</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {solution.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}
              </ul>
            </div>
          )}
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          {/* Evidence */}
          <section>
            <h2 className="text-xl font-bold text-slate-900 mb-4">Supporting Evidence ({groupedEvidence.length} groups · {evidence.length} raw rows)</h2>
            {evidence.length === 0 ? (
              <Card><p className="text-slate-500 italic">No evidence rows recorded.</p></Card>
            ) : (
              <Card className="p-0 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-3">What was observed</th>
                        <th className="px-4 py-3">Observed value</th>
                        <th className="px-4 py-3">Source CSV / row</th>
                        <th className="px-4 py-3">AI engine</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {groupedEvidence.slice(0, 10).map((group) => (
                        <tr key={group.engine} className="hover:bg-slate-50 transition-colors">
                          <td className="px-4 py-3"><div className="font-medium text-slate-900">{evidenceSubject(group.rows[0])}</div><div className="mt-1 text-xs text-slate-500">{evidenceContext(group.rows[0]) || 'Source observation'}</div></td>
                          <td className="px-4 py-3 font-mono text-slate-600">{group.value !== null ? group.value.toFixed(2) : 'Vendor score unavailable'}</td>
                          <td className="px-4 py-3 text-xs text-slate-500"><div className="max-w-56 break-words">{group.rows[0].original_filename}</div><div>Row {group.rows[0].source_row}</div><Link to={`/evidence?query=${encodeURIComponent(group.rows[0].record_id)}`} className="mt-1 inline-block font-semibold text-brand-primary hover:underline">Open lineage</Link></td>
                          <td className="px-4 py-3 text-slate-500">{group.engine === 'Source evidence' ? 'Not recorded' : group.engine}<div className="mt-1 text-xs">{group.rows.length > 1 ? `${group.rows.length} rows combined` : '1 source row'}</div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {groupedEvidence.length > 10 && <div className="p-4 bg-slate-50 text-center text-sm text-slate-500 border-t border-slate-200">Showing first 10 evidence groups</div>}
                {evidence.length > groupedEvidence.length && <div className="px-4 pb-4 text-xs text-slate-500">Repeated rows remain available in Evidence Explorer. BrandRank has not confirmed whether repetition represents multiple executions, samples, or another hidden dimension.</div>}
              </Card>
            )}
          </section>

          {/* History */}
          <section>
            <h2 className="text-xl font-bold text-slate-900 mb-4">Signal History</h2>
            {history.length === 0 ? (
              <Card><p className="text-slate-500 italic">No prior runs recorded.</p></Card>
            ) : (
              <Card className="p-0 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-3">Run ID</th>
                        <th className="px-4 py-3">Date</th>
                        <th className="px-4 py-3">Value</th>
                        <th className="px-4 py-3">Severity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {history.map((h) => (
                        <tr key={h.assessment_run_id} className="hover:bg-slate-50">
                          <td className="px-4 py-3 font-mono text-xs">{h.assessment_run_id}</td>
                          <td className="px-4 py-3 text-slate-500">{formatLocalDateTime(h.created_at, '—')}</td>
                          <td className="px-4 py-3 font-medium text-slate-900">{h.current_value.toFixed(3)}</td>
                          <td className="px-4 py-3"><Badge variant={h.severity.toLowerCase() as any}>{h.severity}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </section>

          {comparisons && (
            <section>
              <h2 className="text-xl font-bold text-slate-900 mb-4">Comparative Evidence</h2>
              <Card>
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">How consistently do AI engines handle this claim?</h3>
                    <p className="mt-1 text-sm leading-5 text-slate-600">Each score summarizes the available observations for one AI engine and this statement. Comparing the engines helps identify whether the answer is stable or unpredictable.</p>
                  </div>
                  {scoreSpread !== null && <div className="shrink-0 rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-right"><div className="text-[10px] font-bold uppercase tracking-wider text-orange-700">Difference between engines</div><div className="text-xl font-black text-orange-900">{(scoreSpread * 100).toFixed(0)} points</div></div>}
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                  <span className="font-bold text-slate-900">What this means: </span>
                  {strongestEngine && weakestEngine
                    ? `${displayEngineName(strongestEngine.label)} gave the strongest score (${displayScore(strongestEngine.value)}), while ${displayEngineName(weakestEngine.label)} gave the weakest (${displayScore(weakestEngine.value)}). This spread indicates that people using different AI engines may receive materially different answers.`
                    : 'There are not enough comparable engine scores to explain consistency for this statement.'}
                </div>

                {engineRows.length > 0 ? (
                  <div className="mt-5 space-y-3">
                    {comparisons.engine_comparison.map((item) => (
                      <div key={item.label} className="rounded-xl border border-slate-200 p-3">
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <span className="font-bold text-slate-900">{displayEngineName(item.label)}</span>
                          <span className="font-black text-slate-900">{displayScore(item.value)}</span>
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-primary" style={{ width: `${scoreWidth(item.value)}%` }} /></div>
                        <p className="mt-1 text-xs text-slate-500">Average vendor score: {item.value === null ? 'not reported' : item.value.toFixed(3)} on the underlying 0–1 scale{item.sample_count ? ` · ${item.sample_count} source observations combined` : ''}.</p>
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-5 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">No comparable engine scores are available.</p>}

                <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm leading-5 text-blue-900">
                  <span className="font-bold">Important limitation: </span>
                  These scores show disagreement in the source observations. They do not prove that the claim is true or false, do not measure total AI visibility, and do not by themselves justify changing approved content.
                </div>

                <div className="mt-6 border-t border-slate-200 pt-5">
                  <h3 className="text-base font-bold text-slate-900">Competitor comparison</h3>
                  {comparisons.competitor_comparison.length > 0 ? (
                    <>
                      <p className="mt-1 text-sm text-slate-600">{comparisons.competitor_comparison_basis}</p>
                      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">{comparisons.competitor_comparison.map((item) => <div key={item.label} className="rounded-lg bg-slate-50 p-3"><div className="text-xs font-semibold text-slate-500">{displayEngineName(item.label)}</div><div className="mt-1 font-bold text-slate-900">{displayScore(item.value)}</div></div>)}</div>
                    </>
                  ) : <p className="mt-2 rounded-lg bg-slate-50 p-3 text-sm leading-5 text-slate-600">This is a brand-specific claim, so competitor scoring is not applicable in this comparison.</p>}
                </div>
              </Card>
            </section>
          )}
        </div>

        {/* Sidebar Info */}
        <div className="space-y-6">
          <Card>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-200 pb-2 mb-4">Technical Metadata</h3>
            <div className="space-y-4 text-sm">
              <div>
                <span className="block text-slate-500">Rule ID</span>
                <span className="font-mono text-slate-900">{signal.signal_rule_id} v{signal.signal_rule_version}</span>
              </div>
              <div>
                <span className="block text-slate-500">Group Key</span>
                <span className="font-mono text-slate-900">{signal.group_key}</span>
              </div>
              <div>
                <span className="block text-slate-500">Truth Validation</span>
                <Badge variant={signal.truth_validation_status === 'VALIDATED' ? 'verified' : 'provisional'}>
                  {signal.truth_validation_status}
                </Badge>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
