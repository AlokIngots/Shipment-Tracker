import logo from '../assets/alok-logo.png'

// One header for every screen, staff included: the company logo on white,
// which is what an export buyer recognises from the paperwork. Its grey
// lettering would disappear on navy, which is why the bar is white.
export default function Header() {
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
