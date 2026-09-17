from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
import json
import re

from openai import AzureOpenAI, OpenAI

from app.agents.tools import get_agent_availability, save_agent_run
from app.settings import effective_api_base, effective_api_key, effective_chat_deployment, effective_llm_mode, settings
from app.services.db import Database


@dataclass
class ChatResult:
    answer: str
    ai_available: bool
    citations: list[dict[str, Any]]
    limitations: list[str]
    retrieved_record_ids: list[str]
    model: str
    latency_ms: int
    headline: str | None = None
    priorities: list[dict[str, Any]] | None = None
    decision_required: str | None = None
    evidence_references: dict[str, dict[str, Any]] | None = None
    fallback_used: bool = False


def _get_client() -> tuple[str, Any] | None:
    api_key = effective_api_key()
    endpoint = effective_api_base()
    deployment = effective_chat_deployment()
    mode = effective_llm_mode()

    if mode == 'managed_responses':
        if not api_key or not endpoint:
            return None
        return (
            mode,
            OpenAI(
                api_key=api_key,
                base_url=endpoint,
                default_headers={'apikey': api_key},
            ),
        )

    if not api_key or not endpoint or not deployment:
        return None
    return (
        mode,
        AzureOpenAI(
            api_key=api_key,
            api_version=settings.openai_api_version,
            azure_endpoint=endpoint,
        ),
    )


def _route_intent(question: str) -> str:
    """Classify the user intent into specific domains."""
    q = question.lower()
    if re.search(r'\b(grok|gemini|openai|chatgpt|perplexity|claude|anthropic|meta ai)\b', q) and any(
        phrase in q for phrase in ('perform', 'doing', 'say', 'visibility on', 'on grok', 'on gemini', 'on claude')
    ):
        return 'engine_performance'
    if 'signal' in q or 'gap' in q or 'vulnerability' in q or 'risk' in q:
        return 'signals'
    if 'intervention' in q or 'action' in q or 'do about' in q or 'fix' in q:
        return 'interventions'
    if 'outcome' in q or 'result' in q or 'measure' in q or 'impact' in q:
        return 'outcomes'
    if 'trust' in q or 'blocked' in q or 'quality' in q or 'metric' in q:
        return 'trust'
    return 'broad'


def _extract_engine(question: str) -> str | None:
    engines = ('grok', 'gemini', 'openai', 'chatgpt', 'perplexity', 'claude', 'anthropic', 'meta ai')
    q = question.lower()
    for engine in engines:
        if engine in q:
            return engine
    return None


