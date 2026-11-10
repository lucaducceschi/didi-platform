export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'Not available'
  }
  return value.toFixed(digits)
}

