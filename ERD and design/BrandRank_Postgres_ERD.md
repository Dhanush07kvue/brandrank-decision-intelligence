# BrandRank PostgreSQL ERD (Clear Text Version)

```mermaid
erDiagram
  ingestion_runs ||--o{ ingestion_source_files : contains
  ingestion_source_files ||--o{ ingestion_source_records : contains
  ingestion_source_records ||--|| ingestion_canonical_observations : canonicalizes
  ingestion_runs ||--o{ core_brand_snapshots : creates
  core_brands ||--o{ core_brand_snapshots : snapshots

  core_brand_snapshots ||--o{ visibility_prompt_rankings : has
  core_brand_snapshots ||--o{ visibility_prompt_sources : has
  core_brand_snapshots ||--o{ visibility_prompt_summaries : has
  core_brand_snapshots ||--o{ visibility_prompt_engine_scores : has
  visibility_search_prompts ||--o{ visibility_prompt_rankings : prompt
  visibility_search_prompts ||--o{ visibility_prompt_sources : prompt
  visibility_search_prompts ||--o{ visibility_prompt_summaries : prompt
  visibility_search_prompts ||--o{ visibility_prompt_engine_scores : prompt
  core_brands ||--o{ visibility_prompt_rankings : ranked_brand
  core_referenced_sources ||--o{ visibility_prompt_sources : source
  core_llm_models ||--o{ visibility_prompt_sources : optional_llm
  core_llm_models ||--o{ visibility_prompt_engine_scores : engine

  readiness_web_pages ||--o{ readiness_readiness_groups : page
  readiness_readiness_groups ||--o{ readiness_readiness_factors : group
  core_brand_snapshots ||--o{ readiness_readiness_groups : snapshot
  core_brand_snapshots ||--o{ readiness_readiness_factors : snapshot

  accuracy_accuracy_statements ||--o{ accuracy_statement_observations : statement
  accuracy_accuracy_statements ||--o{ accuracy_accuracy_assessments : statement
  core_brand_snapshots ||--o{ accuracy_statement_observations : snapshot
  core_brand_snapshots ||--o{ accuracy_accuracy_assessments : snapshot
  core_llm_models ||--o{ accuracy_accuracy_assessments : model
```

## Snapshot grain

- `core.brand_snapshots` models `Brand + IngestionTimestamp`.
- Child facts are not keyed by snapshot alone; they keep their own UUID primary key plus lineage keys:
  - `snapshot_id`
  - `source_record_id`
  - `canonical_record_id`
  - `schema_contract_version`
  - `adapter_version`
  - `source_file_id` + `source_row`
