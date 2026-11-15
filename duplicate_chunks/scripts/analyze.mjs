#!/usr/bin/env node
// Duplicate-chunk analyzer for the GEHA crawl_dir corpus.
//
// Inventories every source document under crawl_dir/raw, decides which ones
// have been processed into chunks, and finds exact, near and containment
// duplicates among the chunks of the processed documents. Writes the results
// to public/data for the web app.
//
// No dependencies: runs with any Node 18+.
//
//   node scripts/analyze.mjs [--crawl-dir PATH] [--out DIR]
//        [--near 0.7] [--containment 0.9] [--shingle 3] [--min-tokens 8]

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Options

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = parseArgs(process.argv.slice(2));
const CRAWL_DIR = path.resolve(
  args["crawl-dir"] ?? process.env.CRAWL_DIR ?? "/Users/dc/geha/crawl_dir",
);
const OUT_DIR = path.resolve(args.out ?? path.join(HERE, "..", "public", "data"));
const PARAMS = {
  nearThreshold: num(args.near, 0.7),
  containmentThreshold: num(args.containment, 0.9),
  shingleSize: Math.round(num(args.shingle, 3)),
  minTokens: Math.round(num(args["min-tokens"], 8)),
  numPerm: 128,
  bands: 64,
};

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const [k, v] = a.slice(2).split("=", 2);
    out[k] = v ?? argv[++i];
  }
  return out;
}
function num(v, d) {
  const n = Number(v);
  return v === undefined || Number.isNaN(n) ? d : n;
}

// ---------------------------------------------------------------------------
// Inventory

function readJson(p) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return null;
  }
}
function isDir(p) {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}
function listDirs(p) {
  if (!isDir(p)) return [];
  return fs
    .readdirSync(p, { withFileTypes: true })
    .filter((e) => e.isDirectory() && !e.name.startsWith("."))
    .map((e) => e.name);
}
function walkFiles(root, pred, acc = []) {
  if (!isDir(root)) return acc;
  for (const e of fs.readdirSync(root, { withFileTypes: true })) {
    if (e.name.startsWith(".")) continue;
    const p = path.join(root, e.name);
    if (e.isDirectory()) walkFiles(p, pred, acc);
    else if (pred(p)) acc.push(p);
  }
  return acc;
}
function findFile(root, name) {
  // Direct or one-level-nested lookup (candidate/chunks.jsonl, chunks.jsonl)
  for (const rel of [name, path.join("candidate", name)]) {
    const p = path.join(root, rel);
    if (fs.existsSync(p)) return p;
  }
  return walkFiles(root, (p) => path.basename(p) === name)[0] ?? null;
}

// Same rule crawl_dir.src.consumer_paths.document_id uses.
const documentIdFor = (rel) => rel.replace(/\.[^./]+$/, "").split(path.sep).join("--");
const keyFor = (family, id) =>
  createHash("sha1").update(`${family}/${id}`).digest("hex").slice(0, 12);

function inventory() {
  const rawRoot = path.join(CRAWL_DIR, "raw");
  const runsRoot = path.join(CRAWL_DIR, "runs");
  const reviewedRoot = path.join(CRAWL_DIR, "reviewed");
  if (!isDir(rawRoot)) throw new Error(`No raw/ directory under ${CRAWL_DIR}`);

  const docs = new Map(); // key -> doc
  const families = new Set([...listDirs(rawRoot), ...listDirs(runsRoot)]);

  for (const family of families) {
    for (const file of walkFiles(path.join(rawRoot, family), (p) => /\.pdf$/i.test(p))) {
      const rel = path.relative(path.join(rawRoot, family), file);
      const id = documentIdFor(rel);
      const key = keyFor(family, id);
      docs.set(key, {
        key,
        family,
        documentId: id,
        sourcePath: path.relative(CRAWL_DIR, file),
        sourceBytes: fs.statSync(file).size,
        hasSource: true,
      });
    }
    // Runs for documents whose source PDF is not (or no longer) in raw/
    for (const id of listDirs(path.join(runsRoot, family))) {
      const key = keyFor(family, id);
      if (!docs.has(key))
        docs.set(key, { key, family, documentId: id, sourcePath: null, sourceBytes: 0, hasSource: false });
    }
  }

  for (const doc of docs.values()) {
    Object.assign(doc, resolveRuns(doc, runsRoot, reviewedRoot));
  }
  return [...docs.values()].sort(
    (a, b) => a.family.localeCompare(b.family) || a.documentId.localeCompare(b.documentId),
  );
}

