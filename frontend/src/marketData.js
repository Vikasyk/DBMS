const spices = 'https://www.indianspices.com/marketing/price/domestic/current-market-price'
const meghalaya = 'https://megamb.gov.in/public/MegambHome.aspx'
const sirsi = 'https://mandipulse.com/mandi/karnataka-uttara-kannada-sirsi-apmc/black-pepper'

// Prices are INR per quintal. Spices Board publishes INR/kg (1 quintal = 100 kg).
export const snapshot = [
  { product: 'Black pepper', state: 'Karnataka', market: 'Sirsi APMC', variety: 'Local',
    low: 72010, high: 76011, price: 73909, basis: 'Modal', date: '2026-11-23', source: 'MandiPulse', url: sirsi },
  ...[['Garbled', 775], ['Ungarbled', 755]].map(([variety, kg]) => ({
    product: 'Black pepper', state: 'Kerala', market: 'Cochin', variety, price: kg * 100,
    basis: 'Average', date: '2026-11-23', source: 'Spices Board / IPSTA', url: spices,
  })),
  ...[['Sikkim', 'Singtam', 1500, 1387], ['Sikkim', 'Gangtok', 1450, 1300],
      ['West Bengal', 'Siliguri', 1575, 1440]].flatMap(([state, market, large, small]) =>
    [['Badadana', large], ['Chotadana', small]].map(([variety, kg]) => ({
      product: 'Large cardamom', state, market, variety, price: kg * 100, basis: 'Quoted',
      date: '2026-11-19', source: 'Spices Board', url: spices,
    }))),
  ...[
    ['Rice', 'Local', 6000, 8000], ['Rice', 'Sticky Type', 9000, 11000],
    ['Broomstick', 'Local', 8300, 9400], ['Orange', 'Local', 13000, 17000],
    ['Guava', 'Local', 5000, 6000], ['Ginger', 'Local', 13000, 15000],
    ['Turmeric powder', 'Local', 20000, 28000], ['Cabbage', 'MH-139', 800, 1000],
    ['Cauliflower', 'Local', 1000, 1200], ['Lettuce', 'Local', 10000, 12000],
    ['Pumpkin', 'Local', 2000, 3000], ['Potato', 'Local', 1800, 2000],
    ['Tomato', '017', 2000, 2500], ['Carrot', 'New Kuroda', 2000, 2500],
    ['French beans', 'Local', 4000, 5000], ['Capsicum', 'California Wonder', 3000, 5000],
    ['Squash', 'Squash', 800, 1000], ['Bottle gourd', 'Local', 2000, 3000],
    ['Colacasia', 'Local', 4000, 5000], ['Coriander', 'Local', 6000, 7000],
    ['Green chilli', 'Local', 9000, 12000],
  ].map(([product, variety, low, high]) => ({
    product, state: 'Meghalaya', market: 'Statewide', variety, low, high,
    basis: 'Range', date: '2026-11-23', source: 'Meghalaya Marketing Board', url: meghalaya,
  })),
]

const archive = 'https://raw.githubusercontent.com/kunal-rajput-317/mandi-data/main/data'
const storageKey = 'tracefood.mandi.csv.v1'
const archiveUrl = date => archive + '/' + date.slice(0, 7).replace('-', '/') + '/' + date + '.csv'

// Split RFC 4180 fields, including quoted market names containing commas.
function csvRows(csv) {
  const rows = []
  let row = [], field = '', quoted = false
  for (let i = 0; i < csv.length; i++) {
    const c = csv[i]
    if (c === '"') {
      if (quoted && csv[i + 1] === '"') { field += '"'; i++ }
      else quoted = !quoted
    } else if (!quoted && c === ',') { row.push(field); field = '' }
    else if (!quoted && c === '\n') { row.push(field.trim()); rows.push(row); row = []; field = '' }
    else field += c
  }
  if (quoted) throw new Error('Incomplete market file')
  if (row.length || field.trim()) rows.push([...row, field.trim()])
  return rows
}

