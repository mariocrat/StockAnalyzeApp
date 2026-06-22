import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { getStoredAuthSessionToken, installGlobalClientEventReporting } from './utils/clientEventLog.js'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8002'

installGlobalClientEventReporting({
  apiBase: API_BASE,
  getSessionToken: getStoredAuthSessionToken,
})

createRoot(document.getElementById('root')).render(
  <App />
)
