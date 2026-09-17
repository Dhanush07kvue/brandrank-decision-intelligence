from __future__ import annotations

import uuid
from datetime import datetime, timezone

import duckdb

VALID_TRANSITIONS: dict[str, list[str]] = {
    'DETECTED':               ['NEEDS_DIAGNOSIS', 'REJECTED'],
    'NEEDS_DIAGNOSIS':        ['NEEDS_TRUTH_VALIDATION', 'REJECTED', 'INSUFFICIENT_EVIDENCE'],
    'NEEDS_TRUTH_VALIDATION': ['READY_FOR_OWNER_REVIEW', 'NEEDS_DIAGNOSIS', 'REJECTED'],
    'READY_FOR_OWNER_REVIEW': ['APPROVED_FOR_BRIEF', 'REJECTED', 'NEEDS_TRUTH_VALIDATION'],
    'APPROVED_FOR_BRIEF':     ['IN_CREATION', 'REJECTED'],
    'IN_CREATION':            ['IN_MLR', 'APPROVED', 'REJECTED'],
    'IN_MLR':                 ['APPROVED', 'IN_CREATION', 'REJECTED'],
    'APPROVED':               ['PUBLISHED', 'REJECTED'],
    'PUBLISHED':              ['AWAITING_RETEST'],
    'AWAITING_RETEST':        ['MEASURED', 'PUBLISHED'],
    'MEASURED':               ['CLOSED'],
    'CLOSED':                 [],
    'REJECTED':               [],
    'INSUFFICIENT_EVIDENCE':  ['NEEDS_DIAGNOSIS'],
}

_COLUMNS = '''
    intervention_id, signal_instance_id, brand_id, market,
    business_problem, diagnosed_cause, recommended_action,
    target_prompt_id, target_product_id, target_claim_id, target_page_id,
    approved_evidence, risk_route, owner, approver, status, priority, confidence,
    baseline_run_id, baseline_metric, target_metric,
    planned_publish_date, actual_publish_date, retest_date,
    created_at, updated_at
'''


def _row_to_dict(r: tuple) -> dict:
    keys = [c.strip() for c in _COLUMNS.split(',')]
    return dict(zip(keys, r))


def create_intervention(con: duckdb.DuckDBPyConnection, req: dict) -> dict:
    sig = con.execute(
        '''select brand_id, market, governance_status, truth_validation_status, workflow_status
           from signal_instances where signal_instance_id = ?''',
        [req['signal_instance_id']],
    ).fetchone()
    if sig is None:
        raise ValueError(f"Signal {req['signal_instance_id']} not found")

    if sig[2] == 'BLOCKED':
        raise ValueError('Blocked signals cannot create interventions')

    now = datetime.now(timezone.utc).isoformat()
    intervention_id = uuid.uuid4().hex[:24]

    con.execute(
        f'insert into interventions ({_COLUMNS}) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        [
            intervention_id, req['signal_instance_id'], sig[0], sig[1],
            req['business_problem'], req['diagnosed_cause'], req['recommended_action'],
            req.get('target_prompt_id'), req.get('target_product_id'),
            req.get('target_claim_id'), req.get('target_page_id'),
            req.get('approved_evidence'), req.get('risk_route'), req.get('owner'),
            None, 'NEEDS_DIAGNOSIS', req.get('priority', 'MEDIUM'), 0.5,
            None, None, None, None, None, None, now, now,
        ],
    )
    return fetch_intervention(con, intervention_id)  # type: ignore[return-value]


