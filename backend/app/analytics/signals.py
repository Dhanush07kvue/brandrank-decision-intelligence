from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import hashlib
import json
import statistics

import yaml
from app.settings import settings

CONFIG_PATH = Path(__file__).resolve().parents[3] / 'config' / 'signal_rules.yaml'


@dataclass
class SignalRule:
    signal_rule_id: str
    version: int
    enabled: bool
    name: str
    signal_type: str
    module: str
    evaluator: str
    description_template: str
    business_priority: str
    default_workflow_status: str
    conditions: dict[str, Any]
    severity_bands: list[dict[str, Any]]
    default_severity: str
    governance_status: str = 'EXPERIMENTAL'
    blocked_reason: str | None = None
    rule_source: str = 'KENVUE_PROPOSED_RULE'
    metric_contract_dependencies: list[str] = field(default_factory=list)
    minimum_metric_validation_status: str = 'PROVISIONAL_INFERRED'
    known_limitations: list[str] = field(default_factory=list)


@dataclass
class SignalCandidate:
    group_key: str
    current_value: float
    engines_affected: int
    evidence: list[dict[str, Any]]
    extra: dict[str, Any] = field(default_factory=dict)


def load_rules(config_path: Path | None = None) -> list[SignalRule]:
    path = config_path or CONFIG_PATH
    raw = yaml.safe_load(path.read_text(encoding='utf-8'))
    rules: list[SignalRule] = []
    for r in raw.get('rules', []):
        rules.append(
            SignalRule(
                signal_rule_id=r['signal_rule_id'],
                version=int(r['version']),
                enabled=bool(r.get('enabled', True)),
                name=r['name'],
                signal_type=r['signal_type'],
                module=r['module'],
                evaluator=r['evaluator'],
                description_template=r['description_template'],
                business_priority=r['business_priority'],
                default_workflow_status=r['default_workflow_status'],
                conditions=r.get('conditions', {}),
                severity_bands=r.get('severity_bands', []),
                default_severity=r.get('default_severity', 'LOW'),
                governance_status=r.get('governance_status', 'EXPERIMENTAL'),
                blocked_reason=r.get('blocked_reason'),
                rule_source=r.get('rule_source', 'KENVUE_PROPOSED_RULE'),
                metric_contract_dependencies=r.get('metric_contract_dependencies', []),
                minimum_metric_validation_status=r.get('minimum_metric_validation_status', 'PROVISIONAL_INFERRED'),
                known_limitations=r.get('known_limitations', []),
            )
        )
    return rules


def calculate_severity(value: float, rule: SignalRule) -> str:
    comparator = rule.conditions.get('comparator', 'below')
    bands = rule.severity_bands
    if comparator == 'below':
        for band in sorted(bands, key=lambda b: b.get('max', float('inf'))):
            if value <= band['max']:
                return band['severity']
    else:
        for band in sorted(bands, key=lambda b: b.get('min', float('-inf')), reverse=True):
            if value >= band['min']:
                return band['severity']
    return rule.default_severity


def calculate_confidence(evidence_count: int, runs_affected: int, engines_affected: int, min_runs: int = 1) -> float:
    evidence_component = min(1.0, evidence_count / 10) * 0.5
    persistence_component = min(1.0, runs_affected / max(min_runs, 1)) * 0.3
    engine_component = min(1.0, max(engines_affected, 1) / 3) * 0.2
    return round(min(1.0, evidence_component + persistence_component + engine_component), 2)


def _mk_signal_instance_id(rule_id: str, version: int, run_id: str, brand_id: str, market: str, group_key: str) -> str:
    seed = f"{rule_id}|{version}|{run_id}|{brand_id}|{market}|{group_key}"
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]


