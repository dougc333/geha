export interface Health {
  ready: boolean
  model: string
  source_documents: number
  estimated_context_calls: number
  estimated_context_calls_by_document: Record<string, number>
  documents: string[]
  recommended_document: string
  document_readiness: Record<string, {
    batch_markdown_available: boolean
    batch_markdown?: string
    react_converted_source: boolean
  }>
  canonical_chunker: string
}

export interface RunEvent {
  type: string
  seq: number
  at: string
  source?: string
  run?: string
  index?: number
  total?: number
  chunks?: number
  chunk_id?: string
  status?: string
  error?: string
  pages?: number
  tables?: number
  [key: string]: unknown
}

export interface DocumentProgress {
  source: string
  run?: string
  canonical: 'queued' | 'running' | 'complete' | 'failed'
  contextual: 'queued' | 'running' | 'complete' | 'failed'
  chunksDone: number
  chunksTotal: number
  pages?: number
  tables?: number
  error?: string
  markdownVerified?: boolean
  markdownChars?: number
}

export interface ChunkPair {
  chunk_id: string
  pages: number[]
  section: string
  text: string
  deterministic_contextualized_text: string
  retrieval_context?: string
  contextual_retrieval_text?: string
  model?: string
  prompt_cache?: CacheUsage
}

export interface ChunkResponse {
  run: string
  completed: number
  total: number
  chunks: ChunkPair[]
}

export interface CacheUsage {
  input_tokens: number
  output_tokens: number
  cache_creation_input_tokens: number
  cache_read_input_tokens: number
}

export interface PromptContract {
  prompt_version: string
  system_prompt: string
  document_block: string
  document_cache_control: { type: string }
  user_template: string
  cache_scope: string
}

export interface CacheTestResult {
  available?: boolean
  passed: boolean
  model: string
  document: string
  document_chars: number
  prompt_version: string
  cache_control: { type: string }
  first: CacheUsage
  second: CacheUsage
  explanation: string
  tested_at?: string
}
