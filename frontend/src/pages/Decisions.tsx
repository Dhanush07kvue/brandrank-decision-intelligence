import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSignals, createIntervention } from '../services/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

const STATUS_GROUPS = [
  { key: 'NEEDS_DIAGNOSIS', label: 'Needs Diagnosis', color: 'bg-red-500' },
  { key: 'NEEDS_TRUTH_VALIDATION', label: 'Needs Truth Validation', color: 'bg-orange-500' },
  { key: 'READY_FOR_OWNER_REVIEW', label: 'Ready for Owner Review', color: 'bg-amber-500' },
  { key: 'APPROVED_FOR_BRIEF', label: 'Approved for Brief', color: 'bg-blue-500' },
  { key: 'DETECTED', label: 'Detected', color: 'bg-purple-500' },
  { key: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient Evidence', color: 'bg-slate-500' },
];

interface Signal {
  signal_instance_id: string;
  title: string;
  signal_type: string;
  severity: string;
  confidence: number;
  business_priority: string;
  current_value: number;
  delta: number | null;
  workflow_status: string;
  diagnosis_status: string;
  truth_validation_status: string;
  evidence_count: number;
  runs_affected: number;
  engines_affected: number;
}

export function Decisions() {
  const navigate = useNavigate();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    getSignals({ limit: 200 } as any)
      .then(setSignals)
      .catch(() => setError('Could not load signals'))
      .finally(() => setLoading(false));
  }, []);

  const grouped: Record<string, Signal[]> = {};
  for (const s of signals) {
    const key = s.workflow_status || 'DETECTED';
    grouped[key] = grouped[key] || [];
    grouped[key].push(s);
  }

  async function handleCreateIntervention(sig: Signal) {
    setCreating(sig.signal_instance_id);
    try {
      const iv = await createIntervention({
        signal_instance_id: sig.signal_instance_id,
        business_problem: `${sig.title} — score (${(sig.current_value * 100).toFixed(0)}%) on priority prompts`,
        diagnosed_cause: 'Pending diagnosis',
        recommended_action: 'Review signal evidence and validate approved truth',
        priority: sig.business_priority === 'HIGH' ? 'HIGH' : 'MEDIUM',
      });
      setSuccessMsg(`Intervention created. Opening workspace…`);
      setTimeout(() => {
        setSuccessMsg(null);
        navigate(`/interventions/${iv.intervention_id}`);
      }, 1200);
    } catch (e: any) {
      setError(e.message || 'Failed to create intervention');
    } finally {
      setCreating(null);
    }
  }

  if (loading) return <div className="p-10 text-slate-500 animate-pulse">Loading decision backlog...</div>;

  const totalSignals = signals.length;
  const highPriority = signals.filter(s => s.business_priority === 'HIGH').length;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Decision Backlog</h1>
          <p className="text-slate-500 mt-2 text-lg">Signals requiring action, grouped by workflow status.</p>
        </div>
      </div>

      {error && <Card className="bg-red-50 text-red-800 border-red-200 flex justify-between">
        <span>{error}</span>
        <button onClick={() => setError(null)} className="font-bold">✕</button>
      </Card>}
      
      {successMsg && <Card className="bg-emerald-50 text-emerald-800 border-emerald-200">
        <span>{successMsg}</span>
      </Card>}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card glass className="p-4 text-center">
          <div className="text-2xl font-black text-slate-900">{totalSignals}</div>
          <div className="text-xs font-semibold text-slate-500 uppercase mt-1">Total signals</div>
        </Card>
        <Card glass className="p-4 text-center">
          <div className="text-2xl font-black text-red-600">{highPriority}</div>
          <div className="text-xs font-semibold text-red-500/80 uppercase mt-1">High priority</div>
        </Card>
        <Card glass className="p-4 text-center border-b-4 border-b-red-500">
          <div className="text-2xl font-black text-slate-900">{grouped['NEEDS_DIAGNOSIS']?.length ?? 0}</div>
          <div className="text-xs font-semibold text-slate-500 uppercase mt-1">Need diagnosis</div>
        </Card>
        <Card glass className="p-4 text-center border-b-4 border-b-orange-500">
          <div className="text-2xl font-black text-slate-900">{grouped['NEEDS_TRUTH_VALIDATION']?.length ?? 0}</div>
          <div className="text-xs font-semibold text-slate-500 uppercase mt-1">Need truth</div>
        </Card>
        <Card glass className="p-4 text-center border-b-4 border-b-blue-500">
          <div className="text-2xl font-black text-slate-900">{grouped['APPROVED_FOR_BRIEF']?.length ?? 0}</div>
          <div className="text-xs font-semibold text-slate-500 uppercase mt-1">Approved</div>
        </Card>
      </div>

      {signals.length === 0 ? (
        <Card className="text-center py-12 text-slate-500">
          <p>No signals in the decision backlog. Run signal evaluation from Data Trust.</p>
        </Card>
      ) : (
        <div className="space-y-8">
          {STATUS_GROUPS.map(group => {
            const items = grouped[group.key];
            if (!items?.length) return null;
            return (
              <section key={group.key}>
                <div className="flex items-center gap-3 mb-4">
                  <span className={`w-3 h-3 rounded-full ${group.color}`}></span>
                  <h2 className="text-xl font-bold text-slate-900">{group.label}</h2>
                  <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full text-xs font-bold">{items.length}</span>
                </div>
                <Card className="p-0 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-3">Signal</th>
                          <th className="px-4 py-3">Severity</th>
                          <th className="px-4 py-3">Priority</th>
                          <th className="px-4 py-3">Score</th>
                          <th className="px-4 py-3">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {items.map(sig => (
                          <tr key={sig.signal_instance_id} className="hover:bg-slate-50">
                            <td className="px-4 py-3">
                              <button
                                className="font-medium text-brand-primary hover:underline text-left"
                                onClick={() => navigate(`/signals/${sig.signal_instance_id}`)}
                              >
                                {sig.title}
                              </button>
                            </td>
                            <td className="px-4 py-3"><Badge variant={sig.severity.toLowerCase() as any}>{sig.severity}</Badge></td>
                            <td className="px-4 py-3"><Badge variant={sig.business_priority === 'HIGH' ? 'high' : 'medium'}>{sig.business_priority}</Badge></td>
                            <td className="px-4 py-3 font-mono">{(sig.current_value * 100).toFixed(0)}%</td>
                            <td className="px-4 py-3">
                              <div className="flex gap-2">
                                <Button
                                  variant="primary"
                                  onClick={() => handleCreateIntervention(sig)}
                                  disabled={creating === sig.signal_instance_id}
                                >
                                  {creating === sig.signal_instance_id ? 'Creating...' : 'Create Intervention'}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
