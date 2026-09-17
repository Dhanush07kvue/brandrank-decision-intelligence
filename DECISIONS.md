# Decisions — Brand Activation Decision Intelligence

## Active Decisions

### D1: Routing Architecture (Client-side with Persistent Shell)

**Decision:** Use React Router v6 with client-side routing, maintain Shell component as persistent overlay.

**Why:**
- Client-side routing enables deep links and browser history
- Avoids server-side complexity for single-developer setup
- Existing app shell (status bar, AI indicator) should persist across route changes
- Matches existing frontend tech stack (React + Vite)

**How to Apply:**
- App.tsx becomes root route provider with Shell
- Each page is a separate component route
- State management via Context API where needed
- URL state for filters/search preserved via useLocation hooks
- No hash-based routing (use history mode)

**Related:** Full routing migration happens in Phase 1

---

### D2: Signal Engine (Backend Deterministic Evaluation with YAML Registry)

**Decision:** Signal rules live in `config/signal_rules.yaml`, evaluated deterministically on backend, signals persisted in database.

**Why:**
- YAML is human-editable and version-controllable
- Backend evaluation ensures consistent logic
- Signals become first-class queryable entities
- Supports rule versioning and audit trail
- Future enterprise: easy to publish to governance system

**How to Apply:**
- Create signal_rules.yaml with 5+ rule definitions
- Load and validate on API startup
- Implement analytics/signals.py service
- Evaluate on every ingestion run
- Store results in signal_instances table
- Frontend queries and displays signals (read-only)

**Related:** Phase 2 implementation

---

### D3: Truth Data (Local POC Files with Adapter Interfaces)

**Decision:** Store truth (products, claims, content, prompts) in local CSV/JSON files in `config/truth/`, create adapter interfaces for future enterprise integration.

**Why:**
- Local files keep POC simple and self-contained
- CSV is portable and version-controllable
- Adapter pattern prepares for Salsify/Aprimo/Contentful integration
- No external service dependency for POC
- Future: swap adapter, keep contract stable

**How to Apply:**
- Create config/truth/ directory with:
  - product_truth.csv
  - claim_truth.csv
  - content_assets.csv
  - prompt_priorities.csv
- Implement BaseAdapter interface
- Create LocalFileAdapter for POC
- Create interfaces for enterprise adapters (SalsifyAdapter, ArimoAdapter, etc.)
- On startup, load local truth into database
- Truth validation API queries database

**Related:** Phase 3 implementation, Section 3.1

---

### D4: State Management (Context API + Hooks, No Heavy State Library)

**Decision:** Use React Context API with hooks for global state, no Redux/Zustand.

**Why:**
- Single developer, moderate complexity
- Avoids additional dependency
- Sufficient for current needs
- Can migrate to Zustand if needed later
- Keeps bundle small

**How to Apply:**
- Create AppContext for:
  - Current brand, market
  - Latest assessment date
  - AI status
  - Current user (if needed)
- Create hooks: useAppContext, useDatasetStatus, etc.
- Lift common API calls to context providers
- Use useLocation for route-specific state

**Related:** Phase 1 implementation

---

### D5: Dataset Metrics (Unambiguous Labels with Definitions)

**Decision:** Replace ambiguous labels with explicit metric names, document every definition in data model.

**Why:**
- Audit trail requires clear definitions
- Ambiguity leads to decision errors
- Leadership needs confidence in numbers
- Future governance requires unambiguous contracts

**How to Apply:**
```
Old → New mapping:
"Files accounted for" → (removed, replaced with 4 explicit metrics below)
- archive_entries_discovered (ZIP entries found)
- physical_files_discovered (physical files after decompression)
- unique_payloads (count of distinct payload_sha256)
- duplicate_payload_references (count of files with duplicate_of_file_id)

Existing but clarified:
- empty_unique_payloads (count of distinct payloads that are empty)
- unsupported_unique_payloads (count of distinct payloads in QUARANTINE)
- canonical_observations (clean records in database)
- assessment_runs (distinct run_id entries)
```

Document in DOMAIN_MODEL.md with formulas and examples.

**Related:** Phase 1, Section 1.2

---

### D6: AI Health Separation (Explicit Synthesis Mode Reporting)

**Decision:** Create separate `/api/health/ai` endpoint that reports synthesis_mode, separates API health from AI health.

