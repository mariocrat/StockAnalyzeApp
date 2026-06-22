import { createRoot } from 'react-dom/client'
import axios from 'axios'
import './index.css'
import App from './App.jsx'
import { installAxiosRequestIdMessages } from './utils/apiErrorRequestId.js'
import { getStoredAuthSessionToken, installGlobalClientEventReporting } from './utils/clientEventLog.js'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8002'

installAxiosRequestIdMessages(axios)
installGlobalClientEventReporting({
  apiBase: API_BASE,
  getSessionToken: getStoredAuthSessionToken,
})

createRoot(document.getElementById('root')).render(
  <App />
)
