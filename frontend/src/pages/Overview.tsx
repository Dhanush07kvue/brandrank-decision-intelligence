import { useEffect, useState } from 'react';
import { getDatasetStatus, getSignals, getInterventions, getQuality } from '../services/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Link } from 'react-router-dom';

type Status = {
  canonical_observations: number;
};

type Quality = {
  physical_files_discovered: number;
};

export function Overview() {
  const [status, setStatus] = useState<Status | null>(null);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [interventions, setInterventions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const [s, q, sigs, ints] = await Promise.all([
          getDatasetStatus().catch(() => null),
          getQuality().catch(() => null),
          getSignals().catch(() => []),
          getInterventions().then((result: any) => (result.interventions || []).filter((item: any) => !['CLOSED', 'REJECTED'].includes(item.status))).catch(() => [])
        ]);
        setStatus(s);
        setQuality(q);
        setSignals(sigs.filter((s: any) => s.governance_status !== 'BLOCKED'));
        setInterventions(ints);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  if (loading) {
    return <div className="p-10 text-slate-500 animate-pulse">Loading executive summary...</div>;
  }

  const criticalSignals = signals.filter(s => s.severity === 'CRITICAL');
  const highSignals = signals.filter(s => s.severity === 'HIGH');
  const topSignals = [...criticalSignals, ...highSignals].slice(0, 5);
  const topInterventions = interventions.slice(0, 5);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Executive Overview</h1>
          <p className="text-slate-500 mt-2 text-lg">Top signals and immediate priorities.</p>
        </div>
        <Link to="/assistant">
          <Button variant="primary">Ask AI Assistant</Button>
        </Link>
      </div>

      {/* Hero Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card glass className="bg-gradient-premium border-none text-white">
          <h3 className="text-sm font-semibold opacity-90 uppercase tracking-wider">Critical Risks</h3>
          <p className="text-4xl font-black mt-2">{criticalSignals.length}</p>
        </Card>
        <Card glass>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">High Risks</h3>
          <p className="text-4xl font-black mt-2 text-slate-800">{highSignals.length}</p>
        </Card>
        <Card glass>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Active Signals</h3>
          <p className="text-4xl font-black mt-2 text-slate-800">{signals.length}</p>
        </Card>
        <Card glass>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Data Volume</h3>
          <p className="text-4xl font-black mt-2 text-slate-800">{status?.canonical_observations?.toLocaleString() || 0}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Top Signals */}
        <section className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-slate-900">Priority Signals</h2>
            <Link to="/signals" className="text-sm font-semibold text-brand-primary hover:underline">View All</Link>
          </div>
          <div className="space-y-4">
            {topSignals.length > 0 ? topSignals.map(sig => (
              <Card key={sig.signal_instance_id} className="interactive-scale cursor-pointer">
                <Link to={`/signals/${encodeURIComponent(sig.signal_instance_id)}`}>
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-bold text-slate-900">{sig.title}</h3>
                      <p className="text-sm text-slate-600 mt-1 line-clamp-2">{sig.description}</p>
                    </div>
                    <Badge variant={sig.severity.toLowerCase() as any}>{sig.severity}</Badge>
                  </div>
                </Link>
              </Card>
            )) : (
              <Card><p className="text-slate-500 italic">No priority signals found.</p></Card>
            )}
          </div>
        </section>

        {/* Top Interventions */}
        <section className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-slate-900">Active Interventions</h2>
            <Link to="/interventions" className="text-sm font-semibold text-brand-primary hover:underline">View All</Link>
          </div>
          <div className="space-y-4">
            {topInterventions.length > 0 ? topInterventions.map(intv => (
              <Card key={intv.intervention_id} className="interactive-scale cursor-pointer">
                <Link to={`/interventions/${encodeURIComponent(intv.intervention_id)}`}>
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-bold text-slate-900">{intv.business_problem}</h3>
                      <p className="text-sm text-slate-600 mt-1 line-clamp-2">{intv.recommended_action}</p>
                    </div>
                    <Badge variant="provisional">{intv.status}</Badge>
                  </div>
                </Link>
              </Card>
            )) : (
              <Card><p className="text-slate-500 italic">No active interventions found.</p></Card>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
