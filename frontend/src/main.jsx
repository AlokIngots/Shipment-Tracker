import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// The two typefaces, served from this site rather than from Google, so the
// Content-Security-Policy stays 'self'. Upright weights only.
import '@fontsource-variable/archivo/wght.css'
import '@fontsource-variable/public-sans/wght.css'
import './index.css'
// Three contiguous slices of what used to be one App.css, imported in
// the order they were cut, so the cascade is exactly as it was.
import './styles/shell.css'
import './styles/screens.css'
import './styles/staff.css'
// The brand look for every screen; see the note at the top of the file.
import './styles/customer.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
