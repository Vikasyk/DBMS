import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, Boxes, ChartNoAxesCombined, FlaskConical, Plus, RefreshCw,
  ScanLine, ShieldAlert, ShieldCheck, Truck,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, formatDate, formatQuantity, titleCase } from '../api'
import { DataTable, EmptyState, Notice, PageHeader, Panel, StatusBadge } from '../ui'

const dashboardMetrics = [
  { key: 'batches', label: 'Tracked batches', caption: 'Across the supply chain', icon: Boxes, tone: 'green', link: '/batches' },
  { key: 'shipments', label: 'Shipments', caption: 'Recorded movements', icon: Truck, tone: 'blue', link: '/shipments' },
  { key: 'open_alerts', label: 'Open alerts', caption: 'Awaiting review', icon: ShieldAlert, tone: 'amber', link: '/anomalies?status=OPEN' },
  { key: 'recent_failed_checks', label: 'Failed checks', caption: 'In the past 30 days', icon: Activity, tone: 'rose', link: '/quality' },
]

const money = new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 2, minimumFractionDigits: 0,
})
const chartDate = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' })

function RetailChart({ rows, loading, error }) {
  const [range, setRange] = useState(14)
  const daily = new Map()
  for (const row of rows) {
    const day = daily.get(row.price_date) || { date: row.price_date, total: 0, count: 0 }
    day.total += Number(row.selling_price)
    day.count += 1
    daily.set(row.price_date, day)
  }
  const points = [...daily.values()]
    .sort((a, b) => a.date.localeCompare(b.date)).slice(-range)
    .map(({ date, total, count }) => ({ date, price: Math.round(total / count * 100) / 100 }))
  const latest = points.at(-1)
  return (
    <Panel
      className="price-pulse"
      title="Retail price trend"
      description="Tomato · Bengaluru · daily mean per kg"
      actions={
        <select className="compact-select" aria-label="Price chart window" value={range} onChange={(event) => setRange(Number(event.target.value))}>
          <option value={7}>Last 7 price days</option>
          <option value={14}>Last 14 price days</option>
          <option value={30}>Last 30 price days</option>
        </select>
      }
    >
      {error ? <Notice tone="danger">{error}</Notice> : loading && !latest ? (
        <div className="chart-loading" role="status">Loading price history…</div>
      ) : !latest ? (
        <EmptyState icon={ChartNoAxesCombined} title="No retail prices recorded" description="Tomato prices recorded in Bengaluru will appear here." />
      ) : (
        <>
          <div className="price-pulse-lead">
            <strong>{money.format(latest.price)}<small> / kg</small></strong>
            <span>{formatDate(latest.date)}</span>
          </div>
          <div className="retail-chart" aria-label="Chart of daily Tomato retail prices in Bengaluru">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <AreaChart data={points} margin={{ left: 0, right: 12, top: 13, bottom: 0 }} accessibilityLayer>
                <defs>
                  <linearGradient id="retail-fill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#43886b" stopOpacity={0.24} />
                    <stop offset="100%" stopColor="#80b59b" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#e7ede8" strokeDasharray="4 4" />
                <XAxis dataKey="date" tickFormatter={(value) => chartDate.format(new Date(value))}
                  axisLine={false} tickLine={false} tickMargin={11} minTickGap={24}
                  tick={{ fill: '#5f7067', fontSize: 12 }} />
                <YAxis tickFormatter={(value) => money.format(value)} width={46} axisLine={false}
                  tickLine={false} tick={{ fill: '#5f7067', fontSize: 12 }} />
                <Tooltip labelFormatter={formatDate} formatter={(value) => [`${money.format(value)} / kg`, 'Mean retail price']}
                  contentStyle={{ border: '1px solid #dfebe3', borderRadius: 12 }} />
                <Area type="monotone" dataKey="price" stroke="#2d7656" strokeWidth={3} fill="url(#retail-fill)"
                  dot={points.length < 9 ? { fill: '#2d7656', r: 4, stroke: '#fff', strokeWidth: 2 } : false}
                  activeDot={{ r: 6 }} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      <Link to="/prices" className="text-link">View price analytics</Link>
    </Panel>
  )
}

function QualityWatch({ summary, loading }) {
  if (!summary) return (
    <Panel className="quality-watch" title="Quality watch" description="Failed checks and alerts to review">
      <EmptyState icon={ShieldCheck} title={loading ? 'Loading quality records…' : 'Quality summary unavailable'} />
    </Panel>
  )
  const checks = summary?.recent_failed_checks || []
  const alerts = summary?.open_alerts_by_type || []
  return (
    <Panel className="quality-watch" title="Quality watch" description="Failed checks and alerts to review">
      <div className="quality-watch-list">
        {checks.length ? checks.slice(0, 2).map((item) => (
          <Link className="quality-item" to={`/quality?check=${encodeURIComponent(item.check_id)}`} key={item.check_id}>
            <span className="metric-icon metric-rose"><ShieldAlert size={18} /></span>
            <span className="quality-item-main">
              <strong>{item.product_name || item.batch_id}</strong>
              <small>{item.batch_id} · {formatDate(item.check_date)}</small>
            </span>
            <StatusBadge value="FAIL" />
          </Link>
        )) : <div className="quality-clear"><ShieldCheck size={18} /><span>No recorded failed checks.</span></div>}
      </div>
      <div className="quality-alerts">
        <h3>Open alerts</h3>
        {alerts.length ? alerts.map((item) => (
          <Link to={`/anomalies?status=OPEN&type=${encodeURIComponent(item.alert_type)}`}
            className="quality-alert-summary" key={item.alert_type}>
            <span>{titleCase(item.alert_type)}</span><StatusBadge tone="amber">{item.count}</StatusBadge>
          </Link>
        )) : <p>Nothing is awaiting review.</p>}
      </div>
      <Link to="/quality" className="text-link">Open quality investigations</Link>
    </Panel>
  )
}

const shipmentColumns = [
  { key: 'shipment_id', label: 'Shipment', render: (id) => <Link className="identifier" to={`/shipments?shipment=${encodeURIComponent(id)}`}>{id}</Link> },
  { key: 'shipment_date', label: 'Date', render: formatDate },
  { key: 'source_location', label: 'Source' },
  { key: 'retailer_name', label: 'Retailer' },
  { key: 'destination_city', label: 'Destination' },
]

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [prices, setPrices] = useState([])
  const [error, setError] = useState('')
  const [priceError, setPriceError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    setError('')
    setPriceError('')
    setLoading(true)
    const overview = api('/dashboard/summary', { signal })
      .then((data) => { if (!signal.aborted) setSummary(data) })
      .catch((err) => { if (!signal.aborted) setError(err.message) })
    const retail = api('/prices/history', {
      params: { product: 'Tomato', market: 'Bengaluru', stage: 'RETAIL', unit: 'kg', limit: 200 }, signal,
    }).then((data) => { if (!signal.aborted) setPrices(data) })
      .catch((err) => { if (!signal.aborted) setPriceError(err.message) })
    Promise.all([overview, retail]).then(() => { if (!signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [refresh])

  return (
    <div className="dashboard page-stack">
      <PageHeader title="Supply chain overview" description="Track batches, shipments, quality checks and prices from one place."
        actions={<>
          <button type="button" className="button button-secondary refresh-button" onClick={() => setRefresh((value) => value + 1)} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'is-spinning' : ''} /> Refresh
          </button>
          <Link to="/register?kind=batch" className="button button-primary"><Plus size={18} /> Register batch</Link>
        </>} />

      <section className="dashboard-hero" aria-labelledby="hero-heading">
        <div className="hero-content">
          <h2 id="hero-heading">From farm to shelf</h2>
          <p>Follow a product’s origin, see where it went and investigate quality issues along the way.</p>
          <div className="cluster hero-actions">
            <Link to="/batches" className="button hero-primary"><ScanLine size={17} /> Trace a batch</Link>
            <Link to="/simulation" className="button hero-secondary"><FlaskConical size={17} /> Run a simulation</Link>
          </div>
        </div>
      </section>

      {error && <Notice tone="danger" title="Dashboard data is unavailable">{error}</Notice>}
      <section className="metrics-grid" aria-label="Supply chain counts">
        {dashboardMetrics.map(({ key, label, caption, icon: Icon, tone, link }) => (
          <Link to={link} key={key} className="metric-card">
            <span className={`metric-icon metric-${tone}`}><Icon size={20} aria-hidden="true" /></span>
            <span className="metric-label">{label}</span>
            <strong>{summary ? formatQuantity(summary.counts[key]) : '—'}</strong>
            <span className="metric-caption">{caption}</span>
          </Link>
        ))}
      </section>

      <div className="dashboard-insights">
        <RetailChart rows={prices} error={priceError} loading={loading} />
        <QualityWatch summary={summary} loading={loading} />
      </div>

      <Panel title="Recent shipments" description="Latest movements to retailers"
        actions={<Link to="/shipments" className="button button-secondary">Manage shipments</Link>}>
        <div className="desktop-shipments">
          <DataTable columns={shipmentColumns} rows={summary?.recent_shipments || []}
            getRowKey={(row) => row.shipment_id} caption="Recent shipments"
            empty={loading ? 'Loading recent shipments…' : 'No shipments recorded'} />
        </div>
        <div className="mobile-shipments">
          {summary?.recent_shipments?.length ? summary.recent_shipments.map((row) => (
            <Link to={`/shipments?shipment=${encodeURIComponent(row.shipment_id)}`}
              key={row.shipment_id} className="mobile-shipment">
              <div><strong className="identifier">{row.shipment_id}</strong><span>{formatDate(row.shipment_date)}</span></div>
              <strong>{row.retailer_name} · {row.destination_city}</strong>
              <span>From {row.source_location}</span>
            </Link>
          )) : <EmptyState title={loading ? 'Loading recent shipments…' : 'No shipments recorded'} />}
        </div>
      </Panel>
    </div>
  )
}