**Why:**
- API can be healthy while AI is unreachable
- Fallback mode needs clear indicator
- Frontend needs to show distinct states
- Audit trail requires mode history

**How to Apply:**
```json
GET /api/health → { "status": "ok" } (basic)

GET /api/health/ai → {
  "api": "healthy",
  "database": "healthy",
  "evidence_retrieval": "healthy",
  "llm_configured": true,
  "llm_reachable": true|false,
  "synthesis_mode": "llm" | "evidence_fallback"
}
```

Synthesis_mode determined by:
- LLM configured (API key + endpoint + deployment)
- LLM reachable (test connection at startup + periodic)
- Evidence retrieval working (DuckDB accessible)

**Related:** Phase 1, Section 1.3

---

### D7: Signal Evaluation Idempotency (Per Assessment Run)

**Decision:** Signal evaluation is idempotent: same (assessment run + rule ID + rule version) always produces same signal instances.

**Why:**
- Reproducibility for audit
- Supports re-evaluation without side effects
- Enables deterministic replay for debugging
- Necessary for outcome comparison

**How to Apply:**
- Signal instance ID derived from: hash(assessment_run_id, signal_rule_id, signal_rule_version, brand, market)
- Before inserting, check if signal already exists
- If exists, update (not duplicate)
- Log any changes
- Support --force-reevaluate flag for manual re-run

**Related:** Phase 2 signal evaluation service

---

### D8: Intervention Workflow (Explicit State Transitions with Validation)

**Decision:** Intervention status transitions are guarded: only allowed transitions execute, other attempts fail with clear message.

**Why:**
- Governance requires controlled workflow
- Prevents accidental state bypass
- Audit trail shows all transitions
- Supports multiple approval gates

**How to Apply:**
```
Allowed transitions:
DETECTED → NEEDS_DIAGNOSIS → NEEDS_TRUTH_VALIDATION → READY_FOR_OWNER_REVIEW
         → APPROVED_FOR_BRIEF → IN_CREATION → IN_MLR → APPROVED → PUBLISHED

AWAITING_RETEST (after published)
MEASURED → CLOSED or REJECTED (any time)
```

Implement as method: `intervention.transition(target_status)` with guard logic.

**Related:** Phase 3, Section 3.3

---

### D9: Outcome Comparison Guards (Non-Negotiable Checks)

**Decision:** Outcome is only marked IMPROVED if all comparison guards pass; otherwise INCONCLUSIVE, never false positive IMPROVED.

**Why:**
- Prevents attribution of improvement to wrong cause
- Maintains trust in outcome measurement
- Leadership decisions depend on outcome reliability

**How to Apply:**
```
Guards (all must pass for IMPROVED):
✓ Same brand, same market, same language
✓ Same or comparable prompt/metric
✓ Comparable AI engines (>= 50% overlap)
✓ Post-change assessment after publication_date
✓ Minimum 3 evidence records baseline + post
✓ Rule/metric definitions compatible
✓ No major data quality issues
```

If any guard fails:
- Status → INCONCLUSIVE
- Add specific guard failure to limitations
- Expose in outcome UI as "comparison uncontrolled"

**Related:** Phase 4, Section 4.1

---

### D10: Demo Fixture (Extended Aveeno Data with Clear POC Markers)

**Decision:** Use existing Aveeno data as base, add simulated POC records clearly marked with source_type='SIMULATED_POC', never display simulated as vendor data.

**Why:**
- Demonstrates closed-loop without fabricating vendor evidence
- Keeps real data unmixed
- Transparent about what's real vs. demo
- Easier to maintain separation

**How to Apply:**
```
In canonical_observations:
- Add source_type field: VENDOR | SIMULATED_POC
- VENDOR rows: existing Aveeno data
- SIMULATED_POC rows: demo rows with schema_family marked

In signals/interventions:
- Filter: only use VENDOR observations for decisions
- Demo can override for visualization

In UI:
- Data Trust view shows source_type distribution
- Signal detail shows (VENDOR / SIMULATED)
- Never claim simulated data as real
```

Create config/demo/aveeno_fixture.sql with ~20-30 simulated records.

**Related:** Phase 4, Section 4.4

---

### D11: Assistant Architecture (Tool-Driven with Explicit Context)

**Decision:** Assistant uses structured tool calls (not free-form prompts), tools return deterministic data, LLM synthesis optional, fallback answers deterministic.

