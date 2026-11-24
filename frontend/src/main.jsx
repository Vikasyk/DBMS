import { lazy, StrictMode, Suspense, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter, Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  Boxes, ChartNoAxesCombined, ChevronRight, CircleAlert, FlaskConical, LayoutDashboard,
  Menu, PlusSquare, ScanLine, Search, ShieldCheck, Sparkles, Sprout, Truck, Workflow, X,
} from 'lucide-react'
import '@fontsource-variable/dm-sans'
import '@fontsource-variable/manrope'
import './styles.css'
import { api, appRecordId } from './api'
import Dashboard from './pages/Dashboard'

const Register = lazy(() => import('./pages/Operations').then(({ Register }) => ({ default: Register })))
const Processing = lazy(() => import('./pages/Operations').then(({ Processing }) => ({ default: Processing })))
const Shipments = lazy(() => import('./pages/Operations').then(({ Shipments }) => ({ default: Shipments })))
const BatchTrace = lazy(() => import('./pages/Trace').then(({ BatchTrace }) => ({ default: BatchTrace })))
const Quality = lazy(() => import('./pages/Trace').then(({ Quality }) => ({ default: Quality })))
const Simulation = lazy(() => import('./pages/Trace').then(({ Simulation }) => ({ default: Simulation })))
const Prices = lazy(() => import('./pages/Insights').then(({ Prices }) => ({ default: Prices })))
const Anomalies = lazy(() => import('./pages/Insights').then(({ Anomalies }) => ({ default: Anomalies })))
const Ask = lazy(() => import('./pages/Insights').then(({ Ask }) => ({ default: Ask })))

const groups = [
  { links: [{ path: '/', title: 'Overview', icon: LayoutDashboard, component: Dashboard }] },
  { title: 'Traceability', links: [
    { path: '/batches', title: 'Batch trace', icon: Boxes, component: BatchTrace },
    { path: '/register', title: 'Register', icon: PlusSquare, component: Register },
    { path: '/processing', title: 'Processing', icon: Workflow, component: Processing },
    { path: '/shipments', title: 'Shipments', icon: Truck, component: Shipments },
  ] },
  { title: 'Quality', links: [
    { path: '/quality', title: 'Quality checks', icon: ShieldCheck, component: Quality },
    { path: '/simulation', title: 'What-if simulation', icon: FlaskConical, component: Simulation },
  ] },
  { title: 'Intelligence', links: [
    { path: '/prices', title: 'Prices and forecasts', icon: ChartNoAxesCombined, component: Prices },
    { path: '/anomalies', title: 'Anomalies', icon: CircleAlert, component: Anomalies },
    { path: '/ask', title: 'Ask TraceFood', icon: Sparkles, component: Ask },
  ] },
]
const pages = groups.flatMap((group) => group.links)

function recordRoute(value) {
  const id = appRecordId(value)
  if (/^B\d{1,11}$/.test(id)) return `/batches?batch=${id}`
  if (/^S\d{1,11}$/.test(id)) return `/shipments?shipment=${id}`
  if (/^QC\d{1,10}$/.test(id)) return `/quality?check=${id}`
  if (/^A\d{1,11}$/.test(id)) return `/anomalies?alert=${id}`
  return null
}

