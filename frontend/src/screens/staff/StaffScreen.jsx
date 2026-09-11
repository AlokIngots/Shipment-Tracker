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
  { key: 'activity', label: 'Activity' },
]

// The Alok Ingots side. A staff account has no orders of its own, so this is
// what it sees instead of the customer portal: two tabs over the same data,
// one for building an order and one for papering it.
export default function StaffScreen({ session, onSignOut, onChangePassword }) {
  const [tab, setTab] = useState('orders')

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

      <div className="tabs" role="tablist">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? 'tab tab--on' : 'tab'}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Remounted rather than hidden when the tab changes, so each page
          reloads its data and neither can show what the other has just
          changed underneath it. */}
      {tab === 'orders' && <StaffOrdersScreen />}
      {tab === 'documents' && <StaffDocumentsScreen />}
      {tab === 'accounts' && <StaffAccountsScreen />}
      {tab === 'activity' && <StaffActivityScreen />}
    </>
  )
}
