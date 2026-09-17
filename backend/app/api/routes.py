from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
import json
import uuid

from app.models.schemas import (
    ChatCitation,
    ClaimTruthRecord,
    ContentAssetRecord,
    DatasetStatus,
    FileManifestRecord,
    IngestionOverviewResponse,
    IngestionModuleRecord,
    IngestionSchemaRecord,
    OntologyEntityRecord,
    OntologyFieldRecord,
    IngestionSummary,
    IngestionStartRequest,
    IngestionProgressRecord,
    IngestionErrorRecord,
    InterventionBriefResponse,
    InterventionCreateRequest,
    InterventionListResponse,
    InterventionRecord,
    InterventionTransitionRequest,
    InterventionUpdateRequest,
    LeadershipChatRequest,
    LeadershipChatResponse,
    MeasureInterventionRequest,
    ObservationQuery,
    ObservationRecord,
    OutcomeRecord,
    PromptPriorityRecord,
    ReferenceChecks,
    SchemaSummaryRecord,
    SeedFixturesResponse,
    SignalComparisonItem,
    SignalComparisonsResponse,
    SignalEvaluateResponse,
    SignalEvidenceRecord,
    SignalHistoryPoint,
    SignalInstanceRecord,
    MetricContractRecord,
    SchemaContractRecord,
    AssessmentRunRecord,
    SemanticBlockerRecord,
    VendorQuestionRecord,
    CurrentContextRecord,
    EvidenceExplorerRecord,
    EvidenceExplorerResponse,
)
from app.analytics.signals import (
    evaluate_signals,
    audit_signal_coverage,
    business_signal_fields,
    get_signal_comparisons,
    get_signal_evidence,
    get_signal_history,
    load_rules,
    persist_signal_instances,
)
from app.agents.leadership_chat import ask_leadership_question
from app.services.db import Database
from app.services.interventions import (
    create_intervention,
    fetch_intervention,
    generate_brief,
    list_interventions,
    transition_intervention,
    update_intervention,
)
from app.services.outcomes import (
    fetch_outcome,
    list_outcomes,
    measure_intervention,
)
from app.services.fixtures import seed_poc_fixtures
from app.settings import settings, effective_api_key, effective_api_base, effective_chat_deployment, effective_llm_mode
from app.ingestion.pipeline import run_ingestion

router = APIRouter()
db = Database(settings.db_path)
DEMO_INGEST_OVERRIDE_PASSWORD = 'KENVUE-DEMO-2026'
_ingestion_jobs: dict[str, dict] = {}


def _latest_file_run(con) -> str | None:
    row = con.execute('''
        select run_id
        from file_manifest
        group by run_id
        order by max(ingested_at) desc nulls last, run_id desc
        limit 1
    ''').fetchone()
    return row[0] if row else None


@router.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/health/ai')
def health_ai() -> dict[str, str | bool]:
    api_key = effective_api_key()
    endpoint = effective_api_base()
    deployment = effective_chat_deployment()
    llm_mode = effective_llm_mode()

    llm_configured = bool(api_key and endpoint and (settings.openai_model if llm_mode == 'managed_responses' else deployment))
    llm_configured_valid = llm_configured and api_key not in {'YOUR_OPENAI_API_KEY', 'YOUR_AZURE_OPENAI_API_KEY'}

    con = db.connect()
    try:
        con.execute('select 1')
        database_healthy = True
    except Exception:
        database_healthy = False
    finally:
        con.close()

    evidence_retrieval_healthy = database_healthy

    llm_reachable = False
    if llm_configured_valid:
        try:
            if llm_mode == 'managed_responses':
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=endpoint, default_headers={'apikey': api_key})
                client.responses.create(model=settings.openai_model, input='health check', max_output_tokens=1)
                llm_reachable = True
            else:
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    api_key=api_key,
                    api_version=settings.openai_api_version,
                    azure_endpoint=endpoint,
                )
                client.models.list()
                llm_reachable = True
        except Exception:
            llm_reachable = False

    synthesis_mode = 'llm' if (llm_configured_valid and llm_reachable) else 'evidence_fallback'

    return {
        'api': 'healthy',
        'database': 'healthy' if database_healthy else 'unhealthy',
        'evidence_retrieval': 'healthy' if evidence_retrieval_healthy else 'unhealthy',
        'llm_configured': llm_configured_valid,
        'llm_reachable': llm_reachable,
        'synthesis_mode': synthesis_mode,
    }


@router.get('/context/current', response_model=CurrentContextRecord)
def current_context() -> CurrentContextRecord:
    con = db.connect()
    row = con.execute('''
        select run_id, source_system, brand_id, market, language, context_provenance_json, quality_status
        from assessment_runs order by ingested_at desc limit 1
    ''').fetchone()
    if row is None:
        con.close()
        return CurrentContextRecord(
            brand_id=settings.brand_id, brand_display=settings.brand_display, market=settings.market,
            language=settings.language, assessment_run_id=None, source_system=settings.source_system,
            semantic_trust_state='UNRESOLVED',
            context_provenance={'brand': 'ACQUISITION_CONFIG', 'market': 'ACQUISITION_CONFIG', 'language': 'ACQUISITION_CONFIG'},
        )
    blockers = con.execute("select count(*) from semantic_blockers where status = 'ACTIVE'").fetchone()[0]
    con.close()
    provenance = json.loads(row[5]) if row[5] else {}
    return CurrentContextRecord(
        brand_id=row[2] or settings.brand_id,
        brand_display=settings.brand_display,
        market=row[3] or settings.market,
        language=row[4] or settings.language,
        assessment_run_id=row[0],
        source_system=row[1] or settings.source_system,
        semantic_trust_state='BLOCKED' if blockers else (row[6] or 'PROVISIONAL'),
        context_provenance=provenance,
    )


@router.get('/signal-rules')
def signal_rules() -> list[dict]:
    return [
        {
            'signal_rule_id': r.signal_rule_id, 'version': r.version, 'name': r.name,
            'signal_type': r.signal_type, 'enabled': r.enabled, 'governance_status': r.governance_status,
            'rule_source': r.rule_source, 'blocked_reason': r.blocked_reason,
            'metric_contract_dependencies': r.metric_contract_dependencies,
            'minimum_metric_validation_status': r.minimum_metric_validation_status,
            'known_limitations': r.known_limitations,
        }
        for r in load_rules()
    ]


