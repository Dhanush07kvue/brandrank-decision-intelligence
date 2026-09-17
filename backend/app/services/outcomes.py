from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone

import duckdb

_COLUMNS = '''
    outcome_id, intervention_id, baseline_run_id, post_change_run_id,
    published_at, retested_at, baseline_value, post_change_value,
    absolute_delta, percentage_delta, engines_improved, prompts_improved,
    citation_share_before, citation_share_after, competitor_delta,
    outcome_status, confidence, comparison_limitations, created_at
    , brand_id, market, language, source_system, metric_contract_id, context_provenance_json
'''


def _row_to_dict(r: tuple) -> dict:
    keys = [c.strip() for c in _COLUMNS.split(',')]
    return dict(zip(keys, r))


def measure_intervention(con: duckdb.DuckDBPyConnection, intervention_id: str, post_run_id: str) -> dict:
    from app.services.interventions import fetch_intervention
    iv = fetch_intervention(con, intervention_id)
    if iv is None:
        raise ValueError(f"Intervention {intervention_id} not found")

    baseline_run_id = iv.get('baseline_run_id')
    if not baseline_run_id:
        row = con.execute('select min(assessment_run_id) from signal_instances').fetchone()
        baseline_run_id = row[0] if row else None

    limitations: list[str] = []

    sig_rule = con.execute(
        'select signal_rule_id, group_key from signal_instances where signal_instance_id = ?',
        [iv['signal_instance_id']],
    ).fetchone()

    if sig_rule is None:
        limitations.append('Source signal instance not found; comparison not possible.')
        return _persist_outcome(con, intervention_id, baseline_run_id, post_run_id,
                                iv.get('actual_publish_date'), None, None, None,
                                None, None, None, None, None, 'INCONCLUSIVE', 0.0,
                                '; '.join(limitations))

    rule_id, group_key = sig_rule

    baseline = con.execute(
        '''select s.current_value, s.brand_id, s.market, ar.language, ar.module, s.metric_contract_id
           from signal_instances s left join assessment_runs ar on ar.run_id = s.assessment_run_id
           where s.signal_rule_id = ? and s.group_key = ? and s.assessment_run_id = ?''',
        [rule_id, group_key, baseline_run_id],
    ).fetchone()
    post = con.execute(
        '''select s.current_value, s.brand_id, s.market, ar.language, ar.module, s.metric_contract_id
           from signal_instances s left join assessment_runs ar on ar.run_id = s.assessment_run_id
           where s.signal_rule_id = ? and s.group_key = ? and s.assessment_run_id = ?''',
        [rule_id, group_key, post_run_id],
    ).fetchone()

    if baseline is None:
        limitations.append(f'No baseline signal data found for run {baseline_run_id}.')
    if post is None:
        limitations.append(f'No post-change signal data found for run {post_run_id}.')

    if baseline is None or post is None:
        return _persist_outcome(con, intervention_id, baseline_run_id, post_run_id,
                                iv.get('actual_publish_date'), None, None, None,
                                None, None, None, None, None, None, None,
                                'AWAITING_MORE_RUNS', 0.3,
                                '; '.join(limitations) or 'Insufficient run data for comparison.')

    context_labels = ('brand', 'market', 'language', 'module', 'metric contract')
    for index, label in enumerate(context_labels, start=1):
        if baseline[index] != post[index]:
            limitations.append(f'Baseline and post-change {label} differ; outcome is not comparable.')
    if limitations and any('not comparable' in item for item in limitations):
        return _persist_outcome(con, intervention_id, baseline_run_id, post_run_id,
                                iv.get('actual_publish_date'), None, None, None, None, None,
                                None, None, None, None, None, 'INCONCLUSIVE', 0.1,
                                '; '.join(limitations))

    b_val = float(baseline[0])
    p_val = float(post[0])
    delta = p_val - b_val
    pct_delta = (delta / b_val * 100) if b_val != 0 else 0.0

    if abs(delta) < 0.01:
        status, confidence = 'NO_MATERIAL_CHANGE', 0.6
    elif delta > 0:
        status, confidence = 'IMPROVED', 0.75
    else:
        status, confidence = 'DETERIORATED', 0.7

    if baseline_run_id == post_run_id:
        limitations.append('Baseline and post-change runs are identical; comparison is uncontrolled.')
        status, confidence = 'INCONCLUSIVE', 0.1

    limitations.append('Attribution is observational; external factors may have influenced the result.')

    return _persist_outcome(con, intervention_id, baseline_run_id, post_run_id,
                            iv.get('actual_publish_date'), None, b_val, p_val,
                            delta, pct_delta, None, None, None, None, None,
                            status, confidence, '; '.join(limitations))


def _persist_outcome(
    con: duckdb.DuckDBPyConnection,
    intervention_id: str,
    baseline_run_id: str | None,
    post_change_run_id: str | None,
    published_at: str | None,
    retested_at: str | None,
    baseline_value: float | None,
    post_change_value: float | None,
    absolute_delta: float | None,
    percentage_delta: float | None,
    engines_improved: int | None,
    prompts_improved: int | None,
    citation_share_before: float | None,
    citation_share_after: float | None,
    competitor_delta: float | None,
    outcome_status: str,
    confidence: float,
    comparison_limitations: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    outcome_id = uuid.uuid4().hex[:24]
    context = con.execute('''
        select i.brand_id, i.market, ar.language, ar.source_system, s.metric_contract_id,
               ar.context_provenance_json
        from interventions i
        left join signal_instances s on s.signal_instance_id = i.signal_instance_id
        left join assessment_runs ar on ar.run_id = coalesce(?, s.assessment_run_id)
        where i.intervention_id = ?
    ''', [baseline_run_id, intervention_id]).fetchone()
    context_values = list(context) if context else [None, None, None, None, None, None]
    values = [
        outcome_id, intervention_id, baseline_run_id, post_change_run_id,
        published_at, retested_at or now, baseline_value, post_change_value,
        absolute_delta, percentage_delta, engines_improved, prompts_improved,
        citation_share_before, citation_share_after, competitor_delta,
        outcome_status, confidence, comparison_limitations, now, *context_values,
    ]
    placeholders = ','.join('?' for _ in values)
    con.execute(
        f'insert into intervention_outcomes ({_COLUMNS}) values ({placeholders})',
        values,
    )
    row = con.execute(
        f'select {_COLUMNS} from intervention_outcomes where outcome_id = ?', [outcome_id],
    ).fetchone()
    return _row_to_dict(row)  # type: ignore[arg-type]


def fetch_outcome(con: duckdb.DuckDBPyConnection, intervention_id: str) -> dict | None:
    row = con.execute(
        f'select {_COLUMNS} from intervention_outcomes where intervention_id = ? order by created_at desc limit 1',
        [intervention_id],
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_outcomes(con: duckdb.DuckDBPyConnection, limit: int = 100) -> list[dict]:
    rows = con.execute(
        f'select {_COLUMNS} from intervention_outcomes order by created_at desc limit ?', [limit],
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
