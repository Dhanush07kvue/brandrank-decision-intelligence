from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.analytics.signals import (
    calculate_confidence,
    calculate_severity,
    evaluate_signals,
    get_signal_comparisons,
    get_signal_evidence,
    get_signal_history,
    load_rules,
    persist_signal_instances,
)
from app.services.db import Database

CONFIG_PATH = Path(__file__).resolve().parents[2] / 'config' / 'signal_rules.yaml'


@pytest.fixture()
def con(tmp_path):
    db = Database(tmp_path / 'test.duckdb')
    connection = db.connect()
    yield connection
    connection.close()


def _insert_observation(con, *, run_id, record_id, file_id, source_row, module, row):
    con.execute(
        '''
        insert into canonical_observations (
          run_id, record_id, file_id, source_row, module, qualifiers_json, observation_state
        ) values (?, ?, ?, ?, ?, ?, 'PARSED')
        ''',
        [run_id, record_id, file_id, source_row, module, json.dumps({'row': row})],
    )


def _insert_file(con, *, run_id, file_id, original_filename):
    con.execute(
        '''
        insert into file_manifest (run_id, file_id, original_filename, ingestion_status)
        values (?, ?, ?, 'INGESTED')
        ''',
        [run_id, file_id, original_filename],
    )


# --- Rule registry -----------------------------------------------------

def test_load_rules_returns_configured_rule_types():
    rules = load_rules(CONFIG_PATH)
    ids = {r.signal_rule_id for r in rules}
    assert ids == {
        'VISIBILITY_GAP_001',
        'CROSS_LLM_INCONSISTENCY_001',
        'CLAIM_SUBSTANTIATION_RISK_001',
            'READINESS_DETERIORATION_001',
            'EVIDENCE_ACCESSIBILITY_001',
            'COMPETITIVE_PLAYBOOK_GAP_001',
            'BRAND_ATTRIBUTE_BENCHMARK_001',
        }
    assert all(r.enabled or r.governance_status == 'BLOCKED' for r in rules)


# --- Pure functions ------------------------------------------------------

def test_calculate_severity_below_comparator_bands():
    rules = load_rules(CONFIG_PATH)
    rule = next(r for r in rules if r.signal_rule_id == 'VISIBILITY_GAP_001')
    assert calculate_severity(0.10, rule) == 'CRITICAL'
    assert calculate_severity(0.20, rule) == 'HIGH'
    assert calculate_severity(0.30, rule) == 'MEDIUM'
    assert calculate_severity(0.90, rule) == 'LOW'


def test_calculate_severity_above_comparator_bands():
    rules = load_rules(CONFIG_PATH)
    rule = next(r for r in rules if r.signal_rule_id == 'CROSS_LLM_INCONSISTENCY_001')
    assert calculate_severity(0.35, rule) == 'CRITICAL'
    assert calculate_severity(0.25, rule) == 'HIGH'
    assert calculate_severity(0.18, rule) == 'MEDIUM'
    assert calculate_severity(0.01, rule) == 'LOW'


def test_calculate_confidence_bounds_and_monotonicity():
    low = calculate_confidence(evidence_count=1, runs_affected=1, engines_affected=1, min_runs=5)
    high = calculate_confidence(evidence_count=20, runs_affected=5, engines_affected=6, min_runs=5)
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0
    assert high > low
    assert high == 1.0


# --- Evaluator: visibility_gap -------------------------------------------

def test_visibility_gap_fires_below_threshold(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_search_term_lotion.csv')
    for i, (engine, rank) in enumerate([('GROK', 0.10), ('GEMINI', 0.15), ('ANTHROPIC', 0.05)]):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='Visibility',
            row={
                'rowType': 'ranking',
                'searchTerm': 'best lotion for eczema',
                'cohort': engine,
                'brandName': 'Aveeno',
                'rank': rank,
                'isHero': 'True',
            },
        )

    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    visibility = [r for r in results if r['signal_rule_id'] == 'VISIBILITY_GAP_001']
    assert len(visibility) == 1
    signal = visibility[0]
    assert signal['group_key'] == '__BLOCKED__'
    assert signal['governance_status'] == 'BLOCKED'
    assert signal['severity'] == 'BLOCKED'
    assert signal['evidence_count'] == 0
    assert signal['baseline_value'] is None
    assert signal['delta'] is None


