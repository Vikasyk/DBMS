import { useEffect, useId, useRef, useState } from 'react'
import {
  Box, Factory, GitFork, MapPin, PackageOpen, PackagePlus, Plus, Search,
  ShoppingBasket, Sprout, Trash2, Truck, Warehouse,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatDate, formatQuantity, titleCase } from '../api.js'
import { DataTable, EmptyState, Field, Notice, PageHeader, Panel, StatusBadge } from '../ui.jsx'
import '../operations.css'

const FARMS = ['Tomato', 'Onion', 'Potato', 'Mango']
const OUTPUTS = ['Tomato Puree', 'Tomato Onion Masala', 'Mango Pulp', 'Potato Chips']
const UNITS = ['kg', 'L', 'unit']
const TRANSFORMATIONS = ['PULPING', 'MIXING', 'CLEANING', 'SORTING', 'PACKAGING', 'COLD_STORAGE', 'OTHER']
const HANDLING = ['CLEANING', 'SORTING', 'PACKAGING', 'COLD_STORAGE', 'OTHER']
const MASTER = {
  farm: { title: 'Farm', plural: 'Farms', endpoint: '/farms', icon: Sprout, contacts: true },
  facility: { title: 'Facility', plural: 'Facilities', endpoint: '/facilities', icon: Factory, contacts: false },
  retailer: { title: 'Retailer', plural: 'Retailers', endpoint: '/retailers', icon: ShoppingBasket, contacts: true },
}
const DATE_LABEL = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' })
const RUPEES = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })

function dateAfter(days, base) {
  const day = base ? new Date(`${base}T12:00:00`) : new Date()
  day.setDate(day.getDate() + days)
  const parts = Object.fromEntries(DATE_LABEL.formatToParts(day).map(part => [part.type, part.value]))
  return `${parts.year}-${parts.month}-${parts.day}`
}

function textValue(form, name) {
  return String(form.get(name) ?? '').trim()
}

function batchPath(code) {
  return `/batches?batch=${encodeURIComponent(code)}`
}

function shipmentPath(code) {
  return `/shipments?shipment=${encodeURIComponent(code)}`
}

function useRecords(path, { revision = 0, all = false } = {}) {
  const [response, setResponse] = useState(null)
  const key = `${path}|${revision}`
  useEffect(() => {
    if (!path) return undefined
    const controller = new AbortController()
    async function read() {
      const signal = controller.signal
      if (!all) return api(path, { signal })
      const records = []
      let page
      do {
        page = await api(path, { params: { limit: 200, offset: records.length }, signal })
        records.push(...page)
      } while (page.length === 200)
      return records
    }
    read().then(data => {
      if (!controller.signal.aborted) setResponse({ key, data, error: null })
    }).catch(error => {
      if (!controller.signal.aborted) setResponse({ key, data: null, error: error.message })
    })
    return () => controller.abort()
  }, [path, key, all])
  return {
    data: response?.key === key ? response.data : null,
    error: response?.key === key ? response.error : null,
    loading: Boolean(path) && response?.key !== key,
  }
}

function useFormRequest() {
  const active = useRef(false)
  const [state, setState] = useState({ busy: false, error: null, data: null })
  async function submit(event, action, onSaved) {
    event.preventDefault()
    if (active.current) return
    active.current = true
    const form = event.currentTarget
    const values = new FormData(form)
    setState({ busy: true, error: null, data: null })
    try {
      const data = await action(values)
      onSaved?.(data, form)
      setState({ busy: false, data, error: null })
    } catch (error) {
      setState({ busy: false, data: null, error: error.message })
    } finally {
      active.current = false
    }
  }
  return { ...state, submit }
}

function WorkflowTabs({ options, active, onChange, label }) {
  return (
    <div className="tabs op-tabs" role="group" aria-label={label}>
      {options.map(({ id, label: name, icon: Icon }) => (
        <button
          key={id}
          type="button"
          className={`tab${active === id ? ' is-active' : ''}`}
          aria-pressed={active === id}
          onClick={() => onChange(id)}
        >
          <Icon size={16} aria-hidden="true" />
          {name}
        </button>
      ))}
    </div>
  )
}

