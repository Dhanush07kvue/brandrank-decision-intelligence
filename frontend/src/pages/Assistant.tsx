import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { renderMarkdown } from '../utils/markdown';
import { askLeadershipChatAdvanced, getCurrentContext } from '../services/api';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{
    citation_text: string;
    file_id: string;
    source_row: number;
    record_id: string;
    url: string | null;
  }>;
  limitations?: string[];
  headline?: string;
  priorities?: Array<{ title: string; why_it_matters: string; status: string; recommended_next_step: string; confidence: string; evidence_refs: string[] }>;
  decision_required?: string | null;
  evidence_references?: Record<string, { record_id: string; file_id: string }>;
  timestamp: number;
};

export function Assistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      content: 'I\'m the Decision Intelligence Assistant. Ask me about priorities, risks, evidence-backed recommendations, or data quality status.',
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'EXECUTIVE' | 'ANALYST'>('EXECUTIVE');
  const [historyEnabled, setHistoryEnabled] = useState(true);
  const [context, setContext] = useState<Record<string, unknown>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const savedMode = localStorage.getItem('di_assistant_mode');
    const savedHistory = localStorage.getItem('di_assistant_history');
    if (savedMode === 'EXECUTIVE' || savedMode === 'ANALYST') setMode(savedMode);
    if (savedHistory !== null) setHistoryEnabled(savedHistory === 'true');
    getCurrentContext().then(setContext).catch(() => undefined);
  }, []);

  async function sendMessage() {
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await askLeadershipChatAdvanced({
        question: input,
        mode,
        history_enabled: historyEnabled,
        history: historyEnabled ? messages.slice(-8).map((message) => ({ role: message.role, content: message.content })) : [],
        context,
      });
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        limitations: response.limitations,
        headline: response.headline,
        priorities: response.priorities,
        decision_required: response.decision_required,
        evidence_references: response.evidence_references,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto flex flex-col h-[calc(100vh-140px)] animate-fade-in">
      <div className="mb-6">
        <div className="flex justify-between items-start gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Kenvue AEO/GEO Decision Intelligence Assistant</h1>
            <p className="text-slate-500 mt-2 text-lg">Ask what matters, why it matters, what evidence supports it, and what decision is required.</p>
          </div>
          <div className="flex gap-2 items-center text-xs">
            <select value={mode} onChange={(e) => setMode(e.target.value as 'EXECUTIVE' | 'ANALYST')} className="border border-slate-200 rounded-lg px-2 py-2 bg-white">
              <option value="EXECUTIVE">Executive</option>
              <option value="ANALYST">Analyst</option>
            </select>
            <button onClick={() => setHistoryEnabled((value) => { const next = !value; localStorage.setItem('di_assistant_history', String(next)); return next; })} className="border border-slate-200 rounded-lg px-3 py-2 bg-white">
              History: {historyEnabled ? 'On' : 'Off'}
            </button>
            <button onClick={() => setMessages([])} className="border border-slate-200 rounded-lg px-3 py-2 bg-white">Clear</button>
          </div>
        </div>
      </div>

      <Card className="flex-1 flex flex-col p-0 overflow-hidden bg-white/80 backdrop-blur-md shadow-lg border border-slate-200">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'}`}>
              <div 
                className={`px-6 py-4 rounded-2xl shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-brand-primary text-white rounded-br-none' 
                    : 'bg-white border border-slate-200 text-slate-800 rounded-bl-none'
                }`}
              >
                {msg.role === 'assistant' && msg.headline ? null : (
                  <div className={`prose prose-sm ${msg.role === 'user' ? 'prose-invert text-white' : 'text-slate-800'}`}>
                    {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
                  </div>
                )}
                {msg.role === 'assistant' && msg.headline && (
                  <div className="mt-4 space-y-3 not-prose">
                    <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                      <div className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Headline</div>
                      <div className="font-semibold text-slate-900 mt-1">{msg.headline}</div>
                    </div>
                    {msg.priorities && msg.priorities.length > 0 && <div className="space-y-2">
                      <div className="text-[10px] uppercase tracking-wider font-bold text-slate-500">Priorities</div>
                      {msg.priorities.slice(0, 4).map((priority, index) => (
                        <div key={`${priority.title}-${index}`} className="border border-slate-200 rounded-lg p-3 text-sm">
                          <div className="flex items-center justify-between gap-2"><span className="font-semibold text-slate-900">{priority.title}</span><span className="text-xs text-slate-500">{priority.status} · {priority.confidence}</span></div>
                          <p className="text-slate-600 mt-1">{priority.why_it_matters}</p>
                          <p className="text-slate-500 mt-1"><span className="font-semibold">Next:</span> {priority.recommended_next_step}</p>
                          <div className="flex gap-2 mt-2">{priority.evidence_refs.map((ref) => <Link key={ref} to={`/evidence?query=${encodeURIComponent(msg.evidence_references?.[ref]?.record_id || ref)}`} className="text-xs font-mono text-brand-primary hover:underline">{ref}</Link>)}</div>
                        </div>
                      ))}
                    </div>}
                    {msg.decision_required && <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900"><div className="font-semibold">Decision required</div><p className="mt-1">{msg.decision_required}</p></div>}
                    {msg.evidence_references && Object.keys(msg.evidence_references).length > 0 && <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm"><div className="flex items-center justify-between gap-2 mb-2"><span className="font-semibold text-slate-700">Evidence</span><span className="text-xs text-slate-400">{Object.keys(msg.evidence_references).length} references</span></div><div className="flex flex-wrap gap-2">{Object.entries(msg.evidence_references).slice(0, 8).map(([ref, evidence]) => <Link key={ref} to={`/evidence?query=${encodeURIComponent(evidence.record_id)}`} className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-brand-primary hover:bg-teal-100">{ref}</Link>)}</div>{Object.keys(msg.evidence_references).length > 8 && <p className="mt-2 text-xs text-slate-400">Showing the first 8 references. Open Evidence Explorer for the complete lineage.</p>}</div>}
                    {msg.limitations && msg.limitations.length > 0 && <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm text-slate-600"><div className="font-semibold text-slate-700">Limitations</div><ul className="list-disc list-inside mt-1 space-y-1">{msg.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></div>}
                  </div>
                )}
              </div>
              
              {msg.role === 'assistant' && !msg.headline && (msg.citations || msg.limitations) && (
                <div className="mt-2 w-full space-y-2 pl-4 border-l-2 border-slate-200">
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="text-xs">
                      <strong className="text-slate-600 block mb-1 uppercase tracking-wider">Evidence ({msg.citations.length})</strong>
                      <ul className="space-y-1">
                        {msg.citations.slice(0, 3).map((c, i) => (
                          <li key={i} className="text-slate-500 italic bg-white p-2 rounded border border-slate-100">
                            <span className="font-mono bg-slate-100 px-1 rounded mr-1 text-[10px]">E{i + 1}</span>{c.citation_text} <span className="font-mono bg-slate-100 px-1 rounded ml-1 text-[10px]">{c.record_id.slice(0, 8)}</span>
                          </li>
                        ))}
                        {msg.citations.length > 3 && (
                          <li className="text-slate-400 font-medium">+{msg.citations.length - 3} more sources...</li>
                        )}
                      </ul>
                    </div>
                  )}
                  {msg.limitations && msg.limitations.length > 0 && (
                    <div className="text-xs mt-2 bg-amber-50 border border-amber-100 p-2 rounded text-amber-800">
                      <strong className="block mb-1 uppercase tracking-wider">Limitations</strong>
                      <ul className="list-disc list-inside">
                        {msg.limitations.map((l, i) => (
                          <li key={i}>{l}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex mr-auto items-start max-w-[85%]">
              <div className="bg-white border border-slate-200 text-slate-800 px-6 py-4 rounded-2xl rounded-bl-none shadow-sm flex items-center gap-2">
                <div className="w-2 h-2 bg-brand-primary rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-brand-primary rounded-full animate-bounce delay-75"></div>
                <div className="w-2 h-2 bg-brand-primary rounded-full animate-bounce delay-150"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-white border-t border-slate-200">
          {error && <div className="text-red-500 text-sm mb-2 px-2">{error}</div>}
          <div className="flex gap-4">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask for priorities, risks, or semantic blockers..."
              className="flex-1 resize-none bg-slate-50 border border-slate-200 rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent text-sm"
              rows={2}
              disabled={loading}
            />
            <Button onClick={sendMessage} disabled={loading || !input.trim()} className="h-auto px-8 rounded-xl">
              Send
            </Button>
          </div>
          <div className="mt-3 flex gap-4 text-xs text-slate-500 justify-center">
            <button className="hover:text-brand-primary hover:underline" onClick={() => setInput("What should leadership prioritize based on current evidence?")}>Priority read-out</button>
            <button className="hover:text-brand-primary hover:underline" onClick={() => setInput("Are there any critical data quality issues or semantic blockers?")}>Diagnostic check</button>
            <button className="hover:text-brand-primary hover:underline" onClick={() => setInput("Write a 30-day business brief based on the active signals")}>Generate brief</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
