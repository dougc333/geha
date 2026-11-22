export type RunStatus = 'checking' | 'idle' | 'starting' | 'running' | 'complete' | 'error'
export type ViewMode = 'before' | 'after'
export type RunView = 'current' | 'previous'

export interface AgentEvent {
  type: string
  seq: number
  at: string
  [key: string]: unknown
}

export interface PdfImageStructure {
  xref?: number
  format: string
  width_px?: number
  height_px?: number
  bbox_points: number[]
  coverage_percent: number
  full_page: boolean
}

export interface PdfPageStructure {
  classification: 'image_only' | 'text_layer_over_page_image' | 'text_with_embedded_images' | 'text_only'
  page_width_points: number
  page_height_points: number
  extractable_text_chars: number
  font_count: number
  image_count: number
  full_page_image_count: number
  images: PdfImageStructure[]
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
  verification_status?: 'passed' | 'failed'
  correction_changed?: boolean
  page_structure?: PdfPageStructure
  page_structure_source?: 'saved_json' | 'saved_source_pdf'
}

export interface PageComparison {
  before?: ComparisonArtifact
  after?: ComparisonArtifact
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
  ready: boolean
  model: string
  documents: DemoDocument[]
  selectedDocument: string
  status: RunStatus
  runId?: string
  events: AgentEvent[]
  pageComparisons: Record<number, PageComparison>
  previousPageComparisons: Record<number, PageComparison>
  previousRunId?: string
  runView: RunView
  selectedComparisonPage?: number
  before?: ComparisonArtifact
  after?: ComparisonArtifact
  activeView: ViewMode
  countdown: number
  error?: string
}
