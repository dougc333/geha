import { useEffect } from "react";
import type { Chunk } from "../lib/schema";
import { docKeyOf, useStore } from "../store/useStore";

export type ChunkState =
  | { state: "loading" }
  | { state: "error"; error: string }
  | { state: "ready"; chunk: Chunk };

/** Full text and metadata for one chunk; loads its document's chunk file on demand. */
export function useChunk(uid: string | null): ChunkState | null {
  const docKey = uid ? docKeyOf(uid) : null;
  const entry = useStore((s) => (docKey ? s.docChunks[docKey] : undefined));
  const loadDoc = useStore((s) => s.loadDoc);
  useEffect(() => {
    if (docKey) loadDoc(docKey);
  }, [docKey, loadDoc]);

  if (!uid || !docKey) return null;
  if (!entry || entry.state === "loading") return { state: "loading" };
  if (entry.state === "error") return { state: "error", error: entry.error };
  const chunk = entry.data.chunks.find((c) => c.uid === uid);
  return chunk ? { state: "ready", chunk } : { state: "error", error: `Chunk ${uid} not found` };
}

/** All chunks for one document. */
export function useDocChunks(docKey: string | null) {
  const entry = useStore((s) => (docKey ? s.docChunks[docKey] : undefined));
  const loadDoc = useStore((s) => s.loadDoc);
  useEffect(() => {
    if (docKey) loadDoc(docKey);
  }, [docKey, loadDoc]);
  return entry;
}