@router.get('/evidence', response_model=EvidenceExplorerResponse)
def evidence_explorer(
    query: str | None = None,
    evidence_type: str | None = None,
    assessment_run_id: str | None = None,
    signal_instance_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> EvidenceExplorerResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    con = db.connect()
    run_id = assessment_run_id or _latest_file_run(con)
    where = ['c.run_id = ?']
    params: list[object] = [run_id]
    if query:
        where.append("""(
            lower(coalesce(c.record_id, '')) like ?
            or lower(coalesce(c.file_id, '')) like ?
            or lower(coalesce(c.payload_sha256, '')) like ?
            or lower(coalesce(c.text_value, '')) like ?
            or lower(coalesce(c.metric_name, '')) like ?
            or lower(coalesce(c.qualifiers_json, '')) like ?
            or exists (
              select 1 from file_manifest m2
              where m2.run_id = c.run_id and m2.file_id = c.file_id
                and lower(coalesce(m2.original_filename, '')) like ?
            )
        )""")
        needle = f'%{query.lower()}%'
        params.extend([needle, needle, needle, needle, needle, needle, needle])
    if signal_instance_id:
        where.append('exists (select 1 from signal_evidence se where se.signal_instance_id = ? and se.record_id = c.record_id and se.assessment_run_id = c.run_id)')
        params.append(signal_instance_id)
    if evidence_type and evidence_type.upper() == 'DEMO_FIXTURE':
        where.append("lower(coalesce(c.qualifiers_json, '')) like '%demo_fixture%'")
    where_sql = ' and '.join(where)
    total = con.execute(f'select count(*) from canonical_observations c where {where_sql}', params).fetchone()[0]
    rows = con.execute(f'''
        select c.record_id, c.file_id, c.source_row, c.run_id, c.metric_name, c.metric_value,
               c.text_value, c.payload_sha256, c.qualifiers_json, m.original_filename
        from canonical_observations c
        left join file_manifest m on m.file_id = c.file_id and m.run_id = c.run_id
        where {where_sql}
        order by c.source_row asc limit ? offset ?
    ''', [*params, limit, offset]).fetchall()
    con.close()
    items = []
    for idx, row in enumerate(rows, start=offset + 1):
        qualifiers = json.loads(row[8]) if row[8] else {}
        items.append(EvidenceExplorerRecord(
            evidence_ref=f'E{idx}', evidence_type=evidence_type or ('DEMO_FIXTURE' if 'DEMO_FIXTURE' in str(qualifiers) else 'BRANDRANK_OBSERVATION'),
            record_id=row[0], file_id=row[1], source_row=row[2], assessment_run_id=row[3],
            title=row[4] or row[6] or row[9] or 'Canonical observation',
            detail=f"{row[4] or 'Observation'} = {row[5] if row[5] is not None else row[6] or 'n/a'}",
            payload_sha256=row[7], qualifiers=qualifiers,
        ))
    return EvidenceExplorerResponse(items=items, total_count=int(total), limit=limit, offset=offset)


def _run_ingestion_job(job_id: str, override_existing: bool) -> None:
    def update_progress(patch: dict) -> None:
        _ingestion_jobs[job_id].update(patch)

    try:
        summary = run_ingestion(
            settings.input_root,
            db,
            settings.output_dir,
            progress_callback=update_progress,
            guard_existing=True,
            override_existing=override_existing,
        )
        update_progress({
            'status': 'RUNNING',
            'total_files': summary.physical_files,
            'processed_files': summary.physical_files,
            'percentage': 99.0,
            'run_id': summary.run_id,
            'stage': 'Evaluating governed and experimental signals',
        })
        eval_con = db.connect()
        try:
            evaluated = evaluate_signals(
                eval_con,
                summary.run_id,
                brand_id=settings.brand_id,
                brand_display=settings.brand_display,
                market=settings.market,
            )
            persist_signal_instances(eval_con, summary.run_id, evaluated)
        finally:
            eval_con.close()
        _ingestion_jobs[job_id].update({
            'status': 'COMPLETED',
            'total_files': summary.physical_files,
            'processed_files': summary.physical_files,
            'percentage': 100.0,
            'run_id': summary.run_id,
            'stage': f'Ingestion and signal evaluation complete ({len(evaluated)} findings)',
            'summary': _ingestion_summary_payload(summary),
            'error': None,
        })
    except Exception as exc:
        _ingestion_jobs[job_id].update({
            'status': 'FAILED',
            'stage': 'Ingestion failed',
            'error': str(exc),
        })


def _ingestion_summary_payload(summary) -> dict:
    payload = dict(summary.__dict__)
    payload.update({
        'empty_unique_payloads': summary.empty_files,
        'duplicate_payload_references': summary.duplicate_files,
        'unsupported_unique_payloads': summary.quarantined_files,
    })
    return payload


@router.post('/ingest/start', response_model=IngestionProgressRecord)
def start_ingestion(payload: IngestionStartRequest, background_tasks: BackgroundTasks) -> IngestionProgressRecord:
    if payload.override_existing and payload.password != DEMO_INGEST_OVERRIDE_PASSWORD:
        raise HTTPException(status_code=403, detail='Invalid demo ingestion override password')
    if any(job['status'] in {'QUEUED', 'RUNNING'} for job in _ingestion_jobs.values()):
        raise HTTPException(status_code=409, detail='An ingestion job is already running')

    job_id = f'ingest_{uuid.uuid4().hex[:12]}'
    _ingestion_jobs[job_id] = {
        'job_id': job_id,
        'status': 'QUEUED',
        'total_files': 0,
        'processed_files': 0,
        'percentage': 0.0,
        'run_id': None,
        'stage': 'Queued',
        'summary': None,
        'error': None,
    }
    background_tasks.add_task(_run_ingestion_job, job_id, payload.override_existing)
    return IngestionProgressRecord(**_ingestion_jobs[job_id])


@router.get('/ingest/progress/{job_id}', response_model=IngestionProgressRecord)
def ingestion_progress(job_id: str) -> IngestionProgressRecord:
    job = _ingestion_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Ingestion job not found')
    return IngestionProgressRecord(**job)


@router.get('/ingestion-errors', response_model=list[IngestionErrorRecord])
def ingestion_errors(run_id: str | None = None, limit: int = 100) -> list[IngestionErrorRecord]:
    con = db.connect()
    selected_run = run_id or _latest_file_run(con)
    if not selected_run:
        con.close()
        return []
    rows = con.execute('''
        select run_id, file_id, source_row, error_type, error_message, raw_row
        from ingestion_errors
        where run_id = ?
        order by source_row, file_id
        limit ?
    ''', [selected_run, max(1, min(limit, 500))]).fetchall()
    con.close()
    def parse_raw(value: str | None) -> dict:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {'value': parsed}
        except json.JSONDecodeError:
            return {'raw': value}

    return [IngestionErrorRecord(
        run_id=row[0], file_id=row[1], source_row=int(row[2] or 0), error_type=row[3],
        error_message=row[4], raw_row=parse_raw(row[5]),
    ) for row in rows]


@router.post('/ingest', response_model=IngestionSummary)
def ingest() -> IngestionSummary:
    summary = run_ingestion(settings.input_root, db, settings.output_dir)
    return IngestionSummary(**_ingestion_summary_payload(summary))


@router.get('/dataset-status', response_model=DatasetStatus)
def dataset_status() -> DatasetStatus:
    con = db.connect()
    latest = _latest_file_run(con)

    physical_files = con.execute('select count(*) from file_manifest where run_id = ?', [latest]).fetchone()[0] if latest else 0
    unique_payloads = con.execute('select count(distinct payload_sha256) from file_manifest where run_id = ?', [latest]).fetchone()[0] if latest else 0
    duplicate_refs = con.execute('select count(*) from file_manifest where run_id = ? and duplicate_of_file_id is not null', [latest]).fetchone()[0] if latest else 0
    canonical_obs = con.execute('select count(*) from canonical_observations where run_id = ?', [latest]).fetchone()[0] if latest else 0
    assessment_runs = con.execute('select count(distinct run_id) from file_manifest').fetchone()[0]
    families = con.execute('select count(distinct schema_family) from canonical_observations where run_id = ?', [latest]).fetchone()[0] if latest else 0
    archive_entries = con.execute('''
        select coalesce(sum(archive_entries_discovered), 0)
        from (select distinct physical_path, archive_entries_discovered from file_manifest where run_id = ?)
    ''', [latest]).fetchone()[0] if latest else 0

    con.close()

    return DatasetStatus(
        ai_available=bool(effective_api_key() and effective_api_key() not in {'YOUR_OPENAI_API_KEY', 'YOUR_AZURE_OPENAI_API_KEY'}),
        latest_run_id=latest,
        archive_entries_discovered=int(archive_entries or 0),
        physical_files_discovered=physical_files,
        unique_payloads=unique_payloads,
        duplicate_payload_references=duplicate_refs,
        canonical_observations=canonical_obs,
        assessment_runs=assessment_runs,
        schema_families=families,
    )


@router.post('/search-observations', response_model=list[ObservationRecord])
def search_observations(payload: ObservationQuery) -> list[ObservationRecord]:
    con = db.connect()
    where = ['1=1']
    params: list[object] = []
    if payload.query:
        where.append('(lower(text_value) like ? or lower(metric_name) like ? or lower(schema_family) like ?)')
        q = f"%{payload.query.lower()}%"
        params.extend([q, q, q])
    if payload.module:
        where.append('lower(module) = ?')
        params.append(payload.module.lower())

    sql = f"""
    select record_id, file_id, source_row, module, schema_family, metric_name, metric_value, text_value, qualifiers_json
    from canonical_observations
    where {' and '.join(where)}
    order by run_id desc, source_row asc
    limit ?
    """
    params.append(payload.limit)
    rows = con.execute(sql, params).fetchall()
    con.close()

    return [
        ObservationRecord(
            record_id=r[0],
            file_id=r[1],
            source_row=r[2],
            module=r[3],
            schema_family=r[4],
            metric_name=r[5],
            metric_value=r[6],
            text_value=r[7],
            qualifiers=json.loads(r[8]) if r[8] else {},
        )
        for r in rows
    ]


@router.get('/quality')
def quality() -> dict:
    con = db.connect()
    latest = _latest_file_run(con)
    if latest is None:
        con.close()
        raise HTTPException(status_code=404, detail='No ingestion run found')

    out = {
        'run_id': latest,
        'physical_files_discovered': con.execute('select count(*) from file_manifest where run_id = ?', [latest]).fetchone()[0],
        'unique_payloads': con.execute('select count(distinct payload_sha256) from file_manifest where run_id = ?', [latest]).fetchone()[0],
        'unsupported_unique_payloads': con.execute("select count(*) from file_manifest where run_id = ? and ingestion_status = 'QUARANTINED_UNSUPPORTED'", [latest]).fetchone()[0],
        'empty_unique_payloads': con.execute('select count(*) from file_manifest where run_id = ? and is_empty = true', [latest]).fetchone()[0],
        'duplicate_payload_references': con.execute('select count(*) from file_manifest where run_id = ? and duplicate_of_file_id is not null', [latest]).fetchone()[0],
    }
    con.close()
    return out


@router.get('/manifest', response_model=list[FileManifestRecord])
def manifest(limit: int = 100, offset: int = 0, status: str | None = None, query: str | None = None) -> list[FileManifestRecord]:
    con = db.connect()
    latest = _latest_file_run(con)
    if latest is None:
        con.close()
        return []

    where = ['run_id = ?']
    params: list[object] = [latest]
    if status:
        where.append('ingestion_status = ?')
        params.append(status)
    if query:
        where.append('lower(original_filename) like ?')
        params.append(f'%{query.lower()}%')

    sql = f"""
    select m.file_id, m.original_filename, m.physical_path, m.schema_fingerprint, m.row_count,
           m.parsed_row_count, m.rejected_row_count, m.is_empty, m.duplicate_of_file_id,
           m.ingestion_status, m.adapter_name, m.adapter_version,
           coalesce(c.schema_family, 'unclassified'), coalesce(c.canonical_row_count, 0), m.header_json, m.schema_contract_id
    from file_manifest m
    left join (
      select run_id, file_id, any_value(schema_family) as schema_family, count(*) as canonical_row_count
      from canonical_observations
      group by run_id, file_id
    ) c on c.run_id = m.run_id and c.file_id = m.file_id
    where m.run_id = ?
      {"and m.ingestion_status = ?" if status else ""}
      {"and lower(m.original_filename) like ?" if query else ""}
    order by m.original_filename asc
    limit ? offset ?
    """
    params.append(limit)
    params.append(max(0, offset))
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [
        FileManifestRecord(
            file_id=r[0],
            original_filename=r[1],
            physical_path=r[2],
            schema_fingerprint=r[3],
            row_count=r[4],
            parsed_row_count=r[5],
            rejected_row_count=r[6],
            is_empty=r[7],
            duplicate_of_file_id=r[8],
            ingestion_status=r[9],
            adapter_name=r[10],
            adapter_version=r[11],
            canonical_row_count=int(r[13] or 0),
            schema_contract_id=r[15],
            schema_family=r[12],
            source_columns=json.loads(r[14]) if r[14] else [],
        )
        for r in rows
    ]


@router.get('/schema-summary', response_model=list[SchemaSummaryRecord])
def schema_summary() -> list[SchemaSummaryRecord]:
    con = db.connect()
    latest = _latest_file_run(con)
    if latest is None:
        con.close()
        return []
    rows = con.execute(
        '''
        select c.schema_family,
               count(distinct c.file_id) as file_count,
               count(*) as row_count
        from canonical_observations c
        where c.run_id = ?
        group by 1
        order by row_count desc
        ''',
        [latest],
    ).fetchall()
    con.close()
    return [SchemaSummaryRecord(schema_family=r[0], file_count=r[1], row_count=r[2]) for r in rows]


def _ingestion_ontology() -> list[OntologyEntityRecord]:
    return [
        OntologyEntityRecord(
            entity='Source file',
            purpose='The physical input and its ingestion outcome. This preserves what arrived, including duplicates and quarantined files.',
            table='file_manifest',
            fields=[
                OntologyFieldRecord(name='run_id', data_type='text', meaning='The ingestion batch that discovered this file.', role='batch lineage', populated_from='pipeline run'),
                OntologyFieldRecord(name='file_id', data_type='text', meaning='Stable identifier for one physical or archived file occurrence.', role='file lineage', populated_from='discovery adapter'),
                OntologyFieldRecord(name='original_filename', data_type='text', meaning='The filename supplied by the source system.', role='human traceability', populated_from='input path or archive entry'),
                OntologyFieldRecord(name='payload_sha256', data_type='text', meaning='Content fingerprint used to identify duplicate payloads without deleting the physical reference.', role='deduplication', populated_from='file bytes'),
                OntologyFieldRecord(name='schema_fingerprint', data_type='text', meaning='Fingerprint of the discovered header shape.', role='schema matching', populated_from='parsed header'),
                OntologyFieldRecord(name='row_count', data_type='integer', meaning='Rows found in the parsed source file.', role='source volume', populated_from='parser'),
                OntologyFieldRecord(name='ingestion_status', data_type='text', meaning='Whether the file was supported, empty, duplicated, or quarantined with an error.', role='quality state', populated_from='parser and adapter'),
            ],
        ),
        OntologyEntityRecord(
            entity='Canonical observation',
            purpose='The common row-level evidence model used by search, evidence, signal rules, and lineage views.',
            table='canonical_observations',
            fields=[
                OntologyFieldRecord(name='record_id', data_type='text', meaning='Stable identifier for one canonicalized source row.', role='row lineage', populated_from='file, source row, and row hash'),
                OntologyFieldRecord(name='file_id', data_type='text', meaning='Links the observation back to the source file occurrence.', role='lineage join', populated_from='file_manifest'),
                OntologyFieldRecord(name='source_row', data_type='integer', meaning='Original row number in the source file.', role='lineage join', populated_from='parser'),
                OntologyFieldRecord(name='schema_family', data_type='text', meaning='Recognized source shape, such as claims, citations, readiness, or visibility.', role='semantic classification', populated_from='schema adapter'),
                OntologyFieldRecord(name='module', data_type='text', meaning='Business area that owns the observation: Visibility, Content Readiness, or AI Vulnerability.', role='business context', populated_from='configured context and path inference'),
                OntologyFieldRecord(name='metric_name', data_type='text', meaning='Only a contract-mapped metric promoted to the canonical metric fields.', role='governed metric', populated_from='row type and metric contract'),
                OntologyFieldRecord(name='metric_value', data_type='number', meaning='Numeric value for the promoted metric; interpretation remains controlled by its metric contract.', role='governed metric value', populated_from='source row'),
                OntologyFieldRecord(name='text_value', data_type='text', meaning='Prompt, claim, or question text used to group and explain evidence.', role='business subject', populated_from='source row'),
                OntologyFieldRecord(name='qualifiers_json', data_type='JSON', meaning='The preserved raw source row plus context qualifiers. Raw fields remain available but are not automatically governed metrics.', role='raw evidence preservation', populated_from='source row'),
                OntologyFieldRecord(name='record_hash', data_type='text', meaning='Fingerprint of the source row used for reproducibility and change detection.', role='integrity', populated_from='raw row'),
                OntologyFieldRecord(name='adapter_version', data_type='text', meaning='Version of the parser/schema adapter that produced this observation.', role='reproducibility', populated_from='schema adapter'),
                OntologyFieldRecord(name='observation_state', data_type='text', meaning='Lifecycle state of the row, currently OBSERVATION for accepted canonical evidence.', role='lifecycle', populated_from='ingestion pipeline'),
            ],
        ),
        OntologyEntityRecord(
            entity='Signal finding',
            purpose='A rule-based pattern aggregated from canonical observations. One signal can represent many rows, files, prompts, or AI engines.',
            table='signal_instances',
            fields=[
                OntologyFieldRecord(name='signal_instance_id', data_type='text', meaning='Stable identifier for one rule finding in one assessment run.', role='finding identity', populated_from='rule, run, and group key'),
                OntologyFieldRecord(name='signal_type', data_type='text', meaning='The business pattern detected, such as AI answer inconsistency or readiness gap.', role='finding category', populated_from='signal rule registry'),
                OntologyFieldRecord(name='group_key', data_type='text', meaning='The claim, prompt, factor, or other subject across which evidence was aggregated.', role='aggregation grain', populated_from='canonical observation fields'),
                OntologyFieldRecord(name='governance_status', data_type='text', meaning='Whether the rule is GOVERNED, EXPERIMENTAL, or BLOCKED for decision use.', role='decision safety', populated_from='metric and rule contracts'),
                OntologyFieldRecord(name='evidence_count', data_type='integer', meaning='Number of linked source observations supporting the finding; repeated rows are retained and labelled.', role='evidence strength', populated_from='signal evidence links'),
            ],
        ),
    ]


@router.get('/ingestion/overview', response_model=IngestionOverviewResponse)
def ingestion_overview() -> IngestionOverviewResponse:
    con = db.connect()
    latest = _latest_file_run(con)
    if latest is None:
        con.close()
        return IngestionOverviewResponse(
            run_id=None, physical_files=0, unique_payloads=0, duplicate_references=0,
            parsed_files=0, quarantined_files=0, empty_files=0, source_rows=0,
            canonical_observations=0, ontology=_ingestion_ontology(), modules=[], schemas=[],
        )

    counts = con.execute('''
        select
          count(*) as physical_files,
          count(distinct payload_sha256) as unique_payloads,
          count(*) filter (where duplicate_of_file_id is not null) as duplicate_references,
          count(*) filter (where parsed_row_count is not null) as parsed_files,
          count(*) filter (where ingestion_status like 'QUARANTINED%') as quarantined_files,
          count(*) filter (where is_empty) as empty_files,
          coalesce(sum(row_count), 0) as source_rows
        from file_manifest where run_id = ?
    ''', [latest]).fetchone()
    canonical_count = con.execute('select count(*) from canonical_observations where run_id = ?', [latest]).fetchone()[0]
    rule_eligible_count = con.execute('''
        select count(*) from canonical_observations
        where run_id = ? and (
          (module = 'Visibility' and json_extract_string(qualifiers_json, '$.row.rowType') = 'ranking'
             and lower(json_extract_string(qualifiers_json, '$.row.brandName')) = lower(?)
             and try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double) is not null) or
          (module = 'AI Vulnerability' and json_extract_string(qualifiers_json, '$.row.rowType') = 'llm'
             and try_cast(json_extract_string(qualifiers_json, '$.row.llmAccuracyScore') as double) is not null) or
          (module = 'AI Vulnerability' and json_extract_string(qualifiers_json, '$.row.rowType') = 'summary'
             and try_cast(json_extract_string(qualifiers_json, '$.row.consensusAccuracyScore') as double) is not null) or
          (module = 'Content Readiness' and json_extract_string(qualifiers_json, '$.row.rowType') = 'summary'
             and try_cast(json_extract_string(qualifiers_json, '$.row.weightedScore') as double) is not null) or
          (module = 'Content Readiness' and json_extract_string(qualifiers_json, '$.row.rowType') = 'main'
             and nullif(json_extract_string(qualifiers_json, '$.row.sourceUrl'), '') is not null) or
          (schema_family = 'competitive_playbooks'
             and nullif(json_extract_string(qualifiers_json, '$.row.searchTerm'), '') is not null
             and try_cast(json_extract_string(qualifiers_json, '$.row.scoreDiff') as double) is not null) or
          (schema_family = 'brand_reputation_scorecards'
             and json_extract_string(qualifiers_json, '$.row.rowType') = 'entity'
             and try_cast(json_extract_string(qualifiers_json, '$.row.score') as double) is not null)
        )
    ''', [latest, settings.brand_display]).fetchone()[0]
    signal_counts = con.execute('''
        select count(*), count(*) filter (where governance_status = 'BLOCKED')
        from signal_instances where assessment_run_id = ?
    ''', [latest]).fetchone()

    file_rows = con.execute('''
        select coalesce(m.inferred_module, 'Unclassified'), count(*), count(distinct m.payload_sha256),
               coalesce(sum(m.row_count), 0), coalesce(sum(c.canonical_row_count), 0)
        from file_manifest m
        left join (
          select run_id, file_id, count(*) as canonical_row_count
          from canonical_observations group by run_id, file_id
        ) c on c.run_id = m.run_id and c.file_id = m.file_id
        where m.run_id = ?
        group by 1 order by 1
    ''', [latest]).fetchall()
    modules = [IngestionModuleRecord(module=r[0], physical_files=int(r[1]), unique_payloads=int(r[2]), source_rows=int(r[3] or 0), canonical_observations=int(r[4] or 0)) for r in file_rows]

    schema_rows = con.execute('''
        select c.schema_family, count(distinct m.file_id), count(distinct m.payload_sha256),
               coalesce(sum(m.row_count), 0), count(c.record_id)
        from canonical_observations c
        join file_manifest m on m.run_id = c.run_id and m.file_id = c.file_id
        where c.run_id = ?
        group by c.schema_family order by count(c.record_id) desc
    ''', [latest]).fetchall()
    schemas = []
    for r in schema_rows:
        disposition = 'CANONICALIZED' if int(r[4] or 0) else 'NO_CANONICAL_OBSERVATIONS'
        schemas.append(IngestionSchemaRecord(schema_family=r[0] or 'Unclassified', file_count=int(r[1]), unique_payloads=int(r[2]), source_rows=int(r[3] or 0), canonical_observations=int(r[4] or 0), disposition=disposition))
    con.close()
    return IngestionOverviewResponse(
        run_id=latest, physical_files=int(counts[0] or 0), unique_payloads=int(counts[1] or 0),
        duplicate_references=int(counts[2] or 0), parsed_files=int(counts[3] or 0),
        quarantined_files=int(counts[4] or 0), empty_files=int(counts[5] or 0),
        source_rows=int(counts[6] or 0), canonical_observations=int(canonical_count or 0),
        rule_eligible_observations=int(rule_eligible_count or 0), evaluated_signals=int(signal_counts[0] or 0),
        blocked_evaluations=int(signal_counts[1] or 0), modules=modules, schemas=schemas,
        ontology=_ingestion_ontology(),
    )


@router.get('/reference-checks', response_model=ReferenceChecks)
def reference_checks() -> ReferenceChecks:
    con = db.connect()
    latest = _latest_file_run(con)
    if latest is None:
        con.close()
        raise HTTPException(status_code=404, detail='No ingestion run found')

    physical = con.execute('select count(*) from file_manifest where run_id = ?', [latest]).fetchone()[0]
    unique_payloads = con.execute('select count(distinct payload_sha256) from file_manifest where run_id = ?', [latest]).fetchone()[0]

    vis = con.execute(
        '''
        with vis as (
          select try_cast(json_extract_string(c.qualifiers_json, '$.row.score') as double) as score
          from canonical_observations c
          join file_manifest m on c.file_id = m.file_id and c.run_id = m.run_id
          where c.run_id = ? and m.original_filename like '%visibility_search_terms%'
        )
        select
          count(*) filter (where score is not null) as prompts,
          avg(score) as avg_score,
          sum(case when score = 0 then 1 else 0 end) as zeros,
          sum(case when score < 0.5 then 1 else 0 end) as below_050
        from vis
        ''',
        [latest],
    ).fetchone()

    citation_rows_proxy = con.execute(
        "select coalesce(sum(row_count), 0) from file_manifest where run_id = ? and original_filename like '%sites_referenced%'",
        [latest],
    ).fetchone()[0]
    unique_urls = con.execute('select count(distinct url) from source_domains where run_id = ?', [latest]).fetchone()[0]
    unique_domains = con.execute('select count(distinct domain) from source_domains where run_id = ?', [latest]).fetchone()[0]
    con.close()

    return ReferenceChecks(
        physical_csv_entries=physical,
        unique_payloads=unique_payloads,
        prompts=int(vis[0] or 0),
        avg_visibility_score=float(vis[1]) if vis[1] is not None else None,
        prompts_zero_score=int(vis[2] or 0),
        prompts_below_050=int(vis[3] or 0),
        citation_rows_proxy=int(citation_rows_proxy),
        unique_urls=int(unique_urls),
        unique_domains=int(unique_domains),
    )





@router.post('/leadership-chat', response_model=LeadershipChatResponse)
def leadership_chat(payload: LeadershipChatRequest) -> LeadershipChatResponse:
    con = db.connect()
    latest = _latest_file_run(con)
    con.close()
    result = ask_leadership_question(
        db, latest, payload.question, mode=payload.mode, history_enabled=payload.history_enabled,
        history=[turn.model_dump() for turn in payload.history], app_context=payload.context,
        signal_instance_id=payload.signal_instance_id,
    )
    return LeadershipChatResponse(
        answer=result.answer,
        ai_available=result.ai_available,
        citations=[ChatCitation(**c) for c in result.citations],
        limitations=result.limitations,
        retrieved_record_ids=result.retrieved_record_ids,
        headline=result.headline,
        priorities=result.priorities or [],
        decision_required=result.decision_required,
        evidence_references={k: ChatCitation(**v) for k, v in (result.evidence_references or {}).items()},
        fallback_used=result.fallback_used,
    )


def _signal_instance_row_to_dict(r: tuple) -> dict:
    result = {
        'signal_instance_id': r[0],
        'signal_rule_id': r[1],
        'signal_rule_version': r[2],
        'brand_id': r[3],
        'market': r[4],
        'assessment_run_id': r[5],
        'signal_type': r[6],
        'group_key': r[7],
        'title': r[8],
        'description': r[9],
        'current_value': r[10],
        'baseline_value': r[11],
        'delta': r[12],
        'runs_affected': r[13],
        'engines_affected': r[14],
        'business_priority': r[15],
        'severity': r[16],
        'confidence': r[17],
        'evidence_count': r[18],
        'diagnosis_status': r[19],
        'truth_validation_status': r[20],
        'workflow_status': r[21],
        'governance_status': r[22],
        'rule_source': r[23],
        'metric_contract_id': r[24],
        'metric_validation_status': r[25] or 'PROVISIONAL_INFERRED',
        'data_provenance': r[26] or 'SOURCE_PAYLOAD',
        'known_limitations': json.loads(r[27]) if r[27] else [],
    }
    rule = next((candidate for candidate in load_rules() if candidate.signal_rule_id == result['signal_rule_id']), None)
    if rule is not None:
        result.update(business_signal_fields(
            rule, result['group_key'], float(result['current_value'] or 0), int(result['evidence_count'] or 0),
            int(result['engines_affected'] or 0), result['workflow_status'], result['governance_status'],
            float(result['confidence'] or 0),
        ))
    return result


_SIGNAL_INSTANCE_COLUMNS = '''
    signal_instance_id, signal_rule_id, signal_rule_version, brand_id, market, assessment_run_id,
    signal_type, group_key, title, description, current_value, baseline_value, delta, runs_affected,
    engines_affected, business_priority, severity, confidence, evidence_count, diagnosis_status,
    truth_validation_status, workflow_status, governance_status, rule_source, metric_contract_id,
    metric_validation_status, data_provenance, known_limitations_json
'''


def _fetch_signal_instance(con, signal_instance_id: str) -> dict | None:
    row = con.execute(
        f'select {_SIGNAL_INSTANCE_COLUMNS} from signal_instances where signal_instance_id = ?',
        [signal_instance_id],
    ).fetchone()
    if row is None:
        return None
    return _signal_instance_row_to_dict(row)


@router.post('/signals/evaluate', response_model=SignalEvaluateResponse)
def signals_evaluate() -> SignalEvaluateResponse:
    con = db.connect()
    latest = _latest_file_run(con)
    if latest is None:
        con.close()
        raise HTTPException(status_code=404, detail='No ingestion run found')

    instances = evaluate_signals(
        con, latest, brand_id=settings.brand_id, brand_display=settings.brand_display, market=settings.market,
    )
    persist_signal_instances(con, latest, instances)
    con.close()

    return SignalEvaluateResponse(
        run_id=latest,
        evaluated_signal_count=len(instances),
        signals=[SignalInstanceRecord(**{k: v for k, v in i.items() if k != 'evidence'}) for i in instances],
    )


@router.get('/signal-coverage')
def signal_coverage(assessment_run_id: str | None = None) -> dict:
    con = db.connect()
    run_id = assessment_run_id or _latest_file_run(con)
    if run_id is None:
        con.close()
        raise HTTPException(status_code=404, detail='No ingestion run found')
    coverage = audit_signal_coverage(
        con, run_id, brand_id=settings.brand_id, brand_display=settings.brand_display, market=settings.market,
    )
    con.close()
    return coverage


@router.get('/signals', response_model=list[SignalInstanceRecord])
def list_signals(
    severity: str | None = None,
    signal_type: str | None = None,
    workflow_status: str | None = None,
    business_priority: str | None = None,
    governance_status: str | None = None,
    assessment_run_id: str | None = None,
    module: str | None = None,
    truth_validation_status: str | None = None,
    limit: int = 100,
) -> list[SignalInstanceRecord]:
    con = db.connect()
    latest = assessment_run_id or _latest_file_run(con)
    if latest is None:
        con.close()
        return []

    where = ['assessment_run_id = ?']
    params: list[object] = [latest]
    if severity:
        where.append('severity = ?')
        params.append(severity.upper())
    if signal_type:
        where.append('signal_type = ?')
        params.append(signal_type)
    if workflow_status:
        where.append('workflow_status = ?')
        params.append(workflow_status.upper())
    if business_priority:
        where.append('business_priority = ?')
        params.append(business_priority.upper())
    if governance_status:
        where.append('governance_status = ?')
        params.append(governance_status.upper())
    if truth_validation_status:
        where.append('truth_validation_status = ?')
        params.append(truth_validation_status.upper())
    if module:
        where.append('exists (select 1 from assessment_runs ar where ar.run_id = signal_instances.assessment_run_id and ar.module = ?)')
        params.append(module)



    sql = f'''
    select {_SIGNAL_INSTANCE_COLUMNS} from signal_instances
    where {' and '.join(where)}
    order by
      case severity when 'CRITICAL' then 0 when 'HIGH' then 1 when 'MEDIUM' then 2 else 3 end,
      confidence desc
    limit ?
    '''
    params.append(limit)
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [SignalInstanceRecord(**_signal_instance_row_to_dict(r)) for r in rows]


@router.get('/signals/{signal_instance_id}', response_model=SignalInstanceRecord)
def get_signal(signal_instance_id: str) -> SignalInstanceRecord:
    con = db.connect()
    inst = _fetch_signal_instance(con, signal_instance_id)
    con.close()
    if inst is None:
        raise HTTPException(status_code=404, detail='Signal instance not found')
    return SignalInstanceRecord(**inst)


@router.get('/signals/{signal_instance_id}/evidence', response_model=list[SignalEvidenceRecord])
def get_signal_evidence_endpoint(signal_instance_id: str) -> list[SignalEvidenceRecord]:
    con = db.connect()
    inst = _fetch_signal_instance(con, signal_instance_id)
    if inst is None:
        con.close()
        raise HTTPException(status_code=404, detail='Signal instance not found')

    rows = get_signal_evidence(con, signal_instance_id)
    con.close()
    return [
        SignalEvidenceRecord(
            record_id=r['record_id'],
            file_id=r['file_id'],
            source_row=r['source_row'],
            evidence_role=r['evidence_role'],
            original_filename=r['original_filename'],
            metric_name=r['metric_name'],
            metric_value=r['metric_value'],
            text_value=r['text_value'],
            qualifiers=json.loads(r['qualifiers_json']) if r['qualifiers_json'] else {},
            payload_sha256=r.get('payload_sha256'),
            assessment_run_id=r.get('run_id'),
            engine=(json.loads(r['qualifiers_json']).get('row', {}).get('llm') or json.loads(r['qualifiers_json']).get('row', {}).get('llmSource') or json.loads(r['qualifiers_json']).get('row', {}).get('cohort')) if r.get('qualifiers_json') else None,
        )
        for r in rows
    ]


@router.get('/signals/{signal_instance_id}/history', response_model=list[SignalHistoryPoint])
def get_signal_history_endpoint(signal_instance_id: str) -> list[SignalHistoryPoint]:
    con = db.connect()
    inst = _fetch_signal_instance(con, signal_instance_id)
    if inst is None:
        con.close()
        raise HTTPException(status_code=404, detail='Signal instance not found')

    rows = get_signal_history(con, inst['signal_rule_id'], inst['brand_id'], inst['market'], inst['group_key'])
    con.close()
    return [
        SignalHistoryPoint(
            assessment_run_id=r['assessment_run_id'],
            current_value=r['current_value'],
            severity=r['severity'],
            confidence=r['confidence'],
            workflow_status=r['workflow_status'],
            created_at=str(r['created_at']),
        )
        for r in rows
    ]


@router.get('/signals/{signal_instance_id}/comparisons', response_model=SignalComparisonsResponse)
def get_signal_comparisons_endpoint(signal_instance_id: str) -> SignalComparisonsResponse:
    con = db.connect()
    inst = _fetch_signal_instance(con, signal_instance_id)
    if inst is None:
        con.close()
        raise HTTPException(status_code=404, detail='Signal instance not found')

    comp = get_signal_comparisons(
        con, inst['signal_type'], inst['assessment_run_id'], inst['group_key'], settings.brand_display,
    )
    con.close()
    return SignalComparisonsResponse(
        engine_comparison_basis=comp['engine_comparison_basis'],
        engine_comparison=[SignalComparisonItem(**item) for item in comp['engine_comparison']],
        competitor_comparison_basis=comp['competitor_comparison_basis'],
        competitor_comparison=[SignalComparisonItem(**item) for item in comp['competitor_comparison']],
    )


# ── Intervention endpoints ────────────────────────────────────────────────────

def _intervention_from_row(row: dict) -> InterventionRecord:
    return InterventionRecord(
        intervention_id=row['intervention_id'],
        signal_instance_id=row['signal_instance_id'],
        brand_id=row['brand_id'],
        market=row['market'],
        business_problem=row['business_problem'],
        diagnosed_cause=row['diagnosed_cause'],
        recommended_action=row['recommended_action'],
        target_prompt_id=row['target_prompt_id'],
        target_product_id=row['target_product_id'],
        target_claim_id=row['target_claim_id'],
        target_page_id=row['target_page_id'],
        approved_evidence=row['approved_evidence'],
        risk_route=row['risk_route'],
        owner=row['owner'],
        approver=row['approver'],
        status=row['status'],
        priority=row['priority'],
        confidence=row['confidence'],
        baseline_run_id=row['baseline_run_id'],
        baseline_metric=row['baseline_metric'],
        target_metric=row['target_metric'],
        planned_publish_date=row['planned_publish_date'],
        actual_publish_date=row['actual_publish_date'],
        retest_date=row['retest_date'],
        created_at=str(row['created_at']) if row.get('created_at') else None,
        updated_at=str(row['updated_at']) if row.get('updated_at') else None,
    )


@router.post('/interventions', response_model=InterventionRecord)
def create_intervention_endpoint(payload: InterventionCreateRequest) -> InterventionRecord:
    con = db.connect()
    try:
        row = create_intervention(con, payload.model_dump())
    except ValueError as exc:
        con.close()
        raise HTTPException(status_code=422, detail=str(exc))
    con.close()
    return _intervention_from_row(row)


@router.get('/interventions', response_model=InterventionListResponse)
def list_interventions_endpoint(
    brand_id: str | None = None,
    status: str | None = None,
    signal_instance_id: str | None = None,
    limit: int = 100,
) -> InterventionListResponse:
    con = db.connect()
    rows = list_interventions(con, brand_id=brand_id, status=status,
                              signal_instance_id=signal_instance_id, limit=limit)
    con.close()
    interventions = [_intervention_from_row(r) for r in rows]
    return InterventionListResponse(interventions=interventions, total_count=len(interventions))


@router.get('/interventions/{intervention_id}', response_model=InterventionRecord)
def get_intervention_endpoint(intervention_id: str) -> InterventionRecord:
    con = db.connect()
    row = fetch_intervention(con, intervention_id)
    con.close()
    if row is None:
        raise HTTPException(status_code=404, detail='Intervention not found')
    return _intervention_from_row(row)


@router.patch('/interventions/{intervention_id}', response_model=InterventionRecord)
def update_intervention_endpoint(intervention_id: str, payload: InterventionUpdateRequest) -> InterventionRecord:
    con = db.connect()
    row = update_intervention(con, intervention_id, payload.model_dump(exclude_none=True))
    con.close()
    if row is None:
        raise HTTPException(status_code=404, detail='Intervention not found')
    return _intervention_from_row(row)


@router.post('/interventions/{intervention_id}/transition', response_model=InterventionRecord)
def transition_intervention_endpoint(intervention_id: str, payload: InterventionTransitionRequest) -> InterventionRecord:
    con = db.connect()
    try:
        row = transition_intervention(con, intervention_id, payload.target_status)
    except ValueError as exc:
        con.close()
        raise HTTPException(status_code=422, detail=str(exc))
    con.close()
    if row is None:
        raise HTTPException(status_code=404, detail='Intervention not found')
    return _intervention_from_row(row)


@router.post('/interventions/{intervention_id}/generate-brief', response_model=InterventionBriefResponse)
def generate_brief_endpoint(intervention_id: str) -> InterventionBriefResponse:
    con = db.connect()
    try:
        brief = generate_brief(con, intervention_id)
    except ValueError as exc:
        con.close()
        raise HTTPException(status_code=422, detail=str(exc))
    con.close()
    return InterventionBriefResponse(**brief)


# ── Outcome endpoints ─────────────────────────────────────────────────────────

def _outcome_from_row(row: dict) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=row['outcome_id'],
        intervention_id=row['intervention_id'],
        baseline_run_id=row['baseline_run_id'],
        post_change_run_id=row['post_change_run_id'],
        published_at=row['published_at'],
        retested_at=str(row['retested_at']) if row.get('retested_at') else None,
        baseline_value=row['baseline_value'],
        post_change_value=row['post_change_value'],
        absolute_delta=row['absolute_delta'],
        percentage_delta=row['percentage_delta'],
        engines_improved=row['engines_improved'],
        prompts_improved=row['prompts_improved'],
        citation_share_before=row['citation_share_before'],
        citation_share_after=row['citation_share_after'],
        competitor_delta=row['competitor_delta'],
        outcome_status=row['outcome_status'],
        confidence=row['confidence'],
        comparison_limitations=row['comparison_limitations'],
        brand_id=row.get('brand_id'),
        market=row.get('market'),
        language=row.get('language'),
        source_system=row.get('source_system'),
        metric_contract_id=row.get('metric_contract_id'),
        context_provenance=json.loads(row['context_provenance_json']) if row.get('context_provenance_json') else {},
        created_at=str(row['created_at']) if row.get('created_at') else None,
    )


