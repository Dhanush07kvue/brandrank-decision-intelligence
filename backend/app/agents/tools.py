from __future__ import annotations

from dataclasses import dataclass
import time
import json
from app.services.db import Database
from app.settings import effective_api_base, effective_api_key, effective_chat_deployment, effective_llm_mode, settings


@dataclass
class AgentAvailability:
    enabled: bool
    reason: str


def get_agent_availability() -> AgentAvailability:
    key = effective_api_key()
    endpoint = effective_api_base()
    configured_model = settings.openai_model if effective_llm_mode() == 'managed_responses' else effective_chat_deployment()
    if not key or not endpoint or not configured_model or key in {'YOUR_OPENAI_API_KEY', 'YOUR_AZURE_OPENAI_API_KEY'}:
        return AgentAvailability(False, 'AI agent unavailable: Azure/OpenAI API key is not configured.')
    return AgentAvailability(True, 'AI agent available.')


def get_dataset_status(db: Database) -> dict:
    con = db.connect()
    latest = con.execute('''
        select run_id from file_manifest
        group by run_id
        order by max(ingested_at) desc nulls last, run_id desc
        limit 1
    ''').fetchone()[0]
    cnt = con.execute('select count(*) from canonical_observations').fetchone()[0]
    con.close()
    return {'latest_run_id': latest, 'canonical_observations': cnt}


def search_observations(db: Database, query: str, limit: int = 50) -> list[dict]:
    con = db.connect()
    rows = con.execute(
        '''
        select record_id, file_id, source_row, schema_family, module, metric_name, metric_value, text_value
        from canonical_observations
        where lower(coalesce(text_value, '')) like ? or lower(coalesce(metric_name, '')) like ?
        limit ?
        ''',
        [f'%{query.lower()}%', f'%{query.lower()}%', limit]
    ).fetchall()
    con.close()
    return [
        {
            'record_id': r[0], 'file_id': r[1], 'source_row': r[2], 'schema_family': r[3],
            'module': r[4], 'metric_name': r[5], 'metric_value': r[6], 'text_value': r[7],
            'citation': f"[{r[1]}, row {r[2]}, {r[0]}]",
        }
        for r in rows
    ]


def save_agent_run(
    db: Database,
    run_id: str | None,
    question: str,
    tool_calls: list[dict],
    retrieved_ids: list[str],
    model: str,
    latency_ms: int,
    citations: list[dict] | None = None,
    intent: str | None = None,
    response_mode: str | None = None,
    history_enabled: bool = False,
    fallback_used: bool = False,
    validation_result: str | None = None,
) -> None:
    if run_id is None:
        return
    agent_run_id = f'agent_{int(time.time() * 1000)}'
    con = db.connect()
    con.execute(
        '''
        insert into agent_runs (
          run_id, agent_run_id, user_question, tool_calls_json, retrieved_record_ids_json,
          model, latency_ms, token_usage_json, intent, response_mode, history_enabled,
          fallback_used, validation_result
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [run_id, agent_run_id, question, json.dumps(tool_calls), json.dumps(retrieved_ids), model, latency_ms,
         json.dumps({}), intent, response_mode, history_enabled, fallback_used, validation_result]
    )
    for idx, citation in enumerate(citations or []):
        con.execute(
            '''
            insert into agent_citations (run_id, agent_run_id, citation_text, file_id, source_row, record_id, url)
            values (?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                run_id,
                agent_run_id,
                citation.get('citation_text'),
                citation.get('file_id'),
                citation.get('source_row'),
                citation.get('record_id'),
                citation.get('url'),
            ],
        )
    con.close()
