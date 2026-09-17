import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCurrentContext, getInterventions, seedFixtures } from '../services/api';
import { formatLocalDateTime } from '../utils/dateTime';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

interface Intervention {
  intervention_id: string;
  brand_id: string;
  market: string;
  business_problem: string;
  diagnosed_cause: string;
  recommended_action: string;
  status: string;
  priority: string;
  confidence: number;
  owner: string | null;
  target_page_id: string | null;
  target_claim_id: string | null;
  planned_publish_date: string | null;
  retest_date: string | null;
  updated_at: string | null;
}

export function Interventions() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Intervention[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [brandId, setBrandId] = useState<string | undefined>();

  function load(currentBrandId = brandId) {
    setLoading(true);
    getInterventions(currentBrandId ? { brand_id: currentBrandId } : undefined)
      .then((data: any) => setItems(data.interventions || []))
      .catch(() => setError('Could not load interventions'))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    getCurrentContext().then((context: any) => {
      setBrandId(context.brand_id);
      load(context.brand_id);
    }).catch(() => load());
  }, []);

  async function handleSeed() {
    setSeeding(true);
    try {
      const result = await seedFixtures();
      setMessage(result.message);
      load();
    } catch {
      setError('Failed to seed fixtures');
    } finally {
      setSeeding(false);
    }
  }

  if (loading) return <div className="p-10 text-slate-500 animate-pulse">Loading interventions...</div>;

  const byStatus: Record<string, number> = {};
  for (const iv of items) {
    byStatus[iv.status] = (byStatus[iv.status] || 0) + 1;
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Intervention Workspace</h1>
          <p className="text-slate-500 mt-2 text-lg">Governed activation drafts from signal to brief, publish, and retest.</p>
        </div>
        <Button variant="secondary" onClick={handleSeed} disabled={seeding}>
          {seeding ? 'Seeding...' : 'Seed POC Fixtures'}
        </Button>
      </div>

      {error && <Card className="bg-red-50 text-red-800 border-red-200 flex justify-between">
        <span>{error}</span>
        <button onClick={() => setError(null)} className="font-bold">✕</button>
      </Card>}
      
      {message && <Card className="bg-emerald-50 text-emerald-800 border-emerald-200 flex justify-between">
        <span>{message}</span>
        <button onClick={() => setMessage(null)} className="font-bold">✕</button>
      </Card>}

      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        {Object.entries(byStatus).map(([status, count]) => (
          <Card glass key={status} className="p-4 text-center">
            <div className="text-2xl font-black text-slate-900">{count}</div>
            <div className="text-xs font-semibold text-slate-500 uppercase mt-1 truncate" title={status.replace(/_/g, ' ')}>
              {status.replace(/_/g, ' ')}
            </div>
          </Card>
        ))}
      </div>

      {items.length === 0 ? (
        <Card className="text-center py-12 text-slate-500">
          <p>No interventions yet. Create from the Decision Backlog or seed the configured POC fixtures.</p>
        </Card>
      ) : (
        <Card className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Business Problem</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Owner</th>
                  <th className="px-4 py-3">Publish Date</th>
                  <th className="px-4 py-3">Retest Date</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map(iv => (
                  <tr key={iv.intervention_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 max-w-xs truncate">
                      <button 
                        className="font-medium text-brand-primary hover:underline text-left truncate w-full"
                        onClick={() => navigate(`/interventions/${iv.intervention_id}`)}
                      >
                        {iv.business_problem}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={
                        ['NEEDS_DIAGNOSIS', 'NEEDS_TRUTH_VALIDATION'].includes(iv.status) ? 'critical' :
                        ['READY_FOR_OWNER_REVIEW', 'APPROVED_FOR_BRIEF'].includes(iv.status) ? 'high' :
                        ['IN_CREATION', 'IN_MLR'].includes(iv.status) ? 'medium' :
                        ['APPROVED', 'PUBLISHED', 'MEASURED'].includes(iv.status) ? 'verified' : 'blocked'
                      }>
                        {iv.status.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={iv.priority === 'HIGH' ? 'high' : 'medium'}>{iv.priority}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-600 font-medium">{iv.owner || <span className="text-slate-400 italic">Unassigned</span>}</td>
                    <td className="px-4 py-3 text-slate-500">{iv.planned_publish_date ? formatLocalDateTime(iv.planned_publish_date, '—') : '—'}</td>
                    <td className="px-4 py-3 text-slate-500">{iv.retest_date ? formatLocalDateTime(iv.retest_date, '—') : '—'}</td>
                    <td className="px-4 py-3">
                      <Button variant="ghost" onClick={() => navigate(`/interventions/${iv.intervention_id}`)}>Open</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
