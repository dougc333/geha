import {
  createContext,
  type Dispatch,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
} from "react";
import { ingestionApi, type OcrEngine } from "../api";

export const stages = [
  "queued",
  "uploading",
  "extracting",
  "routing",
  "reviewing",
  "embedding",
  "indexing",
  "complete",
] as const;

export type Stage = (typeof stages)[number];
export type Filter = "all" | Stage | "attention";

export interface DocumentRecord {
  id: string;
  filename: string;
  sizeMb: number;
  pages: number;
  stage: Stage;
  progress: number;
  isPolicy?: boolean;
  route?: "policy_rag" | "generic_artifacts" | "whole_document_context";
  storageStrategy?: "whole_document" | "structure_aware_chunks";
  retrievalUnits?: number;
  contextStatus?: string;
  contextArtifact?: string;
  vectorDatabase?: string;
  sourceArtifact?: string;
  embeddingDimensions?: number;
  chunks?: number;
  tables?: number;
  figures?: number;
  reviewIssues?: number;
  visualManifest?: string;
  pageManifest?: string;
  extractedPages?: number;
  sourceExtractionStatus?: "pending" | "partial" | "complete";
  contextSources?: Partial<Record<"docling" | "deepseek" | "llamaparse", number>>;
  deepseekPages?: number;
  llamaparsePages?: number;
  ocrPages?: number;
  ocrEngine?: OcrEngine;
  llamaparseStatus?: {
    phase?: "docling" | "fallback";
    total: number;
    doclingProcessed?: number;
    submitted: number;
    completed: number;
    failed: number;
    doclingAccepted?: number;
    fallbackTotal?: number;
    currentPage?: number;
    pages: Record<string, {
      status: "processing" | "docling" | "fallback" | "submitted" | "completed" | "failed";
      jobId: string | null;
      message: string | null;
    }>;
  };
  runId?: string;
  runDirectory?: string;
  status?: "queued" | "running" | "needs_review" | "succeeded" | "failed";
  duration?: string;
  updatedAt: string;
}

interface IngestionState {
  documents: Record<string, DocumentRecord>;
  order: string[];
  selectedId: string | null;
  query: string;
  filter: Filter;
  region: string;
  concurrency: number;
  ocrEngine: OcrEngine;
  isRunning: boolean;
  backendConnected: boolean;
  error: string | null;
}

type Action =
  | { type: "select"; id: string | null }
  | { type: "search"; query: string }
  | { type: "filter"; filter: Filter }
  | { type: "setRunning"; value: boolean }
  | { type: "hydrate"; documents: DocumentRecord[] }
  | { type: "backendError"; error: string }
  | { type: "setConcurrency"; value: number }
  | { type: "setOcrEngine"; value: OcrEngine }
  | { type: "advance"; id: string }
  | { type: "retry"; id: string }
  | { type: "addFiles"; files: File[] };

const now = () => new Date().toISOString();

const seedNames = [
  "geha-coverage-policy-bendamustine.pdf",
  "2026-geha-dental-plan-brochure.pdf",
  "UHC-high-deductible-health-plan.pdf",
  "kentucky-medicaid-pa-criteria.pdf",
  "summary-of-benefits-standard-option.pdf",
  "specialty-drug-coverage-policy.pdf",
  "prior-authorization-medical-benefit.pdf",
  "preventive-dental-services.pdf",
  "claims-and-appeals-policy.pdf",
  "pharmacy-formulary-2026.pdf",
  "provider-network-guidelines.pdf",
  "member-eligibility-handbook.pdf",
  "employer-health-benefits-survey-2025.pdf",
  "health-care-dollar-report.pdf",
  "national-health-statistics-213.pdf",
  "estimated-calorie-needs.pdf",
  "caregiving-benefits-white-paper.pdf",
  "medicare-star-ratings-fact-sheet.pdf",
];

const presetStages: Stage[] = [
  "complete", "complete", "complete", "indexing", "embedding", "reviewing",
  "reviewing", "routing", "routing", "extracting", "extracting", "uploading",
  "complete", "complete", "complete", "complete", "complete", "complete",
];

