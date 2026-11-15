export type ScanStatus = "not_scanned" | "queued" | "scanning" | "completed" | "error";

export interface PdfScan {
  id: string;
  family: string;
  name: string;
  path: string;
  status: ScanStatus;
  scannedAt: string | null;
  error: string | null;
  pageCount: number | null;
  nativeTextPages: number | null;
  blankTextPages: number[];
  nativeLabels: boolean | null;
  nativeLabelCount: number | null;
  figureCount: number | null;
  figurePages: number[];
  chartCount: number | null;
  chartPages: number[];
  tableCount: number | null;
  tablePages: number[];
  formCount: number | null;
  formPages: number[];
  formFieldCount: number | null;
  scanSeconds: number | null;
  figureDescription: string;
  recommendation: string;
  recommendedWorkflow: string;
}

export interface CollectionScan {
  key: string;
  path: string;
  status: ScanStatus;
  total: number;
  completed: number;
  errors: number;
  recommendation: string;
  pdfs: PdfScan[];
}

export interface ScanState {
  version: number;
  running: boolean;
  startedAt: string | null;
  completedAt: string | null;
  activePdf: string | null;
  collections: CollectionScan[];
}