@router.post('/interventions/{intervention_id}/measure', response_model=OutcomeRecord)
def measure_outcome_endpoint(intervention_id: str, payload: MeasureInterventionRequest) -> OutcomeRecord:
    con = db.connect()
    if fetch_intervention(con, intervention_id) is None:
        con.close()
        raise HTTPException(status_code=404, detail='Intervention not found')
    try:
        row = measure_intervention(con, intervention_id, payload.post_change_run_id)
    except ValueError as exc:
        con.close()
        raise HTTPException(status_code=422, detail=str(exc))
    con.close()
    return _outcome_from_row(row)


@router.get('/interventions/{intervention_id}/outcome', response_model=OutcomeRecord | None)
def get_outcome_endpoint(intervention_id: str) -> OutcomeRecord | None:
    con = db.connect()
    row = fetch_outcome(con, intervention_id)
    con.close()
    if row is None:
        return None
    return _outcome_from_row(row)


@router.get('/outcomes', response_model=list[OutcomeRecord])
def list_outcomes_endpoint(limit: int = 100) -> list[OutcomeRecord]:
    con = db.connect()
    rows = list_outcomes(con, limit=limit)
    con.close()
    return [_outcome_from_row(r) for r in rows]


# ── Truth registry endpoints ──────────────────────────────────────────────────