const initialDocuments = Object.fromEntries(
  seedNames.map((filename, index) => {
    const stage = presetStages[index];
    const stageIndex = stages.indexOf(stage);
    const isComplete = stage === "complete";
    const isPolicy = index < 12;
    const document: DocumentRecord = {
      id: `doc-${String(index + 1).padStart(2, "0")}`,
      filename,
      sizeMb: Number((1.3 + ((index * 13) % 47) / 10).toFixed(1)),
      pages: 4 + ((index * 17) % 83),
      stage,
      progress: isComplete ? 100 : Math.round((stageIndex / (stages.length - 1)) * 100),
      isPolicy: stageIndex >= stages.indexOf("reviewing") ? isPolicy : undefined,
      route: isComplete || stageIndex >= stages.indexOf("reviewing")
        ? isPolicy ? "policy_rag" : "generic_artifacts"
        : undefined,
      chunks: isComplete ? 22 + ((index * 19) % 108) : undefined,
      reviewIssues: stage === "reviewing" && index === 5 ? 2 : 0,
      duration: isComplete ? `${1 + (index % 4)}m ${12 + index * 3}s` : undefined,
      updatedAt: now(),
    };
    return [document.id, document];
  }),
);

const initialState: IngestionState = {
  documents: initialDocuments,
  order: Object.keys(initialDocuments),
  selectedId: "doc-04",
  query: "",
  filter: "all",
  region: "us-east-1",
  concurrency: 1,
  ocrEngine: "deepseek",
  isRunning: false,
  backendConnected: false,
  error: null,
};

function reducer(state: IngestionState, action: Action): IngestionState {
  switch (action.type) {
    case "select":
      return { ...state, selectedId: action.id };
    case "search":
      return { ...state, query: action.query };
    case "filter":
      return { ...state, filter: action.filter };
    case "setRunning":
      return { ...state, isRunning: action.value };
    case "hydrate": {
      const documents = Object.fromEntries(action.documents.map((document) => [document.id, document]));
      const active = action.documents.some((document) => document.status === "running");
      return {
        ...state,
        documents,
        order: action.documents.map((document) => document.id),
        selectedId: state.selectedId && documents[state.selectedId]
          ? state.selectedId
          : action.documents[0]?.id ?? null,
        isRunning: active,
        backendConnected: true,
        error: null,
      };
    }
    case "backendError":
      return { ...state, backendConnected: false, error: action.error };
    case "setConcurrency":
      return { ...state, concurrency: action.value };
    case "setOcrEngine":
      return { ...state, ocrEngine: action.value };
    case "retry": {
      const document = state.documents[action.id];
      return document
        ? {
            ...state,
            documents: {
              ...state.documents,
              [action.id]: { ...document, stage: "queued", progress: 0, reviewIssues: 0, updatedAt: now() },
            },
          }
        : state;
    }
    case "advance": {
      const document = state.documents[action.id];
      if (!document || document.stage === "complete") return state;
      const nextStage = stages[stages.indexOf(document.stage) + 1];
      const nextIndex = stages.indexOf(nextStage);
      const isPolicy = document.isPolicy ?? !document.filename.match(/survey|report|statistics|calorie|white-paper|fact-sheet/i);
      return {
        ...state,
        documents: {
          ...state.documents,
          [action.id]: {
            ...document,
            stage: nextStage,
            progress: Math.round((nextIndex / (stages.length - 1)) * 100),
            isPolicy: nextIndex >= stages.indexOf("reviewing") ? isPolicy : document.isPolicy,
            route: nextIndex >= stages.indexOf("reviewing")
              ? isPolicy ? "policy_rag" : "generic_artifacts"
              : document.route,
            chunks: nextStage === "complete" ? Math.max(12, document.pages * 2 - 3) : document.chunks,
            duration: nextStage === "complete" ? "2m 41s" : document.duration,
            updatedAt: now(),
          },
        },
      };
    }
    case "addFiles": {
      const additions = action.files.map((file, index) => {
        const id = `upload-${Date.now()}-${index}`;
        return [id, {
          id,
          filename: file.name,
          sizeMb: Number((file.size / 1024 / 1024).toFixed(1)),
          pages: 0,
          stage: "queued" as Stage,
          progress: 0,
          updatedAt: now(),
        } satisfies DocumentRecord] as const;
      });
      return {
        ...state,
        documents: { ...state.documents, ...Object.fromEntries(additions) },
        order: [...additions.map(([id]) => id), ...state.order],
        selectedId: additions[0]?.[0] ?? state.selectedId,
      };
    }
    default:
      return state;
  }
}

