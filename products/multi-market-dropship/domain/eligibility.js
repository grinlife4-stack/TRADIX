export const BLOCKERS = Object.freeze([
  "source_authorized",
  "source_fresh",
  "demand_evidence",
  "supplier_agreement",
  "direct_fulfillment_confirmed",
  "returns_terms_confirmed",
  "positive_contribution_margin",
  "policy_review_passed"
]);

export function evaluateCandidate(candidate) {
  const evidence = candidate?.evidence ?? {};
  const missing = BLOCKERS.filter((key) => evidence[key] !== true);
  const margin = Number(candidate?.economics?.contribution_margin);
  if (!Number.isFinite(margin) || margin <= 0) missing.push("positive_contribution_margin");
  return Object.freeze({
    eligible: missing.length === 0,
    status: missing.length === 0 ? "eligible_for_operator_review" : "blocked",
    blockers: [...new Set(missing)]
  });
}

export function rankCandidate(candidate) {
  const eligibility = evaluateCandidate(candidate);
  const metrics = candidate?.metrics ?? {};
  const demand = clamp(metrics.demand_score);
  const trend = clamp(metrics.trend_score);
  const competition = clamp(metrics.competition_score);
  const margin = clamp(metrics.margin_score);
  const fulfillment = clamp(metrics.fulfillment_score);
  const confidence = clamp(metrics.evidence_confidence);
  const score = Math.round(
    (demand * 0.22 + trend * 0.12 + (100 - competition) * 0.12 +
      margin * 0.22 + fulfillment * 0.16 + confidence * 0.16) * 100
  ) / 100;
  return Object.freeze({
    score,
    eligible: eligibility.eligible,
    status: eligibility.status,
    blockers: eligibility.blockers
  });
}

function clamp(value) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : 0;
}
