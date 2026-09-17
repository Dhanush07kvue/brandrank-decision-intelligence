from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json


def normalize_header(name: str) -> str:
    return ''.join(ch for ch in (name or '').strip().lower() if ch.isalnum() or ch == '_')


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = ' '.join(value.strip().split())
    return cleaned or None


def normalize_url(value: str | None) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    return text.rstrip('/').lower()


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    return False


def _as_float(value: Any) -> float:
    if _is_blank(value):
        raise ValueError('blank')
    return float(str(value).strip())


@dataclass(frozen=True)
class SchemaContract:
    contract_id: str
    version: str
    schema_family: str
    required_headers: tuple[str, ...]
    optional_headers: tuple[str, ...]
    row_type_column: str | None = None

    @property
    def expected_headers(self) -> set[str]:
        return set(self.required_headers) | set(self.optional_headers)


@dataclass(frozen=True)
class ContractMatch:
    status: str
    contract: SchemaContract | None
    missing_required_headers: tuple[str, ...]
    additional_headers: tuple[str, ...]
    candidate_contract_ids: tuple[str, ...]


@dataclass(frozen=True)
class RowValidation:
    accepted: bool
    row_error_type: str | None
    row_error_message: str | None
    normalized_row: dict[str, Any]
    additional_fields: dict[str, Any]


AI_VISIBILITY_V1 = SchemaContract(
    contract_id='AI_VISIBILITY_V1',
    version='1.0.0',
    schema_family='ai_visibility',
    required_headers=('rowtype', 'searchterm'),
    optional_headers=('cohort', 'brandname', 'rank', 'ishero', 'llm', 'sourcename', 'sourceurl'),
    row_type_column='rowtype',
)

CONTENT_READINESS_V1 = SchemaContract(
    contract_id='CONTENT_READINESS_V1',
    version='1.0.0',
    schema_family='content_readiness',
    required_headers=('groupname', 'factorname', 'score'),
    optional_headers=('pagelabel', 'drawerpayload'),
)

VULNERABILITY_ACCURACY_V1 = SchemaContract(
    contract_id='VULNERABILITY_ACCURACY_V1',
    version='1.0.0',
    schema_family='vulnerability_accuracy',
    required_headers=('rowtype', 'statementtext'),
    optional_headers=(
        'statementstatus',
        'overallscore',
        'consensusaccuracyscore',
        'llm',
        'model',
        'llmstatus',
        'llmaccuracyscore',
        'llmanalysis',
    ),
    row_type_column='rowtype',
)

SEARCH_TERM_SUMMARY_V1 = SchemaContract(
    contract_id='SEARCH_TERM_SUMMARY_V1',
    version='1.0.0',
    schema_family='search_term_summary',
    required_headers=('text', 'score', 'category_name'),
    optional_headers=('label', 'heroscore', 'trend', 'category_id', 'category_is_branded'),
)


SCHEMA_CONTRACTS: tuple[SchemaContract, ...] = (
    AI_VISIBILITY_V1,
    CONTENT_READINESS_V1,
    VULNERABILITY_ACCURACY_V1,
    SEARCH_TERM_SUMMARY_V1,
)


def _row_value(row: dict[str, Any], normalized_field: str) -> Any:
    for key, value in row.items():
        if normalize_header(key) == normalized_field:
            return value
    return None


def _match_candidates(headers: list[str]) -> tuple[list[SchemaContract], list[tuple[SchemaContract, tuple[str, ...], int]]]:
    header_set = set(headers)
    exact_matches: list[SchemaContract] = []
    near_matches: list[tuple[SchemaContract, tuple[str, ...], int]] = []

    for contract in SCHEMA_CONTRACTS:
        missing = tuple(sorted(set(contract.required_headers) - header_set))
        overlap = len(header_set & contract.expected_headers)
        if not missing:
            exact_matches.append(contract)
        elif overlap:
            near_matches.append((contract, missing, overlap))
    return exact_matches, near_matches


def classify_contract(headers: list[str]) -> ContractMatch:
    normalized_headers = [normalize_header(h) for h in headers if normalize_header(h)]
    exact_matches, near_matches = _match_candidates(normalized_headers)

    if len(exact_matches) > 1:
        return ContractMatch(
            status='AMBIGUOUS',
            contract=None,
            missing_required_headers=(),
            additional_headers=(),
            candidate_contract_ids=tuple(sorted(c.contract_id for c in exact_matches)),
        )
    if len(exact_matches) == 1:
        contract = exact_matches[0]
        additional = sorted(set(normalized_headers) - contract.expected_headers)
        return ContractMatch(
            status='MATCHED',
            contract=contract,
            missing_required_headers=(),
            additional_headers=tuple(additional),
            candidate_contract_ids=(contract.contract_id,),
        )
    if near_matches:
        near_matches.sort(key=lambda item: item[2], reverse=True)
        top_overlap = near_matches[0][2]
        tied = [item for item in near_matches if item[2] == top_overlap]
        if len(tied) > 1:
            return ContractMatch(
                status='AMBIGUOUS',
                contract=None,
                missing_required_headers=(),
                additional_headers=(),
                candidate_contract_ids=tuple(sorted(item[0].contract_id for item in tied)),
            )
        contract, missing, _ = tied[0]
        return ContractMatch(
            status='MISSING_REQUIRED_HEADERS',
            contract=contract,
            missing_required_headers=missing,
            additional_headers=(),
            candidate_contract_ids=(contract.contract_id,),
        )

    return ContractMatch(
        status='UNSUPPORTED',
        contract=None,
        missing_required_headers=(),
        additional_headers=(),
        candidate_contract_ids=(),
    )


