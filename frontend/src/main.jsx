import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
// Three contiguous slices of what used to be one App.css, imported in
// the order they were cut, so the cascade is exactly as it was.
import './styles/shell.css'
import './styles/screens.css'
import './styles/staff.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
