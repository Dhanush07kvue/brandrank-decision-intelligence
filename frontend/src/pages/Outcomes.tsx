import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getOutcomes } from '../services/api';
import { formatLocalDateTime } from '../utils/dateTime';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

interface Outcome {
  outcome_id: string;
  intervention_id: string;
  baseline_run_id: string | null;
  post_change_run_id: string | null;
  published_at: string | null;
  retested_at: string | null;
  baseline_value: number | null;
  post_change_value: number | null;
  absolute_delta: number | null;
  percentage_delta: number | null;
  engines_improved: number | null;
  prompts_improved: number | null;
  outcome_status: string;
  confidence: number;
  comparison_limitations: string | null;
  created_at: string | null;
}

export function Outcomes() {
  const navigate = useNavigate();
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOutcomes()
      .then(setOutcomes)
      .catch(() => setError('Could not load outcomes'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-10 text-slate-500 animate-pulse">Loading outcome records...</div>;

  const summary: Record<string, number> = {};
  for (const o of outcomes) {
    summary[o.outcome_status] = (summary[o.outcome_status] || 0) + 1;
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Outcome Centre</h1>
          <p className="text-slate-500 mt-2 text-lg">Post-change measurement results with comparison guards and attribution limits.</p>
        </div>
      </div>

      {error && <Card className="bg-red-50 text-red-800 border-red-200">
        <p>{error}</p>
      </Card>}

      {outcomes.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          {Object.entries(summary).map(([status, count]) => (
            <Card glass key={status} className="p-4 text-center">
              <div className="text-2xl font-black text-slate-900">{count}</div>
              <div className="text-xs font-semibold text-slate-500 uppercase mt-1 truncate" title={status.replace(/_/g, ' ')}>
                {status.replace(/_/g, ' ')}
              </div>
            </Card>
          ))}
        </div>
      )}

      {outcomes.length === 0 ? (
        <Card className="text-center py-12 text-slate-500">
          <p>No outcomes recorded yet. Open an intervention, publish it, then measure the outcome.</p>
          <Button variant="ghost" onClick={() => navigate('/interventions')} className="mt-4">
            Go to Interventions
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          <Card className="p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3">Intervention</th>
                    <th className="px-4 py-3">Outcome</th>
                    <th className="px-4 py-3">Baseline</th>
                    <th className="px-4 py-3">Post-change</th>
                    <th className="px-4 py-3">Delta</th>
                    <th className="px-4 py-3">Pct Change</th>
                    <th className="px-4 py-3">Confidence</th>
                    <th className="px-4 py-3">Retested At</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {outcomes.map(o => {
                    const delta = o.absolute_delta;
                    return (
                      <tr key={o.outcome_id} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <button 
                            className="font-medium text-brand-primary hover:underline text-left font-mono text-xs"
                            onClick={() => navigate(`/interventions/${o.intervention_id}`)}
                          >
                            {o.intervention_id.slice(0, 12)}...
                          </button>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={
                            o.outcome_status === 'IMPROVED' ? 'verified' :
                            o.outcome_status === 'DETERIORATED' ? 'critical' :
                            o.outcome_status === 'MIXED_BY_ENGINE' ? 'high' :
                            ['NO_MATERIAL_CHANGE'].includes(o.outcome_status) ? 'medium' : 'blocked'
                          }>
                            {o.outcome_status.replace(/_/g, ' ')}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 font-mono">{o.baseline_value !== null ? (o.baseline_value * 100).toFixed(1) + '%' : '—'}</td>
                        <td className="px-4 py-3 font-mono">{o.post_change_value !== null ? (o.post_change_value * 100).toFixed(1) + '%' : '—'}</td>
                        <td className={`px-4 py-3 font-mono font-bold ${(delta ?? 0) >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                          {delta !== null ? `${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="px-4 py-3 font-mono">{o.percentage_delta !== null ? `${o.percentage_delta >= 0 ? '+' : ''}${o.percentage_delta.toFixed(1)}%` : '—'}</td>
                        <td className="px-4 py-3 text-slate-500">{(o.confidence * 100).toFixed(0)}%</td>
                        <td className="px-4 py-3 text-slate-500 text-xs">{formatLocalDateTime(o.retested_at, '—')}</td>
                        <td className="px-4 py-3">
                          <Button variant="ghost" onClick={() => navigate(`/interventions/${o.intervention_id}`)}>Open</Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="bg-slate-50 p-4 border-t border-slate-200 text-xs text-slate-500">
              <strong className="text-slate-700">Attribution Limit:</strong> All outcomes are observational comparisons only. External factors may influence results. Comparison requires same brand, market, language, metric and AI engines.
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
