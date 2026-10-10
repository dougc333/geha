import type { AgentEvent, DemoDocument, PageComparison } from './types'

export class RunClient {
  private source?: EventSource

  async health(): Promise<{ ready: boolean; model: string; server_instance_id: string }> {
    const response = await fetch('/api/health')
    if (!response.ok) throw new Error(`Health check failed (${response.status})`)
    return response.json()
  }

  async documents(): Promise<{ documents: DemoDocument[]; default: string }> {
    const response = await fetch('/api/documents')
    if (!response.ok) throw new Error(`Could not load demo documents (${response.status})`)
    return response.json()
  }

  async start(document: string): Promise<{ run_id: string; events: string }> {
    const response = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delay_seconds: 5, document }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.error ?? `Could not start run (${response.status})`)
    return payload
  }

  async previous(document: string): Promise<{
    available: boolean
    run_id?: string
    pages: Record<number, PageComparison>
  }> {
    const response = await fetch(`/api/previous-run?document=${encodeURIComponent(document)}`)
    if (!response.ok) throw new Error(`Could not load previous run (${response.status})`)
    return response.json()
  }

  stream(
    url: string,
    onEvent: (event: AgentEvent) => void,
    onEnd: () => void,
    onError: (error: Error) => void,
  ): void {
    this.close()
    this.source = new EventSource(url)
    this.source.onmessage = (message) => onEvent(JSON.parse(message.data))
    this.source.addEventListener('end', () => {
      this.close()
      onEnd()
    })
    this.source.onerror = () => {
      if (this.source?.readyState === EventSource.CLOSED) {
        onError(new Error('The live event stream closed unexpectedly.'))
      }
    }
  }

  artifact(path?: string): string {
    return path ? `/api/artifact?path=${encodeURIComponent(path)}` : ''
  }

  close(): void {
    this.source?.close()
    this.source = undefined
  }
}
