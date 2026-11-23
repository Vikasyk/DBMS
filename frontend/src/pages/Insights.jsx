import { lazy, Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import {
  Activity, BarChart3, ChartNoAxesCombined, CircleHelp,
  Clipboard, ListFilter, Plus, Send, Sparkles, TriangleAlert,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, formatDate, formatQuantity, titleCase } from '../api.js'
import { DataTable, EmptyState, Field, Notice, PageHeader, Panel, StatusBadge } from '../ui.jsx'
import '../insights.css'

const ImpactReport = lazy(() => import('./Trace.jsx').then((module) => ({ default: module.ImpactReport })))
const PRODUCTS = [
  'Tomato', 'Onion', 'Potato', 'Mango', 'Tomato Puree', 'Tomato Onion Masala', 'Mango Pulp', 'Potato Chips',
]
const UNITS = ['kg', 'L', 'unit']
const STAGES = ['FARM', 'PROCESSING_WHOLESALE', 'RETAIL']
const STATUSES = ['OPEN', 'REVIEWED', 'DISMISSED']
const ALERT_TYPES = ['MASS_BALANCE', 'OVER_ALLOCATION', 'EXPIRED_SHIPMENT', 'YIELD_OUTLIER', 'PRICE_OUTLIER']
const PRICE_VIEWS = [
  ['history', 'Price history'],
  ['stages', 'Stage comparison'],
  ['movements', 'Largest movements'],
  ['forecast', 'Forecast'],
  ['record', 'Record price'],
]
const FIRST_QUESTIONS = [
  'Which retailers received products derived from B101?',
  'Show the price history of batch B103.',
  'Show all batches that failed quality checks.',
]
const COLORS = ['#247854', '#b46b2c', '#3b71b4', '#9a5288', '#718344', '#7564b3', '#a9554a', '#38858c']
const PAGE_SIZE = 40
const number = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })
const money = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const shortDate = new Intl.DateTimeFormat('en-IN', { month: 'short', day: 'numeric', timeZone: 'UTC' })
const stageNames = {
  FARM: 'Farm', PROCESSING_WHOLESALE: 'Wholesale', RETAIL: 'Retail',
}
const methodNames = { RULE: 'Rule', STATISTICAL: 'Statistical', ML: 'Machine learning' }
let conversation = []
const conversationListeners = new Set()

function subscribeConversation(listener) {
  conversationListeners.add(listener)
  return () => conversationListeners.delete(listener)
}

function getConversation() {
  return conversation
}

function saveConversation(next) {
  conversation = next
  for (const listener of conversationListeners) listener()
}

