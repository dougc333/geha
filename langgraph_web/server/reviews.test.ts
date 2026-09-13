import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createReviews, claims } from './reviews.ts'

const decision = {
  action: 'approve',
  reason: 'Checked synthetic facts',
  text: 'Reviewed explanation',
}
test('starts at human review with checkpoint history', async () => {
  const s = createReviews(),
    r = await s.start(claims[0].id, 'start')
  assert.equal(r.status, 'waiting')
  const h = await s.history(r.id)
  assert.ok(h.length >= 3)
  assert.deepEqual(h.at(-1)?.next, ['human_review'])
})
test('approval releases edited text without changing claim', async () => {
  const s = createReviews(),
    before = JSON.stringify(claims),
    r = await s.start(claims[0].id, 'start')
  const done = await s.review(r.id, decision, 'review')
  assert.equal(done.status, 'approved')
  assert.equal(done.answer, decision.text)
  assert.equal(JSON.stringify(claims), before)
  assert.deepEqual((await s.history(r.id)).at(-1)?.next, [])
})
test('rejection does not release the draft', async () => {
  const s = createReviews(),
    r = await s.start(claims[0].id, 'start')
  const done = await s.review(r.id, { ...decision, action: 'reject' }, 'review')
  assert.equal(done.status, 'rejected')
  assert.match(done.answer, /No response released/)
})
test('duplicate starts share a single thread', async () => {
  const s = createReviews(),
    [a, b] = await Promise.all([s.start(claims[0].id, 'same'), s.start(claims[0].id, 'same')])
  assert.equal(a.id, b.id)
  assert.equal(s.list().length, 1)
  assert.throws(() => s.start(claims[1].id, 'same'), /reused/)
})
test('concurrent opposing reviews permit only one decision', async () => {
  const s = createReviews(),
    r = await s.start(claims[0].id, 'start')
  const results = await Promise.allSettled([
    s.review(r.id, decision, 'a'),
    s.review(r.id, { ...decision, action: 'reject' }, 'b'),
  ])
  assert.equal(results.filter((r) => r.status === 'fulfilled').length, 1)
})
test('completed request replay does not create checkpoints', async () => {
  const s = createReviews(),
    r = await s.start(claims[0].id, 'start')
  const done = await s.review(r.id, decision, 'a'),
    n = (await s.history(r.id)).length
  assert.deepEqual(await s.review(r.id, decision, 'a'), done)
  assert.equal((await s.history(r.id)).length, n)
  await assert.rejects(s.review(r.id, { ...decision, action: 'reject' }, 'a'), /reused/)
})
test('invalid requests fail and a fresh service has no history', async () => {
  const s = createReviews()
  assert.throws(() => s.start('missing', 'a'), /not found/)
  const r = await s.start(claims[0].id, 'start')
  await assert.rejects(s.review(r.id, { ...decision, reason: '' }, 'a'))
  const fresh = createReviews()
  assert.equal(fresh.list().length, 0)
  assert.throws(() => fresh.get(r.id), /not found/)
})
