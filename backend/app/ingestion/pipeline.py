from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import json
import hashlib
import csv
import uuid
import polars as pl

from app.adapters.registry import fingerprint
from app.ingestion.contracts import SCHEMA_CONTRACTS, canonical_projection, classify_contract, validate_row
from app.ingestion.discovery import discover_files
from app.ingestion.parser import parse_delimited_bytes, row_hash
from app.services.db import Database
from app.services.postgres import PostgresWarehouse, extract_engine_columns
from app.settings import settings


@dataclass
class IngestionRunSummary:
    run_id: str
    physical_files: int
    unique_payloads: int
    total_rows: int
    parsed_rows: int
    rejected_rows: int
    empty_files: int
    duplicate_files: int
    quarantined_files: int
    archive_entries_discovered: int = 0
    storage_mode: str = 'duckdb'
    destination_status: dict[str, str] | None = None
    schema_contract_counts: dict[str, int] | None = None
    normalized_record_counts: dict[str, int] | None = None
    rejected_row_counts: dict[str, int] | None = None
    reconciliation_state: str = 'NOT_RUN'


def _infer_metadata(filename: str, physical_path: Path | None = None) -> dict[str, str | None]:
    lower = filename.lower()
    brand = lower.split('_')[0] if '_' in lower else None
    module = None

    # Directory name is a more reliable module signal than filename substrings:
    # many real vendor files (e.g. aveeno_search_term_*.csv, aveeno_search_prompts_*.csv,
    # aveeno_competitor_*.csv) live under a module-named folder but do not contain the
    # module name in the filename itself.
    dir_lower = str(physical_path.parent).lower() if physical_path is not None else ''
    if 'visibilitymodule' in dir_lower or dir_lower.endswith('/visibility') or dir_lower.endswith('\\visibility'):
        module = 'Visibility'
    elif 'contentreadinessmodule' in dir_lower:
        module = 'Content Readiness'
    elif 'aivulnerabilitymodule' in dir_lower:
        module = 'AI Vulnerability'
    elif 'overview' in dir_lower:
        module = 'Overview'

    if module is None:
        if 'visibility' in lower:
            module = 'Visibility'
        elif 'readiness' in lower or 'aicr' in lower:
            module = 'Content Readiness'
        elif 'vulnerability' in lower or 'accuracy_statement' in lower:
            module = 'AI Vulnerability'
        elif 'overview' in lower:
            module = 'Overview'

    date = None
    for part in lower.replace('.csv', '').replace('.tsv', '').split('_'):
        if len(part) == 10 and part[4] == '-' and part[7] == '-':
            date = part
            break

    return {
        'brand': brand,
        'module': module,
        'assessment_date': date,
        'market': None,
        'language': None,
    }


def _storage_mode() -> str:
    raw = (settings.storage_mode or 'duckdb').strip().lower()
    if raw not in {'duckdb', 'postgres', 'dual'}:
        raise RuntimeError(f'Invalid BAI_STORAGE_MODE "{settings.storage_mode}". Expected duckdb, postgres, or dual.')
    return raw


def _deferred_reason(filename: str) -> str | None:
    name = filename.lower()
    deferred_patterns = {
        'DEFERRED_VISIBILITY_HISTORICAL': ['_visibility_historical_'],
        'DEFERRED_READINESS_HISTORICAL': ['_readiness_historical_'],
        'DEFERRED_VULNERABILITY_HISTORICAL': ['_vulnerability_historical_'],
        'DEFERRED_VULNERABILITY_SWOT': ['_vulnerability_swot_'],
        'DEFERRED_COMPETITORS_CARD': ['_competitors_'],
        'DEFERRED_COMPETITOR_FLYOUT': ['_competitor_'],
        'DEFERRED_READINESS_GROUP_SCORES': ['_readiness_group_scores_'],
        'DEFERRED_READINESS_GROUP_BREAKDOWN': ['_content_readiness_group_breakdown_'],
        'DEFERRED_SITES_REFERENCED': ['_sites_referenced_'],
        'DEFERRED_CATEGORY_INSIGHTS': ['_category_strengths_', '_category_gaps_', '_category_competitors_'],
        'DEFERRED_VULNERABILITY_CATEGORIES': ['_vulnerability_categories_'],
        'DEFERRED_VULNERABILITY_PROMISE': ['_vulnerability_promise_'],
        'DEFERRED_BRAND_PROMISE_IMPROVEMENT': ['_brand_promise_improvement_'],
    }
    for reason, needles in deferred_patterns.items():
        if any(needle in name for needle in needles):
            return reason
    return None