function useRead(path, params, revision = 0) {
  const query = JSON.stringify(params ?? {})
  const [state, setState] = useState({ key: '', payload: null, error: '' })
  const key = JSON.stringify([path, query, revision])
  useEffect(() => {
    if (!path) return undefined
    const controller = new AbortController()
    let active = true
    api(path, { params: JSON.parse(query), signal: controller.signal })
      .then((payload) => {
        if (active) setState({ key, payload, error: '' })
      })
      .catch((error) => {
        if (active) setState({ key, payload: null, error: error.message })
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [key, path, query])
  if (!path || state.key !== key) return { payload: null, error: '', loading: Boolean(path) }
  return { ...state, loading: false }
}

function useSubmit() {
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const request = useRef(false)
  async function run(path, options) {
    if (request.current) return null
    request.current = true
    setPending(true)
    setError('')
    setResult(null)
    try {
      const data = await api(path, options)
      setResult(data)
      return data
    } catch (failure) {
      setError(failure.message)
      return null
    } finally {
      request.current = false
      setPending(false)
    }
  }
  return { pending, result, error, run }
}

function Loading({ children = 'Loading records…' }) {
  return <div className="insight-loading" role="status"><span />{children}</div>
}

function QueryError({ error }) {
  return error && <Notice tone="danger" title="Request failed">{error}</Notice>
}

function BatchLink({ id }) {
  return id ? <Link className="insight-record-link" to={`/batches?batch=${encodeURIComponent(id)}`}>{id}</Link> : '—'
}

function dateTick(value) {
  return shortDate.format(new Date(value))
}

function priceText(value, unit) {
  return value == null ? '—' : `₹${money.format(Number(value))}/${unit}`
}

function percentText(value) {
  return value == null ? '—' : `${Number(value) > 0 ? '+' : ''}${number.format(Number(value))}%`
}

function pct(value) {
  return value == null ? '—' : (
    <span className={`insight-change ${Number(value) > 0 ? 'is-up' : Number(value) < 0 ? 'is-down' : ''}`}>
      {percentText(value)}
    </span>
  )
}

function PriceChart({ rows, series, unit, bars = false, legend = true }) {
  if (!rows.length || !series.length) return null
  const Chart = bars ? BarChart : LineChart
  const timeline = !bars && rows.length > 1
  const points = timeline ? rows.map((row) => ({ ...row, date: Date.parse(row.date) })) : rows
  const interval = Math.ceil(points.length / 6)
  const axis = timeline ? {
    type: 'number', scale: 'time', domain: ['dataMin', 'dataMax'],
    ticks: points.filter((_, index) => index % interval === 0 || index === points.length - 1).map(({ date }) => date),
  } : {}
  return (
    <div className="insight-chart" aria-label={`Price chart in rupees per ${unit}`}>
      <ResponsiveContainer width="100%" height={300}>
        <Chart data={points} margin={{ top: 14, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e7ece8" strokeDasharray="4 4" vertical={false} />
          <XAxis dataKey="date" {...axis} tickFormatter={dateTick} minTickGap={24} tick={{ fontSize: 12, fill: '#627065' }} tickLine={false} axisLine={false} />
          <YAxis unit="" width={53} tickFormatter={(value) => `₹${number.format(value)}`} tick={{ fontSize: 12, fill: '#627065' }} tickLine={false} axisLine={false} />
          <Tooltip
            labelFormatter={formatDate}
            formatter={(value) => priceText(value, unit)}
            contentStyle={{ border: '1px solid #dce6de', borderRadius: 12, padding: 12 }}
          />
          {legend && <Legend wrapperStyle={{ paddingTop: 12, fontSize: 12 }} />}
          {series.map(({ key, label, color, dashed }) => bars
            ? <Bar key={key} dataKey={key} name={label} fill={color} maxBarSize={44} radius={[5, 5, 0, 0]} isAnimationActive={false} />
            : <Line
                key={key} dataKey={key} name={label} stroke={color} strokeDasharray={dashed ? '6 4' : undefined}
                strokeWidth={2.5} connectNulls type="linear" dot={rows.length < 25} activeDot={{ r: 5 }} isAnimationActive={false}
              />)}
        </Chart>
      </ResponsiveContainer>
    </div>
  )
}

function chartFromHistory(rows) {
  const keys = new Map()
  const dates = new Map()
  for (const row of rows) {
    const label = `${row.product_name} · ${stageNames[row.supply_chain_stage]} · ${row.market_location}`
    if (!keys.has(label)) {
      const index = keys.size
      keys.set(label, { key: `series${index}`, label, color: COLORS[index % COLORS.length] })
    }
    const date = row.price_date
    const key = keys.get(label).key
    if (!dates.has(date)) dates.set(date, { date })
    const bucket = dates.get(date)
    const values = bucket[key] ?? []
    values.push(Number(row.selling_price))
    bucket[key] = values
  }
  return {
    rows: Array.from(dates.values())
      .sort((left, right) => left.date.localeCompare(right.date))
      .map(({ date, ...series }) => ({
        date,
        ...Object.fromEntries(Object.entries(series).map(([key, values]) => [
          key, values.reduce((total, value) => total + value, 0) / values.length,
        ])),
      })),
    series: Array.from(keys.values()),
  }
}

function ProductSelect({ defaultValue, all = false }) {
  return (
    <select name="product" defaultValue={defaultValue}>
      {all && <option value="">All products</option>}
      {PRODUCTS.map((value) => <option key={value}>{value}</option>)}
    </select>
  )
}

function UnitSelect() {
  return <select name="unit" defaultValue="kg">{UNITS.map((value) => <option key={value}>{value}</option>)}</select>
}

function StageSelect({ optional = false }) {
  return (
    <select name="stage" defaultValue={optional ? '' : 'FARM'}>
      {optional && <option value="">All stages</option>}
      {STAGES.map((stage) => <option value={stage} key={stage}>{stageNames[stage]}</option>)}
    </select>
  )
}

function formValues(event) {
  event.preventDefault()
  return Object.fromEntries(Array.from(new FormData(event.currentTarget), ([key, value]) => [key, value.trim()]))
}

function Pagination({ page, hasNext, onChange }) {
  if (page === 1 && !hasNext) return null
  return (
    <div className="insight-pagination">
      <span className="muted">Page {page}</span>
      <button className="button button-secondary" type="button" disabled={page === 1} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      <button className="button button-secondary" type="button" disabled={!hasNext} onClick={() => onChange(page + 1)}>
        Next
      </button>
    </div>
  )
}

const priceColumns = [
  { key: 'price_id', label: 'Price ID' },
  { key: 'batch_id', label: 'Batch', render: (id) => <BatchLink id={id} /> },
  { key: 'product_name', label: 'Product' },
  { key: 'price_date', label: 'Observed', render: formatDate },
  { key: 'supply_chain_stage', label: 'Stage', render: (stage) => stageNames[stage] ?? titleCase(stage) },
  { key: 'market_location', label: 'Market' },
  { key: 'selling_price', label: 'Sale price', render: (value, row) => priceText(value, row.unit) },
  { key: 'cost_per_unit', label: 'Cost', render: (value, row) => priceText(value, row.unit) },
  { key: 'price_change_percentage', label: 'Change', render: pct },
]

function PriceHistory({ movement }) {
  const [filters, setFilters] = useState({ product: movement ? '' : 'Tomato', unit: 'kg' })
  const [page, setPage] = useState(1)
  const state = useRead('/prices/history', {
    ...filters, sort: movement ? 'movement' : 'recent', limit: PAGE_SIZE + 1, offset: (page - 1) * PAGE_SIZE,
  })
  const rows = useMemo(() => (state.payload ?? []).slice(0, PAGE_SIZE), [state.payload])
  const chart = useMemo(() => chartFromHistory(rows), [rows])
  const [visible, setVisible] = useState('')
  const series = chart.series.filter(({ key }) => !visible || key === visible)

  function applyFilters(event) {
    const values = formValues(event)
    setPage(1)
    setVisible('')
    setFilters({ ...values, batch_id: values.batch_id.toUpperCase() })
  }

  return (
    <>
      <Panel title={movement ? 'Movement filters' : 'Observation filters'} description="Compare prices within the same product, unit and market.">
        <form className="insight-filters" onSubmit={applyFilters}>
          <Field label="Product"><ProductSelect all defaultValue={filters.product} /></Field>
          <Field label="Unit"><UnitSelect /></Field>
          <Field label="Stage"><StageSelect optional /></Field>
          <Field label="Market"><input name="market" placeholder="Any market" maxLength="60" /></Field>
          <Field label="Batch ID"><input name="batch_id" placeholder="Any batch" maxLength="12" /></Field>
          <Field label="From"><input name="from" type="date" /></Field>
          <Field label="To"><input name="to" type="date" /></Field>
          <button className="button button-primary" type="submit"><ListFilter size={16} /> Apply filters</button>
        </form>
      </Panel>
      {state.loading && <Loading />}
      <QueryError error={state.error} />
      {state.payload && (
        <>
          {!movement && rows.length > 0 && (
            <Panel
              title="Selling price over time" description={`Daily means of displayed observations · ₹ per ${filters.unit}`}
              actions={chart.series.length > 1 && (
                <select className="insight-chart-selector" aria-label="Chart series" value={visible} onChange={(event) => setVisible(event.target.value)}>
                  <option value="">All series</option>
                  {chart.series.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}
                </select>
              )}
            >
              <PriceChart rows={chart.rows} series={series} unit={filters.unit} legend={series.length <= 6} />
            </Panel>
          )}
          <Panel
            title={movement ? 'Ranked price changes' : 'Price observations'}
            description={movement ? 'Ranked by absolute change from the previous comparable observation.' : 'Recorded prices and costs by batch.'}
          >
            <DataTable columns={priceColumns} rows={rows} empty="No matching price observations." getRowKey={(row) => row.price_id} />
            <Pagination page={page} hasNext={state.payload.length > PAGE_SIZE} onChange={(value) => { setVisible(''); setPage(value) }} />
          </Panel>
        </>
      )}
    </>
  )
}

const stageSeries = [
  { key: 'farm_avg_price', label: 'Farm', color: COLORS[0] },
  { key: 'wholesale_avg_price', label: 'Wholesale', color: COLORS[1] },
  { key: 'retail_avg_price', label: 'Retail', color: COLORS[2] },
]

function StageComparison() {
  const [filters, setFilters] = useState({ product: 'Tomato', unit: 'kg' })
  const state = useRead('/prices/stage-comparison', filters)
  const rows = state.payload ?? []
  const chart = [...rows].reverse().map((row) => ({
    date: row.month,
    ...Object.fromEntries(stageSeries.map(({ key }) => [key, row[key] == null ? null : Number(row[key])])),
  }))
  const cols = [
    { key: 'month', label: 'Month', render: (month) => new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(month)) },
    ...stageSeries.map(({ key, label }) => ({ key, label, render: (value) => priceText(value, filters.unit) })),
    { key: 'farm_to_retail_change_pct', label: 'Farm to retail', render: pct },
    { key: 'observations', label: 'Observations' },
  ]

  return (
    <>
      <Panel title="Monthly prices by stage" description="Monthly averages across recorded markets. The farm-to-retail change can include processing, transport, storage, and wastage.">
        <form className="insight-filters is-compact" onSubmit={(event) => setFilters(formValues(event))}>
          <Field label="Product"><ProductSelect defaultValue="Tomato" /></Field>
          <Field label="Unit"><UnitSelect /></Field>
          <button className="button button-primary" type="submit"><BarChart3 size={16} /> Compare stages</button>
        </form>
        {state.loading && <Loading />}
        <QueryError error={state.error} />
        <PriceChart rows={chart} series={stageSeries} unit={filters.unit} bars />
      </Panel>
      {state.payload && (
        <Panel title="Stage comparison by month">
          <DataTable columns={cols} rows={rows} empty="No monthly prices for this product and unit." getRowKey={(row) => row.month} />
        </Panel>
      )}
    </>
  )
}

function Forecast() {
  const request = useSubmit()
  const result = request.result
  const chart = result ? [
    ...(result.history ?? []).map((row) => ({ date: row.week, observed: Number(row.price) })),
    ...(result.forecast ?? []).map((row) => ({ date: row.week, projected: Number(row.price) })),
  ] : []
  const lastObserved = result?.history?.length - 1
  if (result?.supported && lastObserved >= 0) chart[lastObserved].projected = chart[lastObserved].observed
  const series = [
    { key: 'observed', label: 'Observed weekly mean', color: COLORS[0] },
    ...(result?.supported ? [{ key: 'projected', label: 'Forecast', color: COLORS[2], dashed: true }] : []),
  ]
  const metrics = [
    { key: 'model', label: 'Model' },
    { key: 'mae', label: 'Mean absolute error', render: (value) => priceText(value, result.unit) },
    { key: 'mape', label: 'Mean absolute percentage error', render: (value) => value == null ? '—' : `${number.format(Number(value))}%` },
    { key: 'origins', label: 'Rolling origins' },
  ]

  function evaluate(event) {
    request.run('/prices/forecast', { params: formValues(event) })
  }

  return (
    <>
      <Panel title="Retail price forecast" description="Compare four-week forecasts using at least 52 consecutive completed weeks of retail observations.">
        <form className="insight-filters is-forecast" onSubmit={evaluate}>
          <Field label="Product"><ProductSelect defaultValue="Tomato" /></Field>
          <Field label="Retail market" required><input name="market" defaultValue="Bengaluru" maxLength="60" required /></Field>
          <Field label="Unit"><UnitSelect /></Field>
          <button className="button button-primary" type="submit" disabled={request.pending}>
            <ChartNoAxesCombined size={16} /> {request.pending ? 'Evaluating…' : 'Evaluate forecast'}
          </button>
        </form>
      </Panel>
      <QueryError error={request.error} />
      {result && (
        <Panel title={`${result.product} in ${result.market}`} description="Retail price per completed week">
          {result.supported ? (
            <div className="insight-forecast-summary">
              <div><span>Selected model</span><strong>{result.model}</strong></div>
              <div><span>Consecutive weeks</span><strong>{number.format(result.consecutive_weeks)}</strong></div>
              <div><span>Forecast horizon</span><strong>{result.forecast.length} weeks</strong></div>
            </div>
          ) : (
            <Notice tone="info" title="More observations needed">{result.reason}</Notice>
          )}
          <PriceChart rows={chart} series={series} unit={result.unit} />
          {result.supported && <p className="muted insight-note">Forecasts fitted to the synthetic dataset are demonstrations.</p>}
          {result.forecast?.length > 0 && (
            <DataTable
              columns={[
                { key: 'week', label: 'Week starting', render: formatDate },
                { key: 'price', label: 'Forecast price', render: (value) => priceText(value, result.unit) },
              ]}
              rows={result.forecast}
              getRowKey={(row) => row.week}
            />
          )}
        </Panel>
      )}
      {result?.metrics?.length > 0 && (
        <Panel title="Rolling-origin evaluation" description="The models are evaluated on held-out weeks. Lower error is better.">
          <DataTable columns={metrics} rows={result.metrics} getRowKey={(row) => row.model} />
        </Panel>
      )}
    </>
  )
}

function today() {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function RecordPrice() {
  const request = useSubmit()
  const batches = useRead('/batches', { limit: 100 })
  const [batchId, setBatchId] = useState('')
  const selected = batches.payload?.find((row) => row.batch_id === batchId.trim().toUpperCase())
  const unit = selected?.unit
  async function save(event) {
    const fields = formValues(event)
    await request.run('/prices', {
      method: 'POST',
      body: {
        batch_id: fields.batch_id.toUpperCase(),
        price_date: fields.price_date,
        market_location: fields.market,
        supply_chain_stage: fields.stage,
        selling_price: fields.selling_price,
        cost_per_unit: fields.cost_per_unit || null,
      },
    })
  }
  return (
    <Panel title="New price observation" description="Attach a selling price and, if known, the recorded cost per unit to a batch.">
      <form className="stack" onSubmit={save}>
        <div className="form-grid">
          <Field label="Batch ID" hint={selected?.product_name ?? 'Enter any existing batch ID.'} required>
            <input
              name="batch_id" list="price-batch-options" value={batchId}
              onChange={(event) => setBatchId(event.target.value.toUpperCase())}
              placeholder="B108" maxLength={12} pattern="B[0-9]+" required
            />
            <datalist id="price-batch-options">
              {(batches.payload ?? []).map((row) => <option key={row.batch_id} value={row.batch_id}>{row.product_name}</option>)}
            </datalist>
          </Field>
          <Field label="Observation date" required><input name="price_date" type="date" defaultValue={today()} required /></Field>
          <Field label="Market" required><input name="market" placeholder="Bengaluru" maxLength="60" required /></Field>
          <Field label="Supply chain stage" required><StageSelect /></Field>
          <Field label={`Selling price (${unit ? `₹/${unit}` : '₹ per batch unit'})`} required>
            <input name="selling_price" type="number" min="0" step="0.01" required />
          </Field>
          <Field label={`Recorded cost (${unit ? `₹/${unit}` : '₹ per batch unit'})`}>
            <input name="cost_per_unit" type="number" min="0" step="0.01" />
          </Field>
        </div>
        <QueryError error={request.error} />
        {request.result && (
          <Notice tone="success" title={`Price ${request.result.price_id} recorded`}>
            {request.result.product_name} · {priceText(request.result.selling_price, request.result.unit)} · {request.result.market_location}
          </Notice>
        )}
        <div>
          <button className="button button-primary" type="submit" disabled={request.pending}>
            <Plus size={16} /> {request.pending ? 'Recording…' : 'Record price'}
          </button>
        </div>
      </form>
    </Panel>
  )
}

export function Prices() {
  const [params, setParams] = useSearchParams()
  const selected = params.get('view')
  const view = PRICE_VIEWS.some(([key]) => key === selected) ? selected : 'history'
  function openView(key) {
    const next = new URLSearchParams(params)
    if (key === 'history') next.delete('view')
    else next.set('view', key)
    setParams(next)
  }
  return (
    <div className="insights stack">
      <PageHeader title="Prices and trends" description="Track observations, compare supply chain stages, and evaluate retail forecasts." />
      <nav className="tabs insight-tabs" aria-label="Price workflows">
        {PRICE_VIEWS.map(([key, label]) => (
          <button type="button" className={`tab ${key === view ? 'is-active' : ''}`} key={key} onClick={() => openView(key)} aria-current={key === view ? 'page' : undefined}>
            {label}
          </button>
        ))}
      </nav>
      {(view === 'history' || view === 'movements') && <PriceHistory key={view} movement={view === 'movements'} />}
      {view === 'stages' && <StageComparison />}
      {view === 'forecast' && <Forecast />}
      {view === 'record' && <RecordPrice />}
    </div>
  )
}

function scoreText(alert) {
  if (alert.anomaly_score == null) return 'Score unavailable'
  const score = Number(alert.anomaly_score)
  switch (alert.alert_type) {
    case 'MASS_BALANCE': return `${number.format(score * 100)}% more recorded output than input`
    case 'OVER_ALLOCATION': return `${number.format(score * 100)}% above the batch’s initial quantity`
    case 'EXPIRED_SHIPMENT': return `${number.format(score)} days after expiry`
    case 'YIELD_OUTLIER': return `${number.format(score)} absolute robust z-score`
    case 'PRICE_OUTLIER': return `Score at percentile ${number.format(score * 100)} of training observations`
    default: return number.format(score)
  }
}

function Evidence({ alert }) {
  const { mass_balance: balance, shipment_line: shipment, price, ledger } = alert.evidence ?? {}
  const batch = useRead(ledger?.length ? `/batches/${encodeURIComponent(alert.batch_id)}` : null)
  return (
    <div className="stack">
      {balance && (
        <div className="insight-evidence-section">
          <h3>Mass balance</h3>
          <dl className="insight-evidence-grid">
            <div><dt>Total input</dt><dd>{formatQuantity(balance.total_input_quantity, balance.unit)}</dd></div>
            <div><dt>Recorded output</dt><dd>{formatQuantity(balance.output_quantity, balance.unit)}</dd></div>
            <div><dt>Difference</dt><dd>{formatQuantity(balance.difference, balance.unit)}</dd></div>
            <div><dt>Yield ratio</dt><dd>{number.format(Number(balance.yield_ratio))}</dd></div>
            <div><dt>Input batches</dt><dd>{balance.input_count}</dd></div>
          </dl>
        </div>
      )}
      {ledger?.length > 0 && (
        <div className="insight-evidence-section">
          <h3>Movement ledger</h3>
          <DataTable
            columns={[
              { key: 'event_date', label: 'Date', render: formatDate },
              { key: 'event_type', label: 'Movement', render: titleCase },
              { key: 'reference_id', label: 'Reference' },
              { key: 'quantity', label: 'Quantity', render: (value) => formatQuantity(value, batch.payload?.unit) },
            ]}
            rows={ledger}
            getRowKey={(row) => `${row.event_date}-${row.event_type}-${row.reference_id}`}
          />
        </div>
      )}
      {shipment && (
        <div className="insight-evidence-section">
          <h3>Shipment evidence</h3>
          <dl className="insight-evidence-grid">
            <div><dt>Shipment</dt><dd><Link to={`/shipments?shipment=${encodeURIComponent(shipment.shipment_id)}`}>{shipment.shipment_id}</Link></dd></div>
            <div><dt>Shipped</dt><dd>{formatDate(shipment.shipment_date)}</dd></div>
            <div><dt>Retailer</dt><dd>{shipment.retailer_name}</dd></div>
            <div><dt>Quantity</dt><dd>{formatQuantity(shipment.quantity_shipped, shipment.unit)}</dd></div>
          </dl>
        </div>
      )}
      {price && (
        <div className="insight-evidence-section">
          <h3>Price evidence</h3>
          <dl className="insight-evidence-grid">
            <div><dt>Observation</dt><dd>{price.price_id} · {formatDate(price.price_date)}</dd></div>
            <div><dt>Market and stage</dt><dd>{price.market_location} · {stageNames[price.supply_chain_stage]}</dd></div>
            <div><dt>Selling price</dt><dd>{priceText(price.selling_price, price.unit)}</dd></div>
            <div><dt>Previous comparable price</dt><dd>{priceText(price.previous_comparable_price, price.unit)}</dd></div>
            <div><dt>Change from previous price</dt><dd>{pct(price.price_change_percentage)}</dd></div>
          </dl>
        </div>
      )}
    </div>
  )
}

function AlertDetail({ alertId, revision, onUpdated }) {
  const { payload: alert, loading, error } = useRead(`/anomalies/${encodeURIComponent(alertId)}`, null, revision)
  const review = useSubmit()
  async function save(status) {
    const updated = await review.run(`/anomalies/${encodeURIComponent(alertId)}`, {
      method: 'PATCH', body: { alert_status: status },
    })
    if (updated) onUpdated()
  }
  return (
    <Panel title={alert ? `${titleCase(alert.alert_type)} · ${alertId}` : `Alert ${alertId}`} description={alert?.product_name}>
      {loading && <Loading>Loading alert evidence…</Loading>}
      <QueryError error={error || review.error} />
      {review.result && <Notice tone="success" title={`Alert marked ${titleCase(review.result.alert_status).toLowerCase()}`} />}
      {alert && (
        <div className="stack">
          <div className="cluster">
            <StatusBadge value={alert.alert_status} />
            <BatchLink id={alert.batch_id} />
            <span className="muted">{methodNames[alert.detection_method]} · {formatDate(alert.alert_date)}</span>
          </div>
          <p className="insight-alert-description">{alert.description}</p>
          <p className="insight-score"><Activity size={16} /> {scoreText(alert)}</p>
          <Evidence alert={alert} />
          <div className="cluster insight-review-actions">
            <button className="button button-secondary" type="button" disabled={review.pending || alert.alert_status === 'REVIEWED'} onClick={() => save('REVIEWED')}>Mark reviewed</button>
            <button className="button button-ghost" type="button" disabled={review.pending || alert.alert_status === 'DISMISSED'} onClick={() => save('DISMISSED')}>Dismiss alert</button>
          </div>
        </div>
      )}
    </Panel>
  )
}

export function Anomalies() {
  const [params, setParams] = useSearchParams()
  const status = STATUSES.includes(params.get('status')) ? params.get('status') : ''
  const alertType = ALERT_TYPES.includes(params.get('type')) ? params.get('type') : ''
  const batchId = params.get('batch') ?? ''
  const page = Math.max(1, Math.min(5000, Number.parseInt(params.get('page') ?? '1', 10) || 1))
  const selected = params.get('alert')
  const detail = useRef(null)
  const [revision, setRevision] = useState(0)
  const detection = useSubmit()
  const state = useRead('/anomalies', { status, alert_type: alertType, batch_id: batchId, limit: PAGE_SIZE + 1, offset: (page - 1) * PAGE_SIZE }, revision)
  useEffect(() => {
    if (selected && detail.current) detail.current.focus()
  }, [selected])
  function update(values) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next)
  }
  async function run(event) {
    const { tolerance } = formValues(event)
    if (await detection.run('/anomalies/run', { method: 'POST', body: { tolerance: Number(tolerance) / 100 } })) {
      setRevision((value) => value + 1)
      update({ page: '' })
    }
  }
  const cols = [
    {
      key: 'alert_id', label: 'Alert', render: (value) => (
        <button className="insight-record-link" type="button" aria-pressed={selected === value} onClick={() => update({ alert: value })}>{value}</button>
      ),
    },
    { key: 'batch_id', label: 'Batch', render: (id) => <BatchLink id={id} /> },
    { key: 'alert_type', label: 'Detected issue', render: titleCase },
    { key: 'detection_method', label: 'Detection', render: (method) => methodNames[method] ?? titleCase(method) },
    { key: 'alert_status', label: 'Status', render: (value) => <StatusBadge value={value} /> },
  ]

  return (
    <div className="insights stack">
      <PageHeader title="Anomaly center" description="Review detected risks, inspect evidence, and record an outcome." />
      <Panel title="Run detection" description="Scan the available records for rule violations and outliers.">
        <form className="insight-filters is-compact" onSubmit={run}>
          <Field label="Mass-balance tolerance (%)" required>
            <input type="number" min="0" step="0.1" name="tolerance" defaultValue={2} required />
          </Field>
          <button className="button button-primary" type="submit" disabled={detection.pending}>
            <Activity size={16} /> {detection.pending ? 'Running detection…' : 'Run detection'}
          </button>
        </form>
        <QueryError error={detection.error} />
        {detection.result && (
          <Notice tone="success" title={`${number.format(detection.result.new_alerts)} new alerts`}>
            {Object.entries(detection.result.counts ?? {}).map(([method, count]) => `${methodNames[method] ?? titleCase(method)} ${count}`).join(' · ')}
            {detection.result.notes?.map((note) => <p key={note}>{note}</p>)}
          </Notice>
        )}
      </Panel>
      <Panel title="Alerts">
        <form className="insight-filters is-forecast" key={`${status}-${alertType}-${batchId}`} onSubmit={(event) => {
          const fields = formValues(event)
          update({ ...fields, batch: fields.batch.toUpperCase(), page: '', alert: '' })
        }}>
          <Field label="Status">
            <select name="status" defaultValue={status}><option value="">All statuses</option>{STATUSES.map((value) => <option value={value} key={value}>{titleCase(value)}</option>)}</select>
          </Field>
          <Field label="Alert type">
            <select name="type" defaultValue={alertType}><option value="">All alert types</option>{ALERT_TYPES.map((value) => <option value={value} key={value}>{titleCase(value)}</option>)}</select>
          </Field>
          <Field label="Batch ID"><input name="batch" defaultValue={batchId} maxLength="12" placeholder="Any batch" /></Field>
          <button className="button button-secondary" type="submit"><ListFilter size={16} /> Apply filters</button>
        </form>
        {state.loading && <Loading />}
        <QueryError error={state.error} />
        {state.payload && (
          <>
            <DataTable columns={cols} rows={state.payload.slice(0, PAGE_SIZE)} empty="No alerts match these filters." getRowKey={(row) => row.alert_id} />
            <Pagination page={page} hasNext={state.payload.length > PAGE_SIZE} onChange={(value) => update({ page: value === 1 ? '' : value })} />
          </>
        )}
      </Panel>
      {selected ? (
        <div className="insight-detail" ref={detail} role="region" tabIndex={-1} aria-label="Alert details">
          <AlertDetail key={selected} alertId={selected} revision={revision} onUpdated={() => setRevision((value) => value + 1)} />
        </div>
      ) : (
        <Panel><EmptyState icon={TriangleAlert} title="Select an alert" description="Open an alert ID to inspect evidence and review its outcome." /></Panel>
      )}
    </div>
  )
}

function resultValue(value, row, key) {
  if (value == null) return '—'
  if (key === 'batch_id' && typeof value === 'string' && /^B[0-9]+$/.test(value)) return <BatchLink id={value} />
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (key === 'assessment' || key === 'description') return String(value)
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' && /^(\d{4}-\d{2}-\d{2})$/.test(value)) return formatDate(value)
  if (typeof value === 'number' && key.startsWith('quantity')) return formatQuantity(value, row.unit)
  return String(value)
}

function ResponseRows({ rows }) {
  if (!rows?.length) return null
  const columns = Object.keys(rows[0]).map((key) => ({
    key,
    label: titleCase(key),
    render: (value, row) => resultValue(value, row, key),
  }))
  return <DataTable columns={columns} rows={rows} />
}

function SqlResult({ sql, parameters }) {
  const [copyStatus, setCopyStatus] = useState('')
  async function copy() {
    try {
      await navigator.clipboard.writeText(sql)
      setCopyStatus('Copied')
    } catch {
      setCopyStatus('Copy unavailable')
    }
  }
  return (
    <details className="insight-sql">
      <summary>SQL and parameters</summary>
      <button className="button button-ghost" type="button" onClick={copy}><Clipboard size={14} /> {copyStatus || 'Copy SQL'}</button>
      <pre><code>{sql}</code></pre>
      {Object.keys(parameters ?? {}).length > 0 && <pre>{JSON.stringify(parameters, null, 2)}</pre>}
    </details>
  )
}

function Answer({ result, error, ask, pending }) {
  if (error) return <Notice tone="danger" title="Unable to answer">{error}</Notice>
  if (!result) return <Loading>Looking up your question…</Loading>
  if (result.simulation) {
    return <Suspense fallback={<Loading>Loading the impact report…</Loading>}><ImpactReport report={result.simulation} /></Suspense>
  }
  return (
    <div className="stack">
      <p>{result.answer}</p>
      <ResponseRows rows={result.rows} />
      {result.sql && <SqlResult sql={result.sql} parameters={result.parameters} />}
      {result.examples?.length > 0 && (
        <div className="insight-suggestions">
          {result.examples.map((query) => <button className="button button-secondary" type="button" key={query} disabled={pending} onClick={() => ask(query)}>{query}</button>)}
        </div>
      )}
    </div>
  )
}

export function Ask() {
  const entries = useSyncExternalStore(subscribeConversation, getConversation)
  const [question, setQuestion] = useState('')
  const input = useRef(null)
  const log = useRef(null)
  const pending = entries.some((entry) => entry.result === null && !entry.error)
  useEffect(() => {
    const history = log.current
    const latest = history?.lastElementChild
    if (latest) history.scrollTop += latest.getBoundingClientRect().top - history.getBoundingClientRect().top
  }, [entries.length])

  async function ask(prompt) {
    const text = prompt.trim()
    if (!text || getConversation().some((entry) => entry.result === null && !entry.error)) return
    setQuestion('')
    saveConversation([...getConversation(), { text, result: null, error: '' }])
    try {
      const result = await api('/query/nl', { method: 'POST', body: { question: text } })
      saveConversation([...getConversation().slice(0, -1), { text, result, error: '' }])
    } catch (error) {
      saveConversation([...getConversation().slice(0, -1), { text, result: null, error: error.message }])
    } finally {
      input.current?.focus()
    }
  }

  return (
    <div className="insights stack">
      <PageHeader
        title="Ask TraceFood" description="Ask about your records in plain language."
        actions={entries.length > 0 && (
          <button className="button button-secondary" type="button" onClick={() => saveConversation([])} disabled={pending}>Clear conversation</button>
        )}
      />
      <Panel className="insight-chat">
        {entries.length === 0 ? (
          <div className="insight-chat-intro">
            <div className="insight-chat-icon" aria-hidden="true"><Sparkles size={28} /></div>
            <h2>What would you like to trace?</h2>
            <p className="muted">Explore batches, shipments, quality checks, and prices with read-only questions.</p>
            <div className="insight-suggestions">
              {FIRST_QUESTIONS.map((text) => (
                <button className="button button-secondary" type="button" onClick={() => ask(text)} key={text}>
                  <CircleHelp size={16} /> {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="insight-chat-log" ref={log} role="log" aria-label="Conversation" aria-live="polite">
            {entries.map((entry, index) => (
              <div className="insight-chat-entry" key={`${index}-${entry.text}`}>
                <p className="insight-chat-prompt">{entry.text}</p>
                <div className="insight-chat-response">
                  <div className="insight-chat-avatar" aria-hidden="true"><Sparkles size={16} /></div>
                  <div className="insight-chat-message"><Answer result={entry.result} error={entry.error} ask={ask} pending={pending} /></div>
                </div>
              </div>
            ))}
          </div>
        )}
        <form className="insight-composer" onSubmit={(event) => { event.preventDefault(); ask(question) }}>
          <label className="insight-question">
            <span className="insight-visually-hidden">Your question</span>
            <input
              ref={input} value={question}
              onChange={(event) => setQuestion(event.target.value)}
              type="text" maxLength={500} placeholder="Ask about a batch, shipment, or price…" required
            />
          </label>
          <button className="button button-primary" type="submit" disabled={pending || !question.trim()}>
            <Send size={16} /> {pending ? 'Asking…' : 'Ask'}
          </button>
        </form>
      </Panel>
    </div>
  )
}
