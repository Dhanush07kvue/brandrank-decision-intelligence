"""Tests for the intervention service — state machine, CRUD and outcome comparison."""
from __future__ import annotations

import pytest
import duckdb

from app.services.db import Database, SCHEMA_SQL
from app.services.interventions import (
    VALID_TRANSITIONS,
    create_intervention,
    fetch_intervention,
    generate_brief,
    list_interventions,
    transition_intervention,
    update_intervention,
)
from app.services.outcomes import fetch_outcome, measure_intervention
from app.services.fixtures import seed_poc_fixtures


@pytest.fixture()
def con():
    """In-memory DuckDB connection with full schema."""
    c = duckdb.connect(':memory:')
    c.execute(SCHEMA_SQL)
    # Insert a minimal signal instance so interventions can reference it
    c.execute(
        '''insert into signal_instances
           (signal_instance_id, signal_rule_id, signal_rule_version, brand_id, market,
            assessment_run_id, signal_type, group_key, title, description,
            current_value, baseline_value, delta, runs_affected, engines_affected,
            business_priority, severity, confidence, evidence_count,
            diagnosis_status, truth_validation_status, workflow_status)
           values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        ['sig_001', 'VISIBILITY_GAP_001', 1, 'aveeno', 'US', 'run_001',
         'VISIBILITY_GAP', 'eczema', 'Test signal', 'Visibility below threshold',
         0.15, 0.30, -0.15, 2, 3, 'HIGH', 'CRITICAL', 0.85, 12,
         'NEEDS_DIAGNOSIS', 'PENDING', 'NEEDS_DIAGNOSIS'],
    )
    yield c
    c.close()


# ── Creation ──────────────────────────────────────────────────────────────────

def test_create_intervention_basic(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'Low eczema visibility',
        'diagnosed_cause': 'Missing content',
        'recommended_action': 'Publish FAQ page',
    })
    assert iv['intervention_id']
    assert iv['status'] == 'NEEDS_DIAGNOSIS'
    assert iv['brand_id'] == 'aveeno'
    assert iv['market'] == 'US'
    assert iv['confidence'] == 0.5


def test_create_intervention_unknown_signal_raises(con):
    with pytest.raises(ValueError, match='not found'):
        create_intervention(con, {
            'signal_instance_id': 'nonexistent',
            'business_problem': 'x',
            'diagnosed_cause': 'y',
            'recommended_action': 'z',
        })


def test_fetch_missing_returns_none(con):
    assert fetch_intervention(con, 'does_not_exist') is None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_update_intervention(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'Initial problem',
        'diagnosed_cause': 'Unknown',
        'recommended_action': 'TBD',
    })
    updated = update_intervention(con, iv['intervention_id'], {'owner': 'jane.doe@kenvue.com', 'priority': 'HIGH'})
    assert updated['owner'] == 'jane.doe@kenvue.com'
    assert updated['priority'] == 'HIGH'


def test_update_disallowed_field_ignored(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p',
        'diagnosed_cause': 'd',
        'recommended_action': 'r',
    })
    updated = update_intervention(con, iv['intervention_id'], {'status': 'CLOSED', 'owner': 'alice'})
    # status must not be changed via update — only via transition
    assert updated['status'] == 'NEEDS_DIAGNOSIS'
    assert updated['owner'] == 'alice'


def test_list_interventions(con):
    for i in range(3):
        create_intervention(con, {
            'signal_instance_id': 'sig_001',
            'business_problem': f'Problem {i}',
            'diagnosed_cause': 'd',
            'recommended_action': 'r',
        })
    items = list_interventions(con, brand_id='aveeno')
    assert len(items) == 3


# ── State machine ─────────────────────────────────────────────────────────────

def test_valid_transitions_coverage():
    """Every status reachable from the lifecycle must have a transition map entry."""
    terminal = {'CLOSED', 'REJECTED'}
    for status in VALID_TRANSITIONS:
        if status in terminal:
            assert VALID_TRANSITIONS[status] == []
        else:
            assert len(VALID_TRANSITIONS[status]) >= 1


def test_transition_happy_path(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p',
        'diagnosed_cause': 'd',
        'recommended_action': 'r',
    })
    assert iv['status'] == 'NEEDS_DIAGNOSIS'
    iv = transition_intervention(con, iv['intervention_id'], 'NEEDS_TRUTH_VALIDATION')
    assert iv['status'] == 'NEEDS_TRUTH_VALIDATION'
    iv = transition_intervention(con, iv['intervention_id'], 'READY_FOR_OWNER_REVIEW')
    assert iv['status'] == 'READY_FOR_OWNER_REVIEW'


def test_transition_invalid_raises(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p',
        'diagnosed_cause': 'd',
        'recommended_action': 'r',
    })
    with pytest.raises(ValueError, match='Cannot transition'):
        transition_intervention(con, iv['intervention_id'], 'CLOSED')


def test_transition_to_rejected(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p',
        'diagnosed_cause': 'd',
        'recommended_action': 'r',
    })
    iv = transition_intervention(con, iv['intervention_id'], 'REJECTED')
    assert iv['status'] == 'REJECTED'
    # No further transitions from REJECTED
    with pytest.raises(ValueError):
        transition_intervention(con, iv['intervention_id'], 'NEEDS_DIAGNOSIS')


def test_transition_nonexistent_returns_none(con):
    result = transition_intervention(con, 'does_not_exist', 'NEEDS_TRUTH_VALIDATION')
    assert result is None


# ── Brief generation ──────────────────────────────────────────────────────────

def test_generate_brief_structure(con):
    seed_poc_fixtures(con)
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'Eczema page gap',
        'diagnosed_cause': 'Missing FAQ',
        'recommended_action': 'Add oat science content',
        'target_claim_id': 'claim_oat_science_001',
        'target_page_id': 'page_aveeno_oat_science',
        'risk_route': 'STANDARD',
    })
    brief = generate_brief(con, iv['intervention_id'])
    assert brief['brief_type'] == 'ACTIVATION_BRIEF'
    assert brief['signal']['signal_title'] == 'Test signal'
    assert brief['approved_claim']['claim_text'] == 'Oat Science Pioneer — leader in oat science'
    assert brief['target_page']['url'] == 'https://www.aveeno.com/science/oat-science'
    assert 'Aprimo' in brief['note']


def test_generate_brief_missing_raises(con):
    with pytest.raises(ValueError):
        generate_brief(con, 'nonexistent_id')


# ── Outcome measurement ───────────────────────────────────────────────────────

def _make_second_signal(con, run_id: str, value: float) -> None:
    con.execute(
        '''insert into signal_instances
           (signal_instance_id, signal_rule_id, signal_rule_version, brand_id, market,
            assessment_run_id, signal_type, group_key, title, description,
            current_value, baseline_value, delta, runs_affected, engines_affected,
            business_priority, severity, confidence, evidence_count,
            diagnosis_status, truth_validation_status, workflow_status)
           values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        [f'sig_{run_id}', 'VISIBILITY_GAP_001', 1, 'aveeno', 'US', run_id,
         'VISIBILITY_GAP', 'eczema', 'Test signal', '',
         value, 0.15, value - 0.15, 2, 3, 'HIGH', 'CRITICAL', 0.85, 12,
         'NEEDS_DIAGNOSIS', 'PENDING', 'NEEDS_DIAGNOSIS'],
    )