def _build_decision_context_pack(
    db: Database,
    run_id: str | None,
    intent: str,
    engine: str | None = None,
    signal_instance_id: str | None = None,
) -> dict[str, Any]:
    if not run_id:
        return {}

    con = db.connect()
    try:
        pack = {'run_id': run_id, 'intent': intent, 'limitations': []}
        context = con.execute('''
            select source_system, brand_id, market, language, context_provenance_json, quality_status
            from assessment_runs where run_id = ?
        ''', [run_id]).fetchone()
        if context:
            pack['current_context'] = {
                'source_system': context[0], 'brand_id': context[1], 'market': context[2],
                'language': context[3], 'context_provenance': json.loads(context[4]) if context[4] else {},
                'semantic_trust_state': context[5] or 'PROVISIONAL',
            }

        if intent == 'signal_solution' and signal_instance_id:
            signal_row = con.execute('''
                select signal_instance_id, signal_type, group_key, title, description, current_value,
                       severity, confidence, evidence_count, diagnosis_status, truth_validation_status,
                       workflow_status, governance_status, metric_contract_id, metric_validation_status,
                       known_limitations_json
                from signal_instances
                where signal_instance_id = ? and assessment_run_id = ?
            ''', [signal_instance_id, run_id]).fetchone()
            if not signal_row:
                return pack
            pack['signal'] = {
                'id': signal_row[0], 'signal_type': signal_row[1], 'group_key': signal_row[2],
                'title': signal_row[3], 'description': signal_row[4], 'current_value': signal_row[5],
                'severity': signal_row[6], 'confidence': signal_row[7], 'evidence_count': signal_row[8],
                'diagnosis_status': signal_row[9], 'truth_validation_status': signal_row[10],
                'workflow_status': signal_row[11], 'governance_status': signal_row[12],
                'metric_contract_id': signal_row[13], 'metric_validation_status': signal_row[14],
                'known_limitations': json.loads(signal_row[15]) if signal_row[15] else [],
            }
            evidence = con.execute('''
                select c.record_id, c.file_id, c.source_row, c.module, c.metric_name,
                       c.metric_value, c.text_value, c.qualifiers_json, m.original_filename
                from signal_evidence se
                join canonical_observations c
                  on se.record_id = c.record_id and se.assessment_run_id = c.run_id
                left join file_manifest m on m.run_id = c.run_id and m.file_id = c.file_id
                where se.signal_instance_id = ? and se.assessment_run_id = ?
                order by c.source_row
                limit 40
            ''', [signal_instance_id, run_id]).fetchall()
            pack['signal_evidence'] = []
            for row in evidence:
                raw = json.loads(row[7]) if row[7] else {}
                source = raw.get('row', {})
                subject = source.get('statementText') or source.get('searchTerm') or source.get('groupName') or source.get('pageLabel') or row[6] or 'Source observation'
                engine_name = source.get('llm') or source.get('llmSource') or source.get('cohort')
                pack['signal_evidence'].append({
                    'id': row[0], 'file_id': row[1], 'source_row': row[2], 'module': row[3] or 'Unclassified',
                    'metric': row[4] or 'vendor observation', 'value': row[5], 'subject': str(subject),
                    'filename': row[8], 'engine': engine_name, 'raw': source,
                })
            return pack

        if intent == 'engine_performance' and engine:
            observations = con.execute('''
                select record_id, file_id, source_row, module, metric_name, metric_value, text_value, qualifiers_json
                from canonical_observations
                where run_id = ?
                  and lower(coalesce(
                    json_extract_string(qualifiers_json, '$.row.llm'),
                    json_extract_string(qualifiers_json, '$.row.llmSource'),
                    json_extract_string(qualifiers_json, '$.row.cohort')
                  )) = ?
                order by module, source_row
                limit 40
            ''', [run_id, engine.lower()]).fetchall()
            pack['engine'] = engine
            pack['engine_evidence'] = []
            for row in observations:
                raw = json.loads(row[7]) if row[7] else {}
                source = raw.get('row', {})
                subject = source.get('statementText') or source.get('groupName') or source.get('searchTerm') or source.get('text') or source.get('sourceName') or row[6] or 'Observed item'
                value = row[5]
                if value is None:
                    for key in ('llmAccuracyScore', 'consensusAccuracyScore', 'weightedScore', 'factorScore', 'score', 'rank'):
                        try:
                            value = float(source[key]) if source.get(key) not in (None, '') else value
                        except (TypeError, ValueError):
                            pass
                pack['engine_evidence'].append({
                    'id': row[0], 'file_id': row[1], 'source_row': row[2], 'module': row[3] or 'Unclassified',
                    'metric': row[4] or 'vendor observation', 'value': value, 'subject': str(subject),
                })
            return pack

        if intent in ('signals', 'broad'):
            signals = con.execute('''
                select signal_instance_id, title, description, severity, confidence, governance_status
                from signal_instances
                where assessment_run_id = ? and governance_status != 'BLOCKED'
                order by 
                  case severity when 'CRITICAL' then 0 when 'HIGH' then 1 when 'MEDIUM' then 2 else 3 end,
                  confidence desc
                limit 5
            ''', [run_id]).fetchall()
            pack['signals'] = [{'id': s[0], 'title': s[1], 'description': s[2], 'severity': s[3], 'confidence': s[4]} for s in signals]

        if intent in ('interventions', 'broad'):
            interventions = con.execute('''
                select intervention_id, business_problem, recommended_action, status, priority, confidence
                from interventions
                where status != 'COMPLETED'
                order by 
                  case priority when 'HIGH' then 0 when 'MEDIUM' then 1 else 2 end,
                  confidence desc
                limit 5
            ''').fetchall()
            pack['interventions'] = [{'id': i[0], 'problem': i[1], 'action': i[2], 'status': i[3], 'priority': i[4]} for i in interventions]

        if intent in ('outcomes', 'broad'):
            outcomes = con.execute('''
                select o.outcome_id, i.business_problem, o.outcome_status, o.absolute_delta, o.percentage_delta, o.confidence
                from intervention_outcomes o
                join interventions i on o.intervention_id = i.intervention_id
                order by o.created_at desc
                limit 5
            ''').fetchall()
            pack['outcomes'] = [{'id': o[0], 'problem': o[1], 'status': o[2], 'abs_delta': o[3], 'pct_delta': o[4]} for o in outcomes]
            
        if intent in ('trust', 'broad'):
            blocked_rules = con.execute('''
                select signal_rule_id, title, description
                from signal_instances 
                where assessment_run_id = ? and governance_status = 'BLOCKED'
                limit 5
            ''', [run_id]).fetchall()
            pack['blocked_rules'] = [{'id': b[0], 'name': b[1], 'reason': b[2]} for b in blocked_rules]

        return pack
    finally:
        con.close()


