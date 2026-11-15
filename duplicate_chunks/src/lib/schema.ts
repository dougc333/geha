import { z } from "zod";

// Schemas for the files written by scripts/analyze.mjs. The app validates
// everything it loads, so a stale or hand-edited data file fails loudly
// instead of rendering wrong numbers.

export const DupType = z.enum(["exact", "near", "containment"]);
export type DupType = z.infer<typeof DupType>;

export const Scope = z.enum(["within-doc", "cross-doc"]);
export type Scope = z.infer<typeof Scope>;

export const DocStatus = z.enum(["reviewed", "processed", "failed", "not_processed"]);
export type DocStatus = z.infer<typeof DocStatus>;

const countPair = z.object({ pairs: z.number(), chunks: z.number() });
const byStatus = z.record(DocStatus, z.number());

export const Edge = z.object({
  a: z.string(),
  b: z.string(),
  type: DupType,
  scope: Scope,
  jaccard: z.number(),
  containment: z.number(),
  numbersDiffer: z.boolean(),
  onlyA: z.array(z.string()),
  onlyB: z.array(z.string()),
});
export type Edge = z.infer<typeof Edge>;

export const Member = z.object({
  uid: z.string(),
  chunkId: z.string(),
  docKey: z.string(),
  order: z.number(),
  pages: z.array(z.number()),
  section: z.string().nullable(),
  contentType: z.string(),
  chars: z.number(),
  redundant: z.boolean().default(false),
  preview: z.string(),
});
export type Member = z.infer<typeof Member>;

export const Cluster = z.object({
  id: z.string(),
  size: z.number(),
  types: z.array(DupType),
  scope: Scope,
  families: z.array(z.string()),
  docKeys: z.array(z.string()),
  numbersDiffer: z.boolean(),
  redundant: z.number().default(0),
  redundantChars: z.number(),
  canonical: z.string(),
  members: z.array(Member),
  edges: z.array(Edge),
});
export type Cluster = z.infer<typeof Cluster>;

export const DocumentRow = z.object({
  key: z.string(),
  family: z.string(),
  documentId: z.string(),
  sourcePath: z.string().nullable(),
  sourceBytes: z.number(),
  hasSource: z.boolean(),
  status: DocStatus,
  statusReason: z.string(),
  runCount: z.number(),
  selectedRun: z.string().nullable(),
  qcStatus: z.string().nullable(),
  pageCount: z.number().nullable(),
  visualPassedPages: z.number().nullish(),
  structuralWarnings: z.number().nullish(),
  createdAt: z.string().nullish(),
  chunkCount: z.number(),
  pagesWithChunks: z.number().default(0),
  missingPages: z.array(z.number()).default([]),
  involved: z.number(),
  redundant: z.number(),
  chars: z.number(),
  redundantChars: z.number(),
});
export type DocumentRow = z.infer<typeof DocumentRow>;

export const FamilyRow = z.object({
  family: z.string(),
  documents: z.number(),
  byStatus,
  chunks: z.number(),
  involved: z.number(),
  redundant: z.number(),
  chars: z.number(),
  redundantChars: z.number(),
});
export type FamilyRow = z.infer<typeof FamilyRow>;

export const Report = z.object({
  schemaVersion: z.literal(1),
  generatedAt: z.string(),
  crawlDir: z.string(),
  elapsedMs: z.number(),
  params: z.object({
    nearThreshold: z.number(),
    containmentThreshold: z.number(),
    shingleSize: z.number(),
    minTokens: z.number(),
    numPerm: z.number(),
    bands: z.number(),
  }),
  summary: z.object({
    documents: z.number(),
    byStatus,
    pages: z.number().default(0),
    pagesWithChunks: z.number().default(0),
    pagesVisuallyVerified: z.number().default(0),
    chunks: z.number(),
    shortChunks: z.number(),
    chars: z.number(),
    involvedChunks: z.number(),
    redundantChunks: z.number(),
    redundantChars: z.number(),
    clusters: z.number(),
    clustersNumbersDiffer: z.number(),
    pairsNumbersDiffer: z.number().default(0),
    candidatePairs: z.number(),
    byType: z.record(DupType, countPair),
    byScope: z.record(Scope, countPair),
  }),
  families: z.array(FamilyRow),
  documents: z.array(DocumentRow),
  clusters: z.array(Cluster),
});
export type Report = z.infer<typeof Report>;

export const Chunk = z.object({
  uid: z.string(),
  chunkId: z.string(),
  order: z.number(),
  pages: z.array(z.number()),
  section: z.string().nullable(),
  contentType: z.string(),
  tokenCount: z.number(),
  text: z.string(),
  clusterId: z.string().nullable(),
  canonical: z.boolean(),
  redundant: z.boolean().default(false),
});
export type Chunk = z.infer<typeof Chunk>;

export const DocChunks = z.object({ docKey: z.string(), chunks: z.array(Chunk) });
export type DocChunks = z.infer<typeof DocChunks>;

export const Verdict = z.enum(["duplicate", "distinct", "unsure"]);
export type Verdict = z.infer<typeof Verdict>;

/** Readable summary of the first few Zod issues. */
export function describeIssues(error: z.ZodError): string {
  return error.issues
    .slice(0, 5)
    .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
    .join("\n");
}