function SearchDialog({ open, onClose }) {
  const dialog = useRef(null)
  const search = useRef(null)
  const navigate = useNavigate()
  const [value, setValue] = useState('')
  const [invalid, setInvalid] = useState(false)

  useEffect(() => {
    if (open && !dialog.current.open) {
      dialog.current.showModal()
      search.current.focus()
    } else if (!open && dialog.current.open) {
      dialog.current.close()
    }
  }, [open])

  function go(input) {
    const route = recordRoute(input)
    if (!route) {
      setInvalid(true)
      return
    }
    navigate(route)
    dialog.current.close()
  }

  return (
    <dialog ref={dialog} className="record-dialog" aria-labelledby="record-search-heading"
      onClick={(event) => { if (event.target === event.currentTarget) dialog.current.close() }}
      onClose={() => { setValue(''); setInvalid(false); onClose() }}>
      <div className="dialog-body">
        <div className="panel-header">
          <div><h2 id="record-search-heading">Find a record</h2><p>Open a batch, shipment, failed check or alert by ID.</p></div>
          <button type="button" className="icon-button" onClick={() => dialog.current.close()} aria-label="Close search"><X size={20} /></button>
        </div>
        <form className="search-form" onSubmit={(event) => { event.preventDefault(); go(value) }}>
          <input aria-label="Record ID" ref={search} value={value} autoComplete="off" placeholder="Enter a record ID"
            onChange={(event) => { setValue(event.target.value); setInvalid(false) }} aria-invalid={invalid} />
          <button className="button button-primary" type="submit"><Search size={17} /> Open record</button>
        </form>
        {invalid && <p className="field-error" role="alert">Enter a batch, shipment, check or alert ID such as B101, S501, QC4 or A1.</p>}
        <div className="search-examples" aria-label="Fixture shortcuts">
          {['B101', 'S501', 'QC4'].map((id) => <button className="button button-secondary" key={id} onClick={() => go(id)}>{id}</button>)}
        </div>
      </div>
    </dialog>
  )
}

function ConnectionIndicator() {
  const [health, setHealth] = useState('checking')
  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        await api('/health', { signal: AbortSignal.timeout(8000) })
        if (!cancelled) setHealth('online')
      } catch {
        if (!cancelled) setHealth('offline')
      }
    }
    check()
    const timer = window.setInterval(check, 30000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [])
  return (
    <span className={`connection connection-${health}`} role="status">
      <span className="connection-dot" aria-hidden="true" />
      {health === 'online' ? 'Database connected' : health === 'offline' ? 'API unavailable' : 'Checking connection'}
    </span>
  )
}

function App() {
  const { pathname } = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const active = pages.find((page) => page.path === pathname) || pages[0]

  useEffect(() => {
    window.scrollTo(0, 0)
    document.title = `${active.title} · TraceFood`
  }, [pathname, active.title])

  useEffect(() => {
    function shortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
      } else if (event.key === 'Escape') {
        setMobileOpen(false)
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])

  return (
    <div className="app-shell">
      <a href="#workspace-content" className="skip-link" onClick={(event) => {
        event.preventDefault()
        document.getElementById('workspace-content').focus()
      }}>Skip to content</a>
      {mobileOpen && <button type="button" className="menu-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar${mobileOpen ? ' sidebar-open' : ''}`} id="tracefood-navigation">
        <Link to="/" className="brand" onClick={() => setMobileOpen(false)}>
          <span className="brand-mark"><Sprout size={24} strokeWidth={2.1} /></span>
          <span><strong>TraceFood</strong><small>Supply chain operations</small></span>
        </Link>
        <nav aria-label="Main navigation" className="navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group.title || 'Overview'}>
              {group.title && <span className="nav-group-label">{group.title}</span>}
              {group.links.map(({ path, title, icon: Icon }) => (
                <NavLink key={path} end={path === '/'} to={path} onClick={() => setMobileOpen(false)}
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
                  <Icon size={18} strokeWidth={1.8} aria-hidden="true" /><span>{title}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="workspace-icon"><ScanLine size={19} /></span>
          <div><strong>TraceFood Lab</strong><small>Operations workspace</small></div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="cluster topbar-leading">
            <button type="button" className="icon-button mobile-menu-button" aria-label="Toggle navigation"
              aria-expanded={mobileOpen} aria-controls="tracefood-navigation" onClick={() => setMobileOpen(!mobileOpen)}>
              <Menu size={21} />
            </button>
            <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>{active.title}</strong></div>
          </div>
          <div className="cluster topbar-actions">
            <button type="button" className="global-search" aria-label="Search records" onClick={() => setSearchOpen(true)}>
              <Search size={17} /><span>Find a record</span><kbd>Ctrl K</kbd>
            </button>
            <ConnectionIndicator />
          </div>
        </header>
        <main className="workspace-content" id="workspace-content" tabIndex={-1}>
          <Suspense fallback={<div className="page-loading" role="status">Loading workspace…</div>}>
            <Routes>
              {pages.map(({ path, component: Component }) => <Route key={path} path={path} element={<Component />} />)}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode><HashRouter><App /></HashRouter></StrictMode>,
)
