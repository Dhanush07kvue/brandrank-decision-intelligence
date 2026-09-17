# Signal Rules — Brand Activation Decision Intelligence

This document explains, in prose, the deterministic signal rules configured in
`config/signal_rules.yaml` and evaluated by `backend/app/analytics/signals.py`. It is intended for
non-technical stakeholders who need to understand *why* a signal fired without reading code or YAML.

No rule here uses an LLM. Every signal is the deterministic output of a SQL query over
`canonical_observations` (traceable back to a specific source file and row) compared against a
fixed threshold. The LLM's only role, elsewhere in the system, is to explain an already-computed
signal in natural language — never to decide whether one exists.

## How a signal is built

For every rule, the engine computes:

```
Signal = Observation (current value)
       + Benchmark or expected value (the threshold)
       + Persistence (how many runs/engines the condition has been observed in)
       + Business importance (business_priority from the rule)
       + Confidence (see formula below)
       + Governance rule (default_workflow_status — where it enters the human review queue)
```

**Confidence formula** (bounded to [0, 1]):
```
evidence_component  = min(1, evidence_row_count / 10)      * 0.5
persistence_component = min(1, runs_affected / min_runs)    * 0.3
engine_component    = min(1, max(engines_affected, 1) / 3)  * 0.2
confidence = evidence_component + persistence_component + engine_component
```
More evidence rows, more repeated runs, and more distinct AI engines observing the same gap all
raise confidence — a signal seen once, in one engine, with one evidence row, will always score low
confidence even if the value itself is far past the threshold.

**Severity** is assigned by walking the rule's `severity_bands` in order and taking the first band
whose boundary the value crosses; if none match, `default_severity` (always `LOW`) applies.

**Idempotency:** signal instance IDs are derived from
`sha256(rule_id | rule_version | assessment_run_id | brand_id | market | group_key)`. Re-running
`POST /api/signals/evaluate` against the same assessment run always produces the same set of
instance IDs — existing rows for that run are deleted and reinserted, never duplicated.

**Missing data:** if a rule's evaluator finds no rows meeting its `min_evidence_rows` /
`min_runs` gates, it returns no signal for that group — signals are never fabricated to fill a gap.
(An explicit `INSUFFICIENT_EVIDENCE` state is reserved for Phase 3 truth-validation outcomes, where
the question shifts from "does a gap exist" to "do we have enough truth data to validate a fix.")

---

## Rule 1: Persistent Priority-Prompt Visibility Gap

**ID:** `VISIBILITY_GAP_001` · **Type:** `VISIBILITY_GAP` · **Module:** Visibility
**Business priority:** HIGH · **Default workflow status:** NEEDS_DIAGNOSIS

**What it checks:** For each brand + high-priority ("hero") prompt, the average visibility ranking
score across all AI engines that answered it.

**Fires when:** average score `< 0.35`.

**Severity bands:** `≤0.15` CRITICAL · `≤0.25` HIGH · `≤0.35` MEDIUM · else LOW

**Why it matters:** A hero prompt is one the brand has explicitly flagged as high-priority (e.g. a
top-funnel category question). Persistently low visibility on exactly the prompts leadership cares
most about is the highest-priority category of gap in this system.

**Currently firing against real Aveeno data:** yes (70 instances as of the last evaluation run).

---

## Rule 2: Cross-LLM Accuracy Inconsistency

**ID:** `CROSS_LLM_INCONSISTENCY_001` · **Type:** `CROSS_LLM_INCONSISTENCY` · **Module:** AI Vulnerability
**Business priority:** HIGH · **Default workflow status:** NEEDS_DIAGNOSIS

**What it checks:** For each brand statement/claim assessed by multiple AI engines, the standard
deviation of accuracy scores across those engines. Requires at least 3 evidence rows (i.e. at least
3 per-engine assessments of the same statement) before it will fire.

**Fires when:** standard deviation `> 0.15`.

**Severity bands:** `≥0.30` CRITICAL · `≥0.22` HIGH · `≥0.15` MEDIUM · else LOW

**Why it matters:** If AI engines wildly disagree on the accuracy of the same brand statement, at
least some of them are wrong — and a consumer's trust in the brand depends on which engine they
happened to ask.

