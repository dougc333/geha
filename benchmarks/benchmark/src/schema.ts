import { z } from 'zod';

export const CallSchema = z.object({
  call: z.number(),
  function: z.string(),
  depth: z.number(),
  milliseconds: z.number(),
  status: z.string(),
  error: z.string().optional(),
});

export const TableSchema = z.object({
  headers: z.array(z.string()),
  rows: z.array(z.record(z.string())),
  section: z.string().optional(),
});

export const ResultSchema = z.object({
  mode: z.enum(['html', 'spec']),
  status: z.string(),
  total_ms: z.number(),
  model: z.string().nullable().optional(),
  iterations: z.number(),
  calls: z.array(CallSchema),
  table_records: z.array(TableSchema),
  batch: z.string().optional(),
  html: z.string().optional(),
  native_evidence_word_count: z.number().optional(),
});

export const TimingsSchema = z.object({
  inputs: z.object({ pdf: z.string(), spec: z.string() }),
  results: z.array(ResultSchema),
  comparison: z.object({
    ratio_html_to_spec: z.number(),
    shared_headers: z.array(z.string()),
    shared_rows_equal: z.boolean(),
    html_only_headers: z.array(z.string()),
    spec_only_headers: z.array(z.string()),
  }).nullable().optional(),
});

export const RunListSchema = z.array(z.object({
  id: z.string(),
  modifiedAt: z.string(),
  modes: z.array(z.string()),
}));

export const BatchSchema = z.object({
  figures: z.array(z.object({
    source_png: z.string(),
    final_rendered_png: z.string(),
    status: z.string(),
  })),
});

export type BenchmarkResult = z.infer<typeof ResultSchema>;
export type Timings = z.infer<typeof TimingsSchema>;
export type RunInfo = z.infer<typeof RunListSchema>[number];
