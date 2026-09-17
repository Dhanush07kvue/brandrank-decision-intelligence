from __future__ import annotations

from fastapi.testclient import TestClient

from app.agents.leadership_chat import ask_leadership_question
from app.agents.tools import AgentAvailability
from app.analytics.signals import evaluate_signals, persist_signal_instances
from app.main import app
from app.services.db import Database
from app.services.fixtures import DEMO_RUN_ID, seed_poc_fixtures
from app.services.interventions import create_intervention


def test_fastapi_import_and_health():
    response = TestClient(app).get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_demo_seed_is_idempotent_and_linked(tmp_path):
    db = Database(tmp_path / 'demo.duckdb')
    con = db.connect()
    first = seed_poc_fixtures(con)
    second = seed_poc_fixtures(con)
    assert con.execute("select count(*) from signal_instances where assessment_run_id = ?", [DEMO_RUN_ID]).fetchone()[0] == 2
    assert first['outcomes'] == 1
    assert second['outcomes'] == 0
    assert con.execute("select count(*) from interventions where signal_instance_id is not null").fetchone()[0] == 2
    assert con.execute("select count(*) from intervention_outcomes where record_provenance = 'DEMO_FIXTURE'").fetchone()[0] == 1
    con.close()


def test_blocked_rule_is_persisted_and_cannot_create_intervention(tmp_path):
    db = Database(tmp_path / 'blocked.duckdb')
    con = db.connect()
    seed_poc_fixtures(con)
    instances = evaluate_signals(con, DEMO_RUN_ID)
    blocked = next(item for item in instances if item['signal_rule_id'] == 'VISIBILITY_GAP_001')
    assert blocked['governance_status'] == 'BLOCKED'
    assert blocked['severity'] == 'BLOCKED'
    persist_signal_instances(con, DEMO_RUN_ID, instances)
    stored = con.execute(
        "select severity, governance_status from signal_instances where signal_instance_id = ?",
        [blocked['signal_instance_id']],
    ).fetchone()
    assert stored == ('BLOCKED', 'BLOCKED')

    try:
        create_intervention(con, {'signal_instance_id': blocked['signal_instance_id'], 'business_problem': 'x', 'diagnosed_cause': 'y', 'recommended_action': 'z'})
    except ValueError as exc:
        assert 'blocked' in str(exc).lower()
    else:
        raise AssertionError('blocked signal created an intervention')
    con.close()


def test_assistant_fallback_is_structured_and_records_context(tmp_path, monkeypatch):
    db = Database(tmp_path / 'assistant.duckdb')
    con = db.connect()
    seed_poc_fixtures(con)
    con.close()
    monkeypatch.setattr('app.agents.leadership_chat.get_agent_availability', lambda: AgentAvailability(False, 'test fallback'))
    result = ask_leadership_question(db, DEMO_RUN_ID, 'What should leadership prioritize?', history_enabled=False)
    assert result.fallback_used is True
    assert result.headline
    assert result.priorities
    assert result.evidence_references


def test_signal_solution_uses_selected_evidence_and_returns_specific_plan(tmp_path, monkeypatch):
    db = Database(tmp_path / 'signal-solution.duckdb')
    con = db.connect()
    seed_poc_fixtures(con)
    signal_id = con.execute(
        "select signal_instance_id from signal_instances where assessment_run_id = ? order by signal_instance_id limit 1",
        [DEMO_RUN_ID],
    ).fetchone()[0]
    con.close()
    monkeypatch.setattr('app.agents.leadership_chat.get_agent_availability', lambda: AgentAvailability(False, 'test fallback'))

    result = ask_leadership_question(
        db,
        DEMO_RUN_ID,
        'Create a specific solution for this signal.',
        mode='ANALYST',
        history_enabled=False,
        signal_instance_id=signal_id,
    )

    assert result.fallback_used is True
    assert '## Priorities' in result.answer
    assert '## Limitations' in result.answer
    assert signal_id in result.retrieved_record_ids
    assert result.citations
    assert all(c['record_id'] != 'grok-record' for c in result.citations)


def test_engine_question_is_filtered_and_uses_safe_business_fallback(tmp_path, monkeypatch):
    db = Database(tmp_path / 'engine-assistant.duckdb')
    con = db.connect()
    seed_poc_fixtures(con)
    con.execute(
        '''
        insert into canonical_observations (
          run_id, record_id, file_id, source_row, module, metric_name, metric_value,
          text_value, qualifiers_json, observation_state
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OBSERVATION')
        ''',
        [
            DEMO_RUN_ID, 'grok-record', 'demo-source', 2, 'AI Vulnerability',
            'llmAccuracyScore', 0.72, 'Aveeno eczema moisturizer',
            '{"row":{"llm":"GROK","statementText":"Aveeno eczema moisturizer"}}',
        ],
    )
    con.close()
    monkeypatch.setattr('app.agents.leadership_chat.get_agent_availability', lambda: AgentAvailability(True, 'test'))

    result = ask_leadership_question(db, DEMO_RUN_ID, 'How is Aveeno performing on Grok?', history_enabled=False)

    assert result.fallback_used is True
    assert 'Grok' in result.answer
    assert 'Decision Context Pack' not in result.answer
    assert result.retrieved_record_ids == ['grok-record']
