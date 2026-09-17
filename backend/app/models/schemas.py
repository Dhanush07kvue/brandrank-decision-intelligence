from pydantic import BaseModel
from typing import Any, Literal
from pydantic import Field


class IngestionSummary(BaseModel):
    run_id: str
    physical_files: int
    unique_payloads: int
    total_rows: int
    parsed_rows: int
    rejected_rows: int
    empty_unique_payloads: int = 0
    duplicate_payload_references: int = 0
    unsupported_unique_payloads: int = 0
    empty_files: int = 0
    duplicate_files: int = 0
    quarantined_files: int = 0
    archive_entries_discovered: int = 0
    storage_mode: str = 'duckdb'
    destination_status: dict[str, str] = Field(default_factory=dict)
    schema_contract_counts: dict[str, int] = Field(default_factory=dict)
    normalized_record_counts: dict[str, int] = Field(default_factory=dict)
    rejected_row_counts: dict[str, int] = Field(default_factory=dict)
    reconciliation_state: str = 'NOT_RUN'


class IngestionStartRequest(BaseModel):
    override_existing: bool = False
    password: str | None = None


class IngestionProgressRecord(BaseModel):
    job_id: str
    status: Literal['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED']
    total_files: int
    processed_files: int
    percentage: float
    run_id: str | None = None
    stage: str
    summary: IngestionSummary | None = None
    error: str | None = None


class IngestionErrorRecord(BaseModel):
    run_id: str
    file_id: str | None
    source_row: int
    error_type: str
    error_message: str
    raw_row: dict[str, Any]


class DatasetStatus(BaseModel):
    ai_available: bool
    latest_run_id: str | None
    archive_entries_discovered: int
    physical_files_discovered: int
    unique_payloads: int
    duplicate_payload_references: int
    canonical_observations: int
    assessment_runs: int
    schema_families: int


class ObservationQuery(BaseModel):
    query: str | None = None
    module: str | None = None
    limit: int = 50


class ObservationRecord(BaseModel):
    record_id: str
    file_id: str
    source_row: int
    module: str | None
    schema_family: str | None
    metric_name: str | None
    metric_value: float | None
    text_value: str | None
    qualifiers: dict[str, Any]


class FileManifestRecord(BaseModel):
    file_id: str
    original_filename: str
    physical_path: str
    schema_fingerprint: str
    row_count: int
    parsed_row_count: int
    rejected_row_count: int
    is_empty: bool
    duplicate_of_file_id: str | None
    ingestion_status: str
    adapter_name: str
    adapter_version: str
    canonical_row_count: int = 0
    schema_contract_id: str | None = None
    schema_family: str | None = None
    source_columns: list[str] = Field(default_factory=list)


class IngestionSchemaRecord(BaseModel):
    schema_family: str
    file_count: int
    unique_payloads: int
    source_rows: int
    canonical_observations: int
    disposition: str


class IngestionModuleRecord(BaseModel):
    module: str
    physical_files: int
    unique_payloads: int
    source_rows: int
    canonical_observations: int


class OntologyFieldRecord(BaseModel):
    name: str
    data_type: str
    meaning: str
    role: str
    populated_from: str


class OntologyEntityRecord(BaseModel):
    entity: str
    purpose: str
    table: str
    fields: list[OntologyFieldRecord]


class IngestionOverviewResponse(BaseModel):
    run_id: str | None
    physical_files: int
    unique_payloads: int
    duplicate_references: int
    parsed_files: int
    quarantined_files: int
    empty_files: int
    source_rows: int
    canonical_observations: int
    rule_eligible_observations: int = 0
    evaluated_signals: int = 0
    blocked_evaluations: int = 0
    modules: list[IngestionModuleRecord]
    schemas: list[IngestionSchemaRecord]
    ontology: list[OntologyEntityRecord]


class SchemaSummaryRecord(BaseModel):
    schema_family: str
    file_count: int
    row_count: int


class ReferenceChecks(BaseModel):
    physical_csv_entries: int
    unique_payloads: int
    prompts: int
    avg_visibility_score: float | None
    prompts_zero_score: int
    prompts_below_050: int
    citation_rows_proxy: int
    unique_urls: int
    unique_domains: int


class ChatCitation(BaseModel):
    citation_text: str
    file_id: str
    source_row: int
    record_id: str
    url: str | None = None
    evidence_ref: str | None = None


class ChatHistoryTurn(BaseModel):
    role: Literal['user', 'assistant']
    content: str


