# Canonical Data Model

## Design rules

The model is source-agnostic and configuration-driven. Business dimensions are shared across markets and brands; many-to-many relationship tables handle real CPG relationships. Every canonical fact is traceable to immutable raw evidence and the exact contract, adapter, metric and rule versions used at processing time.

## Core entities and grains

| Entity | Grain | Key fields / purpose |
|---|---|---|
| Enterprise / Market / Language | one governed dimension member | `enterprise_id`, `market_id`, `language_id`; market policy and localization |
| Brand / Sub-brand / Product / SKU | one business entity version | stable business key + surrogate key; effective dates and SCD history |
| Content Asset | one asset version | asset URI, content type, owner reference, effective dates; many-to-many product links |
| Source Provider / Product / Module | one provider capability | provider-independent onboarding metadata |
| Assessment Run | one acquisition/evaluation run in a scope | run key, source, date, market, brand, language, module, provenance |
| Prompt / Prompt Territory | one governed consumer question and territory | prompt key, category/brand/product relationships, version |
| AI Provider / Model / Engine | one model or answer engine version | provider, model, engine and effective dates |
| Schema Contract | one versioned source schema | fingerprint, required/optional fields, types, mappings, compatibility and adapter |
| Metric Contract | one semantic metric version | unit, direction, denominator, rank encoding, eligibility and contract state |
| Source Payload | one immutable file/API payload | payload hash, URI, acquisition timestamp, raw bytes/manifest |
| Source Record | one parsed source row/record | payload ID, row number, raw record hash and quarantine state |
| Observation | one canonical measurement at its natural grain | assessment run, source, prompt/claim/product/engine context, value and lineage |
| Signal | one persisted rule finding | rule/version, metric, scope, status, severity, materiality and explanation |
| Diagnosis / Truth Validation | one finding assessment | state, evidence references, owner, limitation and timestamps |
| Decision | one human/agent-reviewed decision | decision state, rationale, approver, linked signals and truth |
| Intervention | one approved or pending action | action, owner, downstream connector, state, linked signals |
| Outcome | one comparable before/after assessment result | baseline/post run, comparable key, delta, confidence and limitation |

## Canonical observation envelope

`observation_id`, `assessment_run_id`, `source_provider_id`, `source_contract_id`, `source_schema_version`, `adapter_version`, `metric_contract_id`, `metric_contract_version`, `market_id`, `brand_id`, `product_id` (optional), `language_id`, `assessment_timestamp`, `prompt_id` (optional), `claim_id` (optional), `ai_provider_id` (optional), `ai_model_id` (optional), `engine_id` (optional), `source_payload_id`, `source_record_id`, `source_file`, `source_row_number`, `payload_hash`, `record_hash`, `raw_value`, `canonical_value`, `unit`, `direction`, `contract_state`, `eligibility_state`, `ingested_at`.

Typed families should retain domain meaning rather than collapsing everything into one untyped EAV table: visibility/rank observations, answer/claim assessments, citation observations, readiness factors, competitive rankings/scorecards, and outcome measurements.

## Relationships and lineage

- One prompt can belong to many categories, products and brands; use bridge tables.
- One source payload produces many source records; one source record can produce one or more canonical observations.
- One signal links to many observations through a signal-evidence bridge.
- One intervention can address many signals; one signal can have many interventions over time.
- An outcome links to baseline and post assessments through a comparable-assessment bridge and stores the comparison contract/version.
- Assistant responses store intent, bounded context, evidence IDs, validation result, model, latency and fallback status without secrets.

## History and versioning

Use surrogate keys plus effective dating/SCD2 for governed dimensions and contracts. Never overwrite a schema or metric contract that was used by an historical run. Replay selects the historical contract and adapter versions. Facts are append-oriented and corrections are explicit adjustment records.

## Governance states

- `GOVERNED`: verified contract semantics and required truth/eligibility conditions are met.
- `EXPERIMENTAL`: provisional semantics; visible with limitations and not eligible for unrestricted governed action.
- `BLOCKED`: unresolved or unsafe semantics; persisted for transparency but cannot create/approve intervention.
