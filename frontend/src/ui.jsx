import { AlertCircle, AlertTriangle, CheckCircle2, Inbox, Info } from 'lucide-react'
import { titleCase } from './api'

export function PageHeader({ title, description, actions, eyebrow, children }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
        {children}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function Panel({ title, description, actions, children, className = '', id }) {
  return (
    <section id={id} className={`panel ${className}`}>
      {(title || description || actions) && (
        <div className="panel-header">
          <div>
            {title && <h2>{title}</h2>}
            {description && <p>{description}</p>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

const noticeIcons = { info: Info, success: CheckCircle2, warning: AlertTriangle, danger: AlertCircle }

export function Notice({ tone = 'info', title, children, className = '' }) {
  const Icon = noticeIcons[tone] || Info
  return (
    <div className={`notice notice-${tone} ${className}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon size={18} aria-hidden="true" />
      <div>{title && <strong>{title}</strong>}{children && <div>{children}</div>}</div>
    </div>
  )
}

export function EmptyState({ title = 'No records to show', description, action, icon: Icon = Inbox }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon size={21} aria-hidden="true" /></span>
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}

const badgeColors = {
  ACTIVE: 'green', PASS: 'green', CONFIRMED: 'red', FAIL: 'red', RECALLED: 'red', OPEN: 'amber',
  ON_HOLD: 'amber', POTENTIALLY_AFFECTED: 'amber', POSSIBLE_SOURCE: 'blue', PROCESSED: 'blue',
  ORIGINAL: 'green', REVIEWED: 'green', DISMISSED: 'neutral', CLOSED: 'neutral', INCONCLUSIVE: 'neutral',
}
const badgeToneAliases = { success: 'green', danger: 'red', warning: 'amber', info: 'blue' }

export function StatusBadge({ value, tone, children }) {
  return (
    <span className={`status-badge status-${badgeToneAliases[tone] || tone || badgeColors[value] || 'neutral'}`}>
      {children ?? (value ? titleCase(value) : '—')}
    </span>
  )
}

export function DataTable({ columns, rows = [], empty, getRowKey, onRowClick, caption }) {
  if (!rows.length) return typeof empty === 'string' ? <EmptyState title={empty} /> : (empty || <EmptyState />)
  return (
    <div className="table-scroll">
      <table className="data-table" aria-label={caption}>
        <thead>
          <tr>{columns.map(({ key, label, align }) => <th scope="col" key={key} style={{ textAlign: align }}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={getRowKey ? getRowKey(row, index) : index}
              className={onRowClick ? 'clickable-row' : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (event) => {
                if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                  event.preventDefault()
                  onRowClick(row)
                }
              } : undefined}
            >
              {columns.map(({ key, render, align }) => (
                <td key={key} style={{ textAlign: align }}>{render ? render(row[key], row) : (row[key] ?? '—')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Field({ label, children, hint, required, className = '' }) {
  return (
    <label className={`field ${className}`}>
      <span>{label}{required && <span className="required-mark" aria-hidden="true"> *</span>}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}
