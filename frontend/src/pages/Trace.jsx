import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Background, Controls, Handle, MarkerType, Position, ReactFlow,
} from '@xyflow/react'
import {
  CalendarDays, ClipboardCheck, FlaskConical, GitFork, LockKeyhole, MapPin, Package, Search, Truck,
} from 'lucide-react'
import '@xyflow/react/dist/style.css'
import { api, appRecordId, formatDate, formatQuantity, titleCase } from '../api.js'
import { DataTable, EmptyState, Field, Notice, PageHeader, Panel, StatusBadge } from '../ui.jsx'
import '../trace.css'

const BATCH_STATES = ['ACTIVE', 'ON_HOLD', 'RECALLED', 'CLOSED']
const QUALITY_STAGES = ['FARM', 'PROCESSING', 'DISTRIBUTION', 'RETAIL']
const QUALITY_RESULTS = ['PASS', 'FAIL', 'INCONCLUSIVE']
const PAGE_SIZE = 8
const routeId = (id) => encodeURIComponent(id)
const batchPath = (id) => `/batches?batch=${routeId(id)}`
const checkPath = (id) => `/quality?check=${routeId(id)}`
const shipmentPath = (id) => `/shipments?shipment=${routeId(id)}`

function useRead(path, filters = {}, revision = 0) {
  const query = JSON.stringify(filters)
  const key = path ? JSON.stringify([path, query, revision]) : null
  const [state, setState] = useState({})

  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    async function read() {
      try {
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])
        const data = await api(path, { params: JSON.parse(query), signal })
        if (!controller.signal.aborted) setState({ key, data })
      } catch (error) {
        if (!controller.signal.aborted) setState({ key, error: error.message })
      }
    }
    read()
    return () => controller.abort()
  }, [key, path, query])

  if (state.key === key) return { ...state, pending: false }
  return { pending: Boolean(path) }
}

function ErrorNotice({ message }) {
  return message ? <Notice tone="danger" title="Request failed">{message}</Notice> : null
}

function TraceTabs({ label, items, active, onChange }) {
  return (
    <div className="tabs trace-tabs" role="group" aria-label={label}>
      {items.map(({ id, label: text }) => (
        <button
          aria-pressed={active === id}
          className={`tab ${active === id ? 'is-active' : ''}`}
          key={id}
          onClick={() => onChange(id)}
          type="button"
        >
          {text}
        </button>
      ))}
    </div>
  )
}

function today() {
  const date = new Date()
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 10)
}

function BatchIdField({ value, onChange, suggestions, listId, label = 'Batch ID' }) {
  return (
    <Field label={label} required>
      <input
        autoComplete="off"
        list={suggestions ? listId : undefined}
        maxLength={12}
        onChange={(event) => onChange(event.target.value.toUpperCase())}
        pattern="B[0-9]+"
        placeholder="B103"
        required
        value={value}
      />
      {suggestions && (
        <datalist id={listId}>
          {suggestions.map((batch) => (
            <option key={batch.batch_id} value={batch.batch_id}>{batch.product_name}</option>
          ))}
        </datalist>
      )}
    </Field>
  )
}

const shipmentColumns = [
  { key: 'shipment_id', label: 'Shipment', render: (value) => <Link to={shipmentPath(value)}>{value}</Link> },
  { key: 'shipment_date', label: 'Shipped on', render: formatDate },
  { key: 'batch_id', label: 'Batch', render: (value) => <Link to={batchPath(value)}>{value}</Link> },
  { key: 'product_name', label: 'Product' },
  { key: 'source_location', label: 'Dispatched from' },
  { key: 'destination_city', label: 'Delivery destination', render: (v,r) => [v,r.destination_state].filter(Boolean).join(', ') || '—' },
  { key: 'shipment_status', label: 'Shipment status' },
  { key: 'carrier_name', label: 'Carrier', render: (v,r) => [v,r.transport_mode].filter(Boolean).join(' · ') || '—' },
  { key: 'actual_delivery_date', label: 'Delivered', render: formatDate },
  { key: 'reported_quantity', label: 'Whole shipment', render: (v,r) => formatQuantity(v,r.reported_unit) },
  { key: 'quantity_shipped', label: 'Batch allocation', render: (value, row) => formatQuantity(value, row.unit) },
  { key: 'retailer_name', label: 'Retailer', render: (value, row) => <>{value}<span className="trace-table-caption">{row.retailer_city}</span></> },
]