def _format_context_text(pack: dict[str, Any]) -> str:
    lines = []
    if pack.get('current_context'):
        c = pack['current_context']
        lines.append(f"## CURRENT CONTEXT\n- {c['brand_id']} | {c['market']} | {c['language']} | run {pack['run_id']} | {c['source_system']} | {c['semantic_trust_state']}")

    if pack.get('signal'):
        s = pack['signal']
        confidence = 'not established' if s.get('confidence') is None else f"{float(s['confidence']):.2f}"
        lines.append("## SELECTED SIGNAL FOR REMEDIATION")
        lines.append(
            f"- [EVIDENCE_REF: {s['id']}] {s['title']} | type={s['signal_type']} | subject={s['group_key']} | "
            f"value={s['current_value']} | severity={s['severity']} | confidence={confidence} | "
            f"governance={s['governance_status']} | metric_validation={s['metric_validation_status']}"
        )
        lines.append(f"- Diagnosis={s['diagnosis_status']} | truth_validation={s['truth_validation_status']} | workflow={s['workflow_status']}")
        if s.get('known_limitations'):
            lines.append(f"- Limitations: {'; '.join(s['known_limitations'])}")
        if pack.get('signal_evidence'):
            lines.append("## SELECTED SIGNAL SOURCE EVIDENCE")
            for item in pack['signal_evidence']:
                raw = item.get('raw') or {}
                prompt = raw.get('searchTerm') or raw.get('statementText') or raw.get('question') or 'No prompt recorded'
                lines.append(
                    f"- [EVIDENCE_REF: {item['id']}] {item['filename']} row {item['source_row']} | "
                    f"subject={item['subject']} | prompt_or_claim={prompt} | metric={item['metric']}={item['value']} | "
                    f"engine={item.get('engine') or 'not recorded'}"
                )

    if pack.get('engine_evidence'):
        lines.append(f"## ENGINE PERFORMANCE: {pack.get('engine', 'selected engine').upper()}")
        for item in pack['engine_evidence']:
            value = 'not reported' if item.get('value') is None else str(item['value'])
            lines.append(f"- [EVIDENCE_REF: {item['id']}] {item['module']} | {item['subject']} | {item['metric']} = {value}")
    
    if 'signals' in pack and pack['signals']:
        lines.append("## ACTIVE SIGNALS")
        for s in pack['signals']:
            lines.append(f"- [EVIDENCE_REF: {s['id']}] {s['severity']} Priority | {s['title']}: {s['description']} (Conf: {s['confidence']:.2f})")
            
    if 'interventions' in pack and pack['interventions']:
        lines.append("\n## INTERVENTIONS IN PROGRESS")
        for i in pack['interventions']:
            lines.append(f"- [EVIDENCE_REF: {i['id']}] {i['priority']} Priority | {i['status']}: {i['problem']} -> {i['action']}")

    if 'outcomes' in pack and pack['outcomes']:
        lines.append("\n## RECENT OUTCOMES")
        for o in pack['outcomes']:
            lines.append(f"- [EVIDENCE_REF: {o['id']}] {o['status']} | {o['problem']} (Change: {o['pct_delta'] or o['abs_delta'] or 0})")
            
    if 'blocked_rules' in pack and pack['blocked_rules']:
        lines.append("\n## BLOCKED GOVERNANCE RULES")
        for b in pack['blocked_rules']:
            lines.append(f"- [EVIDENCE_REF: {b['id']}] {b['name']}: {b['reason']}")

    return '\n'.join(lines)


