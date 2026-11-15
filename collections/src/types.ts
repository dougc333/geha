import { z } from 'zod'

export const StatusSchema = z.enum([
  'discovered', 'missing_from_manifest', 'manifested', 'downloaded',
  'hash_mismatch', 'processing', 'extracted', 'needs_visual_review',
  'failed', 'promoted', 'archived',
])
export type Status = z.infer<typeof StatusSchema>

export const InventoryItemSchema = z.object({
  id: z.string(), title: z.string(), summary: z.string(), collection: z.string(), family: z.string(), year: z.number(),
  url: z.string().url(), rawPath: z.string().nullable(), status: StatusSchema,
  processing: StatusSchema, qc: StatusSchema, promoted: z.boolean(), hashMatches: z.boolean().nullable(),
  updated: z.string(), pages: z.number().nullable(), note: z.string().optional(),
})
export type InventoryItem = z.infer<typeof InventoryItemSchema>

export const InventorySchema = z.array(InventoryItemSchema)