const qualityColumns = [
  { key: 'check_id', label: 'Check ID', render: (value, row) => row.result === 'FAIL' ? <Link to={checkPath(value)}>{value}</Link> : value },
  { key: 'check_date', label: 'Date', render: formatDate },
  { key: 'check_stage', label: 'Stage', render: v => v ? titleCase(v) : 'Unrecorded' },
  { key: 'inspecting_facility_name', label: 'Inspecting facility', render: (v,r) => v || r.inspecting_facility || '—' },
  { key: 'lab_test_code', label: 'Lab test' },
  { key: 'inspector_id', label: 'Inspector' },
  { key: 'result', label: 'Result', render: (value,row) => <StatusBadge value={value}>{row.source_result || titleCase(value)}</StatusBadge> },
  { key: 'contamination_type', label: 'Contamination' },
  { key: 'remarks', label: 'Remarks' },
]

const originColumns = [
  { key: 'original_batch_id', label: 'Source batch', render: (value) => <Link to={batchPath(value)}>{value}</Link> },
  { key: 'product_name', label: 'Product' },
  { key: 'farm_name', label: 'Farm' },
  { key: 'farm_id', label: 'Farm ID' },
  { key: 'city', label: 'City' },
]

const facilityColumns = [
  { key: 'facility_name', label: 'Facility' },
  { key: 'facility_city', label: 'Facility address', render: (v,r) => [r.street,v,r.facility_state,r.pin_code].filter(Boolean).join(', ') },
  { key: 'operation_type', label: 'Operation', render: titleCase },
  { key: 'processing_date', label: 'Date', render: formatDate },
]

function ShipmentTable({ rows, empty }) {
  return (
    <DataTable
      columns={shipmentColumns}
      empty={empty ?? 'No shipments recorded.'}
      getRowKey={(row) => `${row.shipment_id}-${row.batch_id}`}
      rows={rows}
    />
  )
}

function QualityTable({ rows, showBatch = false }) {
  const columns = showBatch ? [
    qualityColumns[0],
    { key: 'batch_id', label: 'Batch', render: (value, row) => <><Link to={batchPath(value)}>{value}</Link><span className="trace-table-caption">{row.product_name}</span></> },
    ...qualityColumns.slice(1),
  ] : qualityColumns
  return (
    <DataTable
      columns={columns}
      empty="No quality checks recorded."
      getRowKey={(row) => row.check_id}
      rows={rows}
    />
  )
}

function OriginsTable({ rows }) {
  return (
    <DataTable
      columns={originColumns}
      empty="No source farms recorded."
      getRowKey={(row) => row.original_batch_id}
      rows={rows}
    />
  )
}

function BatchNode({ data }) {
  const input = data.vertical ? Position.Top : Position.Left
  const output = data.vertical ? Position.Bottom : Position.Right
  const content = <>
    <span className="trace-flow-node-id">{data.kind} {data.id}</span>
    <span className="trace-flow-product" title={data.product}>{data.product}</span>
  </>
  return (
    <div className={`trace-flow-node trace-flow-node--${data.side}`}>
      <Handle type="target" position={input} isConnectable={false} />
      {data.to ? <Link to={data.to} aria-label={`Trace ${data.id} ${data.product}`} className="nodrag nopan">{content}</Link>
        : <div className="trace-flow-info">{content}</div>}
      <Handle type="source" position={output} isConnectable={false} />
    </div>
  )
}

const NODE_TYPES = { batch: BatchNode }