function ResultNotice({ request, children }) {
  if (request.error) return <Notice tone="danger" title="Request failed">{request.error}</Notice>
  if (request.data && children) return <Notice tone="success">{children(request.data)}</Notice>
  return null
}

function ReadResult({ request, children }) {
  if (request.loading) return <p className="op-loading" role="status">Loading records…</p>
  if (request.error) return <Notice tone="danger" title="Could not load records">{request.error}</Notice>
  return request.data ? children(request.data) : null
}

function FormSubmit({ busy, label, disabled, icon: Icon = Plus }) {
  return (
    <div className="op-submit">
      <button className="button button-primary" type="submit" disabled={busy || disabled}>
        {!busy && <Icon size={17} aria-hidden="true" />}
        {busy ? 'Working…' : label}
      </button>
    </div>
  )
}

function MasterSelect({ field, label, options }) {
  return (
    <Field label={label} required>
      <select name={`${field}_id`} defaultValue="" required>
        <option value="" disabled>Select {label.toLowerCase()}</option>
        {options.map(record => (
          <option key={record[`${field}_id`]} value={record[`${field}_id`]}>
            {record[`${field}_name`]} · {record[`${field}_id`]}
          </option>
        ))}
      </select>
    </Field>
  )
}

function BatchFields({ processed = false }) {
  const days = processed ? 90 : 14
  const [production, setProduction] = useState(() => dateAfter(0))
  const [expiry, setExpiry] = useState(() => dateAfter(days))
  const customExpiry = useRef(false)
  function updateProduction(value) {
    setProduction(value)
    if (value && (!customExpiry.current || expiry < value)) setExpiry(dateAfter(days, value))
  }
  return (
    <>
      <Field label={processed ? 'Output product' : 'Product'} required>
        <select name="product_name" defaultValue={(processed ? OUTPUTS : FARMS)[0]} required>
          {(processed ? OUTPUTS : FARMS).map(product => <option key={product}>{product}</option>)}
        </select>
      </Field>
      <Field label={processed ? 'Output quantity' : 'Quantity'} required>
        <input type="number" name="quantity" defaultValue="1" min=".001" max="999999999.999" step=".001" required />
      </Field>
      <Field label="Unit" required>
        <select name="unit" defaultValue="kg" required>
          {UNITS.map(unit => <option key={unit}>{unit}</option>)}
        </select>
      </Field>
      <Field label="Production date" required>
        <input type="date" name="production_date" value={production} onChange={event => updateProduction(event.target.value)} required />
      </Field>
      <Field label="Expiry date" required>
        <input
          type="date" name="expiry_date" min={production} value={expiry}
          onChange={event => { customExpiry.current = true; setExpiry(event.target.value) }} required
        />
      </Field>
    </>
  )
}

function batchPayload(form) {
  return Object.fromEntries(
    ['product_name', 'quantity', 'unit', 'production_date', 'expiry_date'].map(key => [key, textValue(form, key)])
  )
}

