from __future__ import annotations

from pathlib import Path
import duckdb

SCHEMA_SQL = '''
create table if not exists file_manifest (
  run_id varchar,
  file_id varchar,
  physical_path varchar,
  archive_chain varchar,
  archive_entries_discovered bigint default 0,
  original_filename varchar,
  byte_size bigint,
  sha256 varchar,
  payload_sha256 varchar,
  delimiter varchar,
  encoding varchar,
  schema_fingerprint varchar,
  schema_contract_id varchar,
  schema_contract_version varchar,
  schema_drift_json varchar,
  header_json varchar,
  row_count bigint,
  parsed_row_count bigint,
  rejected_row_count bigint,
  is_empty boolean,
  duplicate_of_file_id varchar,
  inferred_brand varchar,
  inferred_module varchar,
  inferred_assessment_date varchar,
  inferred_market varchar,
  inferred_language varchar,
  adapter_name varchar,
  adapter_version varchar,
  destination_status_json varchar,
  ingestion_status varchar,
  error_message varchar,
  ingested_at timestamp default current_timestamp
);

create table if not exists ingestion_errors (
  run_id varchar,
  file_id varchar,
  source_row bigint,
  error_type varchar,
  error_message varchar,
  raw_row varchar
);

create table if not exists canonical_observations (
  run_id varchar,
  record_id varchar,
  file_id varchar,
  payload_sha256 varchar,
  source_row bigint,
  schema_family varchar,
  schema_contract_id varchar,
  schema_contract_version varchar,
  row_type_discriminator varchar,
  module varchar,
  metric_name varchar,
  metric_value double,
  text_value varchar,
  qualifiers_json varchar,
  record_hash varchar,
  adapter_version varchar,
  observation_state varchar,
  ingested_at timestamp default current_timestamp
);

create table if not exists visibility_prompts (
  run_id varchar,
  prompt_id varchar,
  prompt_text varchar,
  category varchar,
  score double,
  source_record_id varchar
);

create table if not exists prompt_llm_scores (
  run_id varchar,
  prompt_id varchar,
  llm_name varchar,
  score double,
  source_record_id varchar
);

create table if not exists rankings (
  run_id varchar,
  ranking_id varchar,
  prompt_id varchar,
  rank_value double,
  entity varchar,
  source_record_id varchar
);

create table if not exists citations (
  run_id varchar,
  citation_id varchar,
  prompt_id varchar,
  url varchar,
  domain varchar,
  source_record_id varchar
);

create table if not exists source_domains (
  run_id varchar,
  record_id varchar,
  file_id varchar,
  domain varchar,
  url varchar,
  source_row bigint
);

create table if not exists competitor_opportunities (
  run_id varchar,
  opportunity_id varchar,
  competitor varchar,
  prompt_or_topic varchar,
  opportunity_score double,
  source_record_id varchar
);

create table if not exists readiness_scores (
  run_id varchar,
  readiness_id varchar,
  group_name varchar,
  factor_name varchar,
  score double,
  source_record_id varchar
);

create table if not exists vulnerability_scores (
  run_id varchar,
  vulnerability_id varchar,
  category varchar,
  entity varchar,
  score double,
  source_record_id varchar
);

create table if not exists claim_assessments (
  run_id varchar,
  claim_id varchar,
  claim_text varchar,
  llm_name varchar,
  assessment_score double,
  source_record_id varchar
);

create table if not exists historical_metrics (
  run_id varchar,
  metric_id varchar,
  metric_name varchar,
  metric_value double,
  assessment_date varchar,
  source_record_id varchar
);

create table if not exists product_truth (
  brand_id varchar,
  intervention_id varchar,
  product_id_sku varchar,
  product_name varchar,
  market varchar,
  language varchar,
  canonical_page_url varchar,
  full_ingredients varchar,
  ingredient_purposes varchar,
  fragrance_allergen_disclosure varchar,
  approved_claim_text varchar,
  claim_scope_qualification varchar,
  evidence_title varchar,
  evidence_url_reference varchar,
  evidence_owner varchar,
  directions_warnings_suitability varchar,
  packaging_material varchar,
  recycled_content_methodology varchar,
  recyclability_methodology varchar,
  approved_sourcing_statement varchar,
  content_owner varchar,
  approver varchar,
  approval_status varchar,
  approval_reference_id varchar,
  last_reviewed_date varchar,
  expiry_review_date varchar,
  record_provenance varchar default 'SOURCE_PAYLOAD'
);

create table if not exists claim_truth (
  claim_id varchar,
  brand_id varchar,
  claim_text varchar,
  consensus_accuracy_score double,
  approval_status varchar,
  approver varchar,
  last_reviewed_date varchar,
  evidence_reference varchar,
  created_at timestamp default current_timestamp,
  record_provenance varchar default 'SOURCE_PAYLOAD'
);

create table if not exists content_assets (
  asset_id varchar,
  brand_id varchar,
  canonical_url varchar,
  content_type varchar,
  readiness_status varchar,
  content_owner varchar,
  approver varchar,
  last_reviewed_date varchar,
  created_at timestamp default current_timestamp,
  record_provenance varchar default 'SOURCE_PAYLOAD'
);

create table if not exists prompt_priorities (
  prompt_id varchar,
  brand_id varchar,
  prompt_text varchar,
  priority_level varchar,
  category varchar,
  is_hero boolean,
  approved_by varchar,
  created_at timestamp default current_timestamp,
  record_provenance varchar default 'SOURCE_PAYLOAD'
);

create table if not exists evidence_links (
  run_id varchar,
  evidence_link_id varchar,
  record_id varchar,
  file_id varchar,
  source_row bigint,
  url varchar
);


create table if not exists interventions (
  intervention_id varchar,
  signal_instance_id varchar,
  brand_id varchar,
  market varchar,
  business_problem varchar,
  diagnosed_cause varchar,
  recommended_action varchar,
  target_prompt_id varchar,
  target_product_id varchar,
  target_claim_id varchar,
  target_page_id varchar,
  approved_evidence varchar,
  risk_route varchar,
  owner varchar,
  approver varchar,
  status varchar,
  priority varchar,
  confidence double,
  baseline_run_id varchar,
  baseline_metric double,
  target_metric double,
  planned_publish_date varchar,
  actual_publish_date varchar,
  retest_date varchar,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp,
  record_provenance varchar default 'SOURCE_PAYLOAD'
);

create table if not exists intervention_measurements (
  run_id varchar,
  intervention_id varchar,
  baseline_metric_name varchar,
  baseline_metric_value double,
  retest_metric_name varchar,
  retest_metric_value double,
  measured_at timestamp
);

create table if not exists agent_runs (
  run_id varchar,
  agent_run_id varchar,
  user_question varchar,
  tool_calls_json varchar,
  retrieved_record_ids_json varchar,
  model varchar,
  latency_ms bigint,
  token_usage_json varchar,
  intent varchar,
  response_mode varchar,
  history_enabled boolean default false,
  fallback_used boolean default false,
  validation_result varchar,
  created_at timestamp default current_timestamp
);

create table if not exists metric_contracts (
  metric_id varchar primary key,
  metric_name varchar,
  module varchar,
  description varchar,
  direction varchar,
  grain varchar,
  calculated_by varchar,
  validation_status varchar,
  created_at timestamp default current_timestamp
);

create table if not exists schema_contracts (
  schema_family varchar primary key,
  adapter_name varchar,
  expected_columns_json varchar,
  description varchar,
  created_at timestamp default current_timestamp
);

create table if not exists assessment_runs (
  run_id varchar primary key,
  source_system varchar default 'BrandRank',
  brand_id varchar,
  market varchar,
  language varchar,
  module varchar,
  acquisition_date varchar,
  vendor_assessment_date varchar,
  context_provenance_json varchar,
  ingestion_run_id varchar,
  quality_status varchar default 'PROVISIONAL',
  acquired_at timestamp,
  ingested_at timestamp default current_timestamp
);

create table if not exists semantic_blockers (
  blocker_id varchar primary key,
  target_entity varchar,
  blocker_type varchar,
  description varchar,
  status varchar,
  created_at timestamp default current_timestamp
);

create table if not exists vendor_questions (
  question_id varchar primary key,
  topic varchar,
  question_text varchar,
  status varchar,
  created_at timestamp default current_timestamp
);

create table if not exists signal_instances (
  signal_instance_id varchar,
  signal_rule_id varchar,
  signal_rule_version int,
  brand_id varchar,
  market varchar,
  assessment_run_id varchar,
  signal_type varchar,
  group_key varchar,
  title varchar,
  description varchar,
  current_value double,
  baseline_value double,
  delta double,
  runs_affected int,
  engines_affected int,
  business_priority varchar,
  severity varchar,
  confidence double,
  evidence_count int,
  diagnosis_status varchar,
  truth_validation_status varchar,
  workflow_status varchar,
  governance_status varchar,
  rule_source varchar,
  metric_contract_id varchar,
  metric_validation_status varchar,
  data_provenance varchar default 'SOURCE_PAYLOAD',
  known_limitations_json varchar,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

create table if not exists signal_evidence (
  signal_instance_id varchar,
  assessment_run_id varchar,
  record_id varchar,
  file_id varchar,
  source_row bigint,
  evidence_role varchar
);

create table if not exists intervention_outcomes (
  outcome_id varchar primary key,
  intervention_id varchar not null,
  baseline_run_id varchar,
  post_change_run_id varchar,
  published_at varchar,
  retested_at varchar,
  baseline_value double,
  post_change_value double,
  absolute_delta double,
  percentage_delta double,
  engines_improved int,
  prompts_improved int,
  citation_share_before double,
  citation_share_after double,
  competitor_delta double,
  outcome_status varchar,
  confidence double,
  comparison_limitations varchar,
  brand_id varchar,
  market varchar,
  language varchar,
  source_system varchar,
  metric_contract_id varchar,
  context_provenance_json varchar,
  created_at timestamp default current_timestamp,
  record_provenance varchar default 'SOURCE_PAYLOAD'
);

create table if not exists agent_citations (
  run_id varchar,
  agent_run_id varchar,
  citation_text varchar,
  file_id varchar,
  source_row bigint,
  record_id varchar,
  url varchar
);
'''


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(str(self.db_path))
        con.execute(SCHEMA_SQL)
        self._ensure_compatibility(con)
        return con

    @staticmethod
    def _ensure_compatibility(con: duckdb.DuckDBPyConnection) -> None:
        """Apply additive columns for databases created by earlier POC phases."""
        additions = {
            'file_manifest': [
                ('archive_entries_discovered', 'bigint default 0'),
                ('schema_contract_id', 'varchar'),
                ('schema_contract_version', 'varchar'),
                ('schema_drift_json', 'varchar'),
                ('destination_status_json', 'varchar'),
            ],
            'canonical_observations': [
                ('schema_contract_id', 'varchar'),
                ('schema_contract_version', 'varchar'),
                ('row_type_discriminator', 'varchar'),
            ],
            'product_truth': [('brand_id', 'varchar'), ("record_provenance", "varchar default 'SOURCE_PAYLOAD'")],
            'claim_truth': [("record_provenance", "varchar default 'SOURCE_PAYLOAD'")],
            'content_assets': [("record_provenance", "varchar default 'SOURCE_PAYLOAD'")],
            'prompt_priorities': [("record_provenance", "varchar default 'SOURCE_PAYLOAD'")],
            'interventions': [("record_provenance", "varchar default 'SOURCE_PAYLOAD'")],
            'intervention_outcomes': [
                ('brand_id', 'varchar'), ('market', 'varchar'), ('language', 'varchar'),
                ('source_system', 'varchar'), ('metric_contract_id', 'varchar'),
                ('context_provenance_json', 'varchar'), ("record_provenance", "varchar default 'SOURCE_PAYLOAD'")
            ],
            'assessment_runs': [
                ('source_system', "varchar default 'BrandRank'"), ('module', 'varchar'),
                ('vendor_assessment_date', 'varchar'), ('context_provenance_json', 'varchar'),
                ('ingestion_run_id', 'varchar'), ('quality_status', "varchar default 'PROVISIONAL'"),
                ('acquired_at', 'timestamp'),
            ],
            'signal_instances': [
                ('metric_contract_id', 'varchar'), ('metric_validation_status', 'varchar'),
                ('data_provenance', "varchar default 'SOURCE_PAYLOAD'"),
            ],
            'agent_runs': [
                ('intent', 'varchar'), ('response_mode', 'varchar'),
                ('history_enabled', 'boolean default false'), ('fallback_used', 'boolean default false'),
                ('validation_result', 'varchar'),
            ],
        }
        for table, columns in additions.items():
            for name, definition in columns:
                con.execute(f'alter table {table} add column if not exists {name} {definition}')
