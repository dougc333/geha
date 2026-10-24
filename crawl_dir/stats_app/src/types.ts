export type Run = {
  id: string
  family: string
  document_id: string
  run_id: string
  created_at: string
  has_stats: boolean
}

export const FLAGS = ['toc', 'form', 'tiny', 'boilerplate', 'table'] as const
export type Flag = (typeof FLAGS)[number]

export type ChunkRow = Record<Flag, boolean> & {
  chunk_id: string
  pages: number[]
  section: string
  content_type: string
  words: number
  boilerplate_share: number
  preview: string
}

export type Summary = Record<Flag, number> & {
  document_id: string
  family: string
  run_id: string
  pages: number
  chunks: number
  median_words: number
  p90_words: number
}

export type RunStats = {
  schema_version: number
  run: string
  computed_at: string
  heuristics: Record<string, number>
  summary: Summary
  chunks: ChunkRow[]
}