function MasterRegistry({ kind }) {
  const master = MASTER[kind]
  const [revision, setRevision] = useState(0)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const list = useRecords(master.endpoint, { revision, all: true })
  const request = useFormRequest()
  function save(event) {
    request.submit(event, form => {
      const payload = {
        [`${kind}_name`]: textValue(form, `${kind}_name`),
        street: textValue(form, 'street') || null,
        city: textValue(form, 'city'),
        state: textValue(form, 'state'),
        pin_code: textValue(form, 'pin_code'),
      }
      if (master.contacts) {
        payload.contact_numbers = [...new Set(textValue(form, 'contact_numbers').split(/[\s,]+/).filter(Boolean))]
      }
      return api(master.endpoint, { method: 'POST', body: payload })
    }, (_, form) => {
      form.reset()
      setRevision(value => value + 1)
    })
  }
  const columns = [
    { key: `${kind}_id`, label: 'ID', render: value => <span className="op-record-id">{value}</span> },
    { key: `${kind}_name`, label: master.title },
    { key: 'city', label: 'City' },
    { key: 'pin_code', label: 'PIN' },
  ]
  return (
    <div className="op-workspace">
      <Panel title={`Register a ${master.title.toLowerCase()}`}>
        <form className="stack" onSubmit={save}>
          <div className="form-grid">
            <Field label={`${master.title} name`} required className="op-full">
              <input name={`${kind}_name`} maxLength="100" required />
            </Field>
            <Field label="Street" className="op-full"><input name="street" maxLength="150" /></Field>
            <Field label="City" required><input name="city" maxLength="60" required /></Field>
            <Field label="State" required><input name="state" defaultValue="Karnataka" maxLength="60" required /></Field>
            <Field label="PIN code" required>
              <input name="pin_code" inputMode="numeric" pattern="[1-9][0-9]{5}" maxLength="6" required />
            </Field>
            {master.contacts && (
              <Field label="Contact numbers" hint="Separate multiple numbers with commas." className="op-full">
                <input name="contact_numbers" type="text" placeholder="+919876543210" />
              </Field>
            )}
          </div>
          <ResultNotice request={request}>
            {record => <span>Registered <strong>{record[`${kind}_name`]}</strong> as {record[`${kind}_id`]}.</span>}
          </ResultNotice>
          <FormSubmit busy={request.busy} label={`Register ${kind}`} />
        </form>
      </Panel>
      <Panel title={master.plural} description={list.data ? `${list.data.length} registered` : undefined} className="op-context">
        <ReadResult request={list}>{records => {
          const filter = search.trim().toLowerCase()
          const rows = records.filter(record => [record[`${kind}_id`], record[`${kind}_name`], record.city, record.pin_code]
            .some(value => String(value ?? '').toLowerCase().includes(filter)))
          const pageSize = 8
          return (
            <div className="stack">
              {records.length > 0 && <input type="search" aria-label={`Search ${master.plural.toLowerCase()}`} placeholder="Search by name or city" value={search}
                onChange={event => { setSearch(event.target.value); setPage(0) }} />}
              <DataTable rows={rows.slice(page * pageSize, (page + 1) * pageSize)} columns={columns} getRowKey={row => row[`${kind}_id`]} empty="No matching records." />
              {rows.length > pageSize && (
                <div className="cluster op-pagination">
                  <button type="button" className="button button-secondary" onClick={() => setPage(value => value - 1)} disabled={!page}>Previous</button>
                  <span className="muted">{page + 1} of {Math.ceil(rows.length / pageSize)}</span>
                  <button type="button" className="button button-secondary" onClick={() => setPage(value => value + 1)} disabled={(page + 1) * pageSize >= rows.length}>Next</button>
                </div>
              )}
            </div>
          )
        }}</ReadResult>
      </Panel>
    </div>
  )
}

function OriginalBatch() {
  const farms = useRecords('/farms', { all: true })
  const request = useFormRequest()
  return (
    <div className="op-workspace">
      <Panel title="Register an original batch" description="Save the source farm and the initial stock.">
        <ReadResult request={farms}>{rows => rows.length ? (
          <form className="stack" onSubmit={event => request.submit(event, form => api('/batches', {
            method: 'POST',
            body: { ...batchPayload(form), farm_id: textValue(form, 'farm_id') },
          }))}>
            <div className="form-grid">
              <div className="op-full"><MasterSelect field="farm" label="Source farm" options={rows} /></div>
              <BatchFields />
            </div>
            <ResultNotice request={request}>{record => (
              <span>Registered <Link to={batchPath(record.batch_id)}>{record.batch_id}</Link> with {formatQuantity(record.quantity, record.unit)} in initial stock.</span>
            )}</ResultNotice>
            <FormSubmit busy={request.busy} label="Register batch" icon={PackagePlus} />
          </form>
        ) : <EmptyState icon={Sprout} title="Register a source farm first" description="Every original batch needs a recorded origin."
          action={<Link className="button button-secondary" to="/register?kind=farm">Register a farm</Link>} />}</ReadResult>
      </Panel>
      <Panel title="Source farms" description={farms.data ? `${farms.data.length} available` : undefined} className="op-context">
        <ReadResult request={farms}>{rows => (
          <div className="op-source-list">
            {rows.slice(0, 6).map(row => (
              <div className="op-source" key={row.farm_id}>
                <span className="op-chip-icon"><Sprout size={17} aria-hidden="true" /></span>
                <div><strong>{row.farm_name}</strong><span>{row.city}{row.state && `, ${row.state}`}</span></div>
                <span className="op-record-id">{row.farm_id}</span>
              </div>
            ))}
            {!rows.length && <p className="muted">No source farms yet.</p>}
            {rows.length > 6 && <Link to="/register?kind=farm" className="op-inline-link">View all farms</Link>}
          </div>
        )}</ReadResult>
      </Panel>
    </div>
  )
}

