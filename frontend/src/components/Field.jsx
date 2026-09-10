// One labelled box on a form. The staff forms have eight each, and writing
// the label/input pair out eight times is how they stop looking alike.

export function Field({ label, hint, wide, children }) {
  return (
    <label className={wide ? 'field field--wide' : 'field'}>
      <span>{label}</span>
      {children}
      {hint && <small className="field-hint">{hint}</small>}
    </label>
  )
}

// A dropdown of exactly what the server will accept. This used to be a text
// box with suggestions, because the CSV importer took any status and the
// form had to match it. Both now share one list, so both can be closed.
export function ChoiceField({ label, value, options, onChange, hint, blankLabel }) {
  return (
    <Field label={label} hint={hint}>
      <select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">{blankLabel ?? 'Not set'}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </Field>
  )
}

export function TextField({ label, value, onChange, hint, wide, ...rest }) {
  return (
    <Field label={label} hint={hint} wide={wide}>
      <input value={value ?? ''} onChange={(e) => onChange(e.target.value)} {...rest} />
    </Field>
  )
}