class AssistantPriority(BaseModel):
    title: str
    why_it_matters: str
    status: str
    recommended_next_step: str
    confidence: str
    evidence_refs: list[str] = Field(default_factory=list)


class LeadershipChatRequest(BaseModel):
    question: str
    signal_instance_id: str | None = None
    mode: str = "EXECUTIVE"
    history_enabled: bool = False
    history: list[ChatHistoryTurn] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class LeadershipChatResponse(BaseModel):
    answer: str
    ai_available: bool
    citations: list[ChatCitation]
    limitations: list[str]
    retrieved_record_ids: list[str]
    headline: str | None = None
    priorities: list[AssistantPriority] = Field(default_factory=list)
    decision_required: str | None = None
    evidence_references: dict[str, ChatCitation] = Field(default_factory=dict)
    fallback_used: bool = False

class SignalEvidenceRef(BaseModel):
    record_id: str
    file_id: str
    source_row: int


class SignalInstanceRecord(BaseModel):
    signal_instance_id: str
    signal_rule_id: str
    signal_rule_version: int
    brand_id: str
    market: str
    assessment_run_id: str
    signal_type: str
    group_key: str
    title: str
    description: str
    current_value: float
    baseline_value: float | None
    delta: float | None
    runs_affected: int
    engines_affected: int
    business_priority: str
    severity: str
    confidence: float
    evidence_count: int
    diagnosis_status: str
    truth_validation_status: str
    workflow_status: str
    governance_status: str = "EXPERIMENTAL"
    rule_source: str = "KENVUE_PROPOSED_RULE"
    metric_contract_id: str | None = None
    metric_validation_status: str = "PROVISIONAL_INFERRED"
    data_provenance: str = "SOURCE_PAYLOAD"
    known_limitations: list[str] = Field(default_factory=list)
    business_title: str | None = None
    business_summary: str | None = None
    business_meaning: str | None = None
    business_impact: str | None = None
    recommended_next_step: str | None = None
    do_not_conclude: str | None = None
    status_label: str | None = None
    confidence_label: str | None = None
    evidence_summary: str | None = None
    technical_title: str | None = None
    technical_metric: str | None = None
    technical_value: float | None = None
    technical_threshold: float | None = None
    technical_rule: str | None = None
    technical_evidence_count: int | None = None


class SignalEvaluateResponse(BaseModel):
    run_id: str
    evaluated_signal_count: int
    signals: list[SignalInstanceRecord]


class SignalEvidenceRecord(BaseModel):
    record_id: str
    file_id: str
    source_row: int
    evidence_role: str
    original_filename: str
    metric_name: str | None
    metric_value: float | None
    text_value: str | None
    qualifiers: dict[str, Any]
    payload_sha256: str | None = None
    schema_contract_id: str | None = None
    assessment_run_id: str | None = None
    engine: str | None = None


class SignalHistoryPoint(BaseModel):
    assessment_run_id: str
    current_value: float
    severity: str
    confidence: float
    workflow_status: str
    created_at: str


class SignalComparisonItem(BaseModel):
    label: str
    value: float | None
    sample_count: int | None = None


class SignalComparisonsResponse(BaseModel):
    engine_comparison_basis: str
    engine_comparison: list[SignalComparisonItem]
    competitor_comparison_basis: str
    competitor_comparison: list[SignalComparisonItem]


class InterventionRecord(BaseModel):
    intervention_id: str
    signal_instance_id: str
    brand_id: str
    market: str
    business_problem: str
    diagnosed_cause: str
    recommended_action: str
    target_prompt_id: str | None
    target_product_id: str | None
    target_claim_id: str | None
    target_page_id: str | None
    approved_evidence: str | None
    risk_route: str | None
    owner: str | None
    approver: str | None
    status: str
    priority: str
    confidence: float
    baseline_run_id: str | None
    baseline_metric: float | None
    target_metric: float | None
    planned_publish_date: str | None
    actual_publish_date: str | None
    retest_date: str | None
    created_at: str | None = None
    updated_at: str | None = None


class InterventionCreateRequest(BaseModel):
    signal_instance_id: str
    business_problem: str
    diagnosed_cause: str
    recommended_action: str
    target_prompt_id: str | None = None
    target_product_id: str | None = None
    target_claim_id: str | None = None
    target_page_id: str | None = None
    approved_evidence: str | None = None
    risk_route: str | None = None
    owner: str | None = None
    priority: str = "MEDIUM"


