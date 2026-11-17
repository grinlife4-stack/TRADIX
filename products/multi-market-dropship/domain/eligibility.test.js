import test from "node:test";
import assert from "node:assert/strict";
import { evaluateCandidate, rankCandidate } from "./eligibility.js";

test("candidate is blocked when no evidence exists", () => {
  const result = evaluateCandidate({});
  assert.equal(result.eligible, false);
  assert.ok(result.blockers.includes("supplier_agreement"));
  assert.ok(result.blockers.includes("positive_contribution_margin"));
});

test("candidate requires every compliance and fulfillment gate", () => {
  const candidate = {
    evidence: {
      source_authorized: true, source_fresh: true, demand_evidence: true,
      supplier_agreement: true, direct_fulfillment_confirmed: true,
      returns_terms_confirmed: true, positive_contribution_margin: true,
      policy_review_passed: true
    },
    economics: { contribution_margin: 12.5 }
  };
  assert.equal(evaluateCandidate(candidate).eligible, true);
});

test("non-positive margin blocks a candidate even if evidence claims otherwise", () => {
  const candidate = {
    evidence: {
      source_authorized: true, source_fresh: true, demand_evidence: true,
      supplier_agreement: true, direct_fulfillment_confirmed: true,
      returns_terms_confirmed: true, positive_contribution_margin: true,
      policy_review_passed: true
    },
    economics: { contribution_margin: 0 }
  };
  assert.equal(evaluateCandidate(candidate).eligible, false);
});

test("ranking never implies eligibility", () => {
  const result = rankCandidate({ metrics: { demand_score: 99, margin_score: 99 } });
  assert.equal(result.score > 0, true);
  assert.equal(result.eligible, false);
  assert.equal(result.status, "blocked");
});

test("scores are clamped and missing metrics are zero", () => {
  const result = rankCandidate({ metrics: { demand_score: 1000, trend_score: -5 } });
  assert.equal(result.score, 34);
});