@router.get('/truth/claims', response_model=list[ClaimTruthRecord])
def list_claims(brand_id: str | None = None) -> list[ClaimTruthRecord]:
    con = db.connect()
    where = 'where brand_id = ?' if brand_id else ''
    params: list[object] = [brand_id] if brand_id else []
    rows = con.execute(
        f'select claim_id, brand_id, claim_text, consensus_accuracy_score, approval_status, approver, last_reviewed_date, evidence_reference from claim_truth {where} order by approval_status, claim_id',
        params,
    ).fetchall()
    con.close()
    return [
        ClaimTruthRecord(
            claim_id=r[0], brand_id=r[1], claim_text=r[2], consensus_accuracy_score=r[3],
            approval_status=r[4], approver=r[5], last_reviewed_date=r[6], evidence_reference=r[7],
        )
        for r in rows
    ]


@router.get('/truth/content-assets', response_model=list[ContentAssetRecord])
def list_content_assets(brand_id: str | None = None) -> list[ContentAssetRecord]:
    con = db.connect()
    where = 'where brand_id = ?' if brand_id else ''
    params: list[object] = [brand_id] if brand_id else []
    rows = con.execute(
        f'select asset_id, brand_id, canonical_url, content_type, readiness_status, content_owner, approver, last_reviewed_date from content_assets {where} order by content_type, asset_id',
        params,
    ).fetchall()
    con.close()
    return [
        ContentAssetRecord(
            asset_id=r[0], brand_id=r[1], canonical_url=r[2], content_type=r[3],
            readiness_status=r[4], content_owner=r[5], approver=r[6], last_reviewed_date=r[7],
        )
        for r in rows
    ]


