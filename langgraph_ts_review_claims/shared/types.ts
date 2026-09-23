export type Claim = {
  id: string
  member: string
  plan: string
  status: 'PENDING_REVIEW' | 'PAID' | 'DENIED' | 'PARTIAL'
  reason: string
  amount: number
}
export type Decision = { action: 'approve' | 'reject'; reason: string; text: string }
export type Review = {
  id: string
  claimId: string
  createdAt: string
  status: 'waiting' | 'approved' | 'rejected'
  draft: string
  answer: string
  decision?: Decision
}
