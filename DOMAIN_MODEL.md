# Domain Model — Brand Activation Decision Intelligence

## Overview

The domain model defines all key entities, their relationships, and metric definitions. This document ensures all data flowing through the system is unambiguous and auditable.

---

## Core Entities

### Assessment Run

A complete ingestion and evaluation cycle.

```
assessment_run_id: unique identifier (timestamp-based, e.g. 2026-08-05T14:32:15Z)
brand_id: (e.g. "aveeno")
market: (e.g. "US", "CA", "MX")
language: (e.g. "en", "es")
assessment_date: ISO date of assessment
retrieved_at: timestamp when data retrieved
vendor_schema_version: source data version (e.g. "brand_rank_v1.2")
ingestion_run_id: reference to ingestion pipeline run
quality_status: PASSED | NEEDS_REVIEW | FAILED
```

### File Discovery and Ingestion

Files are discovered through recursive scanning and ZIP decompression.

```
archive_entries_discovered (count)
  → Number of entries found in ZIP files before extraction
  → Example: one .zip with 50 CSV files inside = 50 archive entries

physical_files_discovered (count)
  → Total physical files after all decompression
  → archive entries + non-archive files
  → Example: 1 .zip (50 entries) + 10 loose files = 60 physical files

unique_payloads (count)
  → Distinct payload_sha256 hashes
  → Same file content with different names = 1 unique payload
  → Example: 60 physical files might have only 45 unique payloads

duplicate_payload_references (count)
  → Number of file_id records with duplicate_of_file_id != null
  → Count of "duplicate" file instances (not the unique payloads)
  → Example: if 15 physical files are duplicates, count = 15
```

**Key relationship:**
```
physical_files_discovered = unique_payloads + duplicate_payload_references + (new payloads)
```

### Payload Quality States

For each unique payload:

```
empty_unique_payloads (count)
  → Distinct payloads with is_empty = true
  → Files with 0 bytes or only headers/whitespace

unsupported_unique_payloads (count)
  → Distinct payloads with ingestion_status = 'QUARANTINED_UNSUPPORTED'
  → Files that don't match any known schema family
```

### Canonical Observations

Clean, deduplicated records suitable for analysis.

```
canonical_observations (count)
  → Rows in the canonical_observations table
  → One row per observation record after parsing and deduplication
  → Each row has:
    - observation_id
    - run_id
    - file_id
    - source_row (original row in source file)
    - module (e.g. "visibility", "readiness", "vulnerability")
    - metric_name (e.g. "visibility_score")
    - metric_value (e.g. 0.45)
    - qualifiers (JSON object with row-level data)
```

### Assessment Run Tracking

```
assessment_runs (count)
  → Number of distinct run_id values in file_manifest
  → Each ingest = one new run_id
  → Supports historical comparison
```

### Schema Families

```
schema_families (count)
  → Number of distinct schema_family values observed
  → Each unique data structure = one family
  → Example: "visibility_search_terms", "readiness_scores", etc.
```

---

## Metric Definitions

### Visibility Score

**Definition:** AI model ranking of search result prominence on a consumer query.

**Scale:** 0.0 (not visible) to 1.0 (prominently visible)

**Usage:** Detect gaps in consumer-facing search visibility for key brand/product claims.

**Source:** Brand Rank search results and LLM evaluations

### Readiness Score

**Definition:** Content readiness assessment across a product's claim-to-evidence chain.

**Scale:** 0.0 (not ready) to 1.0 (fully substantiated)

**Grain:** By product, claim, or claim group

**Usage:** Identify content gaps before consumer exposure.

### Vulnerability Score

**Definition:** Risk or concern assessment: claim disagreement, unsupported assertions, competitive threats.

**Scale:** 0.0 (not vulnerable) to 1.0 (high risk)

**Usage:** Detect claims needing substantiation or retraction.

---

## Historical vs. Current

All observations include an assessment_date.

When querying for "current" signals/priorities, always use:
```
WHERE assessment_date = (SELECT MAX(assessment_date) FROM ...)
```

Never mix historical runs in current analysis unless explicitly comparing.

---

## Lineage: From Source to Signal

```
source_file (e.g. "brand_rank_2026-08-05_visibility_search_terms.csv")
  ↓
physical_file (after extraction/decompression)
  ↓
payload_sha256 (content hash, allows deduplication)
  ↓
canonical_observation (parsed row with schema mapping)
  ↓
signal_instance (rule evaluation, not automatic)
  ↓
intervention (governed action, not automatic)
  ↓
outcome (measurement after intervention)
```

Every claim must be traceable back through this chain:
- Start with an intervention claim
- Find the signal that triggered it
- Find the observation that created the signal
- Find the source file and row
- Verify source integrity

---

## Audit Trail Requirements

All entities must include:

```
created_at (timestamp when record inserted)
updated_at (timestamp when record last modified)
created_by (optional: user/system that created)
source_type (VENDOR | SIMULATED_POC | MANUAL)
```

No record shall be deleted. All changes tracked through updated_at changes.

---

## Ambiguity Elimination

**Previously ambiguous labels:**
- "Files accounted for" → REMOVED (replaced with 4 specific metrics below)
- "Row count" → REMOVED (replaced with canonical_observations)

**New unambiguous labels:**
- archive_entries_discovered
- physical_files_discovered
- unique_payloads
- duplicate_payload_references
- empty_unique_payloads
- unsupported_unique_payloads
- canonical_observations
- assessment_runs
- schema_families

Each can be independently queried and verified.

---

## Example Walkthrough

**Scenario:** User sees "20 canonical observations" for a run.

**Audit trail:**
1. Check canonical_observations table: SELECT COUNT(*) WHERE run_id = 'x' → 20 rows
2. For each row, find source: SELECT file_id, source_row FROM canonical_observations WHERE run_id = 'x'
3. For each file, find physical path: SELECT physical_path FROM file_manifest WHERE file_id = 'y'
4. For each file, check dedup status: SELECT duplicate_of_file_id FROM file_manifest WHERE file_id = 'y'
5. Count unique payloads: SELECT COUNT(DISTINCT payload_sha256) FROM file_manifest WHERE run_id = 'x'

**Result:** 20 observations traced back to 15 unique payloads across 12 physical files in 3 source files.

---

## Future Extensions

**Phase 2:** Signal metrics (severity, confidence)
**Phase 3:** Intervention metrics (baseline, target, delta)
**Phase 4:** Outcome metrics (improvement %, attribution limitations)

Each will follow the same rigor: unambiguous definitions, audit trail, no ambiguity.
