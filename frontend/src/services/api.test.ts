import { afterEach, describe, expect, it, vi } from 'vitest'
import { askLeadershipChatAdvanced, getEvidence } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('API serialization', () => {
  it('serializes bounded assistant settings and context', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ answer: 'ok' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await askLeadershipChatAdvanced({ question: 'priorities', mode: 'ANALYST', history_enabled: true, history: [{ role: 'user', content: 'earlier' }], context: { assessment_run_id: 'run-1' } })
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.mode).toBe('ANALYST')
    expect(body.history_enabled).toBe(true)
    expect(body.context.assessment_run_id).toBe('run-1')
  })

  it('serializes bounded Evidence Explorer filters and pagination', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], total_count: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await getEvidence({ query: 'oat science', evidence_type: 'DEMO_FIXTURE', limit: 25, offset: 50 })
    expect(fetchMock.mock.calls[0][0]).toContain('query=oat+science')
    expect(fetchMock.mock.calls[0][0]).toContain('evidence_type=DEMO_FIXTURE')
    expect(fetchMock.mock.calls[0][0]).toContain('offset=50')
  })
})