export function Register() {
  const [params, setParams] = useSearchParams()
  const kind = Object.hasOwn(MASTER, params.get('kind')) ? params.get('kind') : 'batch'
  const options = [
    { id: 'batch', label: 'Original batch', icon: Box },
    ...Object.entries(MASTER).map(([id, record]) => ({ id, label: record.title, icon: record.icon })),
  ]
  return (
    <div className="stack op-page">
      <PageHeader title="Register records" description="Add source farms, original batches, facilities, and retail destinations." />
      <WorkflowTabs options={options} active={kind} onChange={value => setParams(value === 'batch' ? {} : { kind: value })} label="Registration record type" />
      {kind === 'batch' ? <OriginalBatch /> : <MasterRegistry key={kind} kind={kind} />}
    </div>
  )
}

function useStockItems() {
  const sequence = useRef(1)
  const [items, setItems] = useState([{ key: 0, batchId: '', quantity: '' }])
  const update = (key, field, value) => setItems(rows => rows.map(item => item.key === key ? { ...item, [field]: value } : item))
  function add() {
    const key = sequence.current++
    setItems(rows => [...rows, { key, batchId: '', quantity: '' }])
  }
  return { items, update, add, remove: key => setItems(rows => rows.filter(item => item.key !== key)) }
}

function BatchLookupInput({ name = 'batch_id', list, value, onChange, defaultValue, onBlur }) {
  return (
    <input
      name={name} list={list} placeholder="e.g. B101" pattern="B[0-9]+" maxLength="12" required
      value={value} defaultValue={defaultValue} autoCapitalize="characters" spellCheck="false"
      onChange={event => {
        const code = event.target.value.trim().toUpperCase()
        if (onChange) onChange(code)
        else event.target.value = code
      }}
      onBlur={onBlur}
    />
  )
}

function BatchSuggestions({ list, batches }) {
  return <datalist id={list}>{batches.map(row => (
    <option key={row.batch_id} value={row.batch_id} label={`${row.product_name} · ${formatQuantity(row.available_quantity, row.unit)} available`} />
  ))}</datalist>
}

function StockItem({ batchList, item, index, actionLabel, update, remove, readOnly, removable, idPrefix }) {
  const [lookedUp, setLookedUp] = useState('')
  const known = batchList.find(row => row.batch_id === item.batchId)
  const remote = useRecords(!known && lookedUp && lookedUp === item.batchId ? `/batches/${encodeURIComponent(lookedUp)}` : null)
  const batch = known || remote.data
  const exceeds = batch && Number(item.quantity) > Number(batch.available_quantity)
  return (
    <div className="op-item">
      <Field label={`Batch ID ${index + 1}`} required>
        <BatchLookupInput
          list={idPrefix} value={item.batchId} onChange={value => update(item.key, 'batchId', value)}
          onBlur={() => setLookedUp(/^B\d+$/.test(item.batchId) ? item.batchId : '')}
        />
      </Field>
      <Field label={`${actionLabel}${batch ? ` (${batch.unit})` : ''}`} required>
        <input type="number" min=".001" max="999999999.999" step=".001" placeholder="0.000" required
          value={item.quantity} onChange={event => update(item.key, 'quantity', event.target.value)} />
      </Field>
      <button className="button button-ghost op-remove" type="button" aria-label={`Remove batch line ${index + 1}`}
        onClick={() => remove(item.key)} disabled={!removable || readOnly}>
        <Trash2 size={16} aria-hidden="true" />
      </button>
      {batch && <span className={`op-stock-hint${exceeds ? ' op-stock-over' : ''}`}>
        {batch.product_name} · {formatQuantity(batch.available_quantity, batch.unit)} available
      </span>}
      {!batch && remote.error && <span className="op-stock-hint op-stock-over">{remote.error}</span>}
    </div>
  )
}