export function readArchive(csv, date) {
  const [header = [], ...rows] = csvRows(csv.replace(/^\uFEFF/, ''))
  const required = ['date', 'state', 'district', 'market', 'commodity', 'variety', 'grade', 'min_price', 'max_price', 'modal_price']
  if (!required.every(key => header.includes(key))) throw new Error('Unexpected market file columns')
  const priceNumber = value => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : null
  const quotes = []
  for (const fields of rows) {
    const r = Object.fromEntries(header.map((key, index) => [key, fields[index]?.trim()]))
    if (r.date !== date || !r.state || !r.market || !r.commodity) continue
    const price = priceNumber(r.modal_price), low = priceNumber(r.min_price), high = priceNumber(r.max_price)
    if (!price && !low && !high) continue
    quotes.push({ product: r.commodity, state: r.state, market: [r.market, r.district].filter(Boolean).join(', '),
      variety: [r.variety, r.grade].filter(Boolean).join(' / '), date, price, low, high, basis: price ? 'Modal' : 'Range',
      source: 'AGMARKNET via KrashiMitra', url: archiveUrl(date) })
  }
  if (!quotes.length) throw new Error('No dated quotes in the market file')
  return quotes
}

export function cachedMarket() {
  try {
    const {csv, date} = JSON.parse(localStorage.getItem(storageKey))
    return {date, rows: readArchive(csv, date)}
  } catch { return null }
}

export async function latestMarket(signal) {
  const today = new Date().toLocaleDateString('sv-SE', {timeZone: 'Asia/Kolkata'})
  for (let days = 0; days < 8; days++) {
    const date = new Date(Date.parse(today) - days * 86400000).toISOString().slice(0, 10)
    const res = await fetch(archiveUrl(date), {signal: AbortSignal.any([signal, AbortSignal.timeout(8000)])})
    if (res.status === 404) continue
    if (!res.ok) throw new Error('Archive unavailable')
    const csv = await res.text()
    const rows = readArchive(csv, date)
    try { localStorage.setItem(storageKey, JSON.stringify({csv, date})) } catch { /* Storage may be full. */ }
    return {date, rows}
  }
  throw new Error('Recent market file unavailable')
}

export function readMandiExport(csv) {
  const [columns = [], ...records] = csvRows(csv.replace(/^\uFEFF/, ''))
  const keys = columns.map(key => key.trim().toLowerCase().replaceAll('_x0020_', '_').replace(/\s+/g, '_'))
  const required = ['state', 'district', 'market', 'commodity', 'variety', 'arrival_date', 'min_price', 'max_price', 'modal_price']
  if (!required.every(key => keys.includes(key))) throw new Error('Select a data.gov.in AGMARKNET CSV with market, arrival date and price columns.')
  const rows = []
  for (const fields of records) {
    if (fields.every(field => !field.trim())) continue
    const record = Object.fromEntries(keys.map((key, index) => [key, fields[index]?.trim() || '']))
    const date = record.arrival_date.replace(/^(\d{2})[/-](\d{2})[/-](\d{4})$/, '$3-$2-$1')
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0,10) !== date ||
        !record.commodity || !record.state || !record.market) throw new Error('Invalid date, commodity or market at CSV row ' + (rows.length + 2))
    const amount = value => {
      if (!value || value === '-' || value.toUpperCase() === 'NA') return null
      const number = Number(value.replaceAll(',', ''))
      if (!Number.isFinite(number) || number < 0) throw new Error('Invalid price at CSV row ' + (rows.length + 2))
      return number || null
    }
    rows.push({product: record.commodity, state: record.state, market: [record.market, record.district].filter(Boolean).join(', '),
      variety: [record.variety, record.grade].filter(Boolean).join(' / '), date, price: amount(record.modal_price),
      low: amount(record.min_price), high: amount(record.max_price), basis: amount(record.modal_price) ? 'Modal' : 'Range',
      source: 'Imported mandi CSV', url: 'https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi'})
  }
  const quotes = rows.filter(row => row.price || row.low || row.high)
  if (!quotes.length) throw new Error('The export contains no reported prices.')
  return quotes
}