def _rows_json(con, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


EVALUATORS: dict[str, Callable[[Any, str, str, str, SignalRule], list[SignalCandidate]]] = {}


def _register(name: str):
    def deco(fn):
        EVALUATORS[name] = fn
        return fn
    return deco


@_register('visibility_gap')
def _eval_visibility_gap(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    priority_clause = ""
    if rule.conditions.get('priority_only'):
        priority_clause = "and json_extract_string(qualifiers_json, '$.row.isHero') = 'True'"

    rows = _rows_json(
        con,
        f'''
        select
          json_extract_string(qualifiers_json, '$.row.searchTerm') as group_key,
          json_extract_string(qualifiers_json, '$.row.cohort') as engine,
          try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double) as value,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and module = 'Visibility'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'ranking'
          and lower(json_extract_string(qualifiers_json, '$.row.brandName')) = lower(?)
          {priority_clause}
        ''',
        [run_id, brand_display],
    )

    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r['group_key'] is None or r['value'] is None:
            continue
        groups.setdefault(r['group_key'], []).append(r)

    threshold = rule.conditions['threshold']
    min_evidence_rows = rule.conditions.get('min_evidence_rows', 1)
    candidates: list[SignalCandidate] = []
    for group_key, group_rows in groups.items():
        if len(group_rows) < min_evidence_rows:
            continue
        avg_value = sum(r['value'] for r in group_rows) / len(group_rows)
        if avg_value >= threshold:
            continue
        engines = {r['engine'] for r in group_rows if r['engine']}
        candidates.append(
            SignalCandidate(
                group_key=group_key,
                current_value=avg_value,
                engines_affected=len(engines) or 1,
                evidence=[{'record_id': r['record_id'], 'file_id': r['file_id'], 'source_row': r['source_row']} for r in group_rows],
            )
        )
    return candidates


@_register('cross_llm_inconsistency')
def _eval_cross_llm_inconsistency(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    rows = _rows_json(
        con,
        '''
        select
          json_extract_string(qualifiers_json, '$.row.statementText') as group_key,
          json_extract_string(qualifiers_json, '$.row.llm') as engine,
          try_cast(json_extract_string(qualifiers_json, '$.row.llmAccuracyScore') as double) as value,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and module = 'AI Vulnerability'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'llm'
        ''',
        [run_id],
    )

    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r['group_key'] is None or r['value'] is None:
            continue
        groups.setdefault(r['group_key'], []).append(r)

    threshold = rule.conditions['threshold']
    min_evidence_rows = rule.conditions.get('min_evidence_rows', 3)
    candidates: list[SignalCandidate] = []
    for group_key, group_rows in groups.items():
        if len(group_rows) < min_evidence_rows:
            continue
        values = [r['value'] for r in group_rows]
        spread = statistics.pstdev(values)
        if spread <= threshold:
            continue
        engines = {r['engine'] for r in group_rows if r['engine']}
        candidates.append(
            SignalCandidate(
                group_key=group_key,
                current_value=spread,
                engines_affected=len(engines) or 1,
                evidence=[{'record_id': r['record_id'], 'file_id': r['file_id'], 'source_row': r['source_row']} for r in group_rows],
            )
        )
    return candidates


@_register('claim_substantiation_risk')
def _eval_claim_substantiation_risk(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    rows = _rows_json(
        con,
        '''
        select
          json_extract_string(qualifiers_json, '$.row.statementText') as group_key,
          try_cast(json_extract_string(qualifiers_json, '$.row.consensusAccuracyScore') as double) as value,
          json_extract_string(qualifiers_json, '$.row.statementStatus') as statement_status,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and module = 'AI Vulnerability'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'summary'
        ''',
        [run_id],
    )

    engine_counts = _rows_json(
        con,
        '''
        select json_extract_string(qualifiers_json, '$.row.statementText') as group_key,
               count(distinct json_extract_string(qualifiers_json, '$.row.llm')) as engines
        from canonical_observations
        where run_id = ?
          and module = 'AI Vulnerability'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'llm'
        group by 1
        ''',
        [run_id],
    )
    engine_map = {r['group_key']: r['engines'] for r in engine_counts if r['group_key']}

    threshold = rule.conditions['threshold']
    min_evidence_rows = rule.conditions.get('min_evidence_rows', 1)
    candidates: list[SignalCandidate] = []
    for r in rows:
        if r['group_key'] is None:
            continue
        value = r['value']
        if value is None:
            continue
        if value >= threshold:
            continue
        evidence = [{'record_id': r['record_id'], 'file_id': r['file_id'], 'source_row': r['source_row']}]
        if len(evidence) < min_evidence_rows:
            continue
        candidates.append(
            SignalCandidate(
                group_key=r['group_key'],
                current_value=value,
                engines_affected=engine_map.get(r['group_key'], 1),
                evidence=evidence,
                extra={'disputed': r['statement_status'] == 'False'},
            )
        )
    return candidates


@_register('readiness_deterioration')
def _eval_readiness_deterioration(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    rows = _rows_json(
        con,
        '''
        select
          json_extract_string(qualifiers_json, '$.row.groupName') as group_key,
          try_cast(json_extract_string(qualifiers_json, '$.row.weightedScore') as double) as value,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and module = 'Content Readiness'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'summary'
          and json_extract_string(qualifiers_json, '$.row.weightedScore') is not null
        ''',
        [run_id],
    )

    factor_counts = _rows_json(
        con,
        '''
        select json_extract_string(qualifiers_json, '$.row.groupName') as group_key,
               count(distinct json_extract_string(qualifiers_json, '$.row.llmSource')) as engines
        from canonical_observations
        where run_id = ?
          and module = 'Content Readiness'
          and json_extract_string(qualifiers_json, '$.row.llmSource') is not null
        group by 1
        ''',
        [run_id],
    )
    factor_map = {r['group_key']: r['engines'] for r in factor_counts if r['group_key']}

    threshold = rule.conditions['threshold']
    min_evidence_rows = rule.conditions.get('min_evidence_rows', 1)
    candidates: list[SignalCandidate] = []
    for r in rows:
        if r['group_key'] is None or r['value'] is None:
            continue
        if r['value'] >= threshold:
            continue
        evidence = [{'record_id': r['record_id'], 'file_id': r['file_id'], 'source_row': r['source_row']}]
        if len(evidence) < min_evidence_rows:
            continue
        candidates.append(
            SignalCandidate(
                group_key=r['group_key'],
                current_value=r['value'],
                engines_affected=factor_map.get(r['group_key'], 1),
                evidence=evidence,
            )
        )
    return candidates


@_register('competitive_playbook_risk')
def _eval_competitive_playbook_risk(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    """Turn explicit competitive playbook rows into prompt-level findings.

    These are source-reported opportunities, not proof of causal competitive
    advantage. The source row and its recommended action remain attached as
    evidence for review.
    """
    rows = _rows_json(
        con,
        '''
        select
          json_extract_string(qualifiers_json, '$.row.searchTerm') as search_term,
          coalesce(
            json_extract_string(qualifiers_json, '$.row.sourceName'),
            json_extract_string(qualifiers_json, '$.row.competitorName'),
            'Unlabelled competitor/source'
          ) as competitor,
          try_cast(json_extract_string(qualifiers_json, '$.row.scoreDiff') as double) as value,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and schema_family = 'competitive_playbooks'
          and nullif(json_extract_string(qualifiers_json, '$.row.searchTerm'), '') is not null
        ''',
        [run_id],
    )
    threshold = float(rule.conditions.get('threshold', 0.05))
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row['value'] is None or row['value'] <= threshold:
            continue
        key = f"{row['search_term']} — {row['competitor']}"
        groups.setdefault(key, []).append(row)
    return [
        SignalCandidate(
            group_key=key,
            current_value=max(float(row['value']) for row in group_rows),
            engines_affected=1,
            evidence=[{'record_id': row['record_id'], 'file_id': row['file_id'], 'source_row': row['source_row']} for row in group_rows],
            extra={'competitor': group_rows[0]['competitor']},
        )
        for key, group_rows in groups.items()
    ]


@_register('brand_attribute_benchmark')
def _eval_brand_attribute_benchmark(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    """Find scorecard attributes where a competitor exceeds the primary brand."""
    rows = _rows_json(
        con,
        '''
        select
          json_extract_string(qualifiers_json, '$.row.category') as category,
          json_extract_string(qualifiers_json, '$.row.entity') as entity,
          lower(json_extract_string(qualifiers_json, '$.row.isBrand')) as is_brand,
          try_cast(json_extract_string(qualifiers_json, '$.row.score') as double) as value,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and schema_family = 'brand_reputation_scorecards'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'entity'
          and nullif(json_extract_string(qualifiers_json, '$.row.category'), '') is not null
        ''',
        [run_id],
    )
    threshold = float(rule.conditions.get('threshold', 0.05))
    by_category: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row['value'] is not None and row['entity']:
            by_category.setdefault(row['category'], []).append(row)
    candidates: list[SignalCandidate] = []
    for category, category_rows in by_category.items():
        primary = next((row for row in category_rows if row['is_brand'] == 'true' or str(row['entity']).lower() == brand_display.lower()), None)
        competitors = [row for row in category_rows if row is not primary]
        if not primary or not competitors:
            continue
        leader = max(competitors, key=lambda row: float(row['value']))
        gap = float(leader['value']) - float(primary['value'])
        if gap <= threshold:
            continue
        candidates.append(
            SignalCandidate(
                group_key=category,
                current_value=gap,
                engines_affected=len(competitors),
                evidence=[{'record_id': row['record_id'], 'file_id': row['file_id'], 'source_row': row['source_row']} for row in category_rows],
                extra={'competitor': leader['entity'], 'primary_score': primary['value'], 'competitor_score': leader['value']},
            )
        )
    return candidates


@_register('evidence_accessibility_deficit')
def _eval_evidence_accessibility_deficit(con, run_id: str, brand_id: str, brand_display: str, rule: SignalRule) -> list[SignalCandidate]:
    rows = _rows_json(
        con,
        '''
        select
          json_extract_string(qualifiers_json, '$.row.sourceUrl') as source_url,
          record_id, file_id, source_row
        from canonical_observations
        where run_id = ?
          and module = 'Content Readiness'
          and json_extract_string(qualifiers_json, '$.row.rowType') = 'main'
        ''',
        [run_id],
    )

    urls = [r for r in rows if r['source_url']]
    min_evidence_rows = rule.conditions.get('min_evidence_rows', 5)
    if len(urls) < min_evidence_rows:
        return []

    brand_token = brand_id.lower()
    owned = [r for r in urls if brand_token in r['source_url'].lower()]
    ratio = len(owned) / len(urls)

    threshold = rule.conditions['threshold']
    if ratio >= threshold:
        return []

    return [
        SignalCandidate(
            group_key='owned_domain_share',
            current_value=ratio,
            engines_affected=len(urls),
            evidence=[{'record_id': r['record_id'], 'file_id': r['file_id'], 'source_row': r['source_row']} for r in urls],
            extra={'owned_count': len(owned), 'total_count': len(urls)},
        )
    ]


def _count_runs_affected(con, signal_rule_id: str, brand_id: str, market: str, group_key: str, run_id: str) -> int:
    prior = con.execute(
        '''
        select count(distinct assessment_run_id) from signal_instances
        where signal_rule_id = ? and brand_id = ? and market = ? and group_key = ? and assessment_run_id != ?
        ''',
        [signal_rule_id, brand_id, market, group_key, run_id],
    ).fetchone()[0]
    return int(prior or 0) + 1


def _get_baseline_value(con, signal_rule_id: str, brand_id: str, market: str, group_key: str, run_id: str) -> float | None:
    row = con.execute(
        '''
        select current_value from signal_instances
        where signal_rule_id = ? and brand_id = ? and market = ? and group_key = ? and assessment_run_id < ?
        order by assessment_run_id desc
        limit 1
        ''',
        [signal_rule_id, brand_id, market, group_key, run_id],
    ).fetchone()
    return float(row[0]) if row else None


def _build_title_description(rule: SignalRule, brand_display: str, candidate: SignalCandidate, threshold: float) -> tuple[str, str]:
    title = f"{rule.name}: {candidate.group_key}"
    disputed_note = ''
    if candidate.extra.get('disputed'):
        disputed_note = 'This statement is explicitly flagged as unsubstantiated by consensus (statementStatus=False).'
    description = rule.description_template.format(
        brand=brand_display,
        group=candidate.group_key,
        value=candidate.current_value,
        threshold=threshold,
        engines=candidate.engines_affected,
        disputed_note=disputed_note,
        competitor=candidate.extra.get('competitor', 'competitors'),
    )
    return title, description


def business_signal_fields(
    rule: SignalRule,
    group_key: str,
    current_value: float,
    evidence_count: int,
    engines_affected: int,
    workflow_status: str,
    governance_status: str,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Return business-first language while retaining technical fields."""
    subject = group_key if group_key != '__BLOCKED__' else 'this measurement'
    if rule.signal_type == 'CROSS_LLM_INCONSISTENCY':
        business_title = f'AI engines disagree about “{subject}”'
        meaning = 'The monitored AI engines are not giving a consistent view of the same statement.'
        impact = 'A consumer may receive a different answer depending on which AI assistant they use.'
        next_step = 'Compare the engine-level evidence and validate the approved Kenvue claim and source evidence before changing content.'
        do_not_conclude = 'This does not prove the claim is false or that Aveeno has poor AI visibility.'
        metric = 'variation across AI engines'
    elif rule.signal_type == 'CLAIM_AGREEMENT_INVESTIGATION':
        business_title = f'AI systems show mixed agreement on “{subject}”'
        meaning = 'The combined engine view is below the current experimental agreement level.'
        impact = 'The statement may be interpreted differently across AI platforms.'
        next_step = 'Complete Kenvue truth validation before revising or promoting the statement.'
        do_not_conclude = 'A low vendor score alone does not establish that the underlying claim is untrue.'
        metric = 'vendor agreement score'
    elif rule.signal_type == 'READINESS_DETERIORATION':
        business_title = f'This content may be harder for AI systems to use effectively: {subject}'
        meaning = 'The available readiness measure is below the current experimental review level.'
        impact = 'Important product information may be less consistently available to AI systems.'
        next_step = 'Review the underlying factor and its vendor definition before prioritising a content change.'
        do_not_conclude = 'This does not by itself prove that new content is required or that existing content is ineffective.'
        metric = 'vendor content-readiness score'
    elif rule.signal_type == 'VISIBILITY_GAP':
        business_title = 'Possible AI visibility opportunity'
        meaning = 'The available ranking evidence may indicate weaker representation for a priority prompt, but the rank interpretation is unresolved.'
        impact = 'Leadership should not use this finding as a performance conclusion until the vendor definition is confirmed.'
        next_step = 'Resolve the BrandRank rank-encoding question before taking action.'
        do_not_conclude = 'The raw rank value must not be treated as a percentage or as a confirmed visibility loss.'
        metric = 'provisional visibility rank'
    elif rule.signal_type == 'EVIDENCE_ACCESSIBILITY_DEFICIT':
        business_title = 'AI may not be finding enough authoritative evidence'
        meaning = 'The available cited sources contain too little attributable brand-owned evidence.'
        impact = 'AI systems may rely on less authoritative sources when answering about the brand.'
        next_step = 'Review source ownership and machine-readable evidence coverage.'
        do_not_conclude = 'This does not prove that the content is absent or that a content rewrite will improve results.'
        metric = 'brand-owned source share'
    elif rule.signal_type == 'COMPETITIVE_PLAYBOOK_GAP':
        business_title = f'Competitive content opportunity: {subject}'
        meaning = 'The source playbook identifies a competitor or authoritative source associated with a measurable prompt-level advantage.'
        impact = 'Aveeno may be missing content or evidence that helps answer this specific consumer question.'
        next_step = 'Review the linked playbook row, validate the claimed gap, and route any content change through Kenvue truth and MLR review.'
        do_not_conclude = 'A playbook recommendation is an observed opportunity, not proof that one content change will improve every AI engine.'
        metric = 'reported competitive score difference'
    elif rule.signal_type == 'BRAND_ATTRIBUTE_BENCHMARK':
        business_title = f'Competitor leads Aveeno on {subject}'
        meaning = 'A competitor has a higher source-reported brand attribute score than Aveeno in this scorecard.'
        impact = 'This may indicate a perception or positioning area requiring diagnosis, not a confirmed consumer or sales outcome.'
        next_step = 'Review the scorecard and per-engine rationale, validate the interpretation, and define an evidence-backed response before changing messaging.'
        do_not_conclude = 'This scorecard gap does not prove that the competitor is objectively better or that Aveeno content is ineffective.'
        metric = 'competitor minus Aveeno score'
    else:
        business_title = rule.name
        meaning = 'A configured rule found a pattern that requires review.'
        impact = 'The available evidence may affect a downstream content or decision workflow.'
        next_step = 'Open the evidence and confirm the business interpretation before acting.'
        do_not_conclude = 'The finding is not, by itself, proof of causation or claim truth.'
        metric = 'rule value'

    status_labels = {
        'NEEDS_DIAGNOSIS': 'Needs investigation',
        'NEEDS_TRUTH_VALIDATION': 'Needs Kenvue evidence validation',
        'BLOCKED': 'Cannot be used for action yet',
        'GOVERNED': 'Governed signal',
        'EXPERIMENTAL': 'Experimental finding',
    }
    confidence_label = 'High' if (confidence or 0) >= 0.75 else 'Medium' if (confidence or 0) >= 0.5 else 'Low'
    if governance_status == 'BLOCKED':
        confidence_label = 'Not available — blocked by semantic validation'
    return {
        'business_title': business_title,
        'business_summary': f'{business_title}. {meaning}',
        'business_meaning': meaning,
        'business_impact': impact,
        'recommended_next_step': next_step,
        'do_not_conclude': do_not_conclude,
        'status_label': status_labels.get(workflow_status, workflow_status.replace('_', ' ').title()),
        'confidence_label': f'Evidence strength: {confidence_label}',
        'evidence_summary': f'{evidence_count} linked source observation(s) across {engines_affected or 0} AI engine(s).',
        'technical_title': f'{rule.name}: {group_key}',
        'technical_metric': metric,
        'technical_value': current_value,
        'technical_threshold': rule.conditions.get('threshold'),
        'technical_rule': f'{rule.signal_rule_id} v{rule.version}',
        'technical_evidence_count': evidence_count,
    }


def _metric_contract_state(con, rule: SignalRule) -> tuple[str | None, str]:
    contract_id = rule.metric_contract_dependencies[0] if rule.metric_contract_dependencies else None
    if not contract_id:
        return None, rule.minimum_metric_validation_status
    row = con.execute(
        'select validation_status from metric_contracts where metric_id = ?', [contract_id]
    ).fetchone()
    if row and row[0]:
        return contract_id, row[0]
    # Lightweight evaluator tests and a brand-new empty POC database may not
    # have contract seed rows yet. Once the contract registry exists, a missing
    # dependency is correctly treated as unresolved and blocks the rule.
    registry_exists = con.execute('select count(*) from metric_contracts').fetchone()[0] > 0
    return contract_id, rule.minimum_metric_validation_status if not registry_exists else 'UNRESOLVED'


def evaluate_signals(
    con,
    run_id: str,
    brand_id: str | None = None,
    brand_display: str | None = None,
    market: str | None = None,
    config_path: Path | None = None,
) -> list[dict[str, Any]]:
    brand_id = brand_id or settings.brand_id
    brand_display = brand_display or settings.brand_display
    market = market or settings.market
    rules = load_rules(config_path)
    results: list[dict[str, Any]] = []

    for rule in rules:
        if not rule.enabled and rule.governance_status != 'BLOCKED':
            continue

        # BLOCKED rules produce a structured blocked evaluation, not a signal
        metric_contract_id, metric_validation_status = _metric_contract_state(con, rule)
        dependency_blocked = (
            rule.governance_status == 'GOVERNED' and metric_validation_status != 'VERIFIED_VENDOR'
        ) or metric_validation_status == 'UNRESOLVED'
        if rule.governance_status == 'BLOCKED' or dependency_blocked:
            blocked_reason = rule.blocked_reason or (
                f'Metric contract {metric_contract_id or "unresolved"} has validation status '
                f'{metric_validation_status}; this rule cannot produce an eligible signal.'
            )
            blocked_instance = {
                    'signal_instance_id': _mk_signal_instance_id(
                        rule.signal_rule_id, rule.version, run_id, brand_id, market, '__BLOCKED__'
                    ),
                    'signal_rule_id': rule.signal_rule_id,
                    'signal_rule_version': rule.version,
                    'brand_id': brand_id,
                    'market': market,
                    'assessment_run_id': run_id,
                    'signal_type': rule.signal_type,
                    'group_key': '__BLOCKED__',
                    'title': f'[BLOCKED] {rule.name}',
                    'description': blocked_reason,
                    'current_value': 0.0,
                    'baseline_value': None,
                    'delta': None,
                    'runs_affected': 0,
                    'engines_affected': 0,
                    'business_priority': rule.business_priority,
                    'severity': 'BLOCKED',
                    'confidence': 0.0,
                    'evidence_count': 0,
                    'diagnosis_status': 'BLOCKED',
                    'truth_validation_status': 'BLOCKED',
                    'workflow_status': 'BLOCKED',
                    'governance_status': 'BLOCKED',
                    'rule_source': rule.rule_source,
                    'metric_contract_id': metric_contract_id,
                    'metric_validation_status': metric_validation_status,
                    'data_provenance': 'SOURCE_PAYLOAD',
                    'known_limitations': rule.known_limitations,
                    'evidence': [],
                }
            blocked_instance.update(business_signal_fields(
                rule, '__BLOCKED__', 0.0, 0, 0, 'BLOCKED', 'BLOCKED', 0.0,
            ))
            results.append(blocked_instance)
            continue

        evaluator = EVALUATORS.get(rule.evaluator)
        if evaluator is None:
            continue

        candidates = evaluator(con, run_id, brand_id, brand_display, rule)
        for candidate in candidates:
            title, description = _build_title_description(rule, brand_display, candidate, rule.conditions['threshold'])
            runs_affected = _count_runs_affected(con, rule.signal_rule_id, brand_id, market, candidate.group_key, run_id)
            baseline_value = _get_baseline_value(con, rule.signal_rule_id, brand_id, market, candidate.group_key, run_id)
            delta = round(candidate.current_value - baseline_value, 4) if baseline_value is not None else None
            confidence = calculate_confidence(
                evidence_count=len(candidate.evidence),
                runs_affected=runs_affected,
                engines_affected=candidate.engines_affected,
                min_runs=rule.conditions.get('min_runs', 1),
            )
            severity = calculate_severity(candidate.current_value, rule)
            signal_instance_id = _mk_signal_instance_id(
                rule.signal_rule_id, rule.version, run_id, brand_id, market, candidate.group_key
            )

            instance = {
                    'signal_instance_id': signal_instance_id,
                    'signal_rule_id': rule.signal_rule_id,
                    'signal_rule_version': rule.version,
                    'brand_id': brand_id,
                    'market': market,
                    'assessment_run_id': run_id,
                    'signal_type': rule.signal_type,
                    'group_key': candidate.group_key,
                    'title': title,
                    'description': description,
                    'current_value': round(candidate.current_value, 4),
                    'baseline_value': baseline_value,
                    'delta': delta,
                    'runs_affected': runs_affected,
                    'engines_affected': candidate.engines_affected,
                    'business_priority': rule.business_priority,
                    'severity': severity,
                    'confidence': confidence,
                    'evidence_count': len(candidate.evidence),
                    'diagnosis_status': 'NOT_STARTED',
                    'truth_validation_status': 'NOT_STARTED',
                    'workflow_status': rule.default_workflow_status,
                    'governance_status': rule.governance_status,
                    'rule_source': rule.rule_source,
                    'metric_contract_id': metric_contract_id,
                    'metric_validation_status': metric_validation_status,
                    'data_provenance': 'SOURCE_PAYLOAD',
                    'known_limitations': rule.known_limitations,
                    'evidence': candidate.evidence,
                }
            instance.update(business_signal_fields(
                rule, candidate.group_key, round(candidate.current_value, 4), len(candidate.evidence),
                candidate.engines_affected, rule.default_workflow_status, rule.governance_status, confidence,
            ))
            results.append(instance)

    return results


def audit_signal_coverage(
    con,
    run_id: str,
    brand_id: str | None = None,
    brand_display: str | None = None,
    market: str | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Explain exactly what each configured rule received and why it fired.

    This is deliberately read-only. It uses the same row-shape predicates as
    the evaluators, while keeping blocked rules visible as blocked rather than
    silently treating them as zero findings.
    """
    brand_id = brand_id or settings.brand_id
    brand_display = brand_display or settings.brand_display
    market = market or settings.market
    rules = load_rules(config_path)

    specs = {
        'visibility_gap': {
            'module': 'Visibility', 'row_types': ['ranking'], 'key': '$.row.searchTerm',
            'value': "try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double)",
            'where': "lower(json_extract_string(qualifiers_json, '$.row.brandName')) = lower(?)",
            'params': [brand_display], 'input_label': 'Visibility ranking observations',
        },
        'cross_llm_inconsistency': {
            'module': 'AI Vulnerability', 'row_types': ['llm'], 'key': '$.row.statementText',
            'value': "try_cast(json_extract_string(qualifiers_json, '$.row.llmAccuracyScore') as double)",
            'where': 'true', 'params': [], 'input_label': 'Per-engine claim observations',
        },
        'claim_substantiation_risk': {
            'module': 'AI Vulnerability', 'row_types': ['summary'], 'key': '$.row.statementText',
            'value': "try_cast(json_extract_string(qualifiers_json, '$.row.consensusAccuracyScore') as double)",
            'where': 'true', 'params': [], 'input_label': 'Claim consensus summaries',
        },
        'readiness_deterioration': {
            'module': 'Content Readiness', 'row_types': ['summary'], 'key': '$.row.groupName',
            'value': "try_cast(json_extract_string(qualifiers_json, '$.row.weightedScore') as double)",
            'where': 'true', 'params': [], 'input_label': 'Content-readiness summaries',
        },
        'evidence_accessibility_deficit': {
            'module': 'Content Readiness', 'row_types': ['main'], 'key': '$.row.sourceUrl',
            'value': "case when nullif(json_extract_string(qualifiers_json, '$.row.sourceUrl'), '') is not null then 1.0 else null end",
            'where': 'true', 'params': [], 'input_label': 'Referenced-source rows with URLs',
        },
        'competitive_playbook_risk': {
            'module': 'Overview', 'row_types': ['visibility'], 'key': '$.row.searchTerm',
            'value': "try_cast(json_extract_string(qualifiers_json, '$.row.scoreDiff') as double)",
            'where': "schema_family = 'competitive_playbooks'", 'params': [], 'input_label': 'Competitive playbook rows', 'row_type_optional': True,
        },
        'brand_attribute_benchmark': {
            'module': 'AI Vulnerability', 'row_types': ['entity'], 'key': '$.row.category',
            'value': "try_cast(json_extract_string(qualifiers_json, '$.row.score') as double)",
            'where': "schema_family = 'brand_reputation_scorecards'", 'params': [], 'input_label': 'Brand attribute scorecards',
        },
    }

    rule_audit: list[dict[str, Any]] = []
    for rule in rules:
        spec = specs.get(rule.evaluator)
        if spec is None:
            rule_audit.append({
                'rule_id': rule.signal_rule_id, 'name': rule.name, 'signal_type': rule.signal_type,
                'status': rule.governance_status, 'input_observation_type': 'Unknown',
                'eligible_rows': 0, 'groups_evaluated': 0, 'signals_fired': 0,
                'signals_suppressed': 0, 'signals_blocked': 0,
                'reason': 'No evaluator coverage definition is registered.',
            })
            continue

        row_type_placeholders = ','.join('?' for _ in spec['row_types'])
        row_type_clause = 'true' if spec.get('row_type_optional') else f"json_extract_string(qualifiers_json, '$.row.rowType') in ({row_type_placeholders})"
        sql = f'''
            select json_extract_string(qualifiers_json, '{spec['key']}') as group_key,
                   {spec['value']} as value
            from canonical_observations
              where run_id = ? and module = ?
              and {row_type_clause}
              and ({spec['where']})
        '''
        params: list[Any] = [run_id, spec['module'], *([] if spec.get('row_type_optional') else spec['row_types']), *spec['params']]
        rows = _rows_json(con, sql, params)
        usable = [row for row in rows if row['group_key'] not in (None, '') and row['value'] is not None]
        groups = {row['group_key'] for row in usable}
        metric_contract_id, metric_validation_status = _metric_contract_state(con, rule)
        dependency_blocked = (
            rule.governance_status == 'GOVERNED' and metric_validation_status != 'VERIFIED_VENDOR'
        ) or metric_validation_status == 'UNRESOLVED'
        blocked = rule.governance_status == 'BLOCKED' or dependency_blocked
        candidates = EVALUATORS[rule.evaluator](con, run_id, brand_id, brand_display, rule) if not blocked else []
        fired = len(candidates)
        # A blocked rule always produces one persisted global BLOCKED
        # evaluation, even when no candidate rows can be safely interpreted.
        # Keep that evaluation visible in the audit rather than reporting a
        # misleading zero just because the blocked rule had zero eligible groups.
        blocked_count = (max(len(groups), 1) if blocked else 0)
        suppressed = max(len(groups) - fired - blocked_count, 0)
        if blocked:
            reason = rule.blocked_reason or f'Metric contract {metric_contract_id or "unresolved"} is {metric_validation_status}.'
        elif fired:
            reason = f'{fired} group(s) crossed the configured rule condition.'
        elif groups:
            reason = 'Groups were evaluated, but none crossed the configured condition.'
        else:
            reason = 'No eligible rows matched this rule input shape in the selected run.'
        rule_audit.append({
            'rule_id': rule.signal_rule_id, 'name': rule.name, 'signal_type': rule.signal_type,
            'status': 'BLOCKED' if blocked else rule.governance_status,
            'input_observation_type': spec['input_label'], 'eligible_rows': len(usable),
            'groups_evaluated': len(groups), 'signals_fired': fired,
            'signals_suppressed': suppressed, 'signals_blocked': blocked_count,
            'metric_contract_id': metric_contract_id, 'metric_validation_status': metric_validation_status,
            'reason': reason,
        })

    physical = con.execute('select count(*) from file_manifest where run_id = ?', [run_id]).fetchone()[0]
    unique_payloads = con.execute('select count(distinct payload_sha256) from file_manifest where run_id = ?', [run_id]).fetchone()[0]
    parsed_files = con.execute('select count(*) from file_manifest where run_id = ? and parsed_row_count is not null', [run_id]).fetchone()[0]
    recognized_files = con.execute("select count(*) from file_manifest where run_id = ? and ingestion_status not like 'QUARANTINED%' and ingestion_status <> 'EMPTY_UNSUPPORTED'", [run_id]).fetchone()[0]
    source_rows = con.execute('select coalesce(sum(row_count), 0) from file_manifest where run_id = ?', [run_id]).fetchone()[0]
    canonical = con.execute('select count(*) from canonical_observations where run_id = ?', [run_id]).fetchone()[0]
    signal_rows = con.execute('select count(*) from signal_instances where assessment_run_id = ?', [run_id]).fetchone()[0]
    blocked_signals = con.execute("select count(*) from signal_instances where assessment_run_id = ? and governance_status = 'BLOCKED'", [run_id]).fetchone()[0]
    return {
        'run_id': run_id,
        'funnel': {
            'physical_files': int(physical or 0), 'unique_payloads': int(unique_payloads or 0),
            'parsed_files': int(parsed_files or 0), 'recognized_files': int(recognized_files or 0),
            'source_rows': int(source_rows or 0), 'canonical_observations': int(canonical or 0),
            'rule_eligible_observations': int(sum(item['eligible_rows'] for item in rule_audit)),
            'rule_groups_evaluated': int(sum(item['groups_evaluated'] for item in rule_audit)),
            'unique_signals': int(signal_rows or 0), 'blocked_evaluations': int(blocked_signals or 0),
        },
        'rules': rule_audit,
    }


def persist_signal_instances(con, run_id: str, instances: list[dict[str, Any]]) -> None:
    con.execute('delete from signal_evidence where assessment_run_id = ?', [run_id])
    con.execute('delete from signal_instances where assessment_run_id = ?', [run_id])

    for inst in instances:
        con.execute(
            '''
            insert into signal_instances (
              signal_instance_id, signal_rule_id, signal_rule_version, brand_id, market, assessment_run_id,
              signal_type, group_key, title, description, current_value, baseline_value, delta, runs_affected,
              engines_affected, business_priority, severity, confidence, evidence_count, diagnosis_status,
              truth_validation_status, workflow_status, governance_status, rule_source, metric_contract_id,
              metric_validation_status, data_provenance, known_limitations_json
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?
            )
            ''',
            [
                inst['signal_instance_id'], inst['signal_rule_id'], inst['signal_rule_version'], inst['brand_id'],
                inst['market'], inst['assessment_run_id'], inst['signal_type'], inst['group_key'], inst['title'],
                inst['description'], inst['current_value'], inst['baseline_value'], inst['delta'], inst['runs_affected'],
                inst['engines_affected'], inst['business_priority'], inst['severity'], inst['confidence'],
                inst['evidence_count'], inst['diagnosis_status'], inst['truth_validation_status'], inst['workflow_status'],
                inst.get('governance_status', 'EXPERIMENTAL'), inst.get('rule_source', 'KENVUE_PROPOSED_RULE'),
                inst.get('metric_contract_id'), inst.get('metric_validation_status', 'PROVISIONAL_INFERRED'),
                inst.get('data_provenance', 'SOURCE_PAYLOAD'),
                json.dumps(inst.get('known_limitations', []))
            ],
        )
        for ev in inst['evidence']:
            con.execute(
                '''
                insert into signal_evidence (signal_instance_id, assessment_run_id, record_id, file_id, source_row, evidence_role)
                values (?, ?, ?, ?, ?, ?)
                ''',
                [inst['signal_instance_id'], run_id, ev['record_id'], ev['file_id'], ev['source_row'], 'SUPPORTING_OBSERVATION'],
            )


def get_signal_history(con, signal_rule_id: str, brand_id: str, market: str, group_key: str) -> list[dict[str, Any]]:
    return _rows_json(
        con,
        '''
        select assessment_run_id, current_value, severity, confidence, workflow_status, created_at
        from signal_instances
        where signal_rule_id = ? and brand_id = ? and market = ? and group_key = ?
        order by assessment_run_id asc
        ''',
        [signal_rule_id, brand_id, market, group_key],
    )


def get_signal_evidence(con, signal_instance_id: str) -> list[dict[str, Any]]:
    return _rows_json(
        con,
        '''
        select se.record_id, se.file_id, se.source_row, se.evidence_role,
               m.original_filename, c.metric_name, c.metric_value, c.text_value, c.qualifiers_json,
               c.payload_sha256, c.run_id
        from signal_evidence se
        join canonical_observations c on se.record_id = c.record_id and se.assessment_run_id = c.run_id
        join file_manifest m on se.file_id = m.file_id and c.run_id = m.run_id
        where se.signal_instance_id = ?
          and se.assessment_run_id = (
            select assessment_run_id from signal_instances
            where signal_instance_id = ?
          )
        order by se.source_row asc
        ''',
        [signal_instance_id, signal_instance_id],
    )


def get_signal_comparisons(con, signal_type: str, run_id: str, group_key: str, brand_display: str) -> dict[str, Any]:
    if signal_type == 'VISIBILITY_GAP':
        engine_rows = _rows_json(
            con,
            '''
            select json_extract_string(qualifiers_json, '$.row.cohort') as label,
                   avg(try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double)) as value,
                   count(try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double)) as sample_count
            from canonical_observations
            where run_id = ? and module = 'Visibility'
              and json_extract_string(qualifiers_json, '$.row.rowType') = 'ranking'
              and lower(coalesce(json_extract_string(qualifiers_json, '$.row.brandName'), json_extract_string(qualifiers_json, '$.row.competitorName'))) = lower(?)
              and json_extract_string(qualifiers_json, '$.row.searchTerm') = ?
            group by 1
            ''',
            [run_id, brand_display, group_key],
        )
        competitor_rows = _rows_json(
            con,
            '''
            select json_extract_string(qualifiers_json, '$.row.brandName') as label,
                   avg(try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double)) as value,
                   count(try_cast(json_extract_string(qualifiers_json, '$.row.rank') as double)) as sample_count
            from canonical_observations
            where run_id = ? and module = 'Visibility'
              and json_extract_string(qualifiers_json, '$.row.rowType') = 'ranking'
              and lower(coalesce(json_extract_string(qualifiers_json, '$.row.brandName'), json_extract_string(qualifiers_json, '$.row.competitorName'))) != lower(?)
              and json_extract_string(qualifiers_json, '$.row.searchTerm') = ?
            group by 1
            order by value desc
            limit 5
            ''',
            [run_id, brand_display, group_key],
        )
        return {
            'engine_comparison_basis': 'Vendor visibility-rank value per AI engine; direction is provisional until BrandRank validates the encoding',
            'engine_comparison': engine_rows,
            'competitor_comparison_basis': 'Vendor visibility-rank values for competing brands on the same prompt, sourced from brandName or competitorName; interpretation is provisional',
            'competitor_comparison': competitor_rows,
        }

    if signal_type in ('CROSS_LLM_INCONSISTENCY', 'CLAIM_AGREEMENT_INVESTIGATION'):
        engine_rows = _rows_json(
            con,
            '''
            select coalesce(
                     json_extract_string(qualifiers_json, '$.row.llm'),
                     json_extract_string(qualifiers_json, '$.row.llmSource'),
                     json_extract_string(qualifiers_json, '$.row.cohort')
                   ) as label,
                   avg(try_cast(json_extract_string(qualifiers_json, '$.row.llmAccuracyScore') as double)) as value,
                   count(try_cast(json_extract_string(qualifiers_json, '$.row.llmAccuracyScore') as double)) as sample_count
            from canonical_observations
            where run_id = ? and module = 'AI Vulnerability'
              and json_extract_string(qualifiers_json, '$.row.rowType') = 'llm'
              and json_extract_string(qualifiers_json, '$.row.statementText') = ?
            group by 1
            order by 1
            ''',
            [run_id, group_key],
        )
        return {
            'engine_comparison_basis': 'Average per-engine accuracy score for this statement. Repeated source observations are combined; any hidden execution or prompt dimension not present in the source remains unresolved.',
            'engine_comparison': engine_rows,
            'competitor_comparison_basis': 'Not applicable: claim substantiation is brand-specific',
            'competitor_comparison': [],
        }

    if signal_type == 'READINESS_DETERIORATION':
        engine_rows = _rows_json(
            con,
            '''
            select json_extract_string(qualifiers_json, '$.row.llmSource') as label,
                   avg(try_cast(json_extract_string(qualifiers_json, '$.row.factorScore') as double)) as value,
                   count(try_cast(json_extract_string(qualifiers_json, '$.row.factorScore') as double)) as sample_count
            from canonical_observations
            where run_id = ? and module = 'Content Readiness'
              and json_extract_string(qualifiers_json, '$.row.groupName') = ?
              and json_extract_string(qualifiers_json, '$.row.llmSource') is not null
            group by 1
            order by 1
            ''',
            [run_id, group_key],
        )
        return {
            'engine_comparison_basis': 'Per-engine factor score contributing to this readiness group',
            'engine_comparison': engine_rows,
            'competitor_comparison_basis': 'Not applicable: readiness factors are brand-specific',
            'competitor_comparison': [],
        }

    if signal_type == 'EVIDENCE_ACCESSIBILITY_DEFICIT':
        rows = _rows_json(
            con,
            '''
            select json_extract_string(qualifiers_json, '$.row.sourceUrl') as url
            from canonical_observations
            where run_id = ? and module = 'Content Readiness'
              and json_extract_string(qualifiers_json, '$.row.rowType') = 'main'
              and json_extract_string(qualifiers_json, '$.row.sourceUrl') is not null
            ''',
            [run_id],
        )
        brand_token = ''.join(ch for ch in brand_display.lower() if ch.isalnum())
        owned = sum(1 for r in rows if brand_token and brand_token in ''.join(ch for ch in (r['url'] or '').lower() if ch.isalnum()))
        other = len(rows) - owned
        return {
            'engine_comparison_basis': 'Referenced source domains grouped by ownership (this signal has no per-AI-engine dimension)',
            'engine_comparison': [
                {'label': 'Owned domains', 'value': owned, 'sample_count': owned},
                {'label': 'Third-party domains', 'value': other, 'sample_count': other},
            ],
            'competitor_comparison_basis': 'Not applicable: evidence accessibility is measured at the brand level',
            'competitor_comparison': [],
        }

    return {
        'engine_comparison_basis': 'Not available for this signal type',
        'engine_comparison': [],
        'competitor_comparison_basis': 'Not available for this signal type',
        'competitor_comparison': [],
    }