def _validate_visibility(row: dict[str, Any]) -> RowValidation:
    row_type = normalize_text(str(_row_value(row, 'rowtype') or '').lower())
    search_term = normalize_text(_row_value(row, 'searchterm'))
    if _is_blank(search_term):
        return RowValidation(False, 'missing_required_value', 'searchTerm is required', {}, {})

    normalized = {
        'rowType': row_type,
        'searchTerm': search_term,
        'cohort': normalize_text(_row_value(row, 'cohort')),
        'brandName': normalize_text(_row_value(row, 'brandname')),
        'llm': normalize_text(_row_value(row, 'llm')),
        'sourceName': normalize_text(_row_value(row, 'sourcename')),
        'sourceUrl': normalize_url(_row_value(row, 'sourceurl')),
        'isHero': normalize_text(_row_value(row, 'ishero')),
    }

    rank_value = _row_value(row, 'rank')
    if row_type == 'ranking':
        if _is_blank(normalized['brandName']):
            return RowValidation(False, 'missing_required_value', 'brandName is required for rowType=ranking', {}, {})
        try:
            normalized['rank'] = _as_float(rank_value)
        except (TypeError, ValueError):
            return RowValidation(False, 'invalid_numeric', 'rank must be numeric for rowType=ranking', {}, {})
    elif row_type == 'source':
        if _is_blank(normalized['sourceName']) and _is_blank(normalized['sourceUrl']):
            return RowValidation(False, 'missing_required_value', 'sourceName or sourceUrl is required for rowType=source', {}, {})
        normalized['rank'] = None
    else:
        return RowValidation(False, 'unknown_row_type', f'Unknown rowType "{row_type or ""}" for AI_VISIBILITY_V1', {}, {})

    return RowValidation(True, None, None, normalized, {})


def _validate_readiness(row: dict[str, Any]) -> RowValidation:
    normalized = {
        'pageUrl': normalize_url(_row_value(row, 'pageurl')),
        'pageLabel': normalize_text(_row_value(row, 'pagelabel')),
        'groupName': normalize_text(_row_value(row, 'groupname')),
        'factorName': normalize_text(_row_value(row, 'factorname')),
        'drawerPayload': _row_value(row, 'drawerpayload'),
    }
    if _is_blank(normalized['pageUrl']):
        label = (normalized.get('pageLabel') or '').lower()
        if 'brand overview' in label:
            normalized['pageUrl'] = None
            normalized['isBrandOverview'] = True
        else:
            return RowValidation(False, 'missing_required_value', 'pageUrl is required unless pageLabel is Brand Overview', {}, {})
    else:
        normalized['isBrandOverview'] = False
    if _is_blank(normalized['groupName']):
        return RowValidation(False, 'missing_required_value', 'groupName is required', {}, {})
    if _is_blank(normalized['factorName']):
        return RowValidation(False, 'missing_required_value', 'factorName is required', {}, {})
    try:
        normalized['score'] = _as_float(_row_value(row, 'score'))
    except (TypeError, ValueError):
        return RowValidation(False, 'invalid_numeric', 'score must be numeric', {}, {})

    additional: dict[str, Any] = {}
    payload_raw = normalized['drawerPayload']
    if _is_blank(payload_raw):
        normalized['drawerPayloadJson'] = None
        normalized['drawerPayloadRaw'] = None
    else:
        payload_text = str(payload_raw)
        try:
            normalized['drawerPayloadJson'] = json.loads(payload_text)
            normalized['drawerPayloadRaw'] = None
        except json.JSONDecodeError:
            normalized['drawerPayloadJson'] = None
            normalized['drawerPayloadRaw'] = payload_text
            additional['drawerPayloadMalformed'] = True

    return RowValidation(True, None, None, normalized, additional)


