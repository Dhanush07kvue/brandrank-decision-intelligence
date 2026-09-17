export type GovernanceState = 'GOVERNED' | 'EXPERIMENTAL' | 'BLOCKED'

export function mapGovernanceState(value: string | null | undefined): GovernanceState {
  if (value === 'GOVERNED' || value === 'BLOCKED') return value
  return 'EXPERIMENTAL'
}

