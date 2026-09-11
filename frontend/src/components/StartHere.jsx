import { useEffect, useState } from 'react'
import axios from 'axios'

const TICK = '✓'

// The first-day checklist, shown on a staff screen that is still empty.
//
// Getting a customer to see an order takes three things in a fixed order --
// a customer, a login for somebody there, an order -- and an empty screen
// said none of that. Each step says what it is in a sentence, ticks itself
// once it has been done, and carries the button that does it.
const STEPS = [
  {
    title: 'Add the customer',
    text: 'The company you sell to, with the short code your SAP/PMS export uses for it.',
    count: 'customers',
    action: 'Add customer',
    tab: 'accounts',
    intent: { action: 'new-customer' },
  },
  {
    title: 'Give someone there a login',
    text:
      'Type the email address of the person who follows the orders. The portal ' +
      'gives you a temporary password to send them.',
    count: 'logins',
    action: 'Add customer login',
    tab: 'accounts',
    intent: { action: 'new-login' },
  },
  {
    title: 'Add their order',
    text:
      'Enter the sales order, then add each shipment as it is dispatched. ' +
      'Documents and photos are uploaded against the shipment.',
    count: 'orders',
    action: 'New order',
    tab: 'orders',
    intent: { action: 'new-order' },
  },
]

export default function StartHere({ onGo }) {
  // Null until known. The steps are drawn at once, unticked, rather than the
  // card appearing only after two requests have come back.
  const [counts, setCounts] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([axios.get('/api/staff/accounts'), axios.get('/api/staff/orders')])
      .then(([accounts, orders]) => {
        if (cancelled) return
        const customers = accounts.data.customers
        setCounts({
          customers: customers.length,
          logins: customers.reduce((total, c) => total + c.logins.length, 0),
          orders: orders.data.length,
        })
      })
      .catch(() => {
        // Without the counts the steps still read correctly, just unticked.
      })
    return () => {
      cancelled = true
    }
  }, [])

  const isDone = (step) => counts?.[step.count] > 0
  const next = STEPS.findIndex((step) => !isDone(step))

  return (
    <div className="card starthere">
      <h3 className="starthere-title">Start here</h3>
      <p className="starthere-lead">
        Three steps, in this order, and a customer can see their order.
      </p>
      <ol className="startsteps">
        {STEPS.map((step, index) => {
          const done = isDone(step)
          return (
            <li key={step.title} className={done ? 'startstep startstep--done' : 'startstep'}>
              <span className="startstep-num" aria-hidden="true">
                {done ? TICK : index + 1}
              </span>
              <div className="startstep-body">
                <span className="startstep-title">
                  {step.title}
                  {done && <em className="startstep-flag"> · done</em>}
                </span>
                <span className="startstep-text">{step.text}</span>
              </div>
              {!done && (
                <button
                  type="button"
                  className={index === next ? 'minibutton minibutton--primary' : 'minibutton'}
                  onClick={() => onGo(step.tab, step.intent)}
                >
                  {step.action}
                </button>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