function StockEditor({ state, batchList, title, actionLabel, busy }) {
  const list = useId()
  const used = state.items.map(item => item.batchId).filter(Boolean)
  const duplicate = new Set(used).size !== used.length
  return (
    <fieldset className="op-stock" disabled={busy}>
      <legend>{title}</legend>
      <BatchSuggestions list={list} batches={batchList} />
      <div className="op-item-list">
        {state.items.map((item, index) => (
          <StockItem key={item.key} item={item} index={index} batchList={batchList} actionLabel={actionLabel} idPrefix={list}
            update={state.update} remove={state.remove} readOnly={busy} removable={state.items.length > 1} />
        ))}
      </div>
      {duplicate && <p className="op-stock-over" role="alert">Each batch may appear only once.</p>}
      <button type="button" className="button button-secondary op-add" onClick={state.add}>
        <Plus size={16} aria-hidden="true" /> Add batch
      </button>
    </fieldset>
  )
}

function stockPayload(items, amountField) {
  const ids = items.map(item => item.batchId)
  if (new Set(ids).size !== ids.length) throw new Error('Use each batch only once.')
  return items.map(item => ({ batch_id: item.batchId, [amountField]: item.quantity }))
}

function OperationSelect({ handling = false }) {
  return (
    <Field label="Operation" required>
      <select name="operation_type" defaultValue={handling ? HANDLING[0] : TRANSFORMATIONS[0]} required>
        {(handling ? HANDLING : TRANSFORMATIONS).map(value => <option key={value} value={value}>{titleCase(value)}</option>)}
      </select>
    </Field>
  )
}

function ProcessingForm({ facilities, batches, refreshStock }) {
  const request = useFormRequest()
  const stock = useStockItems()
  const newId = request.data?.batch_id
  const lineage = useRecords(newId ? `/batches/${encodeURIComponent(newId)}/lineage` : null)
  const columns = [
    { key: 'input_batch_id', label: 'Source batch', render: value => <Link className="op-inline-link" to={batchPath(value)}>{value}</Link> },
    { key: 'input_product', label: 'Product' },
    { key: 'quantity_used', label: 'Used', render: (value, row) => formatQuantity(value, row.input_unit) },
  ]
  return (
    <div className="op-workspace">
      <Panel title="Create a processed batch" description="Combine input stock and record the resulting batch.">
        <form className="stack" onSubmit={event => request.submit(event, form => api('/processing', {
          method: 'POST',
          body: {
            ...batchPayload(form),
            facility_id: textValue(form, 'facility_id'),
            operation_type: textValue(form, 'operation_type'),
            inputs: stockPayload(stock.items, 'quantity_used'),
            allow_over_allocation: form.has('allow_over_allocation'),
          },
        }), refreshStock)}>
          <div className="form-grid">
            <MasterSelect field="facility" label="Processing facility" options={facilities} />
            <OperationSelect />
            <BatchFields processed />
          </div>
          {batches.error && <Notice tone="warning">Batch suggestions are unavailable. Enter exact batch IDs to continue.</Notice>}
          <StockEditor state={stock} batchList={batches.data ?? []} title="Input batches" actionLabel="Quantity used" busy={request.busy} />
          <label className="op-check">
            <input type="checkbox" name="allow_over_allocation" />
            <span><strong>Allow quantities above available stock</strong><small>The anomaly rules can flag this discrepancy after saving.</small></span>
          </label>
          <ResultNotice request={request}>{record => <span>Created processed batch <strong>{record.batch_id}</strong>.</span>}</ResultNotice>
          <FormSubmit busy={request.busy} label="Create processed batch" icon={Factory} />
        </form>
      </Panel>
      <Panel title={newId ? 'Recorded output' : 'Batch lineage'} className="op-context">
        {newId ? (
          <div className="stack">
            <div className="op-result-id"><PackageOpen size={20} aria-hidden="true" /><strong>{newId}</strong></div>
            <ReadResult request={lineage}>{report => <DataTable rows={report.edges.filter(edge => edge.output_batch_id === newId)}
              columns={columns} getRowKey={row => row.input_batch_id} />}</ReadResult>
            <Link className="button button-secondary" to={batchPath(newId)}><GitFork size={17} aria-hidden="true" /> View batch trace</Link>
          </div>
        ) : <EmptyState icon={GitFork} title="Input links appear here" description="Save a processed batch to see the quantities linked to its sources." />}
      </Panel>
    </div>
  )
}

