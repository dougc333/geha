import React, { createContext } from 'react'
import { RunClient } from './RunClient'
import type { AgentEvent, ComparisonArtifact, DemoState, RunView, ViewMode } from './types'

interface DemoContextValue extends DemoState {
  startRun: () => Promise<void>
  selectDocument: (document: string) => void
  selectView: (view: ViewMode) => void
  selectRunView: (view: RunView) => void
  selectComparisonPage: (page: number) => void
  artifactUrl: (path?: string) => string
}

const initialState: DemoState = {
  ready: false,
  model: 'gpt-4.1-mini',
  documents: [],
  selectedDocument: 'coverage-policies/geha-coverage-policy-datroway.pdf',
  status: 'checking',
  events: [],
  pageComparisons: {},
  previousPageComparisons: {},
  runView: 'current',
  activeView: 'before',
  countdown: 0,
}

export const DemoContext = createContext<DemoContextValue>({
  ...initialState,
  startRun: async () => undefined,
  selectDocument: () => undefined,
  selectView: () => undefined,
  selectRunView: () => undefined,
  selectComparisonPage: () => undefined,
  artifactUrl: () => '',
})

export class DemoProvider extends React.Component<React.PropsWithChildren, DemoState> {
  state: DemoState = initialState
  private readonly client = new RunClient()
  private countdownTimer?: number
  private serverTimer?: number

  componentDidMount(): void {
    void this.loadHealth()
    this.serverTimer = window.setInterval(() => void this.checkServerInstance(), 5000)
  }

  componentWillUnmount(): void {
    this.client.close()
    window.clearInterval(this.countdownTimer)
    window.clearInterval(this.serverTimer)
  }

  private async loadHealth(): Promise<void> {
    try {
      const [health, catalog] = await Promise.all([
        this.client.health(),
        this.client.documents(),
      ])
      this.setState({
        serverInstanceId: health.server_instance_id,
        ready: health.ready,
        model: health.model,
        documents: catalog.documents,
        selectedDocument: catalog.default,
        status: 'idle',
      })
      void this.loadPreviousRun(catalog.default)
    } catch (error) {
      this.setState({ status: 'error', error: (error as Error).message })
    }
  }

  private async checkServerInstance(): Promise<void> {
    try {
      const health = await this.client.health()
      if (!this.state.serverInstanceId || health.server_instance_id === this.state.serverInstanceId) {
        return
      }
      this.client.close()
      window.clearInterval(this.countdownTimer)
      this.setState({
        serverInstanceId: health.server_instance_id,
        ready: health.ready,
        model: health.model,
        status: 'idle',
        runId: undefined,
        events: [],
        pageComparisons: {},
        runView: 'current',
        selectedComparisonPage: undefined,
        before: undefined,
        after: undefined,
        activeView: 'before',
        countdown: 0,
        error: undefined,
      })
      void this.loadPreviousRun(this.state.selectedDocument)
    } catch {
      // The next successful poll will reconcile state after the server returns.
    }
  }

  startRun = async (): Promise<void> => {
    this.client.close()
    window.clearInterval(this.countdownTimer)
    let previous: Awaited<ReturnType<RunClient['previous']>> = {
      available: false,
      pages: {},
    }
    try {
      previous = await this.client.previous(this.state.selectedDocument)
    } catch {
      // A missing previous run must not block a new live run.
    }
    this.setState({
      status: 'starting', events: [], pageComparisons: {},
      previousPageComparisons: previous.pages,
      previousRunId: previous.run_id,
      runView: 'current',
      selectedComparisonPage: undefined, before: undefined, after: undefined,
      activeView: 'before', countdown: 0, error: undefined, runId: undefined,
    })
    try {
      const run = await this.client.start(this.state.selectedDocument)
      this.setState({ status: 'running', runId: run.run_id })
      this.client.stream(
        run.events,
        this.receiveEvent,
        () => this.setState((state) => ({
          status: state.error || state.status === 'error' ? 'error' : 'complete',
        })),
        (error) => this.setState({ status: 'error', error: error.message }),
      )
    } catch (error) {
      this.setState({ status: 'error', error: (error as Error).message })
    }
  }

