import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { InventoryProvider } from './store'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(<StrictMode><InventoryProvider><App /></InventoryProvider></StrictMode>)