// Mirrors consumer_paths: a promoted reviewed version wins; otherwise the
// newest structurally valid candidate run with chunks.
function resolveRuns(doc, runsRoot, reviewedRoot) {
  const reviewedDir = path.join(reviewedRoot, doc.family, doc.documentId);
  const versions = listDirs(reviewedDir)
    .filter((v) => fs.existsSync(path.join(reviewedDir, v, "manifest.json")))
    .sort();
  if (versions.length) {
    const v = versions.at(-1);
    const chunks = findFile(path.join(reviewedDir, v), "chunks.jsonl");
    if (chunks)
      return {
        status: "reviewed",
        statusReason: `Promoted version ${v}`,
        runCount: listDirs(path.join(runsRoot, doc.family, doc.documentId)).length,
        selectedRun: `reviewed/${v}`,
        qcStatus: "passed",
        pageCount: readJson(path.join(reviewedDir, v, "manifest.json"))?.page_count ?? null,
        chunksPath: chunks,
      };
  }

  const docRuns = path.join(runsRoot, doc.family, doc.documentId);
  const runs = listDirs(docRuns);
  if (!runs.length)
    return {
      status: "not_processed",
      statusReason: "No ingestion run",
      runCount: 0,
      selectedRun: null,
      qcStatus: null,
      pageCount: null,
      chunksPath: null,
    };

  const valid = [];
  const problems = [];
  for (const run of runs) {
    const dir = path.join(docRuns, run);
    const manifest = readJson(path.join(dir, "run-manifest.json"));
    const qc = readJson(path.join(dir, "qc-report.json"));
    const chunks = path.join(dir, "candidate", "chunks.jsonl");
    if (!manifest || !qc) problems.push(`${run}: missing manifest or QC report`);
    else if (!["needs_visual_review", "passed"].includes(qc.status))
      problems.push(`${run}: QC status ${qc.status}`);
    else if (qc.structural_errors?.length)
      problems.push(`${run}: ${qc.structural_errors.length} structural error(s)`);
    else if (!fs.existsSync(chunks)) problems.push(`${run}: no chunks.jsonl`);
    else valid.push({ run, created: String(manifest.created_at ?? ""), qc, chunks });
  }
  if (!valid.length)
    return {
      status: "failed",
      statusReason: problems[0] ?? "No usable run",
      runCount: runs.length,
      selectedRun: null,
      qcStatus: null,
      pageCount: null,
      chunksPath: null,
    };
  valid.sort((a, b) => a.created.localeCompare(b.created));
  const best = valid.at(-1);
  return {
    status: "processed",
    statusReason:
      best.qc.status === "passed" ? "Candidate run passed QC" : "Candidate run awaiting visual review",
    runCount: runs.length,
    selectedRun: best.run,
    qcStatus: best.qc.status,
    pageCount: best.qc.page_count ?? null,
    visualPassedPages: best.qc.visual_verification?.passed_pages ?? null,
    structuralWarnings: best.qc.structural_warnings?.length ?? 0,
    createdAt: best.created || null,
    chunksPath: best.chunks,
  };
}

// ---------------------------------------------------------------------------
// Text features