def test_outcome_improved(con):
    _make_second_signal(con, 'run_002', 0.45)
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p', 'diagnosed_cause': 'd', 'recommended_action': 'r',
    })
    update_intervention(con, iv['intervention_id'], {'baseline_run_id': 'run_001'})
    outcome = measure_intervention(con, iv['intervention_id'], 'run_002')
    assert outcome['outcome_status'] == 'IMPROVED'
    assert outcome['absolute_delta'] > 0
    assert 'observational' in outcome['comparison_limitations']


def test_outcome_deteriorated(con):
    _make_second_signal(con, 'run_003', 0.05)
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p', 'diagnosed_cause': 'd', 'recommended_action': 'r',
    })
    update_intervention(con, iv['intervention_id'], {'baseline_run_id': 'run_001'})
    outcome = measure_intervention(con, iv['intervention_id'], 'run_003')
    assert outcome['outcome_status'] == 'DETERIORATED'
    assert outcome['absolute_delta'] < 0


def test_outcome_inconclusive_same_run(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p', 'diagnosed_cause': 'd', 'recommended_action': 'r',
    })
    update_intervention(con, iv['intervention_id'], {'baseline_run_id': 'run_001'})
    outcome = measure_intervention(con, iv['intervention_id'], 'run_001')
    assert outcome['outcome_status'] == 'INCONCLUSIVE'
    assert outcome['confidence'] <= 0.1


def test_outcome_awaiting_missing_post_run(con):
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p', 'diagnosed_cause': 'd', 'recommended_action': 'r',
    })
    update_intervention(con, iv['intervention_id'], {'baseline_run_id': 'run_001'})
    outcome = measure_intervention(con, iv['intervention_id'], 'run_nonexistent')
    assert outcome['outcome_status'] == 'AWAITING_MORE_RUNS'


def test_fetch_outcome_latest(con):
    _make_second_signal(con, 'run_004', 0.50)
    iv = create_intervention(con, {
        'signal_instance_id': 'sig_001',
        'business_problem': 'p', 'diagnosed_cause': 'd', 'recommended_action': 'r',
    })
    update_intervention(con, iv['intervention_id'], {'baseline_run_id': 'run_001'})
    measure_intervention(con, iv['intervention_id'], 'run_004')
    fetched = fetch_outcome(con, iv['intervention_id'])
    assert fetched is not None
    assert fetched['outcome_status'] == 'IMPROVED'


# ── Fixture seeding ───────────────────────────────────────────────────────────

def test_seed_poc_fixtures_idempotent(con):
    counts1 = seed_poc_fixtures(con)
    counts2 = seed_poc_fixtures(con)
    # Second seed should insert 0 new rows
    assert counts2['claim_truth'] == 0
    assert counts2['content_assets'] == 0
    assert counts2['prompt_priorities'] == 0
    # First seed should have inserted rows
    assert counts1['claim_truth'] > 0
    assert counts1['content_assets'] > 0
    assert counts1['prompt_priorities'] > 0
