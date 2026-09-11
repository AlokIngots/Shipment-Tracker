// The bar at the top of every signed-in screen: what you are looking at on
// the left, what you can do about it on the right. Four screens drew this
// themselves before; one description of it means they cannot drift apart.
export default function Toolbar({ title, subtitle, onBack, backLabel, children }) {
  return (
    <div className="toolbar">
      <div>
        {onBack && (
          <button type="button" className="backlink" onClick={onBack}>
            &#8249; {backLabel ?? 'Back'}
          </button>
        )}
        <h2 className="toolbar-title">{title}</h2>
        {subtitle && <p className="toolbar-sub">{subtitle}</p>}
      </div>
      <div className="toolbar-actions">{children}</div>
    </div>
  )
}
