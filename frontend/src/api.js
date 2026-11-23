const apiBase = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')
const dateFormat = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
})
const quantityFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 3 })

export async function api(path, { method = 'GET', body, params, signal } = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  }
  const query = search.size ? `?${search}` : ''
  const timeout = AbortSignal.timeout(60000)
  let response
  try {
    response = await fetch(`${apiBase}${path}${query}`, {
      method,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    if (error.name === 'TimeoutError') {
      throw new Error(method === 'GET'
        ? 'The request timed out. Try again.'
        : 'The request timed out. Check whether the record was saved before retrying.')
    }
    throw new Error('TraceFood could not reach the API. Check that FastAPI is running.')
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map(({ loc, msg }) => `${loc?.slice(1).join('.') || 'Request'}: ${msg}`).join(' · ')
      : data?.detail
    throw new Error(detail || `The API returned HTTP ${response.status}.`)
  }
  return data
}

export function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? String(value) : dateFormat.format(date)
}

export function formatQuantity(value, unit) {
  if (value == null || value === '') return '—'
  return `${quantityFormat.format(Number(value))}${unit ? ` ${unit}` : ''}`
}

export function titleCase(value) {
  return String(value ?? '').toLowerCase().replace(/[_-]/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}