@router.get('/truth/prompts', response_model=list[PromptPriorityRecord])
def list_prompt_priorities(brand_id: str | None = None) -> list[PromptPriorityRecord]:
    con = db.connect()
    where = 'where brand_id = ?' if brand_id else ''
    params: list[object] = [brand_id] if brand_id else []
    rows = con.execute(
        f'select prompt_id, brand_id, prompt_text, priority_level, category, is_hero, approved_by from prompt_priorities {where} order by priority_level, prompt_id',
        params,
    ).fetchall()
    con.close()
    return [
        PromptPriorityRecord(
            prompt_id=r[0], brand_id=r[1], prompt_text=r[2], priority_level=r[3],
            category=r[4], is_hero=bool(r[5]), approved_by=r[6],
        )
        for r in rows
    ]


# ── Seed POC fixtures ─────────────────────────────────────────────────────────

@router.post('/seed-fixtures', response_model=SeedFixturesResponse)
def seed_fixtures_endpoint() -> SeedFixturesResponse:
    from app.services.fixtures import seed_poc_fixtures

    con = db.connect()
    counts = seed_poc_fixtures(con)
    con.close()
    return SeedFixturesResponse(
        seeded=counts,
        message='Configured POC fixtures seeded. Every simulated record is marked DEMO_FIXTURE and remains separate from vendor data.',
    )


