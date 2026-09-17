import { describe, expect, it } from 'vitest'
import { mapGovernanceState } from './governance'

describe('governance mapping', () => {
  it('preserves the three semantic states exactly', () => {
    expect(mapGovernanceState('GOVERNED')).toBe('GOVERNED')
    expect(mapGovernanceState('EXPERIMENTAL')).toBe('EXPERIMENTAL')
    expect(mapGovernanceState('BLOCKED')).toBe('BLOCKED')
    expect(mapGovernanceState('unknown')).toBe('EXPERIMENTAL')
  })
})

