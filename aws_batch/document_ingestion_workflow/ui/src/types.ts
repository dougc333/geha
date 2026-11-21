export type RunStatus = 'checking' | 'idle' | 'starting' | 'running' | 'complete' | 'error'
export type ViewMode = 'before' | 'after'
export type RunView = string
export type VisionProvider = 'anthropic' | 'nous'
export type BillOfLadingLayout = 'gpt4o_only_8block_ocr.py' | 'refined_layout.py' | 'alt_2/layout.json'

export interface AgentEvent {
  type: string
  seq: number
  at: string
  [key: string]: unknown
}

export interface ComparisonArtifact {
  page: number
  mode?: 'native' | 'vision'
  tool_id?: string
  source_pdf: string
  source_png?: string
  html: string
  html_png?: string
  iterations?: number
  markdown_chars?: number
}

export interface PageComparison {
  before?: ComparisonArtifact
  after?: ComparisonArtifact
}

export interface SavedRun {
  run_id: string
  pages: Record<number, PageComparison>
}

export interface DemoDocument {
  document: string
  title: string
  filename: string
  page_count: number
  image_only_pages: number[]
  visual_reconstruction_pages?: number[]
}

export interface DemoState {
  serverInstanceId?: string
  buildRevision?: string
  ready: boolean
  anthropicReady: boolean
  openaiReady: boolean
  nousReady: boolean
  provider: VisionProvider
  layout: BillOfLadingLayout
  model: string
  documents: DemoDocument[]
  selectedDocument: string
  status: RunStatus
  runId?: string
  events: AgentEvent[]
  pageComparisons: Record<number, PageComparison>
  savedRuns: SavedRun[]
  runView: RunView
  selectedComparisonPage?: number
  before?: ComparisonArtifact
  after?: ComparisonArtifact
  activeView: ViewMode
  countdown: number
  error?: string
}
