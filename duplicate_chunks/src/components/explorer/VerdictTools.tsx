import { useRef, useState } from "react";
import { fmt } from "../../lib/format";
import { useStore } from "../../store/useStore";

/** Export and import the reviewer's verdicts, so a review can be saved with
 * the analysis or shared. */
export default function VerdictTools() {
  const verdicts = useStore((s) => s.verdicts);
  const report = useStore((s) => s.report);
  const importVerdicts = useStore((s) => s.importVerdicts);
  const fileRef = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const n = Object.keys(verdicts).length;

  const exportJson = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          { exportedAt: new Date().toISOString(), analysis: report?.generatedAt, crawlDir: report?.crawlDir, verdicts },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `duplicate-verdicts-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted">{fmt(n)} verdicts saved in this browser</span>
      <button
        onClick={exportJson}
        disabled={!n}
        className="rounded-md border border-line px-2 py-1 text-ink-2 hover:text-ink disabled:opacity-40"
      >
        Export
      </button>
      <button onClick={() => fileRef.current?.click()} className="rounded-md border border-line px-2 py-1 text-ink-2 hover:text-ink">
        Import
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="application/json"
        className="hidden"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          try {
            const count = importVerdicts(JSON.parse(await file.text()));
            setMsg(`Imported ${count}`);
          } catch {
            setMsg("Not a verdicts file");
          }
          e.target.value = "";
          setTimeout(() => setMsg(null), 3000);
        }}
      />
      {msg && <span className="text-ink-2">{msg}</span>}
    </div>
  );
}