def _deterministic_fallback(intent: str, pack: dict[str, Any]) -> str:
    opening = (
        "*Generated from structured evidence. Engine-specific answers use a deterministic evidence view.*\n"
        if intent == 'engine_performance'
        else "*Generated from the selected signal evidence. AI synthesis is currently unavailable.*\n"
        if intent == 'signal_solution'
        else "*Generated from structured evidence. AI synthesis is currently unavailable.*\n"
    )
    lines = [opening]
    if intent == 'signal_solution':
        signal = pack.get('signal')
        evidence = pack.get('signal_evidence', [])
        if not signal:
            return lines[0] + 'The selected signal could not be found in the current assessment run.'
        subject = signal.get('group_key') or signal.get('title')
        lines.append(f"## Remediation plan for {subject}")
        lines.append('\n## Headline')
        lines.append(f"Reduce answer inconsistency for **{subject}** by validating the claim first, then making the approved source evidence easier for AI systems to find and interpret. Do not treat the inconsistency as proof that the claim is false.")
        lines.append('\n## Priorities')
        lines.append(f"- **Confirm the truth position:** route **{subject}** through Kenvue truth validation and record the approved wording, owner, evidence source, and review date before changing public content.")
        lines.append(f"- **Strengthen the source page:** ensure the approved statement and supporting substantiation appear together in clear, machine-readable page content. Use semantic claim/evidence markup only after MLR and regulatory review.")
        lines.append('- **Retest the same setup:** rerun the same statement across the same AI engines, market, language, and prompt set. Compare the per-engine scores and the spread against this baseline; do not mix new prompts into the comparison.')
        lines.append('- **Gate the decision correctly:** keep the action at diagnosis/truth validation until the claim is approved. Do not use the blocked visibility-rank rule to select the content change.')
        lines.append('\n## Evidence')
        lines.append(f"- The selected finding is **{signal.get('severity')}** and {signal.get('governance_status')} with a current inconsistency value of {signal.get('current_value')}.")
        scored = [item for item in evidence if isinstance(item.get('value'), (int, float))]
        if signal.get('signal_type') == 'CROSS_LLM_INCONSISTENCY' and scored:
            highest = max(scored, key=lambda item: float(item['value']))
            lowest = min(scored, key=lambda item: float(item['value']))
            lines.append(
                f"- The linked source rows span {float(lowest['value']):.2f} to {float(highest['value']):.2f}: "
                f"{lowest.get('engine') or 'the lowest-labelled engine'} is lowest and {highest.get('engine') or 'the highest-labelled engine'} is highest. "
                'This is a consistency problem to investigate, not a visibility or claim-truth score.'
            )
        for item in evidence:
            lines.append(f"- [EVIDENCE_REF: {item['id']}] {item['filename']} row {item['source_row']} records {item['subject']} with {item['metric']}={item['value']} for {item.get('engine') or 'an unlabelled source dimension'}.")
        lines.append('\n## Limitations')
        lines.append('- This is a remediation hypothesis, not proof that content changes will cause better AI answers.')
        lines.append('- The source evidence does not establish which wording change will improve every engine; validate one approved change and measure it with a matched retest.')
        if signal.get('known_limitations'):
            lines.append(f"- Metric limitations: {'; '.join(signal['known_limitations'])}")
        return '\n'.join(lines)
    if intent == 'engine_performance':
        engine = str(pack.get('engine') or 'selected engine').title()
        evidence = pack.get('engine_evidence', [])
        if not evidence:
            return f'## {pack.get("current_context", {}).get("brand_id", "Brand")} on {engine}\n\nNo {engine} observations were found in the selected run. This is not evidence of poor performance; the engine may not be present in the source data.'
        lines.append(f"## {pack.get('current_context', {}).get('brand_id', 'Brand')} on {engine}")
        lines.append('\n**Overall picture:** Mixed or not yet established from the available engine-specific evidence.')
        lines.append('\n### What the source data shows')
        for item in evidence[:8]:
            value = 'not reported' if item.get('value') is None else f"{float(item['value']):.2f} vendor score" if isinstance(item.get('value'), (int, float)) else str(item['value'])
            lines.append(f"- **{item['subject']}:** {value} ({item['module']}).")
        lines.append('\n### Business meaning')
        lines.append(f'This describes what {engine} reported in the source data. It does not prove that a claim is true or false, and it should not be treated as a complete measure of AI visibility.')
        lines.append('\n### Next step')
        lines.append('Compare the engine-specific observations with approved Kenvue evidence before changing content or approving an intervention.')
        return '\n'.join(lines)
    if not any(k in pack for k in ['signals', 'interventions', 'outcomes', 'blocked_rules']):
        return lines[0] + "No relevant evidence was found for this question."
    
    lines.append(_format_context_text(pack))
    return '\n'.join(lines)