class InterventionUpdateRequest(BaseModel):
    business_problem: str | None = None
    diagnosed_cause: str | None = None
    recommended_action: str | None = None
    target_prompt_id: str | None = None
    target_product_id: str | None = None
    target_claim_id: str | None = None
    target_page_id: str | None = None
    approved_evidence: str | None = None
    risk_route: str | None = None
    owner: str | None = None
    approver: str | None = None
    priority: str | None = None
    confidence: float | None = None
    baseline_run_id: str | None = None
    baseline_metric: float | None = None
    target_metric: float | None = None
    planned_publish_date: str | None = None
    actual_publish_date: str | None = None
    retest_date: str | None = None


class InterventionTransitionRequest(BaseModel):
    target_status: str


class InterventionListResponse(BaseModel):
    interventions: list[InterventionRecord]
    total_count: int


class InterventionBriefResponse(BaseModel):
    intervention_id: str
    brief_type: str
    brand_id: str
    market: str
    business_problem: str
    diagnosed_cause: str
    recommended_action: str
    signal: dict[str, Any]
    approved_claim: dict[str, Any]
    target_page: dict[str, Any]
    owner: str | None
    approver: str | None
    risk_route: str | None
    baseline_metric: float | None
    target_metric: float | None
    retest_date: str | None
    status: str
    note: str


class OutcomeRecord(BaseModel):
    outcome_id: str
    intervention_id: str
    baseline_run_id: str | None
    post_change_run_id: str | None
    published_at: str | None
    retested_at: str | None
    baseline_value: float | None
    post_change_value: float | None
    absolute_delta: float | None
    percentage_delta: float | None
    engines_improved: int | None
    prompts_improved: int | None
    citation_share_before: float | None
    citation_share_after: float | None
    competitor_delta: float | None
    outcome_status: str
    confidence: float
    comparison_limitations: str | None
    brand_id: str | None = None
    market: str | None = None
    language: str | None = None
    source_system: str | None = None
    metric_contract_id: str | None = None
    context_provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class MeasureInterventionRequest(BaseModel):
    post_change_run_id: str


class ClaimTruthRecord(BaseModel):
    claim_id: str
    brand_id: str
    claim_text: str
    consensus_accuracy_score: float | None
    approval_status: str
    approver: str | None
    last_reviewed_date: str | None
    evidence_reference: str | None


class ContentAssetRecord(BaseModel):
    asset_id: str
    brand_id: str
    canonical_url: str
    content_type: str
    readiness_status: str
    content_owner: str | None
    approver: str | None
    last_reviewed_date: str | None


class PromptPriorityRecord(BaseModel):
    prompt_id: str
    brand_id: str
    prompt_text: str
    priority_level: str
    category: str | None
    is_hero: bool
    approved_by: str | None


class SeedFixturesResponse(BaseModel):
    seeded: dict[str, int]
    message: str


class MetricContractRecord(BaseModel):
    metric_id: str
    metric_name: str
    module: str
    description: str
    direction: str
    grain: str
    calculated_by: str
    validation_status: str
    created_at: str | None = None


class SchemaContractRecord(BaseModel):
    schema_family: str
    adapter_name: str
    expected_columns: list[str]
    description: str
    created_at: str | None = None


class AssessmentRunRecord(BaseModel):
    run_id: str
    brand_id: str
    market: str
    language: str | None
    acquisition_date: str | None
    source_system: str = 'BrandRank'
    module: str | None = None
    context_provenance: dict[str, str] = Field(default_factory=dict)
    quality_status: str = 'PROVISIONAL'
    ingested_at: str | None = None


class SemanticBlockerRecord(BaseModel):
    blocker_id: str
    target_entity: str
    blocker_type: str
    description: str
    status: str
    created_at: str | None = None


class VendorQuestionRecord(BaseModel):
    question_id: str
    topic: str
    question_text: str
    status: str
    created_at: str | None = None


class CurrentContextRecord(BaseModel):
    brand_id: str
    brand_display: str
    market: str
    language: str
    assessment_run_id: str | None
    source_system: str
    semantic_trust_state: str
    context_provenance: dict[str, str] = Field(default_factory=dict)


class EvidenceExplorerRecord(BaseModel):
    evidence_ref: str
    evidence_type: str
    record_id: str | None
    file_id: str | None
    source_row: int | None
    assessment_run_id: str | None
    title: str
    detail: str
    source_url: str | None = None
    payload_sha256: str | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)


class EvidenceExplorerResponse(BaseModel):
    items: list[EvidenceExplorerRecord]
    total_count: int
    limit: int
    offset: int
