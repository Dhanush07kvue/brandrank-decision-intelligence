const LOCAL_DATE_TIME_FORMATTER = new Intl.DateTimeFormat(undefined, {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: true,
  timeZoneName: 'short',
})

export function parseRunIdToDate(runId: string): Date | null {
  const match = runId.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/)
  if (!match) return null

  const [, year, month, day, hour, minute, second] = match
  const parsed = new Date(Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second)
  ))

  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatLocalDateTime(value: string | number | Date | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || value === '') return fallback

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return typeof value === 'string' ? value : fallback

  return LOCAL_DATE_TIME_FORMATTER.format(date)
}

export function formatRunIdLocal(runId: string | null | undefined, fallback = 'Not available'): string {
  if (!runId) return fallback

  const parsed = parseRunIdToDate(runId)
  if (!parsed) return runId

  return formatLocalDateTime(parsed, runId)
}