function graphLayout(lineage, report, direction, vertical) {
  const { batch, shipments, facilities } = report
  const predecessors = new Set(lineage.upstream.map((row) => row.batch_id))
  const details = new Map([[batch.batch_id, batch.product_name]])
  const entities = new Map()
  const links = []
  function entity(id, name, kind, side, to) {
    details.set(id, name)
    entities.set(id, { kind, side, to })
  }
  for (const edge of lineage.edges) {
    details.set(edge.input_batch_id, edge.input_product)
    details.set(edge.output_batch_id, edge.output_product)
    links.push({ source: edge.input_batch_id, target: edge.output_batch_id,
      label: edge.date_conflict ? 'Input dated after output' : edge.quantity_used == null ? 'Input' : formatQuantity(edge.quantity_used, edge.input_unit) })
  }
  if (direction !== 'down') {
    for (const farm of report.origin_farms) {
      if (!details.has(farm.original_batch_id)) continue
      entity(farm.farm_id, farm.farm_name, 'Farm', 'upstream')
      links.push({ source: farm.farm_id, target: farm.original_batch_id, label: 'Origin' })
    }
    for (const facility of facilities) {
      entity(facility.facility_id, facility.facility_name, 'Facility', 'upstream')
      links.push({ source: facility.facility_id, target: batch.batch_id, label: 'Handling' })
    }
  }
  if (direction !== 'up') {
    for (const shipment of shipments) {
      entity(shipment.shipment_id, formatDate(shipment.shipment_date), 'Shipment', 'downstream', shipmentPath(shipment.shipment_id))
      entity(shipment.retailer_id, shipment.retailer_name, 'Retailer', 'downstream')
      links.push({ source: batch.batch_id, target: shipment.shipment_id, label: 'Included in' },
        { source: shipment.shipment_id, target: shipment.retailer_id, label: 'Destination' })
    }
  }
  const outgoing = new Map()
  const incomingCount = new Map()
  for (const { source, target } of links) {
    if (!outgoing.has(source)) outgoing.set(source, [])
    outgoing.get(source).push(target)
    incomingCount.set(target, (incomingCount.get(target) ?? 0) + 1)
  }

  const queue = [...details.keys()].filter((id) => !incomingCount.has(id))
  const columns = new Map(queue.map((id) => [id, 0]))
  for (let index = 0; index < queue.length; index += 1) {
    const id = queue[index]
    for (const target of outgoing.get(id) ?? []) {
      columns.set(target, Math.max(columns.get(target) ?? 0, columns.get(id) + 1))
      const remaining = incomingCount.get(target) - 1
      incomingCount.set(target, remaining)
      if (remaining === 0) queue.push(target)
    }
  }

  const byColumn = new Map()
  for (const id of details.keys()) {
    const column = columns.get(id) ?? 0
    if (!byColumn.has(column)) byColumn.set(column, [])
    byColumn.get(column).push(id)
  }

  const nodes = [...byColumn.entries()].flatMap(([column, ids]) => ids.map((id, row) => {
    const side = id === batch.batch_id ? 'selected' : predecessors.has(id) ? 'upstream' : 'downstream'
    const fromCenter = row - (ids.length - 1) / 2
    return {
      id,
      type: 'batch',
      position: vertical ? { x: fromCenter * 174, y: column * 107 } : { x: column * 228, y: fromCenter * 88 },
      data: { id, product: details.get(id), vertical,
        ...(entities.get(id) ?? { kind: 'Batch', side, to: batchPath(id) }) },
      ariaLabel: `${id} ${details.get(id)}`,
    }
  }))

  const edges = links.map(({source, target, label}) => ({
    id: `${source}-${target}`,
    source, target,
    type: 'smoothstep',
    label,
    labelBgPadding: [5, 3],
    labelBgBorderRadius: 3,
    labelBgStyle: { fill: '#f1f6ef', fillOpacity: 1 },
    labelStyle: { fill: '#346453', fontSize: 11, fontWeight: 700 },
    style: { stroke: '#779386', strokeWidth: 1.55 },
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#779386' },
  }))
  return { nodes, edges }
}

const lineageColumns = [
  { key: 'input_batch_id', label: 'Input batch', render: (value) => <Link to={batchPath(value)}>{value}</Link> },
  { key: 'input_product', label: 'Input product' },
  { key: 'quantity_used', label: 'Amount used', render: (value, row) => formatQuantity(value, row.input_unit) },
  { key: 'date_conflict', label: 'Date check', render: (value) => value ? 'Input dated after output' : 'Consistent' },
  { key: 'output_batch_id', label: 'Output batch', render: (value) => <Link to={batchPath(value)}>{value}</Link> },
  { key: 'output_product', label: 'Output product' },
  { key: 'output_quantity', label: 'Output quantity', render: (value, row) => formatQuantity(value, row.output_unit) },
]