**Why:**
- Tool-driven prevents hallucination
- Structured output enables citation
- Fallback mode works without LLM
- Evidence-backed answers only

**How to Apply:**
```
Tool categories:

Read-only (always available):
- get_dataset_status()
- get_assessment_runs()
- get_material_signals(limit=5)
- get_signal_detail(signal_id)
- get_signal_evidence(signal_id)
- get_decision_backlog()
- get_interventions()
- get_outcomes()

Write-only (requires explicit confirmation):
- create_intervention_draft(signal_id)
- assign_owner(intervention_id, owner)
- transition_intervention(intervention_id, status)
```

Chat modes (guide tool selection):
- Executive
- Signal Analysis
- Claim/Evidence
- Content Opportunity
- Intervention
- Outcome Review
- Data Trust

**Related:** Phase 2-4, Assistant improvements

---

### D12: Documentation Over Comments (Philosophy)

**Decision:** Avoid inline code comments; document WHY in architecture/decision files; document WHAT in README/API docs.

**Why:**
- Comments rot, documentation is maintained
- Code should be self-explanatory (good naming)
- Architecture decisions stay with product intent
- API contracts stay in specs

**How to Apply:**
- Use clear function/variable names
- Write one-line docstrings only (no essay comments)
- Complex algorithms: explain in DECISIONS.md
- API behavior: document in API_CONTRACTS.md
- Domain logic: document in DOMAIN_MODEL.md
- Business rules: document in SIGNAL_RULES.md

**Related:** All phases, especially documentation phase

---

### D13: Signal Evaluator Dispatch (Dedicated Python Functions, Not a Generic DSL)

**Decision:** Each signal rule's retrieval/evaluation logic lives in a dedicated Python function in
`backend/app/analytics/signals.py`, registered by name in an `EVALUATORS` dict via a `@_register(name)`
decorator. The YAML registry (`config/signal_rules.yaml`) controls thresholds, severity bands, business
priority, and default workflow status — it does NOT try to express the retrieval query itself as a
generic JSON-path or condition DSL.

**Why:**
- The five rule types read fundamentally different row shapes out of `canonical_observations`:
  visibility rankings (`module='Visibility'`, `rowType='ranking'`, hero-prompt filtering), per-engine
  claim/accuracy scores (`module='AI Vulnerability'`, grouped by claim/statement text, needs a
  standard-deviation aggregate), readiness factors (`module='Content Readiness'`, flat score lookup),
  and referenced-source URLs (owned-vs-third-party domain ratio). A single generic condition DSL
  (e.g. `score_below: 0.25`) cannot express "group by claim text and compute stddev across engines"
  or "ratio of owned domains among referenced URLs" without becoming a bespoke query language anyway.
- Writing that language would be more code, more indirection, and less debuggable than five direct
  SQL queries in Python, for a single-developer POC with only 5 rule types.
- The YAML still carries everything a governance reviewer needs to audit *without reading code*:
  threshold, comparator (`above`/`below`), severity bands, minimum evidence rows, minimum runs,
  business priority, default workflow status. Only the "how do I find the relevant rows" step is
  code, not config.

**How to Apply:**
- Adding a 6th rule type requires: (1) a new YAML entry with an `evaluator:` name, (2) a new
  `@_register('name')` function in `signals.py` matching that name, returning group_key/value/evidence
  tuples. `evaluate_signals()` dispatches purely by name lookup — no rule-specific code elsewhere.
- Because `canonical_observations.schema_family` classification was found to be unreliable for some
  real vendor files (see D14), evaluators filter on `module` (Visibility / AI Vulnerability / Content
  Readiness) rather than `schema_family`, since `module` is set by directory-based inference which
  proved more robust against real filenames that don't encode their module in the filename itself.

**Related:** Phase 2 implementation, `backend/app/analytics/signals.py`, `config/signal_rules.yaml`

---

### D14: Module Inference by Directory Name (Not Filename Substring Alone)

**Decision:** `_infer_metadata()` in `backend/app/ingestion/pipeline.py` first checks the physical
file's parent directory name for module markers (`VisibilityModule`, `ContentReadinessModule`,
`AIVulnerabilityModule`) before falling back to filename-substring matching (`'visibility' in
filename`, `'readiness' in filename`, etc.).