def _structured_response_fields(answer: str, pack: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str | None]:
    """Create typed response fields from the same bounded pack used for prose."""
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    headline = None
    if '## Headline' in answer:
        idx = lines.index('## Headline') if '## Headline' in lines else -1
        if idx >= 0 and idx + 1 < len(lines):
            headline = lines[idx + 1].lstrip('#-* ').strip()
    if not headline:
        if pack.get('engine_evidence'):
            headline = f"{pack.get('current_context', {}).get('brand_id', 'Brand')} on {str(pack.get('engine', 'selected engine')).title()}"
        else:
            headline = 'Evidence-backed decision context is available.' if pack else 'No decision context is available yet.'

    priorities: list[dict[str, Any]] = []
    evidence_number = 1
    for key in ('signals', 'interventions', 'outcomes', 'blocked_rules', 'engine_evidence', 'signal_evidence'):
        for item in pack.get(key, [])[:3]:
            status = str(item.get('status') or item.get('severity') or ('BLOCKED' if key == 'blocked_rules' else 'PENDING'))
            title = str(item.get('title') or item.get('problem') or item.get('name') or item.get('subject') or item.get('id'))
            why = str(item.get('description') or item.get('problem') or item.get('reason') or item.get('module') or 'Review the evidence before taking action.')
            next_step = 'Review the linked evidence and confirm governance/truth conditions.'
            if key == 'interventions':
                next_step = str(item.get('action') or next_step)
            elif key == 'blocked_rules':
                next_step = 'Resolve the semantic blocker with the vendor before using this rule.'
            elif key == 'engine_evidence':
                next_step = 'Compare the selected engine observation with approved Kenvue evidence before changing content.'
            elif key == 'signal_evidence':
                next_step = 'Use this source row to confirm the claim, source page, and matched retest design.'
            priorities.append({
                'title': title,
                'why_it_matters': why,
                'status': status,
                'recommended_next_step': next_step,
                'confidence': f"{float(item.get('confidence', 0.0)):.0%}" if item.get('confidence') is not None else 'Not established',
                'evidence_refs': [f'E{evidence_number}'],
            })
            evidence_number += 1

    decision_required = None
    if pack.get('signal'):
        decision_required = 'Confirm approved Kenvue truth and source evidence before implementing the remediation.'
    elif pack.get('engine_evidence'):
        decision_required = 'Compare the selected engine evidence with approved Kenvue truth before making a content decision.'
    elif pack.get('blocked_rules'):
        decision_required = 'Resolve the active semantic blockers before approving governed activation.'
    elif pack.get('signals'):
        decision_required = 'Confirm diagnosis and Kenvue truth validation before approving an intervention.'
    return headline, priorities, decision_required