**Currently firing against real Aveeno data:** yes (3 instances).

---

## Rule 3: Claim Disagreement / Substantiation Risk

**ID:** `CLAIM_SUBSTANTIATION_RISK_001` · **Type:** `CLAIM_SUBSTANTIATION_RISK` · **Module:** AI Vulnerability
**Business priority:** HIGH · **Default workflow status:** NEEDS_TRUTH_VALIDATION

**What it checks:** For each brand claim, the consensus (average) accuracy score across all AI
engines that assessed it, plus whether any engine explicitly flagged the statement as false
(`statementStatus == 'False'`), which is called out in the signal description as "unsubstantiated."

**Fires when:** consensus accuracy `< 0.60`.

**Severity bands:** `≤0.35` CRITICAL · `≤0.50` HIGH · `≤0.60` MEDIUM · else LOW

**Why it matters:** This is the rule most directly tied to legal/regulatory risk — a claim that AI
engines rate as low-accuracy or explicitly false is a substantiation problem that likely needs an
approved-truth check before any activation, which is why its default workflow status routes straight
to truth validation rather than general diagnosis.

**Currently firing against real Aveeno data:** yes (1 instance).

---

## Rule 4: Content Readiness Factor Below Floor

**ID:** `READINESS_DETERIORATION_001` · **Type:** `READINESS_DETERIORATION` · **Module:** Content Readiness
**Business priority:** MEDIUM · **Default workflow status:** NEEDS_DIAGNOSIS

**What it checks:** Each named content-readiness factor's score (e.g. structured-data completeness,
machine-readability of a specific content type).

**Fires when:** factor score `< 0.70`.

**Severity bands:** `≤0.50` CRITICAL · `≤0.60` HIGH · `≤0.70` MEDIUM · else LOW

**Why it matters:** Readiness factors are leading indicators — content that scores low on
readiness before publication is unlikely to perform well in AI-engine visibility later, so this
rule is meant to catch problems before they become visibility gaps.

**Currently firing against real Aveeno data:** yes (1 instance).

---

## Rule 5: Citation / Evidence Accessibility Deficit

**ID:** `EVIDENCE_ACCESSIBILITY_001` · **Type:** `EVIDENCE_ACCESSIBILITY_DEFICIT` · **Module:** Content Readiness
**Business priority:** MEDIUM · **Default workflow status:** NEEDS_DIAGNOSIS

**What it checks:** Of all referenced/cited source URLs found for a brand's content, the proportion
that are brand-owned domains versus third-party. Requires at least 5 evidence rows before it will
fire.

**Fires when:** owned-domain ratio `< 0.20` (i.e. less than 20% of citations point to brand-owned
pages).

**Severity bands:** `≤0.05` CRITICAL · `≤0.10` HIGH · `≤0.20` MEDIUM · else LOW

**Why it matters:** If AI engines are citing third-party sources far more than the brand's own
pages, the brand has little control over how its own claims are represented — even if the
third-party content happens to be accurate today.

**Currently firing against real Aveeno data:** not yet — this rule is fully implemented and covered
by dedicated tests (`test_evidence_accessibility_deficit_fires_when_mostly_third_party` and
`..._insufficient_evidence_returns_none` in `backend/tests/test_signals.py`), but no group in the
current real Aveeno dataset has both ≥5 referenced-source rows and an owned-domain ratio below 0.20.
This is reported honestly rather than silently omitted — a rule with zero live instances is not a
bug, it means the real data has not yet crossed that particular floor.

---

## Traceability

Every signal instance carries its full lineage:

```
source file (file_manifest.original_filename)
  → source row (canonical_observations.source_row)
    → canonical observation (canonical_observations.record_id)
      → signal rule (signal_instances.signal_rule_id + signal_rule_version)
        → signal instance (signal_instances.signal_instance_id)
          → evidence link (signal_evidence, many rows per instance)
```

`GET /api/signals/{id}/evidence` returns every evidence row with its originating filename and row
number. `GET /api/signals/{id}/history` returns every prior assessment run's value for the same
rule + group, so a signal's trend is always traceable to specific historical runs, never inferred.
`GET /api/signals/{id}/comparisons` returns real per-AI-engine and real per-competitor values pulled
directly from the same ingested rows — never synthesized or estimated.
