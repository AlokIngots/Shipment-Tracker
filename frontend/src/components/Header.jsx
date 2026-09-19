import logo from '../assets/alok-logo.png'

// Two headers. Customers, and anybody not yet signed in, get the company
// logo on white: it is what an export buyer recognises from the paperwork,
// and its grey lettering disappears on navy. Staff keep the navy bar they
// have always had, so the Admin Console looks exactly as before.
export default function Header({ customer = true }) {
  if (customer) {
    return (
      <header className="cheader">
        <div className="cheader-inner">
          <img className="cheader-logo" src={logo} alt="Alok Ingots" width="107" height="44" />
          <span className="cheader-divider" aria-hidden="true" />
          <span className="cheader-title">Customer Portal</span>
        </div>
      </header>
    )
  }

  return (
    <header className="header">
      <div className="brand">
        <span className="mark">AI</span>
        <div>
          <h1>Alok Ingots</h1>
          <p>Customer Portal</p>
        </div>
      </div>
    </header>
  )
}