def run_ingestion(
    input_root: Path,
    db: Database,
    output_dir: Path,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    guard_existing: bool = False,
    override_existing: bool = False,
) -> IngestionRunSummary:
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    discovered = discover_files(input_root)
    prompt_snapshot_keys: set[tuple[str | None, str | None]] = set()
    for _f in discovered:
        lname = _f.logical_name.lower()
        if 'search_prompts' in lname:
            _meta = _infer_metadata(_f.logical_name, _f.physical_path)
            prompt_snapshot_keys.add((_meta.get('brand'), _meta.get('assessment_date')))

    if progress_callback:
        progress_callback({
            'status': 'RUNNING', 'total_files': len(discovered), 'processed_files': 0,
            'percentage': 0.0, 'run_id': run_id, 'stage': 'Preparing input scan',
        })

    storage_mode = _storage_mode()
    payload_to_file_id: dict[str, str] = {}
    total_rows = parsed_rows = rejected_rows = empty_files = duplicate_files = quarantined_files = 0
    rejected_row_counts: dict[str, int] = {}
    schema_contract_counts: dict[str, int] = {}
    normalized_record_counts: dict[str, int] = {}
    archive_entries_discovered = sum({f.physical_path: f.archive_entries_discovered for f in discovered}.values())

    con = db.connect()
    postgres_writer: PostgresWarehouse | None = None
    destination_status: dict[str, str] = {'duckdb': 'SUCCESS', 'postgres': 'SKIPPED'}
    if storage_mode in {'dual', 'postgres'}:
        if not settings.postgres_url:
            con.close()
            raise RuntimeError('BAI_POSTGRES_URL must be configured when BAI_STORAGE_MODE is dual or postgres.')
        postgres_writer = PostgresWarehouse(settings.postgres_url)
        destination_status['postgres'] = 'SUCCESS'
        postgres_writer.write_run(
            run_id=run_id,
            source_system=settings.source_system,
            brand_id=settings.brand_id,
            market=settings.market,
            language=settings.language,
            storage_mode=storage_mode,
            destination_status=destination_status,
        )
        for contract in SCHEMA_CONTRACTS:
            postgres_writer.write_contract(
                {
                    'contract_id': contract.contract_id,
                    'contract_version': contract.version,
                    'schema_family': contract.schema_family,
                    'required_headers': list(contract.required_headers),
                    'optional_headers': list(contract.optional_headers),
                }
            )

    if guard_existing and not override_existing and discovered:
        payloads = [f.sha256 for f in discovered]
        existing = con.execute(
            'select count(*) from file_manifest where payload_sha256 in (select unnest(?))', [payloads]
        ).fetchone()[0]
        if existing:
            con.close()
            raise RuntimeError('Existing input payloads detected. Use the demo override password to re-ingest them.')

    for file_number, f in enumerate(discovered, start=1):
        try:
            parsed = parse_delimited_bytes(f.bytes_data, f.logical_name)
            schema_fp = fingerprint(parsed.headers)
            contract_match = classify_contract(parsed.headers)
        except Exception as exc:
            quarantined_files += 1
            con.execute(
                '''insert into file_manifest (
                   run_id, file_id, physical_path, archive_chain, original_filename,
                   byte_size, sha256, payload_sha256, ingestion_status, error_message
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [run_id, f.file_id, str(f.physical_path), f.archive_chain, f.logical_name,
                 len(f.bytes_data), f.sha256, f.sha256, 'QUARANTINED_PARSE_ERROR', str(exc)],
            )
            con.execute(
                'insert into ingestion_errors (run_id, file_id, source_row, error_type, error_message, raw_row) values (?, ?, ?, ?, ?, ?)',
                [run_id, f.file_id, 0, 'parse_error', str(exc), json.dumps({'filename': f.logical_name})],
            )
            rejected_row_counts['parse_error'] = rejected_row_counts.get('parse_error', 0) + 1
            if postgres_writer is not None:
                destination_status['postgres'] = 'PARTIAL_FAILURE'
                postgres_writer.write_error(
                    run_id=run_id,
                    file_id=f.file_id,
                    source_row=0,
                    error_type='parse_error',
                    error_message=str(exc),
                    field_name=None,
                    raw_row={'filename': f.logical_name},
                )
            if progress_callback:
                progress_callback({
                    'status': 'RUNNING', 'total_files': len(discovered), 'processed_files': file_number,
                    'percentage': round((file_number / len(discovered) * 100) if discovered else 100.0, 1),
                    'run_id': run_id, 'stage': f'Quarantined parse error: {f.logical_name}',
                })
            continue

        payload_sha = f.sha256
        duplicate_of = payload_to_file_id.get(payload_sha)
        if duplicate_of is None:
            payload_to_file_id[payload_sha] = f.file_id
        else:
            duplicate_files += 1

        row_count = len(parsed.rows)
        rej_count = len(parsed.rejected_rows)
        total_rows += row_count
        parsed_rows += row_count
        rejected_rows += rej_count

        is_empty = row_count == 0
        if is_empty:
            empty_files += 1

        meta = _infer_metadata(f.logical_name, f.physical_path)
        deferred_reason = _deferred_reason(f.logical_name)
        is_legacy_visibility_summary = 'visibility_search_terms' in f.logical_name.lower()
        is_superseded = is_legacy_visibility_summary and (meta.get('brand'), meta.get('assessment_date')) in prompt_snapshot_keys


        status = 'SUPPORTED'
        error_message = None
        contract = contract_match.contract
        schema_family = contract.schema_family if contract is not None else 'unsupported_schema'
        adapter_name = f"{contract.contract_id.lower()}_adapter" if contract is not None else 'unknown_adapter'
        adapter_version = contract.version if contract is not None else '0.0.0'
        schema_contract_id = contract.contract_id if contract is not None else None
        schema_contract_version = contract.version if contract is not None else None
        schema_drift = list(contract_match.additional_headers)
        if deferred_reason is not None:
            status = f'QUARANTINED_{deferred_reason}'
            quarantined_files += 1
            error_message = f'Deferred schema family: {deferred_reason}'
        elif is_superseded:
            status = 'SUPERSEDED_BY_SEARCH_PROMPTS'
            error_message = 'Legacy visibility_search_terms superseded by search_prompts for same brand/date'
        elif contract_match.status == 'MISSING_REQUIRED_HEADERS':
            status = 'QUARANTINED_MISSING_HEADERS'
            quarantined_files += 1
            error_message = f"Missing required headers: {', '.join(contract_match.missing_required_headers)}"
        elif contract_match.status == 'AMBIGUOUS':
            status = 'QUARANTINED_AMBIGUOUS_SCHEMA'
            quarantined_files += 1
            error_message = f"Ambiguous schema match: {', '.join(contract_match.candidate_contract_ids)}"
        elif contract_match.status == 'UNSUPPORTED':
            status = 'EMPTY_UNSUPPORTED' if is_empty else 'QUARANTINED_UNSUPPORTED'
            if not is_empty:
                quarantined_files += 1
                error_message = 'Unsupported non-empty schema quarantined'
        elif contract_match.status == 'MATCHED' and contract is not None:
            schema_contract_counts[contract.contract_id] = schema_contract_counts.get(contract.contract_id, 0) + 1

        con.execute(
            '''
            insert into file_manifest (
              run_id, file_id, physical_path, archive_chain, original_filename, byte_size, sha256, payload_sha256,
              archive_entries_discovered,
              delimiter, encoding, schema_fingerprint, schema_contract_id, schema_contract_version, schema_drift_json,
              header_json, row_count, parsed_row_count, rejected_row_count,
              is_empty, duplicate_of_file_id, inferred_brand, inferred_module, inferred_assessment_date, inferred_market,
              inferred_language, adapter_name, adapter_version, destination_status_json, ingestion_status, error_message
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                run_id, f.file_id, str(f.physical_path), f.archive_chain, f.logical_name, len(f.bytes_data), f.sha256, payload_sha,
                f.archive_entries_discovered,
                parsed.delimiter, parsed.encoding, schema_fp, schema_contract_id, schema_contract_version, json.dumps(schema_drift),
                json.dumps(parsed.headers), row_count, row_count, rej_count,
                is_empty, duplicate_of, meta['brand'], meta['module'], meta['assessment_date'], meta['market'],
                meta['language'], adapter_name, adapter_version, json.dumps(destination_status), status, error_message
            ]
        )
        if postgres_writer is not None:
            try:
                postgres_writer.write_source_file(
                    {
                        'run_id': run_id,
                        'file_id': f.file_id,
                        'source_path': str(f.physical_path),
                        'archive_chain': f.archive_chain,
                        'original_filename': f.logical_name,
                        'payload_sha256': payload_sha,
                        'schema_fingerprint': schema_fp,
                        'schema_contract_id': schema_contract_id,
                        'schema_contract_version': schema_contract_version,
                        'schema_family': schema_family,
                        'schema_drift': schema_drift,
                        'ingestion_status': status,
                        'error_message': error_message,
                        'row_count': row_count,
                        'parsed_row_count': row_count,
                        'rejected_row_count': rej_count,
                    }
                )
            except Exception:
                destination_status['postgres'] = 'PARTIAL_FAILURE'

        for source_row, err_type, raw_row in parsed.rejected_rows:
            con.execute(
                'insert into ingestion_errors (run_id, file_id, source_row, error_type, error_message, raw_row) values (?, ?, ?, ?, ?, ?)',
                [run_id, f.file_id, source_row, err_type, err_type, json.dumps(raw_row, ensure_ascii=False)]
            )
            rejected_row_counts[err_type] = rejected_row_counts.get(err_type, 0) + 1
            if postgres_writer is not None:
                try:
                    postgres_writer.write_error(
                        run_id=run_id,
                        file_id=f.file_id,
                        source_row=source_row,
                        error_type=err_type,
                        error_message=err_type,
                        field_name=None,
                        raw_row=raw_row if isinstance(raw_row, dict) else {'value': raw_row},
                    )
                except Exception:
                    destination_status['postgres'] = 'PARTIAL_FAILURE'

        if duplicate_of is not None or status.startswith('QUARANTINED') or status.startswith('EMPTY_UNSUPPORTED'):
            # keep manifest, skip canonical row insert to avoid duplicate counting
            if progress_callback:
                progress_callback({
                    'status': 'RUNNING', 'total_files': len(discovered), 'processed_files': file_number,
                    'percentage': round((file_number / len(discovered) * 100) if discovered else 100.0, 1),
                    'run_id': run_id, 'stage': 'Checking duplicate payload',
                })
            continue

        for i, row in enumerate(parsed.rows, start=2):
            row_h = row_hash(row)
            record_id = hashlib.sha256(f"{f.file_id}|{i}|{row_h}".encode('utf-8')).hexdigest()[:32]
            validation = validate_row(contract, row)
            if not validation.accepted:
                rejected_rows += 1
                rejected_row_counts[validation.row_error_type or 'invalid_row'] = rejected_row_counts.get(validation.row_error_type or 'invalid_row', 0) + 1
                con.execute(
                    'insert into ingestion_errors (run_id, file_id, source_row, error_type, error_message, raw_row) values (?, ?, ?, ?, ?, ?)',
                    [
                        run_id,
                        f.file_id,
                        i,
                        validation.row_error_type or 'invalid_row',
                        validation.row_error_message or 'Row rejected',
                        json.dumps(row, ensure_ascii=False, default=str),
                    ],
                )
                if postgres_writer is not None:
                    try:
                        postgres_writer.write_error(
                            run_id=run_id,
                            file_id=f.file_id,
                            source_row=i,
                            error_type=validation.row_error_type or 'invalid_row',
                            error_message=validation.row_error_message or 'Row rejected',
                            field_name=None,
                            raw_row=row,
                        )
                    except Exception:
                        destination_status['postgres'] = 'PARTIAL_FAILURE'
                continue

            metric_name, metric_value, text_value = canonical_projection(contract, validation.normalized_row)
            source_record_id = hashlib.sha256(f"{run_id}|{f.file_id}|{i}".encode('utf-8')).hexdigest()[:32]
            qualifiers_row = dict(validation.normalized_row)
            if contract.contract_id == 'CONTENT_READINESS_V1' and qualifiers_row.get('isBrandOverview'):
                qualifiers_row['pageUrl'] = f"brand_overview::{(meta.get('brand') or settings.brand_id).lower()}"
            engine_columns: dict[str, float] = {}
            extra_columns: dict[str, Any] = {}
            if contract.contract_id == 'SEARCH_TERM_SUMMARY_V1':
                engine_columns, extra_columns = extract_engine_columns(row)
                qualifiers_row['engineColumns'] = engine_columns
                qualifiers_row['unmappedColumns'] = extra_columns
            if validation.additional_fields:
                qualifiers_row['validationFlags'] = validation.additional_fields

            qualifiers = {
                'row': qualifiers_row,
                'filename': f.logical_name,
                'archive_chain': f.archive_chain,
                'assessment_date': meta['assessment_date'],
                'module': meta['module'],
                'schema_contract_id': contract.contract_id,
                'schema_contract_version': contract.version,
                'schema_drift_columns': schema_drift,
                'source_system': settings.source_system,
                'context_provenance': {
                    'brand': 'ACQUISITION_CONFIG',
                    'market': 'ACQUISITION_CONFIG',
                    'language': 'ACQUISITION_CONFIG',
                },
            }

            try:
                con.execute(
                    '''
                    insert into canonical_observations (
                      run_id, record_id, file_id, payload_sha256, source_row, schema_family, schema_contract_id, schema_contract_version,
                      row_type_discriminator, module, metric_name, metric_value, text_value, qualifiers_json, record_hash, adapter_version, observation_state
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    [
                        run_id,
                        record_id,
                        f.file_id,
                        payload_sha,
                        i,
                        schema_family,
                        contract.contract_id,
                        contract.version,
                        validation.normalized_row.get('rowType'),
                        meta['module'],
                        metric_name,
                        metric_value,
                        text_value,
                        json.dumps(qualifiers, ensure_ascii=False),
                        row_h,
                        adapter_version,
                        'OBSERVATION',
                    ]
                )

                # Domain extraction is best-effort. A malformed URL must not
                # prevent the canonical observation or the next row/file from
                # being processed.
                for k, v in row.items():
                    if v is None:
                        continue
                    if 'url' in k.lower() and str(v).startswith('http'):
                        url = str(v)
                        domain = url.split('/')[2] if '://' in url else None
                        con.execute(
                            'insert into source_domains (run_id, record_id, file_id, domain, url, source_row) values (?, ?, ?, ?, ?, ?)',
                            [run_id, record_id, f.file_id, domain, url, i]
                        )

                normalized_record_counts[contract.contract_id] = normalized_record_counts.get(contract.contract_id, 0) + 1

                if postgres_writer is not None:
                    try:
                        postgres_writer.write_source_record_and_facts(
                            {
                                'run_id': run_id,
                                'file_id': f.file_id,
                                'source_row': i,
                                'source_record_id': source_record_id,
                                'canonical_record_id': record_id,
                                'schema_family': schema_family,
                                'schema_contract_id': contract.contract_id,
                                'schema_contract_version': contract.version,
                                'adapter_version': adapter_version,
                                'row_hash': row_h,
                                'metric_name': metric_name,
                                'metric_value': metric_value,
                                'text_value': text_value,
                                'row': validation.normalized_row,
                                'raw_row': row,
                                'qualifiers': qualifiers,
                                'snapshot_brand': meta['brand'] or settings.brand_display,
                                'snapshot_market': meta['market'] or settings.market,
                                'snapshot_language': meta['language'] or settings.language,
                                'snapshot_date': meta['assessment_date'],
                                'source_system': settings.source_system,
                                'engine_columns': engine_columns,
                                'extra_columns': extra_columns,
                            }
                        )
                    except Exception as exc:
                        destination_status['postgres'] = 'PARTIAL_FAILURE'
                        con.execute(
                            'insert into ingestion_errors (run_id, file_id, source_row, error_type, error_message, raw_row) values (?, ?, ?, ?, ?, ?)',
                            [
                                run_id,
                                f.file_id,
                                i,
                                'postgres_write_error',
                                str(exc),
                                json.dumps(row, ensure_ascii=False, default=str),
                            ],
                        )
                        rejected_row_counts['postgres_write_error'] = rejected_row_counts.get('postgres_write_error', 0) + 1
            except Exception as exc:
                # Keep the ingestion run moving when one row cannot be
                # canonicalised. The raw row and exact reason remain visible
                # through /api/ingestion-errors.
                rejected_rows += 1
                con.execute(
                    'insert into ingestion_errors (run_id, file_id, source_row, error_type, error_message, raw_row) values (?, ?, ?, ?, ?, ?)',
                    [run_id, f.file_id, i, 'canonicalization_error', str(exc), json.dumps(row, ensure_ascii=False, default=str)]
                )
                rejected_row_counts['canonicalization_error'] = rejected_row_counts.get('canonicalization_error', 0) + 1
                if progress_callback:
                    progress_callback({
                        'status': 'RUNNING', 'total_files': len(discovered), 'processed_files': file_number,
                        'percentage': round((file_number / len(discovered) * 100) if discovered else 100.0, 1),
                        'run_id': run_id, 'stage': f'Skipped invalid row {i} in {f.logical_name}; continuing',
                    })

        if progress_callback:
            progress_callback({
                'status': 'RUNNING', 'total_files': len(discovered), 'processed_files': file_number,
                'percentage': round((file_number / len(discovered) * 100) if discovered else 100.0, 1),
                'run_id': run_id, 'stage': 'Writing canonical observations',
            })

    # export required artifacts
    output_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"copy (select * from file_manifest where run_id = '{run_id}') to '{output_dir / 'file_manifest.csv'}' (header, delimiter ',')")
    con.execute(f"copy (select * from canonical_observations where run_id = '{run_id}') to '{output_dir / 'canonical_observations.parquet'}' (format 'parquet')")
    con.execute(f"copy (select * from file_manifest where run_id = '{run_id}') to '{output_dir / 'schema_registry_report.csv'}' (header, delimiter ',')")

    # The legacy activation_candidates table was removed in favour of the
    # signal -> intervention -> outcome model. Do not query a nonexistent
    # table; consumers can use the canonical artifacts and intervention APIs.
    (output_dir / 'activation_candidates.json').write_text('[]', encoding='utf-8')

    # transparency gaps (heuristic retired, exporting empty template)
    pl.DataFrame({
        'record_id': [],
        'file_id': [],
        'source_row': [],
        'schema_family': [],
        'module': [],
        'metric_name': [],
        'metric_value': [],
        'gap_severity': [],
    }).write_csv(output_dir / 'transparency_gap_register.csv')

    template = pl.DataFrame(
        {
            'intervention_id': [],
            'product_id_sku': [],
            'product_name': [],
            'market': [],
            'language': [],
            'canonical_page_url': [],
            'full_ingredients': [],
            'ingredient_purposes': [],
            'fragrance_allergen_disclosure': [],
            'approved_claim_text': [],
            'claim_scope_qualification': [],
            'evidence_title': [],
            'evidence_url_reference': [],
            'evidence_owner': [],
            'directions_warnings_suitability': [],
            'packaging_material': [],
            'recycled_content_methodology': [],
            'recyclability_methodology': [],
            'approved_sourcing_statement': [],
            'content_owner': [],
            'approver': [],
            'approval_status': [],
            'approval_reference_id': [],
            'last_reviewed_date': [],
            'expiry_review_date': [],
        }
    )
    template.write_csv(output_dir / 'product_truth_template.csv')

    # Product truth readiness snapshot
    readiness_path = output_dir / 'product_truth_readiness.csv'
    with readiness_path.open('w', newline='', encoding='utf-8') as f_readiness:
        writer = csv.DictWriter(
            f_readiness,
            fieldnames=[
                'run_id',
                'product_id_sku',
                'product_name',
                'approval_status',
                'missing_required_fields',
                'readiness_state',
            ],
        )
        writer.writeheader()

    # Before/after intervention report placeholder
    con.execute(
        f"copy (select * from intervention_measurements where run_id = '{run_id}') to '{output_dir / 'before_after_intervention_report.csv'}' (header, delimiter ',')"
    )

    # Activation brief placeholders (filled after activation generation)
    (output_dir / 'activation_brief.md').write_text(
        '# Activation Brief\n\nRun activation generation to populate this brief.\n',
        encoding='utf-8',
    )
    (output_dir / 'activation_brief.json').write_text('{}', encoding='utf-8')

    # Data quality report
    quality_rows = con.execute(
        '''
        select
          ? as run_id,
          count(*) as physical_files,
          count(distinct payload_sha256) as unique_payloads,
          sum(case when is_empty then 1 else 0 end) as empty_files,
          sum(case when duplicate_of_file_id is not null then 1 else 0 end) as duplicate_files,
          sum(case when ingestion_status = 'QUARANTINED_UNSUPPORTED' then 1 else 0 end) as quarantined_unsupported_files,
          sum(row_count) as total_source_rows,
          sum(parsed_row_count) as total_parsed_rows,
          sum(rejected_row_count) as total_rejected_rows
        from file_manifest
        where run_id = ?
        ''',
        [run_id, run_id],
    ).fetchone()
    quality_report = {
        'run_id': quality_rows[0],
        'physical_files': int(quality_rows[1] or 0),
        'unique_payloads': int(quality_rows[2] or 0),
        'empty_files': int(quality_rows[3] or 0),
        'duplicate_files': int(quality_rows[4] or 0),
        'quarantined_unsupported_files': int(quality_rows[5] or 0),
        'total_source_rows': int(quality_rows[6] or 0),
        'total_parsed_rows': int(quality_rows[7] or 0),
        'total_rejected_rows': int(quality_rows[8] or 0),
        'schema_contract_counts': schema_contract_counts,
        'normalized_record_counts': normalized_record_counts,
        'rejected_row_counts': rejected_row_counts,
        'destination_status': destination_status,
    }
    if postgres_writer is not None:
        quality_report['postgres'] = {
            'source_files': postgres_writer.counters.source_files,
            'source_records': postgres_writer.counters.source_records,
            'canonical_observations': postgres_writer.counters.canonical_observations,
            'normalized_facts': postgres_writer.counters.normalized_facts,
            'rejected_rows': postgres_writer.counters.rejected_rows,
            'schema_drift_columns': postgres_writer.counters.schema_drift_columns,
        }
    (output_dir / 'data_quality_report.json').write_text(json.dumps(quality_report, indent=2), encoding='utf-8')

    # Insert assessment run context
    run_context = con.execute('''
        select 
            max(inferred_brand), 
            max(inferred_market), 
            max(inferred_language), 
            max(inferred_assessment_date)
        from file_manifest
        where run_id = ?
    ''', [run_id]).fetchone()
    
    con.execute('''
        insert into assessment_runs (
          run_id, source_system, brand_id, market, language, module, acquisition_date,
          vendor_assessment_date, context_provenance_json, ingestion_run_id, quality_status, acquired_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        run_id, settings.source_system, run_context[0] or settings.brand_id,
        run_context[1] or settings.market, run_context[2] or settings.language,
        None, run_context[3], run_context[3],
        json.dumps({'brand': 'ACQUISITION_CONFIG', 'market': 'ACQUISITION_CONFIG', 'language': 'ACQUISITION_CONFIG'}),
        run_id, ('PARTIAL_FAILURE' if 'PARTIAL_FAILURE' in destination_status.values() else 'PROVISIONAL'), datetime.now(timezone.utc),
    ])

    if postgres_writer is not None:
        final_status = 'PARTIAL_FAILURE' if 'PARTIAL_FAILURE' in destination_status.values() else 'COMPLETED'
        postgres_writer.complete_run(run_id, final_status, destination_status)

    con.close()

    unique_payloads = len(payload_to_file_id)
    summary = IngestionRunSummary(
        run_id=run_id,
        physical_files=len(discovered),
        unique_payloads=unique_payloads,
        total_rows=total_rows,
        parsed_rows=parsed_rows,
        rejected_rows=rejected_rows,
        empty_files=empty_files,
        duplicate_files=duplicate_files,
        quarantined_files=quarantined_files,
        archive_entries_discovered=archive_entries_discovered,
        storage_mode=storage_mode,
        destination_status=destination_status,
        schema_contract_counts=schema_contract_counts,
        normalized_record_counts=normalized_record_counts,
        rejected_row_counts=rejected_row_counts,
        reconciliation_state='PARTIAL_FAILURE' if 'PARTIAL_FAILURE' in destination_status.values() else 'READY',
    )
    if progress_callback:
        progress_callback({
            'status': 'COMPLETED', 'total_files': summary.physical_files,
            'processed_files': summary.physical_files, 'percentage': 100.0,
            'run_id': run_id, 'stage': 'Ingestion complete', 'summary': summary.__dict__,
        })
    return summary