**Why:**
- Real vendor files such as `aveeno_search_term_<term>_2026-07-30.csv`,
  `aveeno_search_prompts_2026-07-30.csv`, and `aveeno_competitor_*.csv` live inside a
  module-named folder (e.g. `.../VisibilityModule/...`) but do not contain the module name in the
  filename itself. Filename-only inference silently left `module` as `NULL` for these files, which
  meant the Visibility signal evaluator (which filters on `module = 'Visibility'`) found zero rows
  and no visibility-gap signals could ever fire against real data — a silent, hard-to-diagnose gap
  between "the rule is correctly implemented" and "the rule ever finds evidence."
- This was caught before Phase 2 sign-off precisely because signal evaluation was tested against
  the real ingested Aveeno archive, not synthetic fixtures alone — synthetic fixtures in
  `test_signals.py` set `module` directly and would never have exposed this gap.

**How to Apply:**
- Directory-based inference takes priority; filename-substring matching remains as a fallback for
  files that genuinely encode the module in their name.
- Re-ingesting the real Aveeno archive after this fix is required for any environment where the
  archive was previously ingested before the fix landed (`inferred_module` is stored per file at
  ingestion time and is not retroactively recomputed).

**Related:** Phase 2, `backend/app/ingestion/pipeline.py::_infer_metadata`, Task #12

---

## Deferred Decisions (Future Enterprise)

### DF1: Multi-Tenant Architecture
**Deferred until:** Enterprise deployment phase
**Notes:** POC assumes single brand; multi-tenant needs database/schema isolation strategy

### DF2: Authentication and Authorization
**Deferred until:** Enterprise deployment phase
**Notes:** POC assumes single developer; enterprise needs OIDC/SAML + RBAC

### DF3: Enterprise Data Adapters
**Deferred until:** Integration phase (Track B, weeks 4-12)
**Notes:** Adapter interfaces created; actual integrations (Salsify, Aprimo, Contentful) deferred

### DF4: Workflow System Integration
**Deferred until:** Workflow integration phase
**Notes:** Brief generation working; actual Aprimo/Teams submission deferred

### DF5: Scheduling and Automation
**Deferred until:** Operations phase
**Notes:** Manual ingestion working; automated extraction/scheduling deferred

### DF6: Performance Optimization
**Deferred until:** Scale testing phase
**Notes:** Current implementation adequate for <1M records; profiling deferred

---

## Constraints and Assumptions

### Constraints
1. Single developer working locally
2. No Docker required (prefer .venv)
3. DuckDB (no enterprise database)
4. Azure OpenAI compatible endpoint required for AI features
5. Client-side routing only (no server-side session)

### Assumptions
1. Latest assessment run is always current (no historical date selection)
2. Aveeno is the primary demo brand (other brands supported generically)
3. English-language data (localization deferred)
4. CSV/Parquet as authoritative data formats
5. Assessment runs are complete snapshots (not incremental)

### Non-Assumptions
- We do NOT assume Aprimo is deployed
- We do NOT assume Salsify has an API key
- We do NOT assume Contentful is configured
- We do NOT assume enterprise authentication
- We do NOT assume multi-tenant setup

All of the above are adapter-ready but not required for POC.

---

## Known Trade-Offs

| Trade-Off | Decision | Why |
|-----------|----------|-----|
| Complexity vs. Completion | Conservative implementation (no premature abstractions) | Single developer, focused MVP |
| Generality vs. Aveeno-specific | Brand-agnostic contracts, Aveeno-specific config | Supports future brands, demo clarity |
| Performance vs. Simplicity | No sharding, no caching (yet) | Works for <1M records, optimize later |
| Automation vs. Manual | All data ingestion manual (no RPA yet) | Simplify POC, automate in Track B |
| UI Polish vs. Function | Basic responsive design, no custom theming | Focus on decision logic, design later |
| LLM Reliance vs. Fallback | Fallback answers work without LLM | Never force AI dependency |

---

## Decision History

**Phase 1 Decisions:** Routing, metrics, health check (created Aug 5)
**Phase 2 Decisions:** Signal engine, rule registry (D2, created Aug 5); evaluator dispatch design
and module-inference fix (D13, D14, added Aug 5 during Phase 2 implementation and real-data testing)
**Phase 3 Decisions:** Truth data, interventions, workflow (created Aug 5)
**Phase 4 Decisions:** Outcomes, demo, documentation (created Aug 5)

All decisions made before implementation to enable focused, bias-free implementation.