const StateContext = createContext<IngestionState | null>(null);
const DispatchContext = createContext<Dispatch<Action> | null>(null);

export function IngestionProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(reducer, initialState);
  useEffect(() => {
    let stopped = false;
    const refresh = async () => {
      try {
        const documents = await ingestionApi.list();
        if (!stopped) dispatch({ type: "hydrate", documents });
      } catch (error) {
        if (!stopped) dispatch({ type: "backendError", error: error instanceof Error ? error.message : "Backend unavailable" });
      }
    };
    void refresh();
    if (!state.isRunning) {
      return () => { stopped = true; };
    }
    const timer = window.setInterval(refresh, 1000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [state.isRunning]);
  return (
    <StateContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider>
    </StateContext.Provider>
  );
}

export function useIngestionState() {
  const value = useContext(StateContext);
  if (!value) throw new Error("useIngestionState must be used inside IngestionProvider");
  return value;
}

export function useIngestionDispatch() {
  const value = useContext(DispatchContext);
  if (!value) throw new Error("useIngestionDispatch must be used inside IngestionProvider");
  return value;
}

export function useIngestionActions() {
  const dispatch = useIngestionDispatch();
  return useMemo(() => ({
    select: (id: string | null) => dispatch({ type: "select", id }),
    search: (query: string) => dispatch({ type: "search", query }),
    setFilter: (filter: Filter) => dispatch({ type: "filter", filter }),
    setConcurrency: (value: number) => dispatch({ type: "setConcurrency", value }),
    setOcrEngine: (value: OcrEngine) => dispatch({ type: "setOcrEngine", value }),
    addFiles: async (files: File[]) => {
      try {
        const additions = await ingestionApi.upload(files);
        const documents = await ingestionApi.list();
        dispatch({ type: "hydrate", documents });
        if (additions[0]) dispatch({ type: "select", id: additions[0].id });
      } catch (error) {
        dispatch({ type: "backendError", error: error instanceof Error ? error.message : "Upload failed" });
      }
    },
    retry: async (id: string) => {
      try {
        await ingestionApi.retry(id);
        dispatch({ type: "setRunning", value: true });
      } catch (error) {
        dispatch({ type: "backendError", error: error instanceof Error ? error.message : "Retry failed" });
      }
    },
  }), [dispatch]);
}

export function useVisibleDocuments() {
  const state = useIngestionState();
  return useMemo(() => state.order
    .map((id) => state.documents[id])
    .filter((document) => {
      const matchesQuery = document.filename.toLowerCase().includes(state.query.toLowerCase());
      const matchesFilter = state.filter === "all"
        || (state.filter === "attention" ? (document.reviewIssues ?? 0) > 0 : document.stage === state.filter);
      return matchesQuery && matchesFilter;
    }), [state.documents, state.filter, state.order, state.query]);
}

export function useSelectedDocument() {
  const state = useIngestionState();
  return state.selectedId ? state.documents[state.selectedId] : undefined;
}

export function useBatchRunner() {
  const state = useIngestionState();
  const dispatch = useIngestionDispatch();
  const run = useCallback(async () => {
    try {
      const result = state.selectedId
        ? await ingestionApi.runDocument(state.selectedId, state.ocrEngine)
        : await ingestionApi.runNext(state.ocrEngine);
      if (result.documentId) dispatch({ type: "select", id: result.documentId });
      dispatch({ type: "setRunning", value: Boolean(result.submitted) });
    } catch (error) {
      dispatch({ type: "backendError", error: error instanceof Error ? error.message : "Batch start failed" });
    }
  }, [dispatch, state.ocrEngine, state.selectedId]);
  return { isRunning: state.isRunning, run };
}