# ── Semantic Trust & Governance ────────────────────────────────────────────────

@router.get('/assessment-runs', response_model=list[AssessmentRunRecord])
def list_assessment_runs() -> list[AssessmentRunRecord]:
    con = db.connect()
    rows = con.execute('''
        select run_id, source_system, brand_id, market, language, module, acquisition_date,
               context_provenance_json, quality_status, ingested_at
        from assessment_runs order by ingested_at desc
    ''').fetchall()
    con.close()
    return [
        AssessmentRunRecord(
            run_id=r[0],
            source_system=r[1] or settings.source_system,
            brand_id=r[2], market=r[3], language=r[4], module=r[5], acquisition_date=r[6],
            context_provenance=json.loads(r[7]) if r[7] else {}, quality_status=r[8] or 'PROVISIONAL',
            ingested_at=str(r[9]) if r[9] else None,
        )
        for r in rows
    ]

@router.get('/metric-contracts', response_model=list[MetricContractRecord])
def list_metric_contracts() -> list[MetricContractRecord]:
    con = db.connect()
    rows = con.execute('select metric_id, metric_name, module, description, direction, grain, calculated_by, validation_status, created_at from metric_contracts').fetchall()
    con.close()
    return [
        MetricContractRecord(
            metric_id=r[0],
            metric_name=r[1],
            module=r[2],
            description=r[3],
            direction=r[4],
            grain=r[5],
            calculated_by=r[6],
            validation_status=r[7],
            created_at=str(r[8]) if r[8] else None,
        )
        for r in rows
    ]

