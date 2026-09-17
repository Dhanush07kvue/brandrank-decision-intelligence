# Enterprise CPG AI Discovery & Decision Intelligence

## Architecture summary

The target platform is a source-agnostic, configuration-driven closed loop:

**Sense → Understand → Trust → Signal → Diagnose → Decide → Act → Measure**

The architecture keeps seven facts distinct: external observation, enterprise truth, signal, recommendation, decision, action and outcome. Vendor payloads land immutably, are fingerprinted against versioned contracts, and are converted to a common observation envelope plus typed observation families. Contract-aware eligibility prevents unknown or provisional semantics from silently becoming governed business decisions.

The platform is organized into Landing/Raw, Bronze, Silver, Gold and Semantic layers. A control plane holds schema, metric, scope, prompt and signal-rule registries. Deterministic signal computation sits before any LLM. Agents and Genie retrieve governed evidence and explain results, but do not replace the signal engine, truth store, workflow engine or approval process.

## Workbook

The Draw.io workbook contains ten independently readable pages: executive reference, logical platform, schema evolution, signal/decision intelligence, agentic architecture, Kenvue technology mapping, runtime/deployment, end-to-end sequence, security/governance/observability, and scale/multi-tenant model.

## Assumptions

- Target scale is orders of magnitude: hundreds of brands, tens of markets, tens of thousands of products/SKUs, hundreds of thousands of prompts, multiple AI engines, daily/weekly assessments and multi-year history.
- Kenvue technology names are implementation candidates, not ownership recommendations or logical dependencies.
- Data residency, retention, RTO/RPO, availability, accessibility and performance targets remain TBD by the business/platform standard.
- Enterprise truth remains authoritative; external scores are observations and do not prove claim truth or causality.

## Open architectural decisions

1. Select the enterprise contract registry/catalog implementation and steward operating model.
2. Confirm source-provider onboarding standards, API/event authentication and raw retention policy.
3. Choose the approved agent framework and model-routing policy.
4. Define data residency, tenant isolation and market-specific policy requirements.
5. Confirm workflow, DAM/PIM/CMS execution connector priorities.
6. Set measurable NFRs, cost allocation dimensions and DR strategy.

## Top risks and controls

| Risk | Control |
|---|---|
| Vendor schema drift silently changes meaning | Fingerprints, versioned contracts, quarantine, drift events and replay |
| 0–1 metrics are interpreted uniformly when they are not | Metric contracts carry direction, unit, denominator, rank encoding and eligibility |
| LLM invents or overstates a recommendation | Typed evidence packs, citations, safety prompt, validation and deterministic fallback |
| Raw data becomes an unrestricted agent surface | Scoped tools, semantic model, row/market policy and audit tracing |
| Operational state is mixed with analytical facts | PostgreSQL/workflow boundary versus lakehouse data products |
| Outcome comparisons are not like-for-like | Comparable assessment keys include market, language, brand, product, metric, engine and prompt context |

## MVP → enterprise migration path

1. **Foundation:** add contract registries, immutable landing, schema evolution and the canonical observation model.
2. **Scale data:** move durable raw/bronze/silver/gold products to Databricks/Delta with Unity Catalog and dbt quality gates.
3. **Intelligence:** promote signal, truth, decision and outcome services behind stable APIs.
4. **Agentic:** add governed tools, bounded evidence retrieval, Genie as a structured analytics specialist and MLflow/OTel evaluation.
5. **Activation:** add durable workflow and downstream DAM/PIM/CMS/commerce adapters.
6. **Learning:** add reassessment, comparable outcomes, cost attribution and cross-brand intelligence.

## Deliberately out of scope initially

Enterprise-wide identity implementation, replacing existing master-data/truth systems, automatic claim approval, autonomous publishing without policy gates, a per-brand deployment model, a single super-agent, and a claim that vendor observations establish causal business impact.