def test_visibility_gap_does_not_fire_above_threshold(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_search_term_lotion.csv')
    _insert_observation(
        con,
        run_id=run_id,
        record_id='rec-0',
        file_id='f1',
        source_row=0,
        module='Visibility',
        row={
            'rowType': 'ranking',
            'searchTerm': 'best lotion for eczema',
            'cohort': 'GROK',
            'brandName': 'Aveeno',
            'rank': 0.90,
            'isHero': 'True',
        },
    )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    visibility = [r for r in results if r['signal_rule_id'] == 'VISIBILITY_GAP_001']
    assert len(visibility) == 1
    assert visibility[0]['governance_status'] == 'BLOCKED'


def test_visibility_gap_ignores_non_hero_prompts(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_search_term_lotion.csv')
    _insert_observation(
        con,
        run_id=run_id,
        record_id='rec-0',
        file_id='f1',
        source_row=0,
        module='Visibility',
        row={
            'rowType': 'ranking',
            'searchTerm': 'non priority prompt',
            'cohort': 'GROK',
            'brandName': 'Aveeno',
            'rank': 0.02,
            'isHero': 'False',
        },
    )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    visibility = [r for r in results if r['signal_rule_id'] == 'VISIBILITY_GAP_001']
    assert len(visibility) == 1
    assert visibility[0]['governance_status'] == 'BLOCKED'


# --- Evaluator: cross_llm_inconsistency ----------------------------------

def test_cross_llm_inconsistency_fires_above_threshold(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_ai_vulnerability.csv')
    for i, (llm, score) in enumerate([('GROK', 0.9), ('GEMINI', 0.2), ('ANTHROPIC', 0.5)]):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='AI Vulnerability',
            row={
                'rowType': 'llm',
                'statementText': 'Aveeno lotion cures eczema overnight',
                'llm': llm,
                'llmAccuracyScore': score,
            },
        )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    inconsistency = [r for r in results if r['signal_rule_id'] == 'CROSS_LLM_INCONSISTENCY_001']
    assert len(inconsistency) == 1
    assert inconsistency[0]['engines_affected'] == 3
    assert inconsistency[0]['current_value'] > 0.15


def test_cross_llm_inconsistency_requires_min_evidence_rows(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_ai_vulnerability.csv')
    for i, (llm, score) in enumerate([('GROK', 0.9), ('GEMINI', 0.1)]):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='AI Vulnerability',
            row={
                'rowType': 'llm',
                'statementText': 'Only two engines rated this',
                'llm': llm,
                'llmAccuracyScore': score,
            },
        )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    inconsistency = [r for r in results if r['signal_rule_id'] == 'CROSS_LLM_INCONSISTENCY_001']
    assert inconsistency == []


def test_cross_llm_comparison_aggregates_repeated_engine_rows(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_ai_vulnerability.csv')
    rows = [
        ('GROK', 0.80), ('GROK', 0.60),
        ('GEMINI', 0.20), ('GEMINI', 0.40),
    ]
    for i, (llm, score) in enumerate(rows):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='AI Vulnerability',
            row={
                'rowType': 'llm',
                'statementText': 'Repeated dimensions for one claim',
                'llm': llm,
                'llmAccuracyScore': score,
            },
        )

    comparisons = get_signal_comparisons(con, 'CROSS_LLM_INCONSISTENCY', run_id, 'Repeated dimensions for one claim', 'Aveeno')
    assert [(row['label'], row['sample_count']) for row in comparisons['engine_comparison']] == [('GEMINI', 2), ('GROK', 2)]
    assert [row['value'] for row in comparisons['engine_comparison']] == [pytest.approx(0.30), pytest.approx(0.70)]


# --- Evaluator: claim_substantiation_risk --------------------------------

def test_claim_substantiation_risk_fires_and_flags_disputed(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_ai_vulnerability.csv')
    _insert_observation(
        con,
        run_id=run_id,
        record_id='rec-0',
        file_id='f1',
        source_row=0,
        module='AI Vulnerability',
        row={
            'rowType': 'summary',
            'statementText': 'Aveeno is dermatologist recommended #1',
            'consensusAccuracyScore': 0.30,
            'statementStatus': 'False',
        },
    )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    risk = [r for r in results if r['signal_rule_id'] == 'CLAIM_SUBSTANTIATION_RISK_001']
    assert len(risk) == 1
    assert risk[0]['severity'] == 'CRITICAL'
    assert 'unsubstantiated' in risk[0]['description']


# --- Evaluator: readiness_deterioration ----------------------------------

def test_readiness_deterioration_fires_below_threshold(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_content_readiness.csv')
    _insert_observation(
        con,
        run_id=run_id,
        record_id='rec-0',
        file_id='f1',
        source_row=0,
        module='Content Readiness',
        row={
            'rowType': 'summary',
            'groupName': 'Ingredient transparency',
            'weightedScore': 0.40,
        },
    )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    readiness = [r for r in results if r['signal_rule_id'] == 'READINESS_DETERIORATION_001']
    assert len(readiness) == 1
    assert readiness[0]['severity'] == 'CRITICAL'


# --- Evaluator: evidence_accessibility_deficit ---------------------------

def test_evidence_accessibility_deficit_fires_when_mostly_third_party(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_content_readiness.csv')
    urls = ['https://thirdparty1.com/a'] * 6 + ['https://aveeno.com/a']
    for i, url in enumerate(urls):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='Content Readiness',
            row={'rowType': 'main', 'sourceUrl': url},
        )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    deficit = [r for r in results if r['signal_rule_id'] == 'EVIDENCE_ACCESSIBILITY_001']
    assert len(deficit) == 1
    assert deficit[0]['group_key'] == 'owned_domain_share'
    assert deficit[0]['current_value'] == pytest.approx(1 / 7, abs=0.001)


def test_evidence_accessibility_deficit_insufficient_evidence_returns_none(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_content_readiness.csv')
    _insert_observation(
        con,
        run_id=run_id,
        record_id='rec-0',
        file_id='f1',
        source_row=0,
        module='Content Readiness',
        row={'rowType': 'main', 'sourceUrl': 'https://thirdparty1.com/a'},
    )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    deficit = [r for r in results if r['signal_rule_id'] == 'EVIDENCE_ACCESSIBILITY_001']
    assert deficit == []


# --- Idempotency ----------------------------------------------------------

def test_evaluate_and_persist_is_idempotent(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_search_term_lotion.csv')
    for i, (engine, rank) in enumerate([('GROK', 0.10), ('GEMINI', 0.15)]):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='Visibility',
            row={
                'rowType': 'ranking',
                'searchTerm': 'idempotency prompt',
                'cohort': engine,
                'brandName': 'Aveeno',
                'rank': rank,
                'isHero': 'True',
            },
        )

    first = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    persist_signal_instances(con, run_id, first)
    first_ids = sorted(r['signal_instance_id'] for r in first)
    first_evidence_count = con.execute(
        'select count(*) from signal_evidence where assessment_run_id = ?', [run_id]
    ).fetchone()[0]

    second = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    persist_signal_instances(con, run_id, second)
    second_ids = sorted(r['signal_instance_id'] for r in second)
    second_evidence_count = con.execute(
        'select count(*) from signal_evidence where assessment_run_id = ?', [run_id]
    ).fetchone()[0]

    assert first_ids == second_ids
    assert first_evidence_count == second_evidence_count
    instance_count = con.execute(
        'select count(*) from signal_instances where assessment_run_id = ?', [run_id]
    ).fetchone()[0]
    assert instance_count == len(first)


def test_baseline_and_delta_computed_from_prior_run(con):
    for i, (run_id, rank) in enumerate([('run-1', 0.10), ('run-2', 0.05)]):
        _insert_file(con, run_id=run_id, file_id=f'f{i}', original_filename='aveeno_search_term_lotion.csv')
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id=f'f{i}',
            source_row=0,
            module='Visibility',
            row={
                'rowType': 'ranking',
                'searchTerm': 'trend prompt',
                'cohort': 'GROK',
                'brandName': 'Aveeno',
                'rank': rank,
                'isHero': 'True',
            },
        )
        results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
        persist_signal_instances(con, run_id, results)

    final_results = evaluate_signals(con, run_id='run-2', config_path=CONFIG_PATH)
    signal = next(r for r in final_results if r['signal_rule_id'] == 'VISIBILITY_GAP_001')
    assert signal['governance_status'] == 'BLOCKED'
    assert signal['baseline_value'] is None
    assert signal['delta'] is None
    assert signal['runs_affected'] == 0


# --- Traceability: evidence / history / comparisons ------------------------

def test_get_signal_evidence_traces_back_to_source_file(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_search_term_lotion.csv')
    _insert_observation(
        con,
        run_id=run_id,
        record_id='rec-0',
        file_id='f1',
        source_row=7,
        module='Visibility',
        row={
            'rowType': 'ranking',
            'searchTerm': 'evidence prompt',
            'cohort': 'GROK',
            'brandName': 'Aveeno',
            'rank': 0.05,
            'isHero': 'True',
        },
    )
    results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
    persist_signal_instances(con, run_id, results)
    signal = next(r for r in results if r['signal_rule_id'] == 'VISIBILITY_GAP_001')

    evidence = get_signal_evidence(con, signal['signal_instance_id'])
    assert evidence == []
    assert signal['governance_status'] == 'BLOCKED'


def test_get_signal_history_returns_ordered_runs(con):
    for run_id, rank in [('run-1', 0.10), ('run-2', 0.05)]:
        _insert_file(con, run_id=run_id, file_id=f'f-{run_id}', original_filename='aveeno_search_term_lotion.csv')
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{run_id}',
            file_id=f'f-{run_id}',
            source_row=0,
            module='Visibility',
            row={
                'rowType': 'ranking',
                'searchTerm': 'history prompt',
                'cohort': 'GROK',
                'brandName': 'Aveeno',
                'rank': rank,
                'isHero': 'True',
            },
        )
        results = evaluate_signals(con, run_id=run_id, config_path=CONFIG_PATH)
        persist_signal_instances(con, run_id, results)

    history = get_signal_history(con, 'VISIBILITY_GAP_001', 'aveeno', 'US', 'history prompt')
    assert history == []


def test_get_signal_comparisons_returns_real_engine_and_competitor_data(con):
    run_id = 'run-1'
    _insert_file(con, run_id=run_id, file_id='f1', original_filename='aveeno_search_term_lotion.csv')
    rows = [
        ('Aveeno', 'GROK', 0.10),
        ('Aveeno', 'GEMINI', 0.15),
        ('CeraVe', 'GROK', 0.80),
    ]
    for i, (brand, engine, rank) in enumerate(rows):
        _insert_observation(
            con,
            run_id=run_id,
            record_id=f'rec-{i}',
            file_id='f1',
            source_row=i,
            module='Visibility',
            row={
                'rowType': 'ranking',
                'searchTerm': 'comparison prompt',
                'cohort': engine,
                'brandName': brand,
                'rank': rank,
                'isHero': 'True',
            },
        )
    comparisons = get_signal_comparisons(con, 'VISIBILITY_GAP', run_id, 'comparison prompt', 'Aveeno')
    engine_labels = {r['label'] for r in comparisons['engine_comparison']}
    assert engine_labels == {'GROK', 'GEMINI'}
    competitor_labels = {r['label'] for r in comparisons['competitor_comparison']}
    assert competitor_labels == {'CeraVe'}
