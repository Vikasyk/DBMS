import nationwideCsv from './agmarknet-2026-11-01.csv?raw'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDate } from './api'
import { DataTable, Panel } from './ui'
import { cachedMarket, latestMarket, readMandiExport, snapshot } from './marketData'

const nationwide = readMandiExport(nationwideCsv).map(row => ({
  ...row, source: 'AGMARKNET archive',
  url: 'https://github.com/Srinithyaaa/india-agri-price-dashboard/blob/main/agmarknet_prices_2026-11-01.csv',
}))

const inr = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 2, minimumFractionDigits: 0})
const lower = text => text.trim().toLowerCase()
const distinct = values => Array.from(new Set(values)).sort((a, b) => a.localeCompare(b))

export default function RegionalPrices({ compact = false }) {
  const [imported, setImported] = useState(() => {
    try { return readMandiExport(localStorage.getItem('tracefood.mandi.import') || '') } catch { return [] }
  })
  const [importStatus, setImportStatus] = useState('')
  async function importFile(event) {
    const file = event.target.files[0]
    event.target.value = ''
    if (!file) return
    try {
      const csv = await file.text()
      const quotes = readMandiExport(csv)
      setImported(quotes)
      setProduct('')
      setRegion('')
      setLimit(30)
      try {
        localStorage.setItem('tracefood.mandi.import', csv)
        setImportStatus('Saved ' + quotes.length + ' imported market quotes in this browser.')
      } catch { setImportStatus('Loaded ' + quotes.length + ' quotes for this visit. Browser storage is full.') }
    } catch (error) { setImportStatus(error.message) }
  }
  const [archive, setArchive] = useState(cachedMarket)
  const [status, setStatus] = useState('Checking for newer mandi reports…')
  const [refresh, setRefresh] = useState(0)
  const [product, setProduct] = useState('')
  const [region, setRegion] = useState('')
  const [unit, setUnit] = useState('quintal')
  const [limit, setLimit] = useState(30)
  useEffect(() => {
    const controller = new AbortController()
    setStatus('Checking for newer mandi reports…')
    latestMarket(controller.signal).then(result => {
      if (!controller.signal.aborted) {
        setArchive(result)
        setStatus('Latest available mandi file checked.')
      }
    }).catch(() => {
      if (!controller.signal.aborted) setStatus('Live archive unavailable. Showing saved, dated reports.')
    })
    return () => controller.abort()
  }, [refresh])
  const rows = useMemo(() => [...imported, ...(archive?.rows || []), ...snapshot, ...nationwide]
    .sort((a, b) => b.date.localeCompare(a.date) || a.state.localeCompare(b.state) || a.market.localeCompare(b.market)), [archive, imported])
  const products = useMemo(() => distinct(rows.map(r => lower(r.product))), [rows])
  const regions = useMemo(() => distinct(rows.map(r => r.state)), [rows])
  const matches = rows.filter(r => (!product || lower(r.product) === product) && (!region || r.state === region))
  const money = value => value == null ? '—' : inr.format(value / (unit === 'kg' ? 100 : 1))
  const columns = [
    {key: 'market', label: 'Market', render: (_, r) => <>{r.market}<br /><small>{r.state}</small></>},
    {key: 'product', label: 'Commodity', render: (_, r) => <>{r.product}<br /><small>{r.variety || 'Grade unspecified'}</small></>},
    {key: 'price', label: '₹ per ' + unit, render: (_, r) => <>{r.price != null ? money(r.price) : [money(r.low), money(r.high)].join(' – ')}<br /><small>{r.basis}</small></>},
    ...(!compact ? [{key: 'low', label: 'Minimum', render: money}, {key: 'high', label: 'Maximum', render: money}] : []),
    {key: 'date', label: 'Reported', render: (_, r) => <>{formatDate(r.date)}<br /><a href={r.url} target="_blank" rel="noreferrer">{r.source}</a></>},
  ]
  return <Panel title="Regional market prices" description="Market-reported commodity prices in Indian rupees. One quintal is 100 kg.">
    <div className="cluster">
      <label>Commodity <select className="compact-select" value={product} onChange={e => {setProduct(e.target.value); setLimit(30)}}>
        <option value="">All commodities</option>{products.map(p => <option key={p} value={p}>{p}</option>)}
      </select></label>
      {!compact && <label>State or UT <select className="compact-select" value={region} onChange={e => {setRegion(e.target.value); setLimit(30)}}>
        <option value="">All regions</option>{regions.map(s => <option key={s}>{s}</option>)}
      </select></label>}
      <label>Unit <select className="compact-select" value={unit} onChange={e => setUnit(e.target.value)}>
        <option value="quintal">Quintal</option><option value="kg">Kilogram</option>
      </select></label>
    </div>
    {!compact && <label>Import AGMARKNET CSV <input type="file" accept=".csv,text/csv" onChange={importFile} /></label>}
    {importStatus && <p role="status">{importStatus}</p>}
    <p role="status">{status}</p>
    <DataTable columns={columns} rows={matches.slice(0, compact ? 3 : limit)} caption="Reported regional commodity prices"
      empty="No published quote in the loaded reports for this commodity and region." />
    {!compact && matches.length > limit && <button className="button button-secondary" onClick={() => setLimit(limit + 30)}>Show more ({matches.length - limit} remaining)</button>}
    {compact ? <Link to="/prices" className="text-link">Compare all regional prices</Link> :
      <button className="button button-secondary" onClick={() => setRefresh(refresh + 1)}>Refresh market reports</button>}
  </Panel>
}

