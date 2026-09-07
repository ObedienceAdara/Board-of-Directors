# Board of Directors v1.0 Baseline

## Purpose

Phase 0 freezes the existing deliberative architecture and makes it measurable before adding autonomous execution, persistent missions, or external actions.

The control pipeline is:

```text
Business brief
  -> multi-agent board deliberation
  -> deterministic domain models
  -> consistency and contradiction checks
  -> CEO decision
  -> provenance ledger
  -> decision-grade report
```

No autonomous external execution is introduced by Phase 0.

## Test Layout

```text
tests/
  unit/          isolated component and metric tests
  integration/   cross-component contract tests
  regression/    tests for previously fixed behavior
  scenarios/     deterministic business control cases
  evals/         quality/evaluation contracts
```

The existing root-level test suite remains in place during the transition. New tests use the structured directories so coverage can be migrated without weakening the current CI contract.

## Baseline Metrics

Every `run_board_meeting(...)` response now contains `baseline_metrics` with schema version `1.0`.

| Metric | Phase 0 behavior |
|---|---|
| Decision correctness | Explicitly `not_scored` until labeled ground truth exists. |
| Calculation correctness | Deterministic structural/invariant checks over Phase 2 outputs. |
| Provenance completeness | Sourced-claim coverage plus ledger validation status. |
| Contradiction detection | Count of deterministic contradictions and adjudicated issues. |
| Pipeline latency | Wall-clock milliseconds for the complete board run. |
| LLM cost | Explicitly `not_available` until normalized provider token/cost telemetry is exposed. |
| Failure rate | Per-run binary reliability metric: `1.0` on pipeline failure, `0.0` otherwise. |

A `not_scored` or `not_available` field is intentional. Phase 0 does not manufacture quality numbers that the runtime cannot substantiate.

## Calculation Correctness

Calculation correctness is not the same thing as business decision correctness. The baseline checks internal deterministic contracts such as:

- twelve-month forecast shape;
- revenue-total reconciliation;
- finite/non-negative funnel yields;
- workforce payroll and forecast structure;
- valid technical delivery duration;
- complete product priority scores.

The deterministic scenario tests additionally lock down exact control-case outputs for finance, sales, and workforce/ramp behavior.

## Control Cases

The deterministic control cases are deliberately small and interpretable. Their purpose is regression detection, not business forecasting.

The workforce control case specifically protects the start-date/ramp contract that previously caused a CI regression: a two-person team starting in month two with a two-month ramp provides 100 hours in month two and 200 hours from month three onward.

## What Phase 0 Does Not Claim

Phase 0 does not yet provide:

- objective decision-quality scoring against real outcomes;
- normalized LLM token/cost accounting;
- continuous event-driven operation;
- autonomous external actions;
- long-horizon mission execution;
- learned policies.

Those capabilities belong to later architectural phases and should be evaluated against this baseline rather than silently replacing it.

## Release Contract

`VERSION` declares `1.0.0` for the stabilization baseline.

A Phase 0-compliant run must preserve truthful runtime status, deterministic calculator behavior, provenance validation, contradiction handling, and the existing board-to-report flow while exposing the baseline metrics envelope.
