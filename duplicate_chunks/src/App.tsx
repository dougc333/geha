import { useEffect, useState } from "react";
import Coverage from "./components/Coverage";
import Dashboard from "./components/Dashboard";
import Explorer from "./components/explorer/Explorer";
import { type Tab, useStore } from "./store/useStore";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "coverage", label: "Coverage" },
  { id: "explorer", label: "Explorer" },
];

export default function App() {
  const load = useStore((s) => s.load);
  const loadReport = useStore((s) => s.loadReport);
  useEffect(() => {
    loadReport();
  }, [loadReport]);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-[1440px] px-4 pt-4 pb-16 sm:px-6">
        {load.state === "ready" ? (
          <Body />
        ) : load.state === "error" ? (
          <LoadError message={load.error ?? "Unknown error"} />
        ) : (
          <div className="py-24 text-center text-sm text-muted">Loading analysis…</div>
        )}
      </main>
    </div>
  );
}

function Body() {
  const tab = useStore((s) => s.tab);
  if (tab === "coverage") return <Coverage />;
  if (tab === "explorer") return <Explorer />;
  return <Dashboard />;
}

function Header() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  const report = useStore((s) => s.report);
  const loadReport = useStore((s) => s.loadReport);
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2">
          <span className="relative block size-6" aria-hidden>
            <span className="absolute top-0 left-0 size-4 rounded bg-exact" />
            <span className="absolute right-0 bottom-0 size-4 rounded bg-near opacity-85" />
          </span>
          <h1 className="text-base font-semibold tracking-tight">Duplicate Chunks</h1>
        </div>
        <nav role="tablist" aria-label="Sections" className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                tab === t.id ? "bg-surface text-ink shadow-sm ring-1 ring-line" : "text-ink-2 hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs text-muted">
          {report && (
            <span title={report.crawlDir} className="hidden md:inline">
              Analyzed {new Date(report.generatedAt).toLocaleString()} ·{" "}
              <code className="font-mono">{report.crawlDir.replace(/^.*\/(geha\/)/, "$1")}</code>
            </span>
          )}
          <button
            onClick={() => loadReport()}
            className="rounded-md border border-line px-2 py-1 text-ink-2 hover:text-ink"
            title="Re-read report.json after running npm run analyze"
          >
            Reload
          </button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<"system" | "light" | "dark">(() => {
    try {
      return (localStorage.getItem("theme") as "light" | "dark" | null) ?? "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      if (theme === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  const next = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
  return (
    <button
      onClick={() => setTheme(next)}
      className="rounded-md border border-line px-2 py-1 text-ink-2 hover:text-ink"
      title={`Theme: ${theme} (click for ${next})`}
    >
      {theme === "dark" ? "Dark" : theme === "light" ? "Light" : "Auto"}
    </button>
  );
}

function LoadError({ message }: { message: string }) {
  return (
    <div className="mx-auto mt-16 max-w-xl rounded-xl border border-line bg-surface p-6">
      <h2 className="font-semibold">The analysis could not be loaded</h2>
      <pre className="mt-3 rounded-lg bg-surface-2 p-3 text-xs whitespace-pre-wrap text-ink-2">{message}</pre>
      <p className="mt-3 text-sm text-ink-2">
        From the project folder, run <code className="font-mono">npm run analyze</code> (it reads{" "}
        <code className="font-mono">/Users/dc/geha/crawl_dir</code> by default; pass{" "}
        <code className="font-mono">--crawl-dir</code> to change it), then press Reload.
      </p>
    </div>
  );
}
