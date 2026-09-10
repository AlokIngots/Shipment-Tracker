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

// A text box with suggestions attached, rather than a dropdown: the CSV
// importer accepts any status, so the form must too. The list only saves
// typing.
export function SuggestField({ label, id, value, options, onChange, hint }) {
  return (
    <Field label={label} hint={hint}>
      <input list={id} value={value} onChange={(e) => onChange(e.target.value)} />
      <datalist id={id}>
        {options.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
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
