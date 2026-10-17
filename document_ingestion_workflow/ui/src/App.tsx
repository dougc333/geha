import { DemoComponent } from './DemoContext'
import { AgentTrace } from './components/AgentTrace'
import { ComparisonWorkspace } from './components/ComparisonWorkspace'
import { ControlStrip } from './components/ControlStrip'
import { Header } from './components/Header'
import { DocumentSelector } from './components/DocumentSelector'
import { Summary } from './components/Summary'
import { ScreenshotToolStats } from './components/ScreenshotToolStats'
import { LayoutToolStats } from './components/LayoutToolStats'

export class App extends DemoComponent {
  render() {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <Header />
        <DocumentSelector />
        <ScreenshotToolStats />
        <LayoutToolStats />
        <ControlStrip />
        <main className="mx-auto grid max-w-[1600px] gap-6 px-6 py-6 lg:px-10 xl:grid-cols-[minmax(0,1fr)_360px]">
          <ComparisonWorkspace />
          <div className="min-w-0">
            <AgentTrace />
          </div>
        </main>
        <Summary />
      </div>
    )
  }
}