def _validate_vulnerability(row: dict[str, Any]) -> RowValidation:
    row_type = normalize_text(str(_row_value(row, 'rowtype') or '').lower())
    statement_text = normalize_text(_row_value(row, 'statementtext'))
    if _is_blank(statement_text):
        return RowValidation(False, 'missing_required_value', 'statementText is required', {}, {})

    normalized = {
        'rowType': row_type,
        'statementText': statement_text,
        'statementStatus': normalize_text(_row_value(row, 'statementstatus')),
        'llm': normalize_text(_row_value(row, 'llm')),
        'model': normalize_text(_row_value(row, 'model')),
        'llmStatus': normalize_text(_row_value(row, 'llmstatus')),
        'llmAnalysis': normalize_text(_row_value(row, 'llmanalysis')),
    }

    def optional_number(field_name: str) -> float | None:
        value = _row_value(row, field_name)
        if _is_blank(value):
            return None
        return _as_float(value)

    try:
        normalized['overallScore'] = optional_number('overallscore')
        normalized['consensusAccuracyScore'] = optional_number('consensusaccuracyscore')
        normalized['llmAccuracyScore'] = optional_number('llmaccuracyscore')
    except (TypeError, ValueError):
        return RowValidation(False, 'invalid_numeric', 'One or more numeric fields are invalid', {}, {})

    if row_type == 'summary':
        if normalized['overallScore'] is None and normalized['consensusAccuracyScore'] is None:
            return RowValidation(
                False,
                'missing_required_value',
                'overallScore or consensusAccuracyScore is required for rowType=summary',
                {},
                {},
            )
    elif row_type == 'llm':
        if _is_blank(normalized['llm']):
            return RowValidation(False, 'missing_required_value', 'llm is required for rowType=llm', {}, {})
        if normalized['llmAccuracyScore'] is None:
            return RowValidation(False, 'missing_required_value', 'llmAccuracyScore is required for rowType=llm', {}, {})
    else:
        return RowValidation(False, 'unknown_row_type', f'Unknown rowType "{row_type or ""}" for VULNERABILITY_ACCURACY_V1', {}, {})

    return RowValidation(True, None, None, normalized, {})


def _validate_summary(row: dict[str, Any]) -> RowValidation:
    normalized = {
        'text': normalize_text(_row_value(row, 'text')),
        'category_name': normalize_text(_row_value(row, 'category_name')),
        'label': normalize_text(_row_value(row, 'label')),
        'trend': normalize_text(_row_value(row, 'trend')),
        'category_id': normalize_text(_row_value(row, 'category_id')),
        'category_is_branded': normalize_text(_row_value(row, 'category_is_branded')),
    }
    if _is_blank(normalized['text']):
        return RowValidation(False, 'missing_required_value', 'text is required', {}, {})
    if _is_blank(normalized['category_name']):
        return RowValidation(False, 'missing_required_value', 'category_name is required', {}, {})
    try:
        normalized['score'] = _as_float(_row_value(row, 'score'))
    except (TypeError, ValueError):
        return RowValidation(False, 'invalid_numeric', 'score must be numeric', {}, {})

    hero_score_raw = _row_value(row, 'heroscore')
    if _is_blank(hero_score_raw):
        normalized['heroScore'] = None
    else:
        try:
            normalized['heroScore'] = _as_float(hero_score_raw)
        except (TypeError, ValueError):
            return RowValidation(False, 'invalid_numeric', 'heroScore must be numeric when provided', {}, {})

    return RowValidation(True, None, None, normalized, {})


def validate_row(contract: SchemaContract, row: dict[str, Any]) -> RowValidation:
    if contract.contract_id == AI_VISIBILITY_V1.contract_id:
        return _validate_visibility(row)
    if contract.contract_id == CONTENT_READINESS_V1.contract_id:
        return _validate_readiness(row)
    if contract.contract_id == VULNERABILITY_ACCURACY_V1.contract_id:
        return _validate_vulnerability(row)
    if contract.contract_id == SEARCH_TERM_SUMMARY_V1.contract_id:
        return _validate_summary(row)
    return RowValidation(False, 'unsupported_contract', f'Unsupported contract {contract.contract_id}', {}, {})


def canonical_projection(contract: SchemaContract, row: dict[str, Any]) -> tuple[str | None, float | None, str | None]:
    if contract.contract_id == AI_VISIBILITY_V1.contract_id:
        row_type = row.get('rowType')
        if row_type == 'ranking':
            return 'rank', row.get('rank'), row.get('searchTerm')
        return None, None, row.get('searchTerm')
    if contract.contract_id == CONTENT_READINESS_V1.contract_id:
        return 'score', row.get('score'), row.get('factorName')
    if contract.contract_id == VULNERABILITY_ACCURACY_V1.contract_id:
        if row.get('rowType') == 'summary':
            value = row.get('consensusAccuracyScore')
            if value is None:
                value = row.get('overallScore')
            return 'consensusAccuracyScore', value, row.get('statementText')
        return 'llmAccuracyScore', row.get('llmAccuracyScore'), row.get('statementText')
    if contract.contract_id == SEARCH_TERM_SUMMARY_V1.contract_id:
        return 'score', row.get('score'), row.get('text')
    return None, None, None
