import { useState } from 'react';
import { Card } from './Card';
import { Button } from './Button';
import { Badge } from './Badge';

const DEMO_STEPS = [
  {
    title: '1. Executive Overview',
    path: '/',
    description: 'Start here. Point out how we focus only on Critical/High risks. No noise. The system filters out irrelevant metrics.'
  },
  {
    title: '2. Semantic Trust',
    path: '/data-trust',
    description: 'Click Data Trust. Explain how Kenvue defines "Truth" via Metric Contracts. Show the Semantic Blockers tab to prove we don\'t activate on bad data.'
  },
  {
    title: '3. Signal Observatory',
    path: '/signals',
    description: 'Go to Signals. Show how signals are classified as Governed, Experimental, or Blocked based on those contracts.'
  },
  {
    title: '4. The Aveeno Story',
    path: '/signals/sig_demo_oat_001',
    description: 'Click into the Oat Science signal. Highlight its experimental trust state, contract status, and exact source-row evidence.'
  },
  {
    title: '5. Governed Activation',
    path: '/interventions',
    description: 'Go to Interventions. Show the drafted brief for Oat Science. We don\'t just score; we draft the exact content to fix the gap.'
  },
  {
    title: '6. Leadership Chat',
    path: '/assistant',
    description: 'Open the Assistant. Ask: "What should leadership prioritize based on current evidence?" Show the structured response and citations.'
  }
];

export function DemoNavigator() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isOpen, setIsOpen] = useState(true);

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button variant="primary" onClick={() => setIsOpen(true)}>
          Show Demo Guide
        </Button>
      </div>
    );
  }

  const step = DEMO_STEPS[currentStep];

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 shadow-2xl animate-fade-in">
      <Card className="border-brand-primary border-2 p-0 overflow-hidden shadow-xl bg-white/95 backdrop-blur-sm">
        <div className="bg-brand-primary text-white p-3 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm">Demo Navigator</span>
            <Badge variant="experimental" className="border-white/20">Configured POC</Badge>
          </div>
          <button onClick={() => setIsOpen(false)} className="text-white/80 hover:text-white font-bold">✕</button>
        </div>
        
        <div className="p-4 space-y-4">
          <div>
            <h3 className="font-extrabold text-brand-secondary text-lg mb-1">{step.title}</h3>
            <p className="text-sm text-slate-600 leading-relaxed">{step.description}</p>
          </div>
          
          <div className="bg-slate-50 p-2 rounded text-xs font-mono text-slate-500 border border-slate-100 flex items-center justify-between">
            <span>Target Route:</span>
            <span className="font-bold text-brand-primary">{step.path}</span>
          </div>

          <div className="flex justify-between items-center pt-2">
            <button 
              onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
              disabled={currentStep === 0}
              className="text-xs font-bold text-slate-400 hover:text-slate-700 disabled:opacity-50"
            >
              ← Previous
            </button>
            <span className="text-xs font-bold text-slate-500">{currentStep + 1} / {DEMO_STEPS.length}</span>
            <Button 
              variant={currentStep === DEMO_STEPS.length - 1 ? 'ghost' : 'primary'}
              onClick={() => setCurrentStep(Math.min(DEMO_STEPS.length - 1, currentStep + 1))}
              disabled={currentStep === DEMO_STEPS.length - 1}
              className="py-1 px-3 text-xs"
            >
              Next Step →
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