  private receiveEvent = (event: AgentEvent): void => {
    this.setState((state) => ({ events: [...state.events, event] }))
    if (event.type === 'native_page_ready') {
      const artifact = event as unknown as ComparisonArtifact
      this.storePageComparison(artifact.page, artifact, artifact)
    } else if (event.type === 'before_ready') {
      const artifact = event as unknown as ComparisonArtifact
      this.storePageComparison(artifact.page, artifact, undefined)
    } else if (event.type === 'after_ready') {
      const artifact = event as unknown as ComparisonArtifact
      this.storePageComparison(artifact.page, undefined, artifact)
    } else if (event.type === 'pause') {
      this.beginCountdown(Number(event.seconds ?? 5))
    } else if (event.type === 'agent_finished') {
      this.setState((state) => {
        if (state.runView === 'previous') {
          return { ...state, status: 'complete' as const, countdown: 0 }
        }
        const pages = Object.keys(state.pageComparisons).map(Number).sort((a, b) => a - b)
        const page = state.selectedComparisonPage ?? pages[0]
        const comparison = page ? state.pageComparisons[page] : undefined
        return {
          ...state,
          status: 'complete',
          countdown: 0,
          selectedComparisonPage: page,
          before: comparison?.before ?? comparison?.after,
          after: comparison?.after ?? comparison?.before,
          activeView: comparison?.after ? 'after' : 'before',
        }
      })
    } else if (event.type === 'agent_error') {
      this.setState({ status: 'error', error: String(event.message), countdown: 0 })
    }
  }

  private storePageComparison(
    page: number,
    before?: ComparisonArtifact,
    after?: ComparisonArtifact,
  ): void {
    this.setState((state) => {
      const current = state.pageComparisons[page] ?? {}
      const merged = {
        before: before ?? current.before,
        after: after ?? current.after,
      }
      const selectFirstCompleted = (
        state.runView === 'current'
        &&
        state.selectedComparisonPage === undefined
        && merged.before !== undefined
        && merged.after !== undefined
      )
      const refreshSelected = (
        state.runView === 'current' && state.selectedComparisonPage === page
      )
      return {
        ...state,
        pageComparisons: {
          ...state.pageComparisons,
          [page]: merged,
        },
        ...(selectFirstCompleted || refreshSelected ? {
          selectedComparisonPage: page,
          before: merged.before ?? merged.after,
          after: merged.after ?? merged.before,
          activeView: merged.after ? 'after' as const : 'before' as const,
        } : {}),
      }
    })
  }

  private async loadPreviousRun(document: string): Promise<void> {
    try {
      const previous = await this.client.previous(document)
      if (this.state.selectedDocument !== document) return
      this.setState({
        previousPageComparisons: previous.pages,
        previousRunId: previous.run_id,
      })
    } catch {
      if (this.state.selectedDocument === document) {
        this.setState({ previousPageComparisons: {}, previousRunId: undefined })
      }
    }
  }

  private beginCountdown(seconds: number): void {
    window.clearInterval(this.countdownTimer)
    this.setState({ countdown: Math.ceil(seconds) })
    this.countdownTimer = window.setInterval(() => {
      this.setState((state) => {
        if (state.countdown <= 1) {
          window.clearInterval(this.countdownTimer)
          return { countdown: 0 }
        }
        return { countdown: state.countdown - 1 }
      })
    }, 1000)
  }

  selectView = (activeView: ViewMode): void => this.setState({ activeView })
  selectRunView = (runView: RunView): void => {
    this.setState((state) => {
      const comparisons = runView === 'previous'
        ? state.previousPageComparisons
        : state.pageComparisons
      const pages = Object.keys(comparisons).map(Number).sort((a, b) => a - b)
      const selectedComparisonPage = pages[0]
      const comparison = selectedComparisonPage
        ? comparisons[selectedComparisonPage]
        : undefined
      return {
        runView,
        selectedComparisonPage,
        before: comparison?.before ?? comparison?.after,
        after: comparison?.after ?? comparison?.before,
        activeView: comparison?.after ? 'after' : 'before',
      }
    })
  }
  selectComparisonPage = (selectedComparisonPage: number): void => {
    this.setState((state) => {
      const comparisons = state.runView === 'previous'
        ? state.previousPageComparisons
        : state.pageComparisons
      const comparison = comparisons[selectedComparisonPage]
      if (!comparison) return null
      return {
        selectedComparisonPage,
        before: comparison.before ?? comparison.after,
        after: comparison.after ?? comparison.before,
        activeView: comparison.after ? 'after' : 'before',
      }
    })
  }
  selectDocument = (selectedDocument: string): void => {
    this.setState({
      selectedDocument,
      previousPageComparisons: {},
      previousRunId: undefined,
      runView: 'current',
      selectedComparisonPage: undefined,
      before: undefined,
      after: undefined,
    })
    void this.loadPreviousRun(selectedDocument)
  }
  artifactUrl = (path?: string): string => this.client.artifact(path)

  render(): React.ReactNode {
    const value: DemoContextValue = {
      ...this.state,
      startRun: this.startRun,
      selectDocument: this.selectDocument,
      selectView: this.selectView,
      selectRunView: this.selectRunView,
      selectComparisonPage: this.selectComparisonPage,
      artifactUrl: this.artifactUrl,
    }
    return <DemoContext.Provider value={value}>{this.props.children}</DemoContext.Provider>
  }
}

export abstract class DemoComponent<P = Record<string, never>, S = Record<string, never>>
  extends React.Component<P, S> {
  static contextType = DemoContext
  declare context: React.ContextType<typeof DemoContext>
}
