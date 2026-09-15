import assert from "node:assert/strict";
import test from "node:test";

import { premiumFor, qleAllowsNewEnrollment, rateCodeFor } from "./enrollmentData.js";

test("maps ZIP prefixes to verified rate codes", () => {
  assert.equal(rateCodeFor("CA", "95014"), 5);
  assert.equal(rateCodeFor("CA", "96001"), 4);
  assert.equal(rateCodeFor("NY", "10001"), 5);
  assert.equal(rateCodeFor("TX", "78701"), 3);
  assert.equal(rateCodeFor("INTL", "00000"), 5);
});

test("looks up verified premiums", () => {
  assert.equal(premiumFor("Standard", "employed-biweekly", "Self Only", 1), 10.82);
  assert.equal(premiumFor("High", "retired-monthly", "Self and Family", 5), 183.37);
});

test("enforces QLE new-enrollment rules", () => {
  assert.equal(qleAllowsNewEnrollment.marriage, true);
  assert.equal(qleAllowsNewEnrollment["losing-other-coverage"], true);
  assert.equal(qleAllowsNewEnrollment["acquiring-family-member"], false);
});