function HandlingForm({ facilities, batches }) {
  const request = useFormRequest()
  const list = useId()
  return (
    <Panel title="Record batch handling" description="Log an operation such as sorting, packaging, or cold storage for an existing batch.">
      <form className="stack" onSubmit={event => request.submit(event, form => api(`/batches/${encodeURIComponent(textValue(form, 'batch_id'))}/handling`, {
        method: 'POST',
        body: {
          facility_id: textValue(form, 'facility_id'),
          operation_type: textValue(form, 'operation_type'),
          processing_date: textValue(form, 'processing_date'),
        },
      }))}>
        <BatchSuggestions list={list} batches={batches.data ?? []} />
        <div className="form-grid">
          <Field label="Batch ID" required><BatchLookupInput list={list} /></Field>
          <MasterSelect field="facility" label="Processing facility" options={facilities} />
          <OperationSelect handling />
          <Field label="Handling date" required><input type="date" name="processing_date" defaultValue={dateAfter(0)} required /></Field>
        </div>
        <ResultNotice request={request}>{record => (
          <span>{titleCase(record.operation_type)} recorded for <Link to={batchPath(record.batch_id)}>{record.batch_id}</Link>.</span>
        )}</ResultNotice>
        <FormSubmit busy={request.busy} label="Record handling" icon={Warehouse} />
      </form>
    </Panel>
  )
}

export function Processing() {
  const [params, setParams] = useSearchParams()
  const [stockRevision, setStockRevision] = useState(0)
  const handling = params.get('mode') === 'handling'
  const facilities = useRecords('/facilities', { all: true })
  const batches = useRecords('/batches', { revision: stockRevision })
  return (
    <div className="stack op-page">
      <PageHeader title="Processing" description="Record transformations and handling across the supply chain." />
      <WorkflowTabs options={[
        { id: 'process', label: 'Create processed batch', icon: Factory },
        { id: 'handling', label: 'Record handling', icon: Warehouse },
      ]} active={handling ? 'handling' : 'process'} onChange={id => setParams(id === 'handling' ? { mode: id } : {})} label="Processing workflow" />
      <ReadResult request={facilities}>{rows => rows.length ? (
        handling ? <HandlingForm facilities={rows} batches={batches} />
          : <ProcessingForm facilities={rows} batches={batches} refreshStock={() => setStockRevision(value => value + 1)} />
      ) : <Panel><EmptyState icon={Factory} title="Register a facility first"
        action={<Link className="button button-secondary" to="/register?kind=facility">Register a facility</Link>} /></Panel>}</ReadResult>
    </div>
  )
}

const shipmentItems = [
  { key: 'batch_id', label: 'Batch', render: value => <Link className="op-inline-link" to={batchPath(value)}>{value}</Link> },
  { key: 'product_name', label: 'Product' },
  { key: 'quantity_shipped', label: 'Shipped', render: (value, row) => formatQuantity(value, row.unit) },
]

