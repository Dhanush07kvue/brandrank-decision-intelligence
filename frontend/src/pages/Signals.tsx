import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { evaluateSignals, getSignals } from '../services/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

type SignalInstance = {
  signal_instance_id: string;
  signal_rule_id: string;
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
  governance_status: string;
  assessment_run_id: string;
  business_title?: string;
  business_summary?: string;
  business_meaning?: string;
  status_label?: string;
  confidence_label?: string;
  technical_value?: number;
  technical_threshold?: number;
  technical_rule?: string;
};

type SignalTypeGuide = {
  label: string;
  meaning: string;
  action: string;
};

const SIGNAL_TYPE_GUIDANCE: Record<string, SignalTypeGuide> = {
  CROSS_LLM_INCONSISTENCY: {
    label: 'AI answer consistency',
    meaning: 'Different AI engines are giving materially different answers about the same claim. This is an instability signal, not proof that Aveeno has low visibility.',
    action: 'Compare the engine-level evidence, validate the underlying claim, then decide whether the content needs clearer, approved source evidence.',
  },
  CLAIM_AGREEMENT_INVESTIGATION: {
    label: 'Claim agreement risk',
    meaning: 'The engines agree with the claim less often than the configured agreement floor.',
    action: 'Send the claim through Kenvue truth validation before changing content or making a regulatory conclusion.',
  },
  VISIBILITY_GAP: {
    label: 'AI visibility gap',
    meaning: 'The available visibility ranking suggests a priority prompt may be underrepresented, but this evaluation is blocked until BrandRank confirms what the rank number means.',
    action: 'Resolve the vendor rank-definition question before using this as a performance or content recommendation.',
  },
  READINESS_DETERIORATION: {
    label: 'Content readiness gap',
    meaning: 'A content-readiness factor is below the configured activation floor.',
    action: 'Review the factor evidence and improve the content only after confirming the vendor scoring definition.',
  },
  EVIDENCE_ACCESSIBILITY_DEFICIT: {
    label: 'Evidence accessibility gap',
    meaning: 'AI engines are citing too few sources that appear to be owned or attributable to the brand.',
    action: 'Check source ownership and machine-readable evidence coverage before treating this as a content defect.',
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

const SIGNAL_TYPES = Object.keys(SIGNAL_TYPE_GUIDANCE);

function signalTypeGuide(signalType: string): SignalTypeGuide {
  return SIGNAL_TYPE_GUIDANCE[signalType] || {
    label: signalType.replaceAll('_', ' ').toLowerCase(),
    meaning: 'A rule-based observation requiring review.',
    action: 'Open the evidence and confirm the business interpretation before acting.',
  };
}

function formatMetric(value: number | null | undefined, digits = 3) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'Not available';
  return Number(value).toFixed(digits);
}

const TABS = [
  { id: 'all', label: 'All Signals' },
  { id: 'governed', label: 'Governed' },
  { id: 'experimental', label: 'Experimental' },
  { id: 'blocked', label: 'Blocked' },
];

export function Signals() {
  const [allSignals, setAllSignals] = useState<SignalInstance[]>([]);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('all');
  const [severity, setSeverity] = useState('');
  const [priority, setPriority] = useState('');
  const [truthStatus, setTruthStatus] = useState('');
  const [signalType, setSignalType] = useState('');

  const loadSignals = async () => {
    setLoading(true);
    setError(null);
    try {
      setAllSignals(await getSignals());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load signals');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSignals();
  }, []);

  const tabSignals = allSignals.filter((signal) => activeTab === 'all' || signal.governance_status === activeTab.toUpperCase());
  const signals = tabSignals.filter((signal) => (
    (!severity || signal.severity === severity) &&
    (!priority || signal.business_priority === priority) &&
    (!truthStatus || signal.truth_validation_status === truthStatus) &&
    (!signalType || signal.signal_type === signalType)
  ));

  function clearFilters() {
    setActiveTab('all');
    setSeverity('');
    setPriority('');
    setTruthStatus('');
    setSignalType('');
  }

  const handleEvaluate = async () => {
    setEvaluating(true);
    setError(null);
    try {
      await evaluateSignals();
      await loadSignals();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to evaluate signals');
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Signal Observatory</h1>
          <p className="text-slate-500 mt-1">Data-driven findings from the semantic trust layer. One finding can summarize many observations and files.</p>
        </div>
        <Button variant="primary" onClick={handleEvaluate} disabled={evaluating}>
          {evaluating ? 'Evaluating...' : 'Re-run Evaluation'}
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 border-b border-slate-200">
        {TABS.map((tab) => (
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

      <Card>
        <div className="flex flex-wrap gap-3 items-center">
          <span className="text-sm font-semibold text-slate-600">Safe filters</span>
          <select aria-label="Severity" value={severity} onChange={(e) => setSeverity(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">All severities</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option>BLOCKED</option>
          </select>
          <select aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">All priorities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option>
          </select>
          <select aria-label="Truth status" value={truthStatus} onChange={(e) => setTruthStatus(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">All truth states</option><option>VALIDATED</option><option>PENDING</option><option>BLOCKED</option><option>NOT_STARTED</option>
          </select>
          <select aria-label="Signal type" value={signalType} onChange={(e) => setSignalType(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">All signal types</option>
            {SIGNAL_TYPES.map((type) => <option key={type} value={type}>{SIGNAL_TYPE_GUIDANCE[type].label}</option>)}
          </select>
          {(activeTab !== 'all' || severity || priority || truthStatus || signalType) && <button type="button" onClick={clearFilters} className="rounded-lg px-3 py-2 text-sm font-semibold text-brand-primary hover:bg-teal-50">Clear filters</button>}
        </div>
      </Card>

      <Card className="bg-slate-50">
        <div className="flex flex-wrap gap-3 items-start">
          <div className="mr-2 min-w-52">
            <p className="text-sm font-bold text-slate-900">How to read signals</p>
            <p className="text-xs text-slate-500 mt-1">One signal can summarize many rows and files. It is a rule-based finding, not a one-file count.</p>
          </div>
          {SIGNAL_TYPES.map((type) => {
            const guide = SIGNAL_TYPE_GUIDANCE[type];
            const count = tabSignals.filter((s) => s.signal_type === type).length;
            return <button type="button" key={type} aria-pressed={signalType === type} onClick={() => setSignalType((current) => current === type ? '' : type)} className={`rounded-lg border bg-white px-3 py-2 text-left hover:border-brand-primary ${signalType === type ? 'border-brand-primary ring-2 ring-teal-100' : 'border-slate-200'}`}>
              <span className="block text-xs font-bold text-slate-700">{guide.label} <span className="text-brand-primary">({count})</span></span>
              <span className="block mt-1 max-w-56 text-[11px] leading-4 text-slate-500">{guide.meaning}</span>
            </button>;
          })}
        </div>
      </Card>

      {error && (
        <Card className="bg-red-50 border-red-200 text-red-800">
          <p>{error}</p>
        </Card>
      )}

      {loading ? (
        <div className="text-slate-500 animate-pulse">Loading signals...</div>
      ) : signals.length === 0 ? (
        <Card className="text-center py-12 text-slate-500">
          <p>No signals found for the selected tab.</p>
        </Card>
      ) : (
        <div className="space-y-4">
          <p className="text-sm font-semibold text-slate-600">Showing {signals.length} of {tabSignals.length} rule-generated finding{signals.length === 1 ? '' : 's'} for the selected filters.</p>
          {signals.map((s) => (
            <Card key={s.signal_instance_id} className="interactive-scale">
              <Link to={`/signals/${s.signal_instance_id}`}>
                {(() => { const guide = signalTypeGuide(s.signal_type); return (
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-lg font-bold text-slate-900 hover:text-brand-primary transition-colors">{s.business_title || s.title}</h3>
                      {s.governance_status && (
                        <Badge variant={s.governance_status.toLowerCase() as any}>{s.governance_status}</Badge>
                      )}
                    </div>
                    <p className="text-slate-600 text-sm">{s.business_summary || guide.meaning}</p>
                    <p className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700"><span className="font-bold">What this means: </span>{s.business_meaning || guide.meaning}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-slate-500 font-medium">
                      <span>Group: {s.group_key}</span>
                      <span>Signal type: {guide.label}</span>
                      <span>Evidence rows: {s.evidence_count}</span>
                      <span>AI engines: {s.engines_affected || 'n/a'}</span>
                      <span>{s.confidence_label || (s.confidence == null ? 'Evidence strength: Not established' : `Evidence strength: ${(s.confidence * 100).toFixed(0)}%`)}</span>
                    </div>
                    <details className="mt-2 text-xs text-slate-500" onClick={(event) => event.stopPropagation()}>
                      <summary className="cursor-pointer font-semibold">Technical details</summary>
                      <span className="mr-4">Rule: {s.technical_rule || s.signal_rule_id}</span>
                      <span className="mr-4">Raw value: {formatMetric(s.technical_value ?? s.current_value)}</span>
                      {s.technical_threshold != null && <span>Threshold: {formatMetric(s.technical_threshold)}</span>}
                    </details>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Badge variant={s.severity.toLowerCase() as any}>{s.severity}</Badge>
                    <span className="text-xs text-slate-400">{s.workflow_status}</span>
                  </div>
                </div>); })()}
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
