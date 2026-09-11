import { useState } from 'react'
import Toolbar from '../../components/Toolbar'
import StaffAccountsScreen from './StaffAccountsScreen'
import StaffActivityScreen from './StaffActivityScreen'
import StaffDocumentsScreen from './StaffDocumentsScreen'
import StaffOrdersScreen from './StaffOrdersScreen'

const TABS = [
  { key: 'orders', label: 'Orders & shipments' },
  { key: 'documents', label: 'Documents & photos' },
  { key: 'accounts', label: 'Customers & logins' },
  { key: 'activity', label: 'Change history' },
]

// The four things staff do most, one press away from any tab. Each opens the
// tab it belongs to with the right form already open, so nobody has to
// remember which tab hides "add a login".
const QUICK = [
  { label: 'Add customer', tab: 'accounts', intent: { action: 'new-customer' } },
  { label: 'Add customer login', tab: 'accounts', intent: { action: 'new-login' } },
  { label: 'New order', tab: 'orders', intent: { action: 'new-order' } },
  { label: 'Upload document', tab: 'documents', intent: { action: 'upload' } },
]

// The Alok Ingots side. A staff account has no orders of its own, so this is
// what it sees instead of the customer portal. Every write it offers lives
// under /api/staff on the server, behind the staff check -- a customer who
// found these screens could not use them.
export default function StaffScreen({ session, onSignOut, onChangePassword }) {
  // `visit` goes up on every move and each screen is keyed on it, so pressing
  // New order while already on the orders tab reopens it with the form open
  // rather than doing nothing.
  const [view, setView] = useState({ tab: 'orders', intent: null, visit: 0 })

  function go(tab, intent = null) {
    setView((v) => ({ tab, intent, visit: v.visit + 1 }))
    window.scrollTo(0, 0)
  }

  return (
    <>
      <Toolbar
        title="Alok Ingots"
        subtitle={`Staff · signed in as ${session.email}`}
      >
        <button type="button" className="button button--ghost" onClick={onChangePassword}>
          Change password
        </button>
        <button type="button" className="button button--ghost" onClick={onSignOut}>
          Sign out
        </button>
      </Toolbar>

      <div className="quickbar" role="group" aria-label="Quick actions">
        {QUICK.map(({ label, tab, intent }) => (
          <button key={label} type="button" className="quick" onClick={() => go(tab, intent)}>
            {label}
          </button>
        ))}
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={view.tab === key}
            className={view.tab === key ? 'tab tab--on' : 'tab'}
            onClick={() => go(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Remounted rather than hidden when the tab changes, so each page
          reloads its data and none can show what another has just changed
          underneath it. */}
      {view.tab === 'orders' && (
        <StaffOrdersScreen key={view.visit} startWith={view.intent} onGo={go} />
      )}
      {view.tab === 'documents' && (
        <StaffDocumentsScreen key={view.visit} startWith={view.intent} onGo={go} />
      )}
      {view.tab === 'accounts' && (
        <StaffAccountsScreen key={view.visit} startWith={view.intent} onGo={go} />
      )}
      {view.tab === 'activity' && <StaffActivityScreen key={view.visit} />}
    </>
  )
}