function ShipmentRecord({ record }) {
  const route = record.totals[0]
  return (
    <Panel title={`Shipment ${record.shipment_id}`}
      actions={route && <StatusBadge value={formatDate(route.shipment_date)} tone="neutral" />}>
      <div className="stack">
        {route && (
          <>
            <div className="op-route">
              <div><span>From</span><strong>{route.source_location}</strong></div>
              <Truck size={18} aria-hidden="true" />
              <div><span>Retail destination</span><strong>{route.retailer_name}</strong>
                <small>{[route.destination_city, route.destination_state].filter(Boolean).join(', ')}</small></div>
            </div>
            <div className="op-totals">
              {record.totals.filter(row => row.unit).map(row => (
                <div key={row.unit}><strong>{formatQuantity(row.total_shipment_quantity, row.unit)}</strong>
                  <span>{row.batch_count} {row.batch_count === 1 ? 'batch' : 'batches'}</span></div>
              ))}
              <div><strong>{RUPEES.format(route.transportation_cost)}</strong><span>Transportation cost</span></div>
            </div>
          </>
        )}
        <DataTable columns={shipmentItems} rows={record.items} getRowKey={row => row.batch_id} empty="No items in this shipment." />
      </div>
    </Panel>
  )
}

function CreateShipment() {
  const retailers = useRecords('/retailers', { all: true })
  const [stockRevision, setStockRevision] = useState(0)
  const batches = useRecords('/batches', { revision: stockRevision })
  const request = useFormRequest()
  const stock = useStockItems()
  return (
    <div className="op-workspace">
      <Panel title="Create a shipment" description="Choose the retailer and quantities being dispatched.">
        <ReadResult request={retailers}>{rows => rows.length ? (
          <form className="stack" onSubmit={event => request.submit(event, form => api('/shipments', {
            method: 'POST',
            body: {
              shipment_date: textValue(form, 'shipment_date'),
              source_location: textValue(form, 'source_location'),
              retailer_id: textValue(form, 'retailer_id'),
              transportation_cost: textValue(form, 'transportation_cost'),
              items: stockPayload(stock.items, 'quantity_shipped'),
            },
          }), () => setStockRevision(value => value + 1))}>
            <div className="form-grid">
              <Field label="Source location" required><input name="source_location" maxLength="150" required /></Field>
              <MasterSelect field="retailer" label="Destination retailer" options={rows} />
              <Field label="Shipment date" required><input type="date" name="shipment_date" defaultValue={dateAfter(0)} required /></Field>
              <Field label="Transportation cost (₹)" required>
                <input type="number" name="transportation_cost" defaultValue="0" min="0" max="9999999999.99" step=".01" required />
              </Field>
            </div>
            {batches.error && <Notice tone="warning">Batch suggestions are unavailable. Enter exact batch IDs to continue.</Notice>}
            <StockEditor state={stock} batchList={batches.data ?? []} title="Shipment items" actionLabel="Quantity shipped" busy={request.busy} />
            <ResultNotice request={request}>{record => <span>Created shipment <strong>{record.shipment_id}</strong>.</span>}</ResultNotice>
            <FormSubmit busy={request.busy} label="Create shipment" icon={Truck} />
          </form>
        ) : <EmptyState icon={ShoppingBasket} title="Register a destination retailer first"
          action={<Link className="button button-secondary" to="/register?kind=retailer">Register a retailer</Link>} />}</ReadResult>
      </Panel>
      {request.data ? <ShipmentRecord record={request.data} /> : (
        <Panel title="Dispatch summary" className="op-context">
          <EmptyState icon={Truck} title="No shipment recorded yet" description="The retailer, shipment totals, and item details appear after saving." />
        </Panel>
      )}
    </div>
  )
}