function LineageGraph({ report, lineage, direction, onShowBoth }) {
  const [vertical, setVertical] = useState(() => window.matchMedia('(max-width: 560px)').matches)
  const { nodes, edges } = useMemo(() => graphLayout(lineage, report, direction, vertical), [report, lineage, direction, vertical])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 560px)')
    const update = (event) => setVertical(event.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  return (
    <>
      <div className="trace-flow" aria-label="Interactive batch lineage graph">
        <ReactFlow
          key={vertical ? 'vertical' : 'horizontal'}
          edges={edges}
          edgesFocusable={false}
          elementsSelectable={false}
          fitView
          fitViewOptions={{ padding: 0.25, maxZoom: 1.25 }}
          maxZoom={2}
          minZoom={0.08}
          nodeTypes={NODE_TYPES}
          nodes={nodes}
          nodesConnectable={false}
          nodesDraggable={false}
          nodesFocusable={false}
          proOptions={{ hideAttribution: true }}
          zoomOnScroll={false}
        >
          <Background color="#dce8df" gap={18} size={1.4} />
          <Controls position="bottom-left" showInteractive={false} />
        </ReactFlow>
      </div>
      {!edges.length && <p role="status">No {direction === 'down' ? 'outputs or shipments' : direction === 'up' ? 'inputs, farm or facilities' : 'connections'} recorded for {report.batch.batch_id}.
        {direction !== 'both' && <> <button type="button" className="button button-secondary" onClick={onShowBoth}>Show both directions</button></>}</p>}
      <div className="trace-flow-legend" aria-label="Lineage legend">
        <span><i className="trace-legend-key trace-legend-key--selected" /> Selected batch</span>
        <span><i className="trace-legend-key trace-legend-key--upstream" /> Upstream</span>
        <span><i className="trace-legend-key trace-legend-key--downstream" /> Downstream</span>
        <span className="muted">Select a batch or shipment to open its record</span>
      </div>
      <details className="trace-edge-details">
        <summary>Batch derivations ({lineage.edges.length})</summary>
        <DataTable
          columns={lineageColumns}
          getRowKey={(row) => `${row.input_batch_id}-${row.output_batch_id}`}
          rows={lineage.edges}
        />
      </details>
    </>
  )
}

function BatchLineage({ report }) {
  const [direction, setDirection] = useState('both')
  const graph = useMemo(() => {
    const lineage = report.lineage
    if (direction === 'both') return lineage
    const related = direction === 'up' ? lineage.upstream : lineage.downstream
    const ids = new Set([report.batch.batch_id, ...related.map((row) => row.batch_id)])
    return { ...lineage, edges: lineage.edges.filter((e) => ids.has(e.input_batch_id) && ids.has(e.output_batch_id)) }
  }, [report, direction])
  return (
    <Panel
      actions={<TraceTabs label="Lineage direction" items={[
        { id: 'both', label: 'Both directions' }, { id: 'up', label: 'Upstream' }, { id: 'down', label: 'Downstream' },
      ]} active={direction} onChange={setDirection} />}
      className="trace-lineage-panel"
      description="Trace batch inputs and outputs, handling facilities, and recorded shipments to retailers."
      title="Lineage map"
    >
      <LineageGraph key={`${report.batch.batch_id}-${direction}`} report={report} lineage={graph} direction={direction} onShowBoth={() => setDirection('both')} />
    </Panel>
  )
}

function BatchSummary({ batch, onStatusChanged }) {
  const [status, setStatus] = useState(batch.status)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const days = batch.shelf_life_remaining_days

  async function update(event) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      const updated = await api(`/batches/${routeId(batch.batch_id)}/status`, {
        method: 'PATCH', body: { status },
      })
      onStatusChanged(updated)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel
      actions={<StatusBadge value={batch.status} />}
      description={`${batch.batch_id} · ${titleCase(batch.batch_type)} batch`}
      title={batch.product_name}
      className="trace-batch-summary"
    >
      <div className="trace-detail-metrics">
        <article><small>Initial quantity</small><strong>{formatQuantity(batch.quantity, batch.unit)}</strong></article>
        <article><small>Available now</small><strong>{formatQuantity(batch.available_quantity, batch.unit)}</strong></article>
        <article><small>Expiry date</small><strong>{formatDate(batch.expiry_date)}</strong><span>{days === 0 ? 'Expires today' : days < 0 ? `Expired ${Math.abs(days)} days ago` : `${days} days remaining`}</span></article>
      </div>
      <div className="trace-detail-notes">
        {batch.source_batch_id && <span>{batch.source_batch_id} · {batch.lot_number} · {batch.grade}</span>}
        {batch.available_quantity === null && <span>Available stock is unknown because movement quantities are incomplete.</span>}
        <span><CalendarDays size={15} aria-hidden="true" /> Produced {formatDate(batch.production_date)}</span>
        {batch.farm_name && <span><MapPin size={15} aria-hidden="true" /> {batch.farm_name}</span>}
        {batch.latest_quality && (
          <span>
            <ClipboardCheck size={15} aria-hidden="true" /> Latest check <StatusBadge value={batch.latest_quality.result} />
            {formatDate(batch.latest_quality.check_date)}
          </span>
        )}
      </div>
      <details className="trace-edge-details">
        <summary>Change batch status</summary>
        <form className="trace-inline-form trace-status-form" onSubmit={update}>
          <Field label="Status">
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {BATCH_STATES.map((state) => <option key={state} value={state}>{titleCase(state)}</option>)}
            </select>
          </Field>
          <button className="button button-secondary" disabled={pending || status === batch.status} type="submit">
            {pending ? 'Saving…' : 'Save batch status'}
          </button>
        </form>
        <ErrorNotice message={error} />
      </details>
    </Panel>
  )
}