function normalize(text) {
  return text
    .toLowerCase()
    .replace(/<[^>]+>/g, " ") // HTML tags inside table chunks
    .replace(/[#*_`>|~]+/g, " ") // markdown punctuation
    .replace(/-{2,}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
const tokenize = (norm) => norm.match(/[a-z0-9]+(?:[.,][0-9]+)*%?/g) ?? [];

function fnv1a(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}
function fmix32(h) {
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  return h >>> 0;
}
function shingles(tokens, k) {
  const out = new Set();
  if (tokens.length === 0) return out;
  if (tokens.length < k) {
    out.add(fnv1a(tokens.join(" ")));
    return out;
  }
  for (let i = 0; i + k <= tokens.length; i++) out.add(fnv1a(tokens.slice(i, i + k).join(" ")));
  return out;
}
const SEEDS = Array.from({ length: PARAMS.numPerm }, (_, i) => fmix32((i + 1) * 0x9e3779b1));
function minhash(set) {
  const sig = new Uint32Array(PARAMS.numPerm).fill(0xffffffff);
  for (const x of set) {
    for (let i = 0; i < PARAMS.numPerm; i++) {
      const h = fmix32(x ^ SEEDS[i]);
      if (h < sig[i]) sig[i] = h;
    }
  }
  return sig;
}
function overlap(a, b) {
  const [small, large] = a.size <= b.size ? [a, b] : [b, a];
  let inter = 0;
  for (const x of small) if (large.has(x)) inter++;
  const union = a.size + b.size - inter;
  return {
    jaccard: union ? inter / union : 0,
    containment: small.size ? inter / small.size : 0,
  };
}

// Figures that distinguish otherwise-similar policy text: dollar amounts,
// percentages, years and other numbers.
const numbersIn = (text) =>
  new Set((text.match(/\$?\d[\d,]*(?:\.\d+)?(?:%|[A-Z](?![A-Za-z]))?/g) ?? []).map((n) => n.replace(/,/g, "")));

// ---------------------------------------------------------------------------
// Main

function main() {
  const started = Date.now();
  const docs = inventory();
  const chunks = [];

  for (const doc of docs) {
    doc.chunkCount = 0;
    doc.pagesWithChunks = 0;
    doc.missingPages = [];
    if (!doc.chunksPath) continue;
    const pages = new Set();
    const lines = fs.readFileSync(doc.chunksPath, "utf8").split("\n").filter(Boolean);
    lines.forEach((line, order) => {
      let c;
      try {
        c = JSON.parse(line);
      } catch {
        return;
      }
      const text = String(c.text ?? "");
      const norm = normalize(text);
      const tokens = tokenize(norm);
      chunks.push({
        uid: `${doc.key}:${order}`,
        chunkId: String(c.chunk_id ?? `${doc.documentId}-${order}`),
        docKey: doc.key,
        order,
        pages: Array.isArray(c.pages) ? c.pages : [],
        section: c.section ?? null,
        contentType: c.content_type ?? "text",
        text,
        norm,
        tokenCount: tokens.length,
        shingles: shingles(tokens, PARAMS.shingleSize),
        numbers: numbersIn(text),
      });
      doc.chunkCount++;
      for (const p of Array.isArray(c.pages) ? c.pages : []) pages.add(p);
    });
    doc.pagesWithChunks = pages.size;
    if (doc.pageCount)
      for (let p = 1; p <= doc.pageCount; p++) if (!pages.has(p)) doc.missingPages.push(p);
  }
  const byUid = new Map(chunks.map((c) => [c.uid, c]));

  // 1. Exact duplicates on normalized text
  const exactGroups = new Map();
  for (const c of chunks) {
    if (!c.norm) continue;
    const h = createHash("sha1").update(c.norm).digest("hex");
    (exactGroups.get(h) ?? exactGroups.set(h, []).get(h)).push(c);
  }
  const edges = [];
  const reps = [];
  for (const group of exactGroups.values()) {
    reps.push(group[0]);
    for (let i = 1; i < group.length; i++)
      edges.push(makeEdge(group[0], group[i], "exact", { jaccard: 1, containment: 1 }));
  }

  // 2+3. Near and containment duplicates among exact-group representatives
  const eligible = reps.filter((c) => c.tokenCount >= PARAMS.minTokens);
  const rows = PARAMS.numPerm / PARAMS.bands;
  const buckets = new Map();
  eligible.forEach((c, idx) => {
    const sig = minhash(c.shingles);
    for (let b = 0; b < PARAMS.bands; b++) {
      let h = b;
      for (let r = 0; r < rows; r++) h = fmix32(h ^ sig[b * rows + r]);
      const key = `${b}:${h}`;
      (buckets.get(key) ?? buckets.set(key, []).get(key)).push(idx);
    }
  });
  const seen = new Set();
  let candidatePairs = 0;
  for (const members of buckets.values()) {
    if (members.length < 2) continue;
    for (let i = 0; i < members.length; i++)
      for (let j = i + 1; j < members.length; j++) {
        const a = members[i];
        const b = members[j];
        const k = a < b ? a * 1e7 + b : b * 1e7 + a;
        if (seen.has(k)) continue;
        seen.add(k);
        candidatePairs++;
        const ca = eligible[a];
        const cb = eligible[b];
        const ov = overlap(ca.shingles, cb.shingles);
        if (ov.jaccard >= PARAMS.nearThreshold) edges.push(makeEdge(ca, cb, "near", ov));
        else if (ov.containment >= PARAMS.containmentThreshold)
          edges.push(makeEdge(ca, cb, "containment", ov));
      }
  }

  // Group pairs with union-find. Groups use every pair, so the explorer shows
  // look-alikes too; redundancy uses only confident pairs (figures agree), so
  // "same template, different numbers" is never counted as waste.
  const components = (list) => {
    const parent = new Map();
    const find = (x) => {
      while (parent.get(x) !== x) {
        parent.set(x, parent.get(parent.get(x)));
        x = parent.get(x);
      }
      return x;
    };
    for (const e of list) {
      for (const u of [e.a, e.b]) if (!parent.has(u)) parent.set(u, u);
      const ra = find(e.a);
      const rb = find(e.b);
      if (ra !== rb) parent.set(ra, rb);
    }
    const groups = new Map();
    for (const u of parent.keys()) {
      const r = find(u);
      (groups.get(r) ?? groups.set(r, []).get(r)).push(u);
    }
    return { groups, find };
  };
  const longestFirst = (a, b) => b.text.length - a.text.length || a.uid.localeCompare(b.uid);

  const redundantSet = new Set();
  for (const uids of components(edges.filter((e) => !e.numbersDiffer)).groups.values()) {
    uids
      .map((u) => byUid.get(u))
      .sort(longestFirst)
      .slice(1)
      .forEach((m) => redundantSet.add(m.uid));
  }

  const { groups, find } = components(edges);
  const edgesByRoot = new Map();
  for (const e of edges) {
    const r = find(e.a);
    (edgesByRoot.get(r) ?? edgesByRoot.set(r, []).get(r)).push(e);
  }

  const docByKey = new Map(docs.map((d) => [d.key, d]));
  const role = new Map(); // uid -> {clusterId, canonical, redundant}
  const clusters = [...groups.entries()]
    .map(([root, uids]) => {
      const members = uids.map((u) => byUid.get(u)).sort(longestFirst);
      const cEdges = edgesByRoot.get(root) ?? [];
      const docKeys = [...new Set(members.map((m) => m.docKey))];
      return {
        members,
        edges: cEdges,
        types: ["exact", "near", "containment"].filter((t) => cEdges.some((e) => e.type === t)),
        scope: docKeys.length > 1 ? "cross-doc" : "within-doc",
        docKeys,
        families: [...new Set(docKeys.map((k) => docByKey.get(k).family))],
        numbersDiffer: cEdges.some((e) => e.numbersDiffer),
        redundant: members.filter((m) => redundantSet.has(m.uid)).length,
        redundantChars: members.filter((m) => redundantSet.has(m.uid)).reduce((s, m) => s + m.text.length, 0),
      };
    })
    .sort((a, b) => b.members.length - a.members.length || b.redundantChars - a.redundantChars)
    .map((c, i) => {
      const id = `c${String(i + 1).padStart(4, "0")}`;
      c.members.forEach((m, j) =>
        role.set(m.uid, { clusterId: id, canonical: j === 0, redundant: redundantSet.has(m.uid) }),
      );
      return {
        id,
        size: c.members.length,
        types: c.types,
        scope: c.scope,
        families: c.families,
        docKeys: c.docKeys,
        numbersDiffer: c.numbersDiffer,
        redundant: c.redundant,
        redundantChars: c.redundantChars,
        canonical: c.members[0].uid,
        members: c.members.map((m) => ({
          uid: m.uid,
          chunkId: m.chunkId,
          docKey: m.docKey,
          order: m.order,
          pages: m.pages,
          section: m.section,
          contentType: m.contentType,
          chars: m.text.length,
          redundant: redundantSet.has(m.uid),
          preview: m.text.replace(/\s+/g, " ").slice(0, 160),
        })),
        edges: c.edges,
      };
    });

  // Per-document and per-family statistics
  for (const doc of docs) Object.assign(doc, { involved: 0, redundant: 0, chars: 0, redundantChars: 0 });
  for (const c of chunks) {
    const d = docByKey.get(c.docKey);
    d.chars += c.text.length;
    const r = role.get(c.uid);
    if (!r) continue;
    d.involved++;
    if (r.redundant) {
      d.redundant++;
      d.redundantChars += c.text.length;
    }
  }

  const statuses = ["reviewed", "processed", "failed", "not_processed"];
  const familyStats = [...new Set(docs.map((d) => d.family))].sort().map((family) => {
    const fd = docs.filter((d) => d.family === family);
    return {
      family,
      documents: fd.length,
      byStatus: Object.fromEntries(statuses.map((s) => [s, fd.filter((d) => d.status === s).length])),
      chunks: sum(fd, "chunkCount"),
      involved: sum(fd, "involved"),
      redundant: sum(fd, "redundant"),
      chars: sum(fd, "chars"),
      redundantChars: sum(fd, "redundantChars"),
    };
  });

  const pairCount = (pred) => edges.filter(pred).length;
  const chunksIn = (pred) => {
    const s = new Set();
    for (const e of edges.filter(pred)) s.add(e.a).add(e.b);
    return s.size;
  };
  const summary = {
    documents: docs.length,
    byStatus: Object.fromEntries(statuses.map((s) => [s, docs.filter((d) => d.status === s).length])),
    pages: sum(docs, "pageCount"),
    pagesWithChunks: sum(docs, "pagesWithChunks"),
    pagesVisuallyVerified: sum(docs, "visualPassedPages"),
    chunks: chunks.length,
    shortChunks: chunks.filter((c) => c.tokenCount < PARAMS.minTokens).length,
    chars: sum(docs, "chars"),
    involvedChunks: role.size,
    redundantChunks: redundantSet.size,
    pairsNumbersDiffer: edges.filter((e) => e.numbersDiffer).length,
    redundantChars: sum(docs, "redundantChars"),
    clusters: clusters.length,
    clustersNumbersDiffer: clusters.filter((c) => c.numbersDiffer).length,
    candidatePairs,
    byType: Object.fromEntries(
      ["exact", "near", "containment"].map((t) => [
        t,
        { pairs: pairCount((e) => e.type === t), chunks: chunksIn((e) => e.type === t) },
      ]),
    ),
    byScope: {
      "within-doc": { pairs: pairCount((e) => e.scope === "within-doc"), chunks: chunksIn((e) => e.scope === "within-doc") },
      "cross-doc": { pairs: pairCount((e) => e.scope === "cross-doc"), chunks: chunksIn((e) => e.scope === "cross-doc") },
    },
  };

  // Write output
  fs.mkdirSync(path.join(OUT_DIR, "docs"), { recursive: true });
  for (const f of fs.readdirSync(path.join(OUT_DIR, "docs"))) fs.unlinkSync(path.join(OUT_DIR, "docs", f));
  const docRows = docs.map(({ chunksPath, ...d }) => d);
  for (const doc of docs) {
    if (!doc.chunkCount) continue;
    const docChunks = chunks
      .filter((c) => c.docKey === doc.key)
      .map((c) => ({
        uid: c.uid,
        chunkId: c.chunkId,
        order: c.order,
        pages: c.pages,
        section: c.section,
        contentType: c.contentType,
        tokenCount: c.tokenCount,
        text: c.text,
        clusterId: role.get(c.uid)?.clusterId ?? null,
        canonical: role.get(c.uid)?.canonical ?? false,
        redundant: redundantSet.has(c.uid),
      }));
    fs.writeFileSync(path.join(OUT_DIR, "docs", `${doc.key}.json`), JSON.stringify({ docKey: doc.key, chunks: docChunks }));
  }
  const report = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    crawlDir: CRAWL_DIR,
    params: PARAMS,
    elapsedMs: Date.now() - started,
    summary,
    families: familyStats,
    documents: docRows,
    clusters,
  };
  fs.writeFileSync(path.join(OUT_DIR, "report.json"), JSON.stringify(report));

  const pct = (n, d) => (d ? ((100 * n) / d).toFixed(1) : "0.0");
  console.log(`crawl_dir:  ${CRAWL_DIR}`);
  console.log(
    `documents:  ${summary.documents} (${Object.entries(summary.byStatus)
      .map(([k, v]) => `${k} ${v}`)
      .join(", ")})`,
  );
  console.log(`chunks:     ${summary.chunks} from processed documents`);
  console.log(
    `duplicates: ${summary.redundantChunks} redundant chunks (${pct(summary.redundantChunks, summary.chunks)}%) in ${summary.clusters} clusters; ${summary.involvedChunks} chunks involved`,
  );
  console.log(
    `by type:    exact ${summary.byType.exact.pairs}, near ${summary.byType.near.pairs}, containment ${summary.byType.containment.pairs} pairs`,
  );
  console.log(`wrote:      ${OUT_DIR} in ${((Date.now() - started) / 1000).toFixed(1)}s`);

  function makeEdge(ca, cb, type, ov) {
    const onlyA = [...ca.numbers].filter((n) => !cb.numbers.has(n));
    const onlyB = [...cb.numbers].filter((n) => !ca.numbers.has(n));
    // For containment, only figures missing from the larger chunk matter.
    const smallerIsA = ca.text.length <= cb.text.length;
    const numbersDiffer =
      type === "containment" ? (smallerIsA ? onlyA.length : onlyB.length) > 0 : onlyA.length + onlyB.length > 0;
    return {
      a: ca.uid,
      b: cb.uid,
      type,
      scope: ca.docKey === cb.docKey ? "within-doc" : "cross-doc",
      jaccard: round(ov.jaccard),
      containment: round(ov.containment),
      numbersDiffer,
      onlyA: onlyA.slice(0, 20),
      onlyB: onlyB.slice(0, 20),
    };
  }
}

const sum = (arr, k) => arr.reduce((s, x) => s + (x[k] ?? 0), 0);
const round = (x) => Math.round(x * 1000) / 1000;

main();