function FindShipment({ existing, onLookup }) {
  const [value, setValue] = useState(existing || '')
  const [revision, setRevision] = useState(0)
  const record = useRecords(existing ? `/shipments/${encodeURIComponent(existing)}` : null, { revision })
  function find(event) {
    event.preventDefault()
    if (existing === value) setRevision(counter => counter + 1)
    else onLookup(value)
  }
  return (
    <div className="stack">
      <Panel title="Look up a shipment">
        <form className="op-search-form" onSubmit={find}>
          <Field label="Shipment ID" required>
            <input value={value} placeholder="e.g. S501" maxLength="12" pattern="S[0-9]+" autoCapitalize="characters" required
              onChange={event => setValue(event.target.value.trim().toUpperCase())} />
          </Field>
          <FormSubmit busy={record.loading} label="Look up shipment" icon={Search} />
        </form>
      </Panel>
      <ReadResult request={record}>{data => <ShipmentRecord record={data} />}</ReadResult>
    </div>
  )
}

function BatchShipmentHistory() {
  const batches = useRecords('/batches')
  const request = useFormRequest()
  const list = useId()
  const rows = [
    { key: 'shipment_id', label: 'Shipment', render: value => <Link className="op-inline-link" to={shipmentPath(value)}>{value}</Link> },
    { key: 'shipment_date', label: 'Date', render: value => formatDate(value) },
    { key: 'quantity_shipped', label: 'Quantity', render: (value, row) => formatQuantity(value, row.unit) },
    { key: 'retailer_name', label: 'Retailer' },
    { key: 'retailer_city', label: 'City' },
  ]
  return (
    <div className="stack">
      <Panel title="Batch movement history" description="Find where a batch was shipped and trace it to its source farms.">
        <form className="op-search-form" onSubmit={event => request.submit(event, form => api(`/reports/batch/${encodeURIComponent(textValue(form, 'batch_id'))}`))}>
          <BatchSuggestions list={list} batches={batches.data ?? []} />
          <Field label="Batch ID" required><BatchLookupInput list={list} /></Field>
          <FormSubmit busy={request.busy} label="Find batch movements" icon={Search} />
        </form>
      </Panel>
      <ResultNotice request={request} />
      {request.data && (
        <div className="op-workspace">
          <Panel title={`Shipments for ${request.data.batch.batch_id}`}>
            <DataTable rows={request.data.shipments} columns={rows} getRowKey={row => row.shipment_id} empty="No shipments recorded for this batch." />
          </Panel>
          <Panel title="Origin farms" className="op-context">
            <div className="op-source-list">
              {request.data.origin_farms.map(row => (
                <div className="op-source" key={row.original_batch_id}>
                  <span className="op-chip-icon"><MapPin size={16} aria-hidden="true" /></span>
                  <div><strong>{row.farm_name}</strong><span>{row.city} · {row.product_name}</span></div>
                  <Link className="op-inline-link" to={batchPath(row.original_batch_id)}>{row.original_batch_id}</Link>
                </div>
              ))}
              {!request.data.origin_farms.length && <p className="muted">No source farms recorded for this batch.</p>}
            </div>
          </Panel>
        </div>
      )}
    </div>
  )
}

export function Shipments() {
  const [params, setParams] = useSearchParams()
  const existing = (params.get('shipment') || '').toUpperCase()
  const selectedMode = params.get('mode')
  const mode = existing ? 'lookup' : ['lookup', 'history'].includes(selectedMode) ? selectedMode : 'create'
  return (
    <div className="stack op-page">
      <PageHeader title="Shipments" description="Dispatch batches, look up deliveries, and trace retail destinations." />
      <WorkflowTabs options={[
        { id: 'create', label: 'Create shipment', icon: Truck },
        { id: 'lookup', label: 'Look up shipment', icon: Search },
        { id: 'history', label: 'Batch shipment history', icon: GitFork },
      ]} active={mode} onChange={id => {
        if (mode !== id) setParams(id === 'create' ? {} : { mode: id })
      }} label="Shipment workflow" />
      {mode === 'lookup' ? <FindShipment key={existing} existing={existing} onLookup={shipment => setParams({ shipment })} />
        : mode === 'history' ? <BatchShipmentHistory /> : <CreateShipment />}
    </div>
  )
}