const BATCH_TABS = [
  { id: 'lineage', label: 'Lineage' },
  { id: 'origin', label: 'Origin and handling' },
  { id: 'quality', label: 'Quality history' },
  { id: 'distribution', label: 'Distribution' },
]

function BatchRecords({ report }) {
  const [tab, setTab] = useState('lineage')
  return (
    <div className="stack">
      <TraceTabs label="Batch records" items={BATCH_TABS} active={tab} onChange={setTab} />
      {tab === 'lineage' && <BatchLineage report={report} />}
      {tab === 'origin' && (
        <>
          <Panel title="Origin farms"><OriginsTable rows={report.origin_farms} /></Panel>
          <Panel title="Facility history">
            <DataTable
              columns={facilityColumns}
              empty="No facility activity recorded."
              getRowKey={(row) => `${row.facility_id}-${row.processing_date}`}
              rows={report.facilities}
            />
          </Panel>
        </>
      )}
      {tab === 'quality' && <Panel title="Quality checks"><QualityTable rows={report.quality_checks} /></Panel>}
      {tab === 'distribution' && <Panel title="Shipment history"><ShipmentTable rows={report.shipments} /></Panel>}
    </div>
  )
}

export function BatchTrace() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [filters, setFilters] = useState({ term: '', state: '', offset: 0 })
  const [revision, setRevision] = useState(0)
  const [notice, setNotice] = useState(null)
  const exact = /^B[0-9]+$/i.test(filters.term)
  const browse = useRead(
    exact ? `/batches/${routeId(filters.term.toUpperCase())}` : '/batches',
    exact ? {} : { product: filters.term, status: filters.state, offset: filters.offset, limit: PAGE_SIZE + 1 },
    revision,
  )
  const rows = exact && browse.data
    ? [browse.data].filter((row) => !filters.state || filters.state === row.status)
    : (browse.data ?? []).slice(0, PAGE_SIZE)
  const hasNextPage = !exact && (browse.data?.length ?? 0) > PAGE_SIZE
  const batchId = appRecordId(params.get('batch') || '') || rows[0]?.batch_id
  const result = useRead(batchId ? `/reports/batch/${routeId(batchId)}` : null, {}, revision)
  const report = result.data

  function selectBatch(id) {
    setParams({ batch: id })
  }

  function search(event) {
    event.preventDefault()
    const term = /^BATCH-/i.test(query.trim()) ? appRecordId(query) : query.trim()
    setFilters({ term, state: status, offset: 0 })
    if (/^B[0-9]+$/i.test(term) && !status) selectBatch(term.toUpperCase())
    else setParams({})
  }

  function changePage(offset) {
    setFilters((current) => ({ ...current, offset }))
    setParams({})
  }

  function statusChanged(updated) {
    setNotice({ id: updated.batch_id, status: updated.status })
    setRevision((current) => current + 1)
  }

  return (
    <>
      <PageHeader
        actions={<Link className="button button-secondary" to="/register"><Package size={16} aria-hidden="true" /> Register batch</Link>}
        description="Search inventory and follow batches across farms, facilities, and retailers."
        title="Batch trace"
      />
      <Panel className="trace-lookup" title="Find a batch">
        <form className="trace-filters" onSubmit={search} role="search">
          <Field label="Batch ID or product">
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="B101 or Tomato" />
          </Field>
          <Field label="Batch status">
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              {BATCH_STATES.map((state) => <option key={state} value={state}>{titleCase(state)}</option>)}
            </select>
          </Field>
          <button className="button button-primary" type="submit"><Search size={16} aria-hidden="true" /> Search batches</button>
        </form>
      </Panel>
      <div className="trace-browser">
        <Panel className="trace-roster" title="Batches">
          <ErrorNotice message={browse.error} />
          {browse.pending && <p className="trace-loading" role="status">Loading batches…</p>}
          {!browse.error && !browse.pending && !rows.length && (
            <EmptyState title="No matches" description="Try another batch ID, product, or status." />
          )}
          {!!rows.length && (
            <ul className="trace-batch-list" aria-label="Matching batches">
              {rows.map((item) => (
                <li key={item.batch_id}>
                  <button
                    aria-current={item.batch_id === batchId ? 'true' : undefined}
                    className={`trace-batch-link ${item.batch_id === batchId ? 'is-active' : ''}`}
                    onClick={() => selectBatch(item.batch_id)}
                    type="button"
                  >
                    <span className="trace-batch-icon"><Package size={18} aria-hidden="true" /></span>
                    <span><strong>{item.product_name}</strong><small>{item.batch_id} · {formatQuantity(item.available_quantity, item.unit)} available</small></span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!exact && (filters.offset > 0 || hasNextPage) && (
            <div className="trace-pagination">
              <button className="button button-ghost" type="button" disabled={filters.offset === 0} onClick={() => changePage(filters.offset - PAGE_SIZE)}>
                Previous
              </button>
              <button className="button button-ghost" type="button" disabled={!hasNextPage} onClick={() => changePage(filters.offset + PAGE_SIZE)}>
                Next
              </button>
            </div>
          )}
        </Panel>
        <div className="stack trace-batch-records">
          <ErrorNotice message={result.error} />
          {result.pending && <p className="trace-loading" role="status">Loading batch details…</p>}
          {report && (
            <>
              {notice?.id === batchId && <Notice tone="success">{batchId} marked {titleCase(notice.status).toLowerCase()}.</Notice>}
              <BatchSummary key={batchId} batch={report.batch} onStatusChanged={statusChanged} />
              <BatchRecords key={batchId} report={report} />
            </>
          )}
          {!batchId && !browse.pending && <EmptyState icon={Package} title="Find a batch to trace" description="Select a search result to see its records." />}
        </div>
      </div>
    </>
  )
}

function Assessment({ value }) {
  const [classification, detail] = value.split(': ')
  const tone = {
    CONFIRMED: 'danger', 'POTENTIALLY AFFECTED': 'warning', 'POSSIBLE SOURCE': 'info',
  }[classification] ?? 'neutral'
  return (
    <>
      <StatusBadge tone={tone} value={classification} />
      {detail && <span className="trace-table-caption">{detail}</span>}
    </>
  )
}

const assessmentColumns = [
  { key: 'batch_id', label: 'Batch', render: (value) => <Link to={batchPath(value)}>{value}</Link> },
  { key: 'product_name', label: 'Product' },
  { key: 'relation', label: 'Relationship', render: titleCase },
  { key: 'depth', label: 'Depth' },
  { key: 'assessment', label: 'Assessment', render: (value) => <Assessment value={value} /> },
]

function ContaminationWindow({ window }) {
  return (
    <Panel title="Possible contamination window">
      <div className="trace-window">
        <div>
          <StatusBadge tone="success" value="LAST PASS" />
          <strong>{window.last_pass_date ? formatDate(window.last_pass_date) : 'Open start'}</strong>
          {window.last_pass_check_id && <span>{titleCase(window.last_pass_stage)} · {window.last_pass_check_id}</span>}
        </div>
        <div className="trace-window-line" aria-hidden="true" />
        <div>
          <StatusBadge tone="danger" value="FAILURE" />
          <strong>{formatDate(window.fail_date)}</strong>
          <span>{titleCase(window.fail_stage)} · {window.failed_check_id}</span>
        </div>
      </div>
      <p className="muted trace-caveat">{window.note}</p>
    </Panel>
  )
}

export function ImpactReport({ report }) {
  const simulated = report.mode === 'SIMULATION'
  const downstreamCount = report.batches.filter((batch) => batch.relation === 'DOWNSTREAM').length
  const shipmentCount = new Set(report.shipments.map((row) => row.shipment_id)).size
  const retailers = new Map(report.shipments.map((row) => [row.retailer_id, row.retailer_name]))

  return (
    <div className="stack trace-impact">
      <Notice tone={simulated ? 'warning' : 'danger'} title={simulated ? 'What-if simulation' : 'Real investigation'}>
        {report.banner} · Batch <Link to={batchPath(report.batch_id)}>{report.batch_id}</Link>
        {report.triggering_check && <> · Check {report.triggering_check.check_id}</>}
      </Notice>
      <div className="trace-impact-metrics" aria-label="Impact totals">
        <article><span className="trace-metric-icon"><GitFork size={19} aria-hidden="true" /></span><span><small>Downstream batches</small><strong>{downstreamCount}</strong></span></article>
        <article><span className="trace-metric-icon"><Truck size={19} aria-hidden="true" /></span><span><small>Shipments</small><strong>{shipmentCount}</strong></span></article>
        <article><span className="trace-metric-icon"><MapPin size={19} aria-hidden="true" /></span><span><small>Retailers</small><strong>{report.retailer_count ?? report.retailers.length}</strong></span></article>
      </div>
      {report.contamination_window && <ContaminationWindow window={report.contamination_window} />}
      <Panel title="Batch assessments">
        <DataTable columns={assessmentColumns} getRowKey={(row) => row.batch_id} rows={report.batches} />
        {report.caveat && <p className="muted trace-caveat">{report.caveat}</p>}
      </Panel>
      <Panel title="Shipments and retailers">
        <ShipmentTable rows={report.shipments} empty="No shipments carried the selected batch or its downstream outputs." />
        {retailers.size > 0 && (
          <ul className="trace-retailer-list" aria-label="Retailer destinations">
            {[...retailers].map(([id, name]) => <li key={id}><MapPin size={14} aria-hidden="true" /> {name} <small>{id}</small></li>)}
          </ul>
        )}
      </Panel>
      {report.quality_checks && <Panel title="Quality evidence"><QualityTable rows={report.quality_checks} /></Panel>}
      {report.origin_farms?.length > 0 && <Panel title="Origin farms"><OriginsTable rows={report.origin_farms} /></Panel>}
    </div>
  )
}

function RecordQuality({ batch, onRecorded }) {
  const [batchId, setBatchId] = useState(batch)
  const [result, setResult] = useState('PASS')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  async function save(event) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setPending(true)
    setError('')
    try {
      const recorded = await api('/quality-checks', {
        method: 'POST',
        body: {
          batch_id: batchId.trim(),
          check_date: data.get('check_date'),
          check_stage: data.get('check_stage'),
          result,
          contamination_type: result === 'FAIL' ? data.get('contamination_type').trim() : null,
          remarks: data.get('remarks').trim() || null,
        },
      })
      form.reset()
      setResult('PASS')
      onRecorded(recorded)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel
      className="trace-action-panel"
      description="Log an inspection result at any point in the supply chain."
      title="Record a quality check"
    >
      <form className="stack" onSubmit={save}>
        <div className="form-grid">
          <BatchIdField value={batchId} onChange={setBatchId} />
          <Field label="Check date" required><input type="date" name="check_date" defaultValue={today()} required /></Field>
          <Field label="Check stage" required>
            <select name="check_stage" required>
              {QUALITY_STAGES.map((stage) => <option key={stage} value={stage}>{titleCase(stage)}</option>)}
            </select>
          </Field>
          <Field label="Result" required>
            <select value={result} onChange={(event) => setResult(event.target.value)} required>
              {QUALITY_RESULTS.map((outcome) => <option key={outcome} value={outcome}>{titleCase(outcome)}</option>)}
            </select>
          </Field>
          {result === 'FAIL' && (
            <Field label="Contamination type" required>
              <input maxLength={40} name="contamination_type" placeholder="Reported substance or organism" required />
            </Field>
          )}
        </div>
        <Field label="Inspection notes"><textarea name="remarks" placeholder="Optional observations or laboratory reference" rows={3} /></Field>
        <ErrorNotice message={error} />
        <div><button className="button button-primary" disabled={pending} type="submit"><ClipboardCheck size={17} aria-hidden="true" /> {pending ? 'Recording…' : 'Record check'}</button></div>
      </form>
    </Panel>
  )
}

function QualityHistory({ batch, onSearch }) {
  const [batchId, setBatchId] = useState(batch)
  const history = useRead(batch ? `/batches/${routeId(batch)}/quality-checks` : null)
  return (
    <Panel className="trace-action-panel" title="Batch quality history">
      <form className="trace-inline-form" onSubmit={(event) => { event.preventDefault(); onSearch(batchId.trim()) }}>
        <BatchIdField value={batchId} onChange={setBatchId} />
        <button className="button button-primary" type="submit"><Search size={16} aria-hidden="true" /> Load checks</button>
      </form>
      <ErrorNotice message={history.error} />
      {history.pending && <p className="trace-loading" role="status">Loading quality checks…</p>}
      {history.data && <QualityTable rows={history.data} />}
    </Panel>
  )
}

const QUALITY_TABS = [
  { id: 'investigate', label: 'Investigations' },
  { id: 'record', label: 'Record a check' },
  { id: 'history', label: 'Batch history' },
]

export function Quality() {
  const [params, setParams] = useSearchParams()
  const requestedTab = params.get('tab')
  const tab = QUALITY_TABS.some(({ id }) => id === requestedTab) ? requestedTab : 'investigate'
  const check = params.get('check')?.toUpperCase() || ''
  const batch = params.get('batch')?.toUpperCase() || ''
  const [searchText, setSearchText] = useState(null)
  const [notice, setNotice] = useState('')
  const report = useRead(tab === 'investigate' && check ? `/investigations/${routeId(check)}` : null)
  const latest = useRead(tab === 'investigate' && !check ? '/dashboard/summary' : null)

  function changeTab(id) {
    setSearchText(null)
    const next = new URLSearchParams(params)
    next.set('tab', id)
    setParams(next)
  }

  function openCheck(id) {
    setSearchText(null)
    setParams({ check: id })
  }

  function recorded(record) {
    setNotice(`Quality check ${record.check_id} recorded.`)
    if (record.result === 'FAIL') openCheck(record.check_id)
  }

  return (
    <>
      <PageHeader description="Review test results and trace potential exposure from recorded failures." title="Quality and investigation" />
      {notice && <Notice tone="success">{notice}</Notice>}
      <TraceTabs label="Quality workflows" items={QUALITY_TABS} active={tab} onChange={changeTab} />
      {tab === 'investigate' && (
        <>
          <Panel className="trace-action-panel" title="Open a failed check">
            <form className="trace-inline-form" onSubmit={(event) => { event.preventDefault(); openCheck((searchText ?? check).trim()) }}>
              <Field label="Failed check ID" required>
                <input
                  value={searchText ?? check}
                  onChange={(event) => setSearchText(event.target.value.toUpperCase())}
                  placeholder="QC4"
                  pattern="QC[0-9]+"
                  maxLength={12}
                  required
                />
              </Field>
              <button className="button button-primary" type="submit"><Search size={16} aria-hidden="true" /> Open investigation</button>
            </form>
            <ErrorNotice message={report.error} />
          </Panel>
          {report.pending && <p className="trace-loading" role="status">Loading investigation…</p>}
          {report.data && <ImpactReport report={report.data} />}
          {!check && (
            <Panel title="Recent failed checks">
              <ErrorNotice message={latest.error} />
              {latest.pending && <p className="trace-loading" role="status">Loading checks…</p>}
              {latest.data && <QualityTable rows={latest.data.recent_failed_checks ?? []} showBatch />}
            </Panel>
          )}
        </>
      )}
      {tab === 'record' && <RecordQuality key={batch} batch={batch} onRecorded={recorded} />}
      {tab === 'history' && <QualityHistory key={batch} batch={batch} onSearch={(id) => setParams({ tab: 'history', batch: id })} />}
    </>
  )
}

export function Simulation() {
  const [params] = useSearchParams()
  const [input, setInput] = useState(null)
  const [report, setReport] = useState(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const batchId = input ?? params.get('batch')?.toUpperCase() ?? 'B101'
  const suggestions = useRead('/batches', { limit: 100 })

  async function run(event) {
    event.preventDefault()
    setPending(true)
    setError('')
    setReport(null)
    try {
      setReport(await api('/simulate/contamination', { method: 'POST', body: { batch_id: batchId.trim() } }))
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <PageHeader
        actions={<StatusBadge tone="info" value="READ ONLY" />}
        description="Preview which batches and retailer destinations would be affected by a hypothetical failure."
        title="What-if simulation"
      />
      <Panel className="trace-action-panel" title="Set up a scenario">
        <div className="trace-sim-info"><LockKeyhole size={17} aria-hidden="true" /><span>The simulation reads existing lineage and shipments. It leaves quality results and batch status unchanged.</span></div>
        <form className="trace-inline-form" onSubmit={run}>
          <BatchIdField value={batchId} onChange={setInput} suggestions={suggestions.data} listId="trace-simulation-batches" />
          <button className="button button-primary" disabled={pending} type="submit"><FlaskConical size={17} aria-hidden="true" /> {pending ? 'Simulating…' : 'Run simulation'}</button>
        </form>
        <ErrorNotice message={error} />
      </Panel>
      {report && <ImpactReport report={report} />}
    </>
  )
}
