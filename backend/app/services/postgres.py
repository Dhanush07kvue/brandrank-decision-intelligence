from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import json
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = ' '.join(value.strip().split())
    return cleaned or None


def normalize_key(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    return normalized.lower()


def normalize_url(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    return normalized.rstrip('/').lower()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


POSTGRES_SCHEMA_SQL = '''
create extension if not exists pgcrypto;

create schema if not exists ingestion;
create schema if not exists core;
create schema if not exists visibility;
create schema if not exists readiness;
create schema if not exists accuracy;

create table if not exists ingestion.runs (
  id uuid primary key default gen_random_uuid(),
  run_id text not null unique,
  source_system text not null,
  brand_id text,
  market text,
  language text,
  storage_mode text not null,
  status text not null default 'IN_PROGRESS',
  destination_status_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists ingestion.schema_contracts (
  id uuid primary key default gen_random_uuid(),
  contract_id text not null unique,
  contract_version text not null,
  schema_family text not null,
  required_headers_json jsonb not null default '[]'::jsonb,
  optional_headers_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists ingestion.source_files (
  id uuid primary key default gen_random_uuid(),
  run_id text not null references ingestion.runs(run_id),
  file_id text not null unique,
  source_path text not null,
  archive_chain text,
  original_filename text not null,
  payload_sha256 text not null,
  schema_fingerprint text,
  schema_contract_id text,
  schema_contract_version text,
  schema_family text,
  schema_drift_json jsonb not null default '[]'::jsonb,
  ingestion_status text not null,
  error_message text,
  row_count bigint not null default 0,
  parsed_row_count bigint not null default 0,
  rejected_row_count bigint not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists ingestion.source_records (
  id uuid primary key default gen_random_uuid(),
  source_record_id text not null unique,
  run_id text not null references ingestion.runs(run_id),
  file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  schema_contract_id text,
  schema_contract_version text,
  row_hash text not null,
  row_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists ingestion.errors (
  id uuid primary key default gen_random_uuid(),
  run_id text not null references ingestion.runs(run_id),
  file_id text,
  source_row bigint not null default 0,
  error_type text not null,
  error_message text not null,
  field_name text,
  raw_row_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists ingestion.canonical_observations (
  id uuid primary key default gen_random_uuid(),
  canonical_record_id text not null unique,
  run_id text not null references ingestion.runs(run_id),
  file_id text not null references ingestion.source_files(file_id),
  source_record_id text not null references ingestion.source_records(source_record_id),
  source_row bigint not null,
  schema_family text not null,
  schema_contract_id text,
  schema_contract_version text,
  row_type_discriminator text,
  adapter_version text not null,
  metric_name text,
  metric_value double precision,
  text_value text,
  qualifiers_json jsonb not null default '{}'::jsonb,
  record_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists core.brands (
  id uuid primary key default gen_random_uuid(),
  brand_name text not null,
  normalized_brand_name text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists core.llm_models (
  id uuid primary key default gen_random_uuid(),
  provider_name text not null,
  model_name text,
  normalized_provider_name text not null,
  normalized_model_name text,
  unique(normalized_provider_name, normalized_model_name)
);

create table if not exists core.referenced_sources (
  id uuid primary key default gen_random_uuid(),
  source_name text,
  source_url text,
  normalized_source_name text,
  normalized_source_url text,
  unique(normalized_source_url)
);

alter table core.referenced_sources drop constraint if exists referenced_sources_normalized_source_name_key;

create table if not exists core.llm_key_alias (
  id uuid primary key default gen_random_uuid(),
  internal_column_key text not null unique,
  llm_model_id uuid references core.llm_models(id),
  display_name text,
  provider_name text,
  exclude_from_sv_score boolean not null default false,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists core.configured_competitors (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references core.brands(id),
  competitor_name text not null,
  competitor_name_normalized text not null,
  paragon_rank integer not null check (paragon_rank between 1 and 5),
  effective_date date,
  inferred_from_data boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  unique(brand_id, paragon_rank, effective_date)
);

create table if not exists core.brand_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_key text not null unique,
  snapshot_date date,
  run_id text not null references ingestion.runs(run_id),
  brand_id uuid not null references core.brands(id),
  ingestion_timestamp timestamptz not null,
  market text,
  language text,
  source_system text not null,
  hero_score double precision,
  hero_score_source text default 'search_prompts',
  created_at timestamptz not null default now()
);

alter table core.brand_snapshots add column if not exists snapshot_date date;

create table if not exists visibility.search_prompts (
  id uuid primary key default gen_random_uuid(),
  prompt_text text not null,
  normalized_prompt_text text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists visibility.prompt_summaries (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  prompt_id uuid not null references visibility.search_prompts(id),
  category_name text,
  score double precision not null,
  label text,
  trend text,
  category_id text,
  category_is_branded text,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  extra_columns_json jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id, category_name)
);

create table if not exists visibility.prompt_engine_scores (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  prompt_id uuid not null references visibility.search_prompts(id),
  internal_column_key text not null,
  llm_model_id uuid references core.llm_models(id),
  score double precision not null,
  is_excluded_from_sv boolean not null default false,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id, internal_column_key)
);

create table if not exists visibility.prompt_rankings (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  prompt_id uuid not null references visibility.search_prompts(id),
  ranked_brand_id uuid not null references core.brands(id),
  cohort text,
  rank_value double precision not null,
  is_hero text,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id)
);

create table if not exists visibility.prompt_sources (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  prompt_id uuid not null references visibility.search_prompts(id),
  source_id uuid references core.referenced_sources(id),
  llm_model_id uuid references core.llm_models(id),
  source_name text,
  source_url text,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id)
);

create table if not exists readiness.web_pages (
  id uuid primary key default gen_random_uuid(),
  page_url text not null,
  normalized_page_url text not null unique,
  page_label text
);

create table if not exists readiness.readiness_groups (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  page_id uuid not null references readiness.web_pages(id),
  group_name text not null,
  normalized_group_name text not null,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id, normalized_group_name)
);

create table if not exists readiness.readiness_factors (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  page_id uuid not null references readiness.web_pages(id),
  group_id uuid not null references readiness.readiness_groups(id),
  factor_name text not null,
  normalized_factor_name text not null,
  score double precision not null,
  drawer_payload_json jsonb,
  drawer_payload_raw text,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id, normalized_factor_name)
);

create table if not exists accuracy.vulnerability_swot (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid references core.brand_snapshots(id),
  entity_name text,
  swot_dimension text,
  score double precision,
  source_record_id text,
  canonical_record_id text,
  created_at timestamptz not null default now()
);

create table if not exists accuracy.brand_daily_scores (
  id uuid primary key default gen_random_uuid(),
  snapshot_date date not null,
  brand_id uuid references core.brands(id),
  module_name text not null,
  score double precision,
  source_record_id text,
  canonical_record_id text,
  created_at timestamptz not null default now(),
  unique(snapshot_date, brand_id, module_name)
);

create table if not exists accuracy.accuracy_statements (
  id uuid primary key default gen_random_uuid(),
  statement_text text not null,
  normalized_statement_text text not null unique
);

create table if not exists accuracy.statement_observations (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  statement_id uuid not null references accuracy.accuracy_statements(id),
  statement_status text,
  overall_score double precision,
  consensus_accuracy_score double precision,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id)
);

create table if not exists accuracy.accuracy_assessments (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references core.brand_snapshots(id),
  statement_id uuid not null references accuracy.accuracy_statements(id),
  llm_model_id uuid references core.llm_models(id),
  llm_name text,
  llm_status text,
  llm_accuracy_score double precision not null,
  llm_analysis text,
  source_record_id text not null references ingestion.source_records(source_record_id),
  canonical_record_id text not null references ingestion.canonical_observations(canonical_record_id),
  schema_contract_version text not null,
  adapter_version text not null,
  source_file_id text not null references ingestion.source_files(file_id),
  source_row bigint not null,
  ingested_at timestamptz not null default now(),
  unique(canonical_record_id, llm_name)
);
'''


@dataclass
class PostgresWriteCounters:
    source_files: int = 0
    source_records: int = 0
    canonical_observations: int = 0
    normalized_facts: int = 0
    rejected_rows: int = 0
    schema_drift_columns: int = 0


@dataclass
class PostgresWarehouse:
    postgres_url: str
    adapter_version: str = '2.0.0'
    engine: Engine | None = None
    _initialized: bool = False
    counters: PostgresWriteCounters = field(default_factory=PostgresWriteCounters)

    def _get_engine(self) -> Engine:
        if self.engine is None:
            self.engine = create_engine(self.postgres_url, future=True)
        return self.engine

    def ensure_schema(self) -> None:
        if self._initialized:
            return
        engine = self._get_engine()
        with engine.begin() as conn:
            for statement in [part.strip() for part in POSTGRES_SCHEMA_SQL.split(';') if part.strip()]:
                conn.execute(text(statement))
            conn.execute(
                text(
                    """
                    insert into core.llm_key_alias (internal_column_key, exclude_from_sv_score, notes)
                    values
                      ('DEEPSEEK', true, 'Excluded from SV score per vendor formula'),
                      ('GOOGLE', true, 'Excluded from SV score per vendor formula'),
                      ('OPEN_AI', false, 'Internal key; display mapping pending'),
                      ('GEMINI', false, 'Internal key; display mapping pending'),
                      ('GROK', false, 'Internal key; display mapping pending'),
                      ('META_AI', false, 'Internal key; display mapping pending'),
                      ('PERPLEXITY', false, 'Internal key; display mapping pending'),
                      ('ANTHROPIC', false, 'Internal key; display mapping pending')
                    on conflict (internal_column_key) do nothing
                    """
                )
            )
        self._initialized = True

    def write_run(
        self,
        *,
        run_id: str,
        source_system: str,
        brand_id: str,
        market: str,
        language: str,
        storage_mode: str,
        destination_status: dict[str, Any],
    ) -> None:
        self.ensure_schema()
        with self._get_engine().begin() as conn:
            conn.execute(
                text(
                    '''
                    insert into ingestion.runs (
                      run_id, source_system, brand_id, market, language, storage_mode, status, destination_status_json
                    ) values (
                      :run_id, :source_system, :brand_id, :market, :language, :storage_mode, 'IN_PROGRESS', cast(:status as jsonb)
                    )
                    on conflict (run_id) do update
                    set source_system = excluded.source_system,
                        brand_id = excluded.brand_id,
                        market = excluded.market,
                        language = excluded.language,
                        storage_mode = excluded.storage_mode,
                        destination_status_json = excluded.destination_status_json
                    '''
                ),
                {
                    'run_id': run_id,
                    'source_system': source_system,
                    'brand_id': brand_id,
                    'market': market,
                    'language': language,
                    'storage_mode': storage_mode,
                    'status': _json(destination_status),
                },
            )

    def complete_run(self, run_id: str, status: str, destination_status: dict[str, Any]) -> None:
        with self._get_engine().begin() as conn:
            conn.execute(
                text(
                    '''
                    update ingestion.runs
                    set status = :status,
                        destination_status_json = cast(:destination_status as jsonb),
                        completed_at = now()
                    where run_id = :run_id
                    '''
                ),
                {'run_id': run_id, 'status': status, 'destination_status': _json(destination_status)},
            )

    def write_contract(self, contract: dict[str, Any]) -> None:
        with self._get_engine().begin() as conn:
            conn.execute(
                text(
                    '''
                    insert into ingestion.schema_contracts (
                      contract_id, contract_version, schema_family, required_headers_json, optional_headers_json
                    ) values (
                      :contract_id, :contract_version, :schema_family, cast(:required_headers as jsonb), cast(:optional_headers as jsonb)
                    )
                    on conflict (contract_id) do update
                    set contract_version = excluded.contract_version,
                        schema_family = excluded.schema_family,
                        required_headers_json = excluded.required_headers_json,
                        optional_headers_json = excluded.optional_headers_json
                    '''
                ),
                {
                    'contract_id': contract['contract_id'],
                    'contract_version': contract['contract_version'],
                    'schema_family': contract['schema_family'],
                    'required_headers': _json(contract['required_headers']),
                    'optional_headers': _json(contract['optional_headers']),
                },
            )

    def write_source_file(self, payload: dict[str, Any]) -> None:
        with self._get_engine().begin() as conn:
            conn.execute(
                text(
                    '''
                    insert into ingestion.source_files (
                      run_id, file_id, source_path, archive_chain, original_filename, payload_sha256, schema_fingerprint,
                      schema_contract_id, schema_contract_version, schema_family, schema_drift_json, ingestion_status, error_message,
                      row_count, parsed_row_count, rejected_row_count
                    ) values (
                      :run_id, :file_id, :source_path, :archive_chain, :original_filename, :payload_sha256, :schema_fingerprint,
                      :schema_contract_id, :schema_contract_version, :schema_family, cast(:schema_drift as jsonb), :ingestion_status, :error_message,
                      :row_count, :parsed_row_count, :rejected_row_count
                    )
                    on conflict (file_id) do update
                    set ingestion_status = excluded.ingestion_status,
                        error_message = excluded.error_message,
                        schema_contract_id = excluded.schema_contract_id,
                        schema_contract_version = excluded.schema_contract_version,
                        schema_family = excluded.schema_family,
                        schema_drift_json = excluded.schema_drift_json,
                        row_count = excluded.row_count,
                        parsed_row_count = excluded.parsed_row_count,
                        rejected_row_count = excluded.rejected_row_count
                    '''
                ),
                {
                    'run_id': payload['run_id'],
                    'file_id': payload['file_id'],
                    'source_path': payload['source_path'],
                    'archive_chain': payload.get('archive_chain'),
                    'original_filename': payload['original_filename'],
                    'payload_sha256': payload['payload_sha256'],
                    'schema_fingerprint': payload.get('schema_fingerprint'),
                    'schema_contract_id': payload.get('schema_contract_id'),
                    'schema_contract_version': payload.get('schema_contract_version'),
                    'schema_family': payload.get('schema_family'),
                    'schema_drift': _json(payload.get('schema_drift', [])),
                    'ingestion_status': payload['ingestion_status'],
                    'error_message': payload.get('error_message'),
                    'row_count': payload.get('row_count', 0),
                    'parsed_row_count': payload.get('parsed_row_count', 0),
                    'rejected_row_count': payload.get('rejected_row_count', 0),
                },
            )
        self.counters.source_files += 1
        self.counters.schema_drift_columns += len(payload.get('schema_drift', []))

    def write_error(
        self,
        *,
        run_id: str,
        file_id: str | None,
        source_row: int,
        error_type: str,
        error_message: str,
        field_name: str | None,
        raw_row: dict[str, Any],
    ) -> None:
        with self._get_engine().begin() as conn:
            conn.execute(
                text(
                    '''
                    insert into ingestion.errors (
                      run_id, file_id, source_row, error_type, error_message, field_name, raw_row_json
                    ) values (
                      :run_id, :file_id, :source_row, :error_type, :error_message, :field_name, cast(:raw_row as jsonb)
                    )
                    '''
                ),
                {
                    'run_id': run_id,
                    'file_id': file_id,
                    'source_row': source_row,
                    'error_type': error_type,
                    'error_message': error_message,
                    'field_name': field_name,
                    'raw_row': _json(raw_row),
                },
            )
        self.counters.rejected_rows += 1

    def _upsert_brand(self, conn, brand_name: str) -> str:
        normalized = normalize_key(brand_name)
        row = conn.execute(
            text(
                '''
                insert into core.brands (brand_name, normalized_brand_name)
                values (:brand_name, :normalized_brand_name)
                on conflict (normalized_brand_name) do update
                set brand_name = excluded.brand_name
                returning id
                '''
            ),
            {'brand_name': brand_name, 'normalized_brand_name': normalized},
        ).fetchone()
        return row[0]

    def _upsert_prompt(self, conn, prompt_text: str) -> str:
        normalized = normalize_key(prompt_text)
        row = conn.execute(
            text(
                '''
                insert into visibility.search_prompts (prompt_text, normalized_prompt_text)
                values (:prompt_text, :normalized_prompt_text)
                on conflict (normalized_prompt_text) do update
                set prompt_text = excluded.prompt_text
                returning id
                '''
            ),
            {'prompt_text': prompt_text, 'normalized_prompt_text': normalized},
        ).fetchone()
        return row[0]

    def _upsert_snapshot(
        self,
        conn,
        *,
        run_id: str,
        brand_name: str,
        market: str | None,
        language: str | None,
        source_system: str,
        snapshot_date: str | None = None,
        hero_score: float | None = None,
    ) -> str:
        brand_id = self._upsert_brand(conn, brand_name)
        # Key on brand+date (the vendor's actual reporting grain, parsed from
        # the filename) so replaying the same day's data upserts one snapshot
        # instead of creating a new one per run_id. Only fall back to run_id
        # for the rare file with no parseable date, so we don't silently
        # collapse genuinely distinct unknown-date snapshots together.
        snapshot_key = f'{normalize_key(brand_name)}|{snapshot_date or run_id}'
        row = conn.execute(
            text(
                '''
                insert into core.brand_snapshots (snapshot_key, snapshot_date, run_id, brand_id, ingestion_timestamp, market, language, source_system, hero_score)
                values (:snapshot_key, :snapshot_date, :run_id, :brand_id, :ingestion_timestamp, :market, :language, :source_system, :hero_score)
                on conflict (snapshot_key) do update
                set market = excluded.market, language = excluded.language, hero_score = coalesce(excluded.hero_score, core.brand_snapshots.hero_score)
                returning id
                '''
            ),
            {
                'snapshot_key': snapshot_key,
                'snapshot_date': snapshot_date,
                'run_id': run_id,
                'brand_id': brand_id,
                'ingestion_timestamp': datetime.now(timezone.utc),
                'market': market,
                'language': language,
                'source_system': source_system,
                'hero_score': hero_score,
            },
        ).fetchone()
        return row[0]

    def _upsert_llm_model(self, conn, provider_name: str, model_name: str | None) -> str:
        row = conn.execute(
            text(
                '''
                insert into core.llm_models (provider_name, model_name, normalized_provider_name, normalized_model_name)
                values (:provider_name, :model_name, :normalized_provider_name, :normalized_model_name)
                on conflict (normalized_provider_name, normalized_model_name) do update
                set provider_name = excluded.provider_name,
                    model_name = excluded.model_name
                returning id
                '''
            ),
            {
                'provider_name': provider_name,
                'model_name': model_name,
                'normalized_provider_name': normalize_key(provider_name),
                'normalized_model_name': normalize_key(model_name),
            },
        ).fetchone()
        return row[0]

    def _upsert_source(self, conn, source_name: str | None, source_url: str | None) -> str:
        normalized_url = normalize_url(source_url)
        normalized_name = normalize_key(source_name)
        row = conn.execute(
            text(
                '''
                insert into core.referenced_sources (source_name, source_url, normalized_source_name, normalized_source_url)
                values (:source_name, :source_url, :normalized_source_name, :normalized_source_url)
                on conflict (normalized_source_url) do update
                set source_name = excluded.source_name
                returning id
                '''
            ),
            {
                'source_name': source_name,
                'source_url': source_url,
                'normalized_source_name': normalized_name,
                'normalized_source_url': normalized_url,
            },
        ).fetchone()
        return row[0]

    def _upsert_statement(self, conn, statement_text: str) -> str:
        row = conn.execute(
            text(
                '''
                insert into accuracy.accuracy_statements (statement_text, normalized_statement_text)
                values (:statement_text, :normalized_statement_text)
                on conflict (normalized_statement_text) do update
                set statement_text = excluded.statement_text
                returning id
                '''
            ),
            {'statement_text': statement_text, 'normalized_statement_text': normalize_key(statement_text)},
        ).fetchone()
        return row[0]

    def _upsert_page(self, conn, page_url: str, page_label: str | None) -> str:
        row = conn.execute(
            text(
                '''
                insert into readiness.web_pages (page_url, normalized_page_url, page_label)
                values (:page_url, :normalized_page_url, :page_label)
                on conflict (normalized_page_url) do update
                set page_label = coalesce(excluded.page_label, readiness.web_pages.page_label)
                returning id
                '''
            ),
            {'page_url': page_url, 'normalized_page_url': normalize_url(page_url), 'page_label': page_label},
        ).fetchone()
        return row[0]

    def write_source_record_and_facts(self, payload: dict[str, Any]) -> int:
        row = payload['row']
        contract_id = payload['schema_contract_id']
        normalized_fact_count = 0
        with self._get_engine().begin() as conn:
            conn.execute(
                text(
                    '''
                    insert into ingestion.source_records (
                      source_record_id, run_id, file_id, source_row, schema_contract_id, schema_contract_version, row_hash, row_json
                    ) values (
                      :source_record_id, :run_id, :file_id, :source_row, :schema_contract_id, :schema_contract_version, :row_hash, cast(:row_json as jsonb)
                    )
                    on conflict (source_record_id) do update
                    set row_json = excluded.row_json
                    '''
                ),
                {
                    'source_record_id': payload['source_record_id'],
                    'run_id': payload['run_id'],
                    'file_id': payload['file_id'],
                    'source_row': payload['source_row'],
                    'schema_contract_id': payload['schema_contract_id'],
                    'schema_contract_version': payload['schema_contract_version'],
                    'row_hash': payload['row_hash'],
                    'row_json': _json(payload['raw_row']),
                },
            )
            self.counters.source_records += 1

            conn.execute(
                text(
                    '''
                    insert into ingestion.canonical_observations (
                      canonical_record_id, run_id, file_id, source_record_id, source_row, schema_family,
                      schema_contract_id, schema_contract_version, row_type_discriminator, adapter_version, metric_name, metric_value, text_value, qualifiers_json, record_hash
                    ) values (
                      :canonical_record_id, :run_id, :file_id, :source_record_id, :source_row, :schema_family,
                      :schema_contract_id, :schema_contract_version, :row_type_discriminator, :adapter_version, :metric_name, :metric_value, :text_value,
                      cast(:qualifiers_json as jsonb), :record_hash
                    )
                    on conflict (canonical_record_id) do update
                    set metric_name = excluded.metric_name,
                        metric_value = excluded.metric_value,
                        text_value = excluded.text_value,
                        qualifiers_json = excluded.qualifiers_json
                    '''
                ),
                {
                    'canonical_record_id': payload['canonical_record_id'],
                    'run_id': payload['run_id'],
                    'file_id': payload['file_id'],
                    'source_record_id': payload['source_record_id'],
                    'source_row': payload['source_row'],
                    'schema_family': payload['schema_family'],
                    'schema_contract_id': payload['schema_contract_id'],
                    'schema_contract_version': payload['schema_contract_version'],
                    'row_type_discriminator': row.get('rowType'),
                    'adapter_version': payload['adapter_version'],
                    'metric_name': payload.get('metric_name'),
                    'metric_value': payload.get('metric_value'),
                    'text_value': payload.get('text_value'),
                    'qualifiers_json': _json(payload.get('qualifiers', {})),
                    'record_hash': payload['row_hash'],
                },
            )
            self.counters.canonical_observations += 1

            snapshot_id = self._upsert_snapshot(
                conn,
                run_id=payload['run_id'],
                brand_name=payload['snapshot_brand'],
                market=payload.get('snapshot_market'),
                language=payload.get('snapshot_language'),
                source_system=payload['source_system'],
                snapshot_date=payload.get('snapshot_date'),
                hero_score=row.get('heroScore'),
            )

            if contract_id == 'AI_VISIBILITY_V1':
                prompt_id = self._upsert_prompt(conn, row['searchTerm'])
                if row['rowType'] == 'ranking':
                    ranked_brand_id = self._upsert_brand(conn, row['brandName'])
                    conn.execute(
                        text(
                            '''
                            insert into visibility.prompt_rankings (
                              snapshot_id, prompt_id, ranked_brand_id, cohort, rank_value, is_hero, source_record_id, canonical_record_id,
                              schema_contract_version, adapter_version, source_file_id, source_row
                            ) values (
                              :snapshot_id, :prompt_id, :ranked_brand_id, :cohort, :rank_value, :is_hero, :source_record_id, :canonical_record_id,
                              :schema_contract_version, :adapter_version, :source_file_id, :source_row
                            )
                            on conflict (canonical_record_id) do nothing
                            '''
                        ),
                        {
                            'snapshot_id': snapshot_id,
                            'prompt_id': prompt_id,
                            'ranked_brand_id': ranked_brand_id,
                            'cohort': row.get('cohort'),
                            'rank_value': row['rank'],
                            'is_hero': row.get('isHero'),
                            'source_record_id': payload['source_record_id'],
                            'canonical_record_id': payload['canonical_record_id'],
                            'schema_contract_version': payload['schema_contract_version'],
                            'adapter_version': payload['adapter_version'],
                            'source_file_id': payload['file_id'],
                            'source_row': payload['source_row'],
                        },
                    )
                    normalized_fact_count += 1
                else:
                    source_id = self._upsert_source(conn, row.get('sourceName'), row.get('sourceUrl'))
                    llm_model_id = None
                    if row.get('llm'):
                        llm_model_id = self._upsert_llm_model(conn, row['llm'], None)
                    conn.execute(
                        text(
                            '''
                            insert into visibility.prompt_sources (
                              snapshot_id, prompt_id, source_id, llm_model_id, source_name, source_url, source_record_id, canonical_record_id,
                              schema_contract_version, adapter_version, source_file_id, source_row
                            ) values (
                              :snapshot_id, :prompt_id, :source_id, :llm_model_id, :source_name, :source_url, :source_record_id, :canonical_record_id,
                              :schema_contract_version, :adapter_version, :source_file_id, :source_row
                            )
                            on conflict (canonical_record_id) do nothing
                            '''
                        ),
                        {
                            'snapshot_id': snapshot_id,
                            'prompt_id': prompt_id,
                            'source_id': source_id,
                            'llm_model_id': llm_model_id,
                            'source_name': row.get('sourceName'),
                            'source_url': row.get('sourceUrl'),
                            'source_record_id': payload['source_record_id'],
                            'canonical_record_id': payload['canonical_record_id'],
                            'schema_contract_version': payload['schema_contract_version'],
                            'adapter_version': payload['adapter_version'],
                            'source_file_id': payload['file_id'],
                            'source_row': payload['source_row'],
                        },
                    )
                    normalized_fact_count += 1

            elif contract_id == 'CONTENT_READINESS_V1':
                page_url = row.get('pageUrl') or f"brand_overview::{normalize_key(payload['snapshot_brand'])}"
                page_id = self._upsert_page(conn, page_url, row.get('pageLabel'))
                group_name = row['groupName']
                normalized_group = normalize_key(group_name)
                group_row = conn.execute(
                    text(
                        '''
                        insert into readiness.readiness_groups (
                          snapshot_id, page_id, group_name, normalized_group_name, source_record_id, canonical_record_id,
                          schema_contract_version, adapter_version, source_file_id, source_row
                        ) values (
                          :snapshot_id, :page_id, :group_name, :normalized_group_name, :source_record_id, :canonical_record_id,
                          :schema_contract_version, :adapter_version, :source_file_id, :source_row
                        )
                        on conflict (canonical_record_id, normalized_group_name) do update
                        set group_name = excluded.group_name
                        returning id
                        '''
                    ),
                    {
                        'snapshot_id': snapshot_id,
                        'page_id': page_id,
                        'group_name': group_name,
                        'normalized_group_name': normalized_group,
                        'source_record_id': payload['source_record_id'],
                        'canonical_record_id': payload['canonical_record_id'],
                        'schema_contract_version': payload['schema_contract_version'],
                        'adapter_version': payload['adapter_version'],
                        'source_file_id': payload['file_id'],
                        'source_row': payload['source_row'],
                    },
                ).fetchone()
                factor_name = row['factorName']
                conn.execute(
                    text(
                        '''
                        insert into readiness.readiness_factors (
                          snapshot_id, page_id, group_id, factor_name, normalized_factor_name, score, drawer_payload_json, drawer_payload_raw,
                          source_record_id, canonical_record_id, schema_contract_version, adapter_version, source_file_id, source_row
                        ) values (
                          :snapshot_id, :page_id, :group_id, :factor_name, :normalized_factor_name, :score, cast(:drawer_payload_json as jsonb), :drawer_payload_raw,
                          :source_record_id, :canonical_record_id, :schema_contract_version, :adapter_version, :source_file_id, :source_row
                        )
                        on conflict (canonical_record_id, normalized_factor_name) do update
                        set score = excluded.score,
                            drawer_payload_json = excluded.drawer_payload_json,
                            drawer_payload_raw = excluded.drawer_payload_raw
                        '''
                    ),
                    {
                        'snapshot_id': snapshot_id,
                        'page_id': page_id,
                        'group_id': group_row[0],
                        'factor_name': factor_name,
                        'normalized_factor_name': normalize_key(factor_name),
                        'score': row['score'],
                        'drawer_payload_json': _json(row.get('drawerPayloadJson')) if row.get('drawerPayloadJson') is not None else None,
                        'drawer_payload_raw': row.get('drawerPayloadRaw'),
                        'source_record_id': payload['source_record_id'],
                        'canonical_record_id': payload['canonical_record_id'],
                        'schema_contract_version': payload['schema_contract_version'],
                        'adapter_version': payload['adapter_version'],
                        'source_file_id': payload['file_id'],
                        'source_row': payload['source_row'],
                    },
                )
                normalized_fact_count += 2

            elif contract_id == 'VULNERABILITY_ACCURACY_V1':
                statement_id = self._upsert_statement(conn, row['statementText'])
                if row['rowType'] == 'summary':
                    conn.execute(
                        text(
                            '''
                            insert into accuracy.statement_observations (
                              snapshot_id, statement_id, statement_status, overall_score, consensus_accuracy_score, source_record_id, canonical_record_id,
                              schema_contract_version, adapter_version, source_file_id, source_row
                            ) values (
                              :snapshot_id, :statement_id, :statement_status, :overall_score, :consensus_accuracy_score, :source_record_id, :canonical_record_id,
                              :schema_contract_version, :adapter_version, :source_file_id, :source_row
                            )
                            on conflict (canonical_record_id) do update
                            set statement_status = excluded.statement_status,
                                overall_score = excluded.overall_score,
                                consensus_accuracy_score = excluded.consensus_accuracy_score
                            '''
                        ),
                        {
                            'snapshot_id': snapshot_id,
                            'statement_id': statement_id,
                            'statement_status': row.get('statementStatus'),
                            'overall_score': row.get('overallScore'),
                            'consensus_accuracy_score': row.get('consensusAccuracyScore'),
                            'source_record_id': payload['source_record_id'],
                            'canonical_record_id': payload['canonical_record_id'],
                            'schema_contract_version': payload['schema_contract_version'],
                            'adapter_version': payload['adapter_version'],
                            'source_file_id': payload['file_id'],
                            'source_row': payload['source_row'],
                        },
                    )
                    normalized_fact_count += 1
                else:
                    llm_model_id = self._upsert_llm_model(conn, row['llm'], row.get('model'))
                    conn.execute(
                        text(
                            '''
                            insert into accuracy.accuracy_assessments (
                              snapshot_id, statement_id, llm_model_id, llm_name, llm_status, llm_accuracy_score, llm_analysis,
                              source_record_id, canonical_record_id, schema_contract_version, adapter_version, source_file_id, source_row
                            ) values (
                              :snapshot_id, :statement_id, :llm_model_id, :llm_name, :llm_status, :llm_accuracy_score, :llm_analysis,
                              :source_record_id, :canonical_record_id, :schema_contract_version, :adapter_version, :source_file_id, :source_row
                            )
                            on conflict (canonical_record_id, llm_name) do update
                            set llm_status = excluded.llm_status,
                                llm_accuracy_score = excluded.llm_accuracy_score,
                                llm_analysis = excluded.llm_analysis
                            '''
                        ),
                        {
                            'snapshot_id': snapshot_id,
                            'statement_id': statement_id,
                            'llm_model_id': llm_model_id,
                            'llm_name': row.get('llm'),
                            'llm_status': row.get('llmStatus'),
                            'llm_accuracy_score': row['llmAccuracyScore'],
                            'llm_analysis': row.get('llmAnalysis'),
                            'source_record_id': payload['source_record_id'],
                            'canonical_record_id': payload['canonical_record_id'],
                            'schema_contract_version': payload['schema_contract_version'],
                            'adapter_version': payload['adapter_version'],
                            'source_file_id': payload['file_id'],
                            'source_row': payload['source_row'],
                        },
                    )
                    normalized_fact_count += 1

            elif contract_id == 'SEARCH_TERM_SUMMARY_V1':
                prompt_id = self._upsert_prompt(conn, row['text'])
                canonical_id = payload['canonical_record_id']
                conn.execute(
                    text(
                        '''
                        insert into visibility.prompt_summaries (
                          snapshot_id, prompt_id, category_name, score, label, trend, category_id, category_is_branded,
                          source_record_id, canonical_record_id, schema_contract_version, adapter_version, source_file_id, source_row, extra_columns_json
                        ) values (
                          :snapshot_id, :prompt_id, :category_name, :score, :label, :trend, :category_id, :category_is_branded,
                          :source_record_id, :canonical_record_id, :schema_contract_version, :adapter_version, :source_file_id, :source_row,
                          cast(:extra_columns_json as jsonb)
                        )
                        on conflict (canonical_record_id, category_name) do update
                        set score = excluded.score,
                            label = excluded.label,
                            trend = excluded.trend
                        '''
                    ),
                    {
                        'snapshot_id': snapshot_id,
                        'prompt_id': prompt_id,
                        'category_name': row.get('category_name'),
                        'score': row['score'],
                        'label': row.get('label'),
                                                'trend': row.get('trend'),
                        'category_id': row.get('category_id'),
                        'category_is_branded': row.get('category_is_branded'),
                        'source_record_id': payload['source_record_id'],
                        'canonical_record_id': canonical_id,
                        'schema_contract_version': payload['schema_contract_version'],
                        'adapter_version': payload['adapter_version'],
                        'source_file_id': payload['file_id'],
                        'source_row': payload['source_row'],
                        'extra_columns_json': _json(payload.get('extra_columns', {})),
                    },
                )
                normalized_fact_count += 1

                engine_columns = payload.get('engine_columns', {})
                for internal_column_key, score in engine_columns.items():
                    alias_row = conn.execute(
                        text('select llm_model_id, exclude_from_sv_score from core.llm_key_alias where internal_column_key = :key'),
                        {'key': internal_column_key},
                    ).fetchone()
                    alias_llm_model_id = alias_row[0] if alias_row else None
                    alias_excluded = bool(alias_row[1]) if alias_row else False
                    conn.execute(
                        text(
                            '''
                            insert into visibility.prompt_engine_scores (
                              snapshot_id, prompt_id, internal_column_key, llm_model_id, score, is_excluded_from_sv, source_record_id, canonical_record_id, schema_contract_version,
                              adapter_version, source_file_id, source_row
                            ) values (
                              :snapshot_id, :prompt_id, :internal_column_key, :llm_model_id, :score, :is_excluded_from_sv, :source_record_id, :canonical_record_id, :schema_contract_version,
                              :adapter_version, :source_file_id, :source_row
                            )
                            on conflict (canonical_record_id, internal_column_key) do update
                            set score = excluded.score,
                                llm_model_id = excluded.llm_model_id,
                                is_excluded_from_sv = excluded.is_excluded_from_sv
                            '''
                        ),
                        {
                            'snapshot_id': snapshot_id,
                            'prompt_id': prompt_id,
                            'internal_column_key': internal_column_key,
                            'llm_model_id': alias_llm_model_id,
                            'score': score,
                            'is_excluded_from_sv': alias_excluded,
                            'source_record_id': payload['source_record_id'],
                            'canonical_record_id': canonical_id,
                            'schema_contract_version': payload['schema_contract_version'],
                            'adapter_version': payload['adapter_version'],
                            'source_file_id': payload['file_id'],
                            'source_row': payload['source_row'],
                        },
                    )
                    normalized_fact_count += 1

        self.counters.normalized_facts += normalized_fact_count
        return normalized_fact_count


def extract_engine_columns(row: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    reserved = {
        'text',
        'score',
        'category_name',
        'label',
        'heroScore',
        'trend',
        'category_id',
        'category_is_branded',
    }
    engines: dict[str, float] = {}
    extra_columns: dict[str, Any] = {}
    for key, value in row.items():
        if key in reserved:
            continue
        if value in (None, ''):
            continue
        token = re.sub(r'[^A-Z0-9_]', '_', key.upper())
        try:
            engines[token] = float(value)
        except (TypeError, ValueError):
            extra_columns[key] = value
    return engines, extra_columns