@router.get('/schema-contracts', response_model=list[SchemaContractRecord])
def list_schema_contracts() -> list[SchemaContractRecord]:
    con = db.connect()
    rows = con.execute('select schema_family, adapter_name, expected_columns_json, description, created_at from schema_contracts').fetchall()
    con.close()
    return [
        SchemaContractRecord(
            schema_family=r[0],
            adapter_name=r[1],
            expected_columns=json.loads(r[2]) if r[2] else [],
            description=r[3],
            created_at=str(r[4]) if r[4] else None,
        )
        for r in rows
    ]

@router.get('/semantic-blockers', response_model=list[SemanticBlockerRecord])
def list_semantic_blockers() -> list[SemanticBlockerRecord]:
    con = db.connect()
    rows = con.execute('select blocker_id, target_entity, blocker_type, description, status, created_at from semantic_blockers').fetchall()
    con.close()
    return [
        SemanticBlockerRecord(
            blocker_id=r[0],
            target_entity=r[1],
            blocker_type=r[2],
            description=r[3],
            status=r[4],
            created_at=str(r[5]) if r[5] else None,
        )
        for r in rows
    ]

@router.get('/vendor-questions', response_model=list[VendorQuestionRecord])
def list_vendor_questions() -> list[VendorQuestionRecord]:
    con = db.connect()
    rows = con.execute('select question_id, topic, question_text, status, created_at from vendor_questions').fetchall()
    con.close()
    return [
        VendorQuestionRecord(
            question_id=r[0],
            topic=r[1],
            question_text=r[2],
            status=r[3],
            created_at=str(r[4]) if r[4] else None,
        )
        for r in rows
    ]
