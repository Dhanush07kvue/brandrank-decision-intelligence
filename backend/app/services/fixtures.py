"""Seed controlled POC demonstration fixtures for Aveeno.

Records are SIMULATED_POC and must not be presented as Brand Rank vendor evidence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import json
import duckdb

CLAIM_FIXTURES = [
    {
        'claim_id': 'claim_oat_science_001',
        'brand_id': 'aveeno',
        'claim_text': 'Oat Science Pioneer — leader in oat science',
        'consensus_accuracy_score': 0.62,
        'approval_status': 'APPROVED',
        'approver': 'Medical-Legal-Regulatory',
        'last_reviewed_date': '2026-01-15',
        'evidence_reference': 'https://www.aveeno.com/science/oat-science',
    },
    {
        'claim_id': 'claim_eczema_001',
        'brand_id': 'aveeno',
        'claim_text': '#1 Dermatologist Recommended Eczema Moisturizer Brand',
        'consensus_accuracy_score': 0.48,
        'approval_status': 'PENDING',
        'approver': None,
        'last_reviewed_date': '2025-11-20',
        'evidence_reference': 'Internal survey reference IQV-2024-US',
    },
    {
        'claim_id': 'claim_barrier_001',
        'brand_id': 'aveeno',
        'claim_text': "Helps replenish and support the skin's moisture barrier",
        'consensus_accuracy_score': 0.71,
        'approval_status': 'APPROVED',
        'approver': 'Medical-Legal-Regulatory',
        'last_reviewed_date': '2026-02-10',
        'evidence_reference': 'https://www.aveeno.com/moisturizers',
    },
    {
        'claim_id': 'claim_24h_001',
        'brand_id': 'aveeno',
        'claim_text': '24-hour moisturization',
        'consensus_accuracy_score': 0.58,
        'approval_status': 'APPROVED',
        'approver': 'Medical-Legal-Regulatory',
        'last_reviewed_date': '2026-01-28',
        'evidence_reference': 'https://www.aveeno.com/moisturizers/daily',
    },
]

CONTENT_ASSET_FIXTURES = [
    {
        'asset_id': 'page_aveeno_oat_science',
        'brand_id': 'aveeno',
        'canonical_url': 'https://www.aveeno.com/science/oat-science',
        'content_type': 'BRAND_PAGE',
        'readiness_status': 'READY_TO_PUBLISH',
        'content_owner': 'Brand Content Team',
        'approver': 'Medical-Legal-Regulatory',
        'last_reviewed_date': '2026-01-15',
    },
    {
        'asset_id': 'page_aveeno_eczema',
        'brand_id': 'aveeno',
        'canonical_url': 'https://www.aveeno.com/eczema',
        'content_type': 'CONDITION_PAGE',
        'readiness_status': 'NEEDS_REVIEW',
        'content_owner': 'Brand Content Team',
        'approver': None,
        'last_reviewed_date': '2025-10-01',
    },
    {
        'asset_id': 'page_aveeno_moisturizers',
        'brand_id': 'aveeno',
        'canonical_url': 'https://www.aveeno.com/moisturizers',
        'content_type': 'PRODUCT_PAGE',
        'readiness_status': 'READY_TO_PUBLISH',
        'content_owner': 'Brand Content Team',
        'approver': 'Medical-Legal-Regulatory',
        'last_reviewed_date': '2026-02-20',
    },
]

PROMPT_PRIORITY_FIXTURES = [
    {
        'prompt_id': 'prompt_eczema_moisturizer',
        'brand_id': 'aveeno',
        'prompt_text': 'best moisturizer for eczema',
        'priority_level': 'HIGH',
        'category': 'Condition Management',
        'is_hero': True,
        'approved_by': 'Brand Strategy',
    },
    {
        'prompt_id': 'prompt_oat_science',
        'brand_id': 'aveeno',
        'prompt_text': 'oat science skincare',
        'priority_level': 'HIGH',
        'category': 'Brand Differentiation',
        'is_hero': True,
        'approved_by': 'Brand Strategy',
    },
    {
        'prompt_id': 'prompt_sensitive_skin',
        'brand_id': 'aveeno',
        'prompt_text': 'gentle moisturizer for sensitive skin',
        'priority_level': 'HIGH',
        'category': 'Skin Type',
        'is_hero': False,
        'approved_by': 'Brand Strategy',
    },
    {
        'prompt_id': 'prompt_barrier_repair',
        'brand_id': 'aveeno',
        'prompt_text': 'skin barrier repair moisturizer',
        'priority_level': 'MEDIUM',
        'category': 'Skin Health',
        'is_hero': False,
        'approved_by': 'Brand Strategy',
    },
]


METRIC_CONTRACT_FIXTURES = [
    {
        'metric_id': 'MTR-VIS-RANK',
        'metric_name': 'rank',
        'module': 'Visibility',
        'description': 'Search engine visibility rank position',
        'direction': 'LOWER_IS_BETTER',
        'grain': 'PER_PROMPT',
        'calculated_by': 'VENDOR',
        'validation_status': 'PROVISIONAL_INFERRED',
    },
    {
        'metric_id': 'MTR-VULN-LLM-ACCURACY',
        'metric_name': 'llmAccuracyScore',
        'module': 'AI Vulnerability',
        'description': 'Accuracy of an AI engine response to a Kenvue claim',
        'direction': 'HIGHER_IS_BETTER',
        'grain': 'PER_ENGINE',
        'calculated_by': 'VENDOR',
        'validation_status': 'PROVISIONAL_INFERRED',
    },
    {
        'metric_id': 'MTR-VULN-CONSENSUS-ACCURACY',
        'metric_name': 'consensusAccuracyScore',
        'module': 'AI Vulnerability',
        'description': 'Average accuracy across multiple AI engines for a claim',
        'direction': 'HIGHER_IS_BETTER',
        'grain': 'PER_CLAIM',
        'calculated_by': 'VENDOR',
        'validation_status': 'PROVISIONAL_INFERRED',
    },
    {
        'metric_id': 'MTR-CR-WEIGHTED-SCORE',
        'metric_name': 'weightedScore',
        'module': 'Content Readiness',
        'description': 'Weighted readiness factor of a brand asset',
        'direction': 'HIGHER_IS_BETTER',
        'grain': 'PER_FACTOR',
        'calculated_by': 'VENDOR',
        'validation_status': 'PROVISIONAL_INFERRED',
    },
]


SCHEMA_CONTRACT_FIXTURES = [
    {
        'schema_family': 'visibility_prompts',
        'adapter_name': 'BrandRankVisibilityAdapter',
        'expected_columns': ['prompt', 'score', 'category'],
        'description': 'Visibility scores per prompt/topic',
    },
    {
        'schema_family': 'vulnerability_claims',
        'adapter_name': 'BrandRankVulnerabilityAdapter',
        'expected_columns': ['claimText', 'consensusAccuracyScore'],
        'description': 'Cross-engine claim substantiation and accuracy',
    },
]


SEMANTIC_BLOCKER_FIXTURES = [
    {
        'blocker_id': 'BLK-VIS-RANK-01',
        'target_entity': 'rule:VISIBILITY_GAP_001',
        'blocker_type': 'UNVERIFIED_METRIC_SEMANTICS',
        'description': 'Visibility rank 0.1 encoding is unverified. If lower is better, 0.1 means position #1, so average < 0.35 threshold erroneously flags best performers as gaps.',
        'status': 'ACTIVE',
    }
]


VENDOR_QUESTION_FIXTURES = [
    {
        'question_id': 'VQ-VIS-RANK-01',
        'topic': 'Visibility Ranking',
        'question_text': 'What is the encoding of rank values (e.g. 0.1)? Does lower mean a better rank position (e.g. 1st vs 10th)?',
        'status': 'OPEN',
    },
    {
        'question_id': 'VQ-VULN-ACCURACY-01',
        'topic': 'AI Vulnerability',
        'question_text': 'How exactly is the llmAccuracyScore formula calculated from individual model responses?',
        'status': 'OPEN',
    }
]

DEMO_RUN_ID = 'demo_run_20260807'
DEMO_SIGNAL_FIXTURES = [
    {
        'signal_instance_id': 'sig_demo_oat_001',
        'signal_rule_id': 'CLAIM_AGREEMENT_INVESTIGATION_001',
        'signal_rule_version': 2,
        'brand_id': 'aveeno',
        'market': 'US',
        'assessment_run_id': DEMO_RUN_ID,
        'signal_type': 'CLAIM_AGREEMENT_INVESTIGATION',
        'group_key': 'Oat Science Pioneer — leader in oat science',
        'title': 'AI claim agreement investigation: Oat Science',
        'description': 'DEMO_FIXTURE: AI engines show provisional disagreement on the Oat Science claim; validate approved truth before action.',
        'current_value': 0.42,
        'baseline_value': 0.55,
        'delta': -0.13,
        'runs_affected': 2,
        'engines_affected': 4,
        'business_priority': 'HIGH',
        'severity': 'HIGH',
        'confidence': 0.82,
        'evidence_count': 1,
        'diagnosis_status': 'READY_FOR_DIAGNOSIS',
        'truth_validation_status': 'PENDING',
        'workflow_status': 'NEEDS_TRUTH_VALIDATION',
        'governance_status': 'EXPERIMENTAL',
        'rule_source': 'KENVUE_PROPOSED_RULE',
        'metric_contract_id': 'MTR-VULN-CONSENSUS-ACCURACY',
        'metric_validation_status': 'PROVISIONAL_INFERRED',
        'data_provenance': 'DEMO_FIXTURE',
        'known_limitations_json': json.dumps([
            'DEMO_FIXTURE: consensusAccuracyScore is vendor-calculated',
            'AI disagreement is not a regulatory substantiation conclusion',
        ]),
    },
    {
        'signal_instance_id': 'sig_demo_visibility_blocked',
        'signal_rule_id': 'VISIBILITY_GAP_001',
        'signal_rule_version': 2,
        'brand_id': 'aveeno',
        'market': 'US',
        'assessment_run_id': DEMO_RUN_ID,
        'signal_type': 'VISIBILITY_GAP',
        'group_key': '__BLOCKED__',
        'title': '[BLOCKED] Persistent priority-prompt visibility gap',
        'description': 'DEMO_FIXTURE: Visibility-rank encoding requires BrandRank validation before interpretation.',
        'current_value': 0.0,
        'baseline_value': None,
        'delta': None,
        'runs_affected': 0,
        'engines_affected': 0,
        'business_priority': 'HIGH',
        'severity': 'BLOCKED',
        'confidence': 0.0,
        'evidence_count': 0,
        'diagnosis_status': 'BLOCKED',
        'truth_validation_status': 'BLOCKED',
        'workflow_status': 'BLOCKED',
        'governance_status': 'BLOCKED',
        'rule_source': 'KENVUE_PROPOSED_RULE',
        'metric_contract_id': 'MTR-VIS-RANK',
        'metric_validation_status': 'PROVISIONAL_INFERRED',
        'data_provenance': 'DEMO_FIXTURE',
        'known_limitations_json': json.dumps(['DEMO_FIXTURE: rank encoding is unresolved']),
    },
]


INTERVENTION_FIXTURES = [
    {
        'intervention_id': 'iv_aveeno_eczema_001',
        'signal_instance_id': 'sig_demo_oat_001',
        'brand_id': 'aveeno',
        'market': 'US',
        'business_problem': 'Loss of visibility on "best moisturizer for eczema" prompt across major LLMs',
        'diagnosed_cause': 'Eczema claim not mapped to active priority',
        'recommended_action': 'Publish targeted Q&A for Eczema Therapy line',
        'status': 'APPROVED_FOR_BRIEF',
        'priority': 'HIGH',
        'confidence': 0.85,
        'owner': 'Sarah Jenkins',
    },
    {
        'intervention_id': 'iv_aveeno_oat_001',
        'signal_instance_id': 'sig_demo_oat_001',
        'brand_id': 'aveeno',
        'market': 'US',
        'business_problem': 'Oat Science Pioneer claim lacks verifiable consensus evidence',
        'diagnosed_cause': 'Legacy science page is not machine-readable',
        'recommended_action': 'Rewrite oat science page with semantic markup',
        'status': 'PUBLISHED',
        'priority': 'HIGH',
        'confidence': 0.92,
        'owner': 'Brand Content Team',
    }
]


OUTCOME_FIXTURES = [
    {
        'outcome_id': 'out_aveeno_oat_001',
        'intervention_id': 'iv_aveeno_oat_001',
        'baseline_value': 0.32,
        'post_change_value': 0.88,
        'absolute_delta': 0.56,
        'percentage_delta': 175.0,
        'outcome_status': 'IMPROVED',
        'confidence': 0.95,
        'comparison_limitations': 'None',
        'record_provenance': 'DEMO_FIXTURE',
    }
]


def seed_poc_fixtures(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    now = datetime.now(timezone.utc).isoformat()
    counts: dict[str, int] = {}
    for table, column in [
        ('signal_evidence', 'assessment_run_id'), ('signal_instances', 'assessment_run_id'),
        ('canonical_observations', 'run_id'), ('file_manifest', 'run_id'),
    ]:
        con.execute(f'delete from {table} where {column} = ?', [DEMO_RUN_ID])

    con.execute('''
        insert into assessment_runs (
          run_id, source_system, brand_id, market, language, module, acquisition_date,
          vendor_assessment_date, context_provenance_json, ingestion_run_id, quality_status, acquired_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict (run_id) do nothing
    ''', [
        DEMO_RUN_ID, 'BrandRank', 'aveeno', 'US', 'en-US', 'AI Vulnerability', '2026-08-07',
        '2026-08-07', json.dumps({'brand': 'DEMO_FIXTURE', 'market': 'DEMO_FIXTURE', 'language': 'DEMO_FIXTURE'}),
        DEMO_RUN_ID, 'PROVISIONAL', now,
    ])
    con.execute('''
        insert into file_manifest (
          run_id, file_id, physical_path, archive_chain, original_filename, byte_size, sha256,
          payload_sha256, delimiter, encoding, schema_fingerprint, header_json, row_count,
          parsed_row_count, rejected_row_count, is_empty, inferred_brand, inferred_module,
          inferred_assessment_date, inferred_market, inferred_language, adapter_name,
          adapter_version, ingestion_status, error_message
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        DEMO_RUN_ID, 'file_demo_oat_001', 'DEMO_FIXTURE', '', 'demo_oat_science.csv', 0,
        'DEMO_FIXTURE', 'DEMO_FIXTURE', ',', 'utf-8', 'demo', json.dumps(['statementText', 'consensusAccuracyScore']),
        1, 1, 0, False, 'aveeno', 'AI Vulnerability', '2026-08-07', 'US', 'en-US',
        'DemoFixtureAdapter', '1.0.0', 'SUPPORTED', 'DEMO_FIXTURE',
    ])
    con.execute('''
        insert into canonical_observations (
          run_id, record_id, file_id, payload_sha256, source_row, schema_family, module,
          metric_name, metric_value, text_value, qualifiers_json, record_hash, adapter_version,
          observation_state
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        DEMO_RUN_ID, 'record_demo_oat_001', 'file_demo_oat_001', 'DEMO_FIXTURE', 2,
        'claim_assessments', 'AI Vulnerability', 'consensusAccuracyScore', 0.42,
        'Oat Science Pioneer — leader in oat science', json.dumps({
            'row': {'rowType': 'summary', 'statementText': 'Oat Science Pioneer — leader in oat science', 'consensusAccuracyScore': '0.42'},
            'provenance': 'DEMO_FIXTURE',
        }), 'DEMO_FIXTURE', 'DemoFixtureAdapter/1.0.0', 'OBSERVATION',
    ])
    for signal in DEMO_SIGNAL_FIXTURES:
        con.execute('''
            insert into signal_instances (
              signal_instance_id, signal_rule_id, signal_rule_version, brand_id, market,
              assessment_run_id, signal_type, group_key, title, description, current_value,
              baseline_value, delta, runs_affected, engines_affected, business_priority,
              severity, confidence, evidence_count, diagnosis_status, truth_validation_status,
              workflow_status, governance_status, rule_source, metric_contract_id,
              metric_validation_status, data_provenance, known_limitations_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            signal['signal_instance_id'], signal['signal_rule_id'], signal['signal_rule_version'], signal['brand_id'],
            signal['market'], signal['assessment_run_id'], signal['signal_type'], signal['group_key'], signal['title'],
            signal['description'], signal['current_value'], signal['baseline_value'], signal['delta'], signal['runs_affected'],
            signal['engines_affected'], signal['business_priority'], signal['severity'], signal['confidence'], signal['evidence_count'],
            signal['diagnosis_status'], signal['truth_validation_status'], signal['workflow_status'], signal['governance_status'],
            signal['rule_source'], signal['metric_contract_id'], signal['metric_validation_status'], signal['data_provenance'],
            signal['known_limitations_json'],
        ])
    con.execute('''
        insert into signal_evidence (signal_instance_id, assessment_run_id, record_id, file_id, source_row, evidence_role)
        values (?, ?, ?, ?, ?, ?)
    ''', ['sig_demo_oat_001', DEMO_RUN_ID, 'record_demo_oat_001', 'file_demo_oat_001', 2, 'DEMO_FIXTURE'])

    inserted = 0
    for c in CLAIM_FIXTURES:
        if con.execute('select 1 from claim_truth where claim_id = ?', [c['claim_id']]).fetchone() is None:
            con.execute(
                'insert into claim_truth (claim_id, brand_id, claim_text, consensus_accuracy_score, approval_status, approver, last_reviewed_date, evidence_reference, created_at) values (?,?,?,?,?,?,?,?,?)',
                [c['claim_id'], c['brand_id'], c['claim_text'], c['consensus_accuracy_score'],
                 c['approval_status'], c['approver'], c['last_reviewed_date'], c['evidence_reference'], now],
            )
            inserted += 1
    counts['claim_truth'] = inserted
    con.execute("update claim_truth set record_provenance = 'DEMO_FIXTURE' where brand_id = 'aveeno' and claim_id in (?, ?, ?, ?)", [c['claim_id'] for c in CLAIM_FIXTURES])

    inserted = 0
    for a in CONTENT_ASSET_FIXTURES:
        if con.execute('select 1 from content_assets where asset_id = ?', [a['asset_id']]).fetchone() is None:
            con.execute(
                'insert into content_assets (asset_id, brand_id, canonical_url, content_type, readiness_status, content_owner, approver, last_reviewed_date, created_at) values (?,?,?,?,?,?,?,?,?)',
                [a['asset_id'], a['brand_id'], a['canonical_url'], a['content_type'],
                 a['readiness_status'], a['content_owner'], a['approver'], a['last_reviewed_date'], now],
            )
            inserted += 1
    counts['content_assets'] = inserted
    con.execute("update content_assets set record_provenance = 'DEMO_FIXTURE' where brand_id = 'aveeno'")

    inserted = 0
    for p in PROMPT_PRIORITY_FIXTURES:
        if con.execute('select 1 from prompt_priorities where prompt_id = ?', [p['prompt_id']]).fetchone() is None:
            con.execute(
                'insert into prompt_priorities (prompt_id, brand_id, prompt_text, priority_level, category, is_hero, approved_by, created_at) values (?,?,?,?,?,?,?,?)',
                [p['prompt_id'], p['brand_id'], p['prompt_text'], p['priority_level'],
                 p['category'], p['is_hero'], p['approved_by'], now],
            )
            inserted += 1
    counts['prompt_priorities'] = inserted
    con.execute("update prompt_priorities set record_provenance = 'DEMO_FIXTURE' where brand_id = 'aveeno'")

    inserted = 0
    for m in METRIC_CONTRACT_FIXTURES:
        if con.execute('select 1 from metric_contracts where metric_id = ?', [m['metric_id']]).fetchone() is None:
            con.execute(
                'insert into metric_contracts (metric_id, metric_name, module, description, direction, grain, calculated_by, validation_status, created_at) values (?,?,?,?,?,?,?,?,?)',
                [m['metric_id'], m['metric_name'], m['module'], m['description'], m['direction'], m['grain'], m['calculated_by'], m['validation_status'], now],
            )
            inserted += 1
    counts['metric_contracts'] = inserted

    inserted = 0
    for s in SCHEMA_CONTRACT_FIXTURES:
        if con.execute('select 1 from schema_contracts where schema_family = ?', [s['schema_family']]).fetchone() is None:
            con.execute(
                'insert into schema_contracts (schema_family, adapter_name, expected_columns_json, description, created_at) values (?,?,?,?,?)',
                [s['schema_family'], s['adapter_name'], json.dumps(s['expected_columns']), s['description'], now],
            )
            inserted += 1
    counts['schema_contracts'] = inserted
    
    inserted = 0
    for b in SEMANTIC_BLOCKER_FIXTURES:
        if con.execute('select 1 from semantic_blockers where blocker_id = ?', [b['blocker_id']]).fetchone() is None:
            con.execute(
                'insert into semantic_blockers (blocker_id, target_entity, blocker_type, description, status, created_at) values (?,?,?,?,?,?)',
                [b['blocker_id'], b['target_entity'], b['blocker_type'], b['description'], b['status'], now],
            )
            inserted += 1
    counts['semantic_blockers'] = inserted
    
    inserted = 0
    for q in VENDOR_QUESTION_FIXTURES:
        if con.execute('select 1 from vendor_questions where question_id = ?', [q['question_id']]).fetchone() is None:
            con.execute(
                'insert into vendor_questions (question_id, topic, question_text, status, created_at) values (?,?,?,?,?)',
                [q['question_id'], q['topic'], q['question_text'], q['status'], now],
            )
            inserted += 1
    counts['vendor_questions'] = inserted

    inserted = 0
    for i in INTERVENTION_FIXTURES:
        if con.execute('select 1 from interventions where intervention_id = ?', [i['intervention_id']]).fetchone() is None:
            con.execute(
                'insert into interventions (intervention_id, signal_instance_id, brand_id, market, business_problem, diagnosed_cause, recommended_action, status, priority, confidence, owner, created_at, record_provenance) values (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [i['intervention_id'], i['signal_instance_id'], i['brand_id'], i['market'], i['business_problem'], i['diagnosed_cause'], i['recommended_action'], i['status'], i['priority'], i['confidence'], i['owner'], now, 'DEMO_FIXTURE'],
            )
            inserted += 1
    counts['interventions'] = inserted

    inserted = 0
    for o in OUTCOME_FIXTURES:
        if con.execute('select 1 from intervention_outcomes where outcome_id = ?', [o['outcome_id']]).fetchone() is None:
            con.execute(
                'insert into intervention_outcomes (outcome_id, intervention_id, baseline_run_id, post_change_run_id, baseline_value, post_change_value, absolute_delta, percentage_delta, outcome_status, confidence, comparison_limitations, created_at, record_provenance) values (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [o['outcome_id'], o['intervention_id'], DEMO_RUN_ID, DEMO_RUN_ID, o['baseline_value'], o['post_change_value'], o['absolute_delta'], o['percentage_delta'], o['outcome_status'], o['confidence'], o['comparison_limitations'], now, 'DEMO_FIXTURE'],
            )
            inserted += 1
    counts['outcomes'] = inserted

    return counts
