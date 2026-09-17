import { useState, useEffect } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

export function Settings() {
  const [mode, setMode] = useState<'EXECUTIVE' | 'ANALYST'>('EXECUTIVE');
  const [historyEnabled, setHistoryEnabled] = useState(true);

  // Load from local storage on mount
  useEffect(() => {
    const savedMode = localStorage.getItem('di_assistant_mode') as 'EXECUTIVE' | 'ANALYST' | null;
    if (savedMode) setMode(savedMode);
    
    const savedHistory = localStorage.getItem('di_assistant_history');
    if (savedHistory !== null) setHistoryEnabled(savedHistory === 'true');
  }, []);

  const handleSave = () => {
    localStorage.setItem('di_assistant_mode', mode);
    localStorage.setItem('di_assistant_history', historyEnabled.toString());
    // Flash a quick alert or notification here if desired
    alert('Settings saved!');
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Configuration</h1>
        <p className="text-slate-500 mt-2 text-lg">System preferences and AI Assistant behavior.</p>
      </div>

      <div className="space-y-6">
        <section>
          <h2 className="text-xl font-bold text-slate-900 mb-4">Intelligence Assistant</h2>
          <Card className="space-y-6">
            
            {/* Mode Selection */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <div>
                  <h3 className="font-bold text-slate-900">Operation Mode</h3>
                  <p className="text-sm text-slate-500">Determines the depth and tone of AI responses.</p>
                </div>
                <Badge variant={mode === 'EXECUTIVE' ? 'verified' : 'high'}>{mode}</Badge>
              </div>
              <div className="flex gap-4 mt-3">
                <button
                  onClick={() => setMode('EXECUTIVE')}
                  className={`flex-1 p-4 rounded-xl border-2 transition-all text-left ${
                    mode === 'EXECUTIVE' 
                      ? 'border-brand-primary bg-brand-light/20' 
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <h4 className={`font-bold ${mode === 'EXECUTIVE' ? 'text-brand-secondary' : 'text-slate-700'}`}>Executive Read-out</h4>
                  <p className="text-xs text-slate-500 mt-1">Concise, action-oriented summaries focusing on "what" and "why it matters".</p>
                </button>
                
                <button
                  onClick={() => setMode('ANALYST')}
                  className={`flex-1 p-4 rounded-xl border-2 transition-all text-left ${
                    mode === 'ANALYST' 
                      ? 'border-brand-primary bg-brand-light/20' 
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <h4 className={`font-bold ${mode === 'ANALYST' ? 'text-brand-secondary' : 'text-slate-700'}`}>Analyst Deep-dive</h4>
                  <p className="text-xs text-slate-500 mt-1">Detailed breakdowns including technical methodology, limitations, and raw evidence.</p>
                </button>
              </div>
            </div>

            <hr className="border-slate-100" />

            {/* Conversation History */}
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-bold text-slate-900">Conversation Context</h3>
                <p className="text-sm text-slate-500">Maintain context across multiple questions during a session.</p>
              </div>
              <button 
                onClick={() => setHistoryEnabled(!historyEnabled)}
                className={`w-14 h-7 rounded-full p-1 transition-colors ${historyEnabled ? 'bg-brand-primary' : 'bg-slate-300'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${historyEnabled ? 'translate-x-7' : 'translate-x-0'}`}></div>
              </button>
            </div>

          </Card>
        </section>

        <div className="flex justify-end">
          <Button variant="primary" onClick={handleSave}>Save Preferences</Button>
        </div>
      </div>
    </div>
  );
}
