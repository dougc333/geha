import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { inventory } from './data'
import { InventorySchema } from './types'
import type { InventoryItem, Status } from './types'

type Filter = 'all' | 'attention' | 'promoted'
type Store = { items: InventoryItem[]; query: string; setQuery: (v: string) => void; filter: Filter; setFilter: (v: Filter) => void; selected: string | null; setSelected: (v: string | null) => void; filtered: InventoryItem[]; refreshing: boolean; snapshotAt?: string; startCrawl: () => Promise<void>; downloadItem: (item: InventoryItem) => Promise<void> }
const InventoryContext = createContext<Store | null>(null)

export function InventoryProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<InventoryItem[]>(inventory)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [selected, setSelected] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [snapshotAt, setSnapshotAt] = useState<string>()
  const refreshInventory = async () => {
    setRefreshing(true)
    try {
      const response = await fetch('http://127.0.0.1:8520/api/collection-inventory')
      if (!response.ok) throw new Error(await response.text())
      const payload = await response.json() as { assets: unknown[]; createdAt: string }
      setItems(InventorySchema.parse(payload.assets))
      setSnapshotAt(payload.createdAt)
    } finally {
      setRefreshing(false)
    }
  }
  useEffect(() => { void refreshInventory() }, [])
  const filtered = useMemo(() => items.filter((item) => {
    const haystack = `${item.title} ${item.collection} ${item.family} ${item.year}`.toLowerCase()
    const matchesQuery = haystack.includes(query.toLowerCase())
    const matchesFilter = filter === 'all' || (filter === 'promoted' ? item.promoted : !item.promoted && ['missing_from_manifest', 'hash_mismatch', 'needs_visual_review', 'failed'].includes(item.status))
    return matchesQuery && matchesFilter
  }), [items, query, filter])
  const startCrawl = refreshInventory
  const downloadItem = async (item: InventoryItem) => {
    const response = await fetch('http://127.0.0.1:8520/api/download-discovered', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: item.url }) })
    if (!response.ok) throw new Error(await response.text())
    await refreshInventory()
  }
  return <InventoryContext.Provider value={{ items, query, setQuery, filter, setFilter, selected, setSelected, filtered, refreshing, snapshotAt, startCrawl, downloadItem }}>{children}</InventoryContext.Provider>
}

export function useInventory() {
  const value = useContext(InventoryContext)
  if (!value) throw new Error('useInventory must be used inside InventoryProvider')
  return value
}

export const statusLabel: Record<Status, string> = {
  discovered: 'Discovered', missing_from_manifest: 'Missing manifest', manifested: 'Manifested', downloaded: 'Downloaded', hash_mismatch: 'Hash mismatch', processing: 'Processing', extracted: 'Extracted', needs_visual_review: 'Visual review', failed: 'Failed', promoted: 'Promoted', archived: 'Archived',
}