def fetch_intervention(con: duckdb.DuckDBPyConnection, intervention_id: str) -> dict | None:
    row = con.execute(
        f'select {_COLUMNS} from interventions where intervention_id = ?',
        [intervention_id],
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_interventions(
    con: duckdb.DuckDBPyConnection,
    brand_id: str | None = None,
    status: str | None = None,
    signal_instance_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    where = ['1=1']
    params: list[object] = []
    if brand_id:
        where.append('brand_id = ?')
        params.append(brand_id)
    if status:
        where.append('status = ?')
        params.append(status.upper())
    if signal_instance_id:
        where.append('signal_instance_id = ?')
        params.append(signal_instance_id)
    params.append(limit)
    sql = f'select {_COLUMNS} from interventions where {" and ".join(where)} order by updated_at desc limit ?'
    return [_row_to_dict(r) for r in con.execute(sql, params).fetchall()]


def update_intervention(con: duckdb.DuckDBPyConnection, intervention_id: str, updates: dict) -> dict | None:
    if fetch_intervention(con, intervention_id) is None:
        return None
    allowed = {
        'business_problem', 'diagnosed_cause', 'recommended_action',
        'target_prompt_id', 'target_product_id', 'target_claim_id', 'target_page_id',
        'approved_evidence', 'risk_route', 'owner', 'approver', 'priority', 'confidence',
        'baseline_run_id', 'baseline_metric', 'target_metric',
        'planned_publish_date', 'actual_publish_date', 'retest_date',
    }
    now = datetime.now(timezone.utc).isoformat()
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not filtered:
        return fetch_intervention(con, intervention_id)
    set_clauses = ', '.join(f'{k} = ?' for k in filtered)
    params = list(filtered.values()) + [now, intervention_id]
    con.execute(f'update interventions set {set_clauses}, updated_at = ? where intervention_id = ?', params)
    return fetch_intervention(con, intervention_id)


def transition_intervention(con: duckdb.DuckDBPyConnection, intervention_id: str, target_status: str) -> dict | None:
    existing = fetch_intervention(con, intervention_id)
    if existing is None:
        return None
    current = existing['status']
    allowed = VALID_TRANSITIONS.get(current, [])
    if target_status not in allowed:
        raise ValueError(f"Cannot transition from {current} to {target_status}. Allowed: {allowed}")
    if target_status == 'APPROVED_FOR_BRIEF':
        signal = con.execute('''
            select governance_status, truth_validation_status
            from signal_instances where signal_instance_id = ?
        ''', [existing['signal_instance_id']]).fetchone()
        if signal and signal[0] == 'BLOCKED':
            raise ValueError('Blocked signals cannot be approved for an intervention brief')
        if signal and signal[1] in ('BLOCKED', 'INSUFFICIENT_EVIDENCE'):
            raise ValueError('Truth validation must be resolved before approving an intervention brief')
    now = datetime.now(timezone.utc).isoformat()
    con.execute('update interventions set status = ?, updated_at = ? where intervention_id = ?',
                [target_status, now, intervention_id])
    return fetch_intervention(con, intervention_id)


def generate_brief(con: duckdb.DuckDBPyConnection, intervention_id: str) -> dict:
    iv = fetch_intervention(con, intervention_id)
    if iv is None:
        raise ValueError(f"Intervention {intervention_id} not found")

    sig = con.execute(
        'select title, description, signal_type, severity, confidence, current_value, baseline_value, delta, business_priority, evidence_count, assessment_run_id from signal_instances where signal_instance_id = ?',
        [iv['signal_instance_id']],
    ).fetchone()

    signal_section: dict = {}
    if sig:
        signal_section = {
            'signal_title': sig[0], 'signal_description': sig[1], 'signal_type': sig[2],
            'severity': sig[3], 'confidence': sig[4], 'current_value': sig[5],
            'baseline_value': sig[6], 'delta': sig[7], 'business_priority': sig[8],
            'evidence_count': sig[9], 'assessment_run_id': sig[10],
        }

    claim_row = None
    if iv.get('target_claim_id'):
        claim_row = con.execute(
            'select claim_text, approval_status, evidence_reference from claim_truth where claim_id = ?',
            [iv['target_claim_id']],
        ).fetchone()

    page_row = None
    if iv.get('target_page_id'):
        page_row = con.execute(
            'select canonical_url, content_type, readiness_status from content_assets where asset_id = ?',
            [iv['target_page_id']],
        ).fetchone()

    return {
        'intervention_id': intervention_id,
        'brief_type': 'ACTIVATION_BRIEF',
        'brand_id': iv['brand_id'],
        'market': iv['market'],
        'business_problem': iv['business_problem'],
        'diagnosed_cause': iv['diagnosed_cause'],
        'recommended_action': iv['recommended_action'],
        'signal': signal_section,
        'approved_claim': {
            'claim_text': claim_row[0] if claim_row else None,
            'approval_status': claim_row[1] if claim_row else None,
            'evidence_reference': claim_row[2] if claim_row else None,
        },
        'target_page': {
            'url': page_row[0] if page_row else None,
            'content_type': page_row[1] if page_row else None,
            'readiness_status': page_row[2] if page_row else None,
        },
        'owner': iv['owner'],
        'approver': iv['approver'],
        'risk_route': iv['risk_route'],
        'baseline_metric': iv['baseline_metric'],
        'target_metric': iv['target_metric'],
        'retest_date': iv['retest_date'],
        'status': iv['status'],
        'note': 'Aprimo adapter interface: submit via POST /adapters/aprimo/brief when integration is enabled.',
    }