def _quality_guard(response: str, pack: dict[str, Any]) -> tuple[bool, str]:
    """Verify the LLM didn't invent data and adhered to the structured contract."""
    # Basic structure check
    if not all(section in response for section in ['## Headline', '## Priorities', '## Evidence', '## Limitations']):
        return False, "Response missing required structured sections (Headline, Priorities, Evidence, Limitations)."
    
    # Hallucination check on evidence refs
    refs_in_response = re.findall(r'\[EVIDENCE_REF:\s*(.+?)\]', response)
    valid_ids = []
    for k in ['signals', 'interventions', 'outcomes', 'blocked_rules', 'engine_evidence', 'signal', 'signal_evidence']:
        if k == 'signal' and k in pack:
            valid_ids.append(str(pack[k]['id']))
        elif k in pack:
            valid_ids.extend([str(item['id']) for item in pack[k]])
            
    for ref in refs_in_response:
        if ref not in valid_ids and ref != 'N/A':
            return False, f"Hallucinated evidence reference: {ref}"
            
    return True, ""


def ask_leadership_question(
    db: Database, run_id: str | None, question: str, mode: str = "EXECUTIVE",
    history_enabled: bool = False, history: list[dict[str, str]] | None = None,
    app_context: dict[str, Any] | None = None,
    signal_instance_id: str | None = None,
) -> ChatResult:
    start = time.time()
    availability = get_agent_availability()
    
    intent = 'signal_solution' if signal_instance_id else _route_intent(question)
    engine = _extract_engine(question) if intent == 'engine_performance' else None
    pack = _build_decision_context_pack(db, run_id, intent, engine=engine, signal_instance_id=signal_instance_id)
    if app_context:
        pack['application_context'] = app_context
    bounded_history = (history or [])[-4:] if history_enabled else []
    if not history_enabled and any(token in question.lower().split() for token in ('why', 'that', 'first', 'it')):
        limitations = ['Previous chat context is off; include the subject in the question for an independent answer.']
    else:
        limitations = []
    context_text = _format_context_text(pack)
    
    # Extract IDs for citations
    retrieved_ids = []
    for k in ['signals', 'interventions', 'outcomes', 'blocked_rules', 'engine_evidence', 'signal', 'signal_evidence']:
        if k in pack:
            if k == 'signal':
                retrieved_ids.append(str(pack[k]['id']))
            else:
                retrieved_ids.extend([str(item['id']) for item in pack[k]])
            
    citations = []
    if pack.get('signal'):
        citations.append({'citation_text': f"Signal: {pack['signal']['title']}", 'file_id': 'db', 'source_row': 0, 'record_id': pack['signal']['id'], 'url': None})
    for item in pack.get('signal_evidence', []):
        citations.append({'citation_text': f"{item['filename']} row {item['source_row']}: {item['subject']}", 'file_id': item['file_id'], 'source_row': item['source_row'], 'record_id': item['id'], 'url': None})
    for item in pack.get('engine_evidence', []):
        citations.append({'citation_text': f"{item['module']}: {item['subject']}", 'file_id': item['file_id'], 'source_row': item['source_row'], 'record_id': item['id'], 'url': None})
    citations.extend(
        {'citation_text': f"Database Record: {rid}", 'file_id': 'db', 'source_row': 0, 'record_id': rid, 'url': None}
        for rid in retrieved_ids if not any(c['record_id'] == rid for c in citations)
    )
    limitations.append('Leadership chat is evidence-backed and read-only.')

    fallback = _deterministic_fallback(intent, pack)
    answer = fallback
    model = settings.openai_model

    # Engine-specific answers use the deterministic renderer until the
    # engine evidence contract is fully verified. This prevents a model from
    # turning a selected-engine slice into unsupported performance claims.
    client_bundle = _get_client() if availability.enabled and intent != 'engine_performance' else None
    
    if client_bundle and context_text:
        llm_mode, client = client_bundle
        
        persona = (
            "You are the Lead Decision Intelligence Analyst for executive leadership. "
            "You strictly answer questions based on the provided DECISION CONTEXT PACK.\n\n"
        )
        if intent == 'signal_solution':
            persona = (
                "You are a senior Kenvue AEO/GEO remediation strategist. Create a specific, evidence-backed solution for the selected signal. "
                "Use only the selected signal, its source rows, CSV lineage, metric status, and limitations in the Decision Context Pack. "
                "Separate observed facts from hypotheses. Never invent approved claims, page URLs, owners, regulatory approval, causation, or guaranteed AI improvement. "
                "Recommend exact next actions, truth/MLR gates, source-content improvements only when supported, and a matched retest plan.\n\n"
            )
        if mode == "EXECUTIVE":
            persona += (
                "EXECUTIVE MODE: Be extremely concise, business-focused, and action-oriented. "
                "Avoid technical data jargon. Focus on 'why this matters' and 'what to do'."
            )
        else:
            persona += (
                "ANALYST MODE: Be detailed, precise, and metrics-focused. "
                "Explain the data thoroughly and highlight statistical confidence."
            )
            
        contract = (
            "\n\nYOUR RESPONSE MUST STRICTLY FOLLOW THIS MARKDOWN FORMAT:\n\n"
            "## Headline\n"
            "(1-2 sentences summarizing the core finding)\n\n"
            "## Priorities\n"
            "- (Bullet points of actions or key insights)\n\n"
            "## Evidence\n"
            "(Cite the specific [EVIDENCE_REF: id] tokens that support your claims)\n\n"
            "## Limitations\n"
            "(Note any gaps in the data or governance blocked rules)"
        )

        history_text = ''
        if bounded_history:
            history_text = '\n\nRECENT CONVERSATION (use only to resolve references; refresh facts from the pack):\n' + '\n'.join(
                f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in bounded_history
            )
        prompt = f"{persona}{contract}\n\nDECISION CONTEXT PACK:\n{context_text}{history_text}\n\nQUESTION: {question}"

        try:
            if llm_mode == 'managed_responses':
                model = settings.openai_model
                resp = client.responses.create(
                    model=model,
                    input=prompt,
                    temperature=0.2, # Lowered from 0.7 to 0.2 for precision
                    max_output_tokens=800,
                )
                answer = getattr(resp, 'output_text', None) or ''
            else:
                model = effective_chat_deployment() or settings.openai_model
                system_message = (
                    'You are the Kenvue AEO/GEO Decision Intelligence Assistant. Use only the supplied Decision Context Pack. '
                    'Never invent claims, owners, approvals, metric definitions, causation, or priorities. Distinguish vendor observation from Kenvue decision and state uncertainty explicitly.'
                )
                if intent == 'signal_solution':
                    system_message = (
                        'You are the Kenvue AEO/GEO remediation strategist. Use only the selected signal evidence in the supplied Decision Context Pack. '
                        'Give concrete, bounded actions and a matched measurement plan. Never invent approved wording, regulatory approval, owners, causation, or guaranteed improvement. '
                        'Treat vendor metrics as observations and respect provisional or blocked governance states.'
                    )
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': system_message},
                        {'role': 'user', 'content': prompt},
                    ],
                    temperature=0.2, # Lowered from 0.7 to 0.2 for precision
                    max_tokens=800,
                )
                answer = resp.choices[0].message.content
                
            if not answer:
                answer = fallback
            else:
                # Apply Answer Quality Guard
                passed, reason = _quality_guard(answer, pack)
                if not passed:
                    limitations.append(f"AI Quality Guard triggered: {reason}. Falling back to raw data.")
                    answer = fallback

        except Exception as exc:
            limitations.append(f'AI synthesis unavailable: {exc.__class__.__name__}')

    latency_ms = int((time.time() - start) * 1000)
    save_agent_run(
        db=db,
        run_id=run_id,
        question=question,
        tool_calls=[{'tool': 'build_decision_context_pack', 'intent': intent}],
        retrieved_ids=retrieved_ids,
        model=model,
        latency_ms=latency_ms,
        citations=citations,
        intent=intent,
        response_mode=mode,
        history_enabled=history_enabled,
        fallback_used=answer == fallback,
        validation_result='FALLBACK' if answer == fallback else 'PASSED',
    )
    
    headline, priorities, decision_required = _structured_response_fields(answer, pack)
    return ChatResult(
        answer=answer,
        ai_available=availability.enabled,
        citations=citations,
        limitations=limitations,
        retrieved_record_ids=retrieved_ids,
        model=model,
        latency_ms=latency_ms,
        headline=headline,
        priorities=priorities,
        decision_required=decision_required,
        evidence_references={f'E{i + 1}': citation for i, citation in enumerate(citations)},
        fallback_used=answer == fallback,
    )
