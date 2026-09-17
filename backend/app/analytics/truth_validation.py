"""Truth validation service for signals.

Given a signal instance (representing a gap, inconsistency, or risk in the data),
this service checks whether approved truth exists that could resolve it.

Outcome states (8 total):
  APPROVED_TRUTH_EXISTS - approved, public, machine-readable truth exists
  TRUTH_EXISTS_NOT_PUBLIC - truth exists but not publicly accessible
  TRUTH_EXISTS_NOT_MACHINE_READABLE - truth exists but not in a machine-readable format
  TRUTH_INCONSISTENT - multiple truths exist but contradict each other
  TRUTH_MISSING - no truth found despite evidence of the need
  MLR_REVIEW_REQUIRED - truth found but needs legal/regulatory review
  NOT_BUSINESS_PRIORITY - no effort has been made to establish truth (deprioritized)
  INSUFFICIENT_EVIDENCE - insufficient data to make a determination
"""

from __future__ import annotations
from typing import Literal


TruthStatus = Literal[
    'APPROVED_TRUTH_EXISTS',
    'TRUTH_EXISTS_NOT_PUBLIC',
    'TRUTH_EXISTS_NOT_MACHINE_READABLE',
    'TRUTH_INCONSISTENT',
    'TRUTH_MISSING',
    'MLR_REVIEW_REQUIRED',
    'NOT_BUSINESS_PRIORITY',
    'INSUFFICIENT_EVIDENCE',
]


def check_claim_truth(con, claim_text: str, brand_id: str) -> dict:
    """Check if approved truth exists for a brand claim."""
    cur = con.execute(
        '''select * from claim_truth
           where brand_id = ? and claim_text = ?
           order by last_reviewed_date desc limit 1''',
        [brand_id, claim_text]
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    
    if row is None:
        return {'status': 'TRUTH_MISSING', 'match': None, 'approval_status': None}
    
    row_dict = dict(zip(cols, row))
    approval = row_dict.get('approval_status', '').upper()
    
    if approval == 'APPROVED':
        return {'status': 'APPROVED_TRUTH_EXISTS', 'match': row_dict, 'approval_status': 'APPROVED'}
    elif approval == 'PENDING':
        return {'status': 'MLR_REVIEW_REQUIRED', 'match': row_dict, 'approval_status': 'PENDING'}
    elif approval == 'REJECTED':
        return {'status': 'TRUTH_MISSING', 'match': row_dict, 'approval_status': 'REJECTED'}
    else:
        return {'status': 'INSUFFICIENT_EVIDENCE', 'match': row_dict, 'approval_status': approval or None}


def check_content_asset(con, canonical_url: str, brand_id: str) -> dict:
    """Check if approved content asset exists for a brand page."""
    cur = con.execute(
        '''select * from content_assets
           where brand_id = ? and canonical_url = ?
           order by last_reviewed_date desc limit 1''',
        [brand_id, canonical_url]
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    
    if row is None:
        return {'status': 'TRUTH_MISSING', 'match': None, 'readiness': None}
    
    row_dict = dict(zip(cols, row))
    status = row_dict.get('readiness_status', '').upper()
    approval = row_dict.get('approver')
    
    if status == 'READY_TO_PUBLISH' and approval:
        return {'status': 'APPROVED_TRUTH_EXISTS', 'match': row_dict, 'readiness': status}
    elif status in ('IN_REVIEW', 'IN_REVISION'):
        return {'status': 'MLR_REVIEW_REQUIRED', 'match': row_dict, 'readiness': status}
    else:
        return {'status': 'INSUFFICIENT_EVIDENCE', 'match': row_dict, 'readiness': status or None}


def check_product_truth(con, product_id_sku: str, brand_id: str) -> dict:
    """Check if approved truth exists for a product."""
    cur = con.execute(
        '''select * from product_truth
           where brand_id = ? and product_id_sku = ?
           order by last_reviewed_date desc limit 1''',
        [brand_id, product_id_sku]
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    
    if row is None:
        return {'status': 'TRUTH_MISSING', 'match': None, 'approval_status': None}
    
    row_dict = dict(zip(cols, row))
    approval = row_dict.get('approval_status', '').upper()
    
    if approval == 'APPROVED':
        return {'status': 'APPROVED_TRUTH_EXISTS', 'match': row_dict, 'approval_status': 'APPROVED'}
    elif approval in ('PENDING', 'IN_MLR'):
        return {'status': 'MLR_REVIEW_REQUIRED', 'match': row_dict, 'approval_status': approval}
    else:
        return {'status': 'INSUFFICIENT_EVIDENCE', 'match': row_dict, 'approval_status': approval or None}


def check_prompt_priority(con, prompt_text: str, brand_id: str) -> dict:
    """Check if a prompt is business-priority for a brand."""
    cur = con.execute(
        '''select priority_level, is_hero from prompt_priorities
           where brand_id = ? and prompt_text = ?
           limit 1''',
        [brand_id, prompt_text]
    )
    row = cur.fetchone()
    
    if row is None:
        return {'is_priority': False, 'priority_level': None, 'is_hero': False}
    
    priority, is_hero = row[0], row[1]
    return {'is_priority': priority in ('HIGH', 'MEDIUM'), 'priority_level': priority, 'is_hero': bool(is_hero)}


def validate_signal_truth(con, signal_instance: dict) -> dict:
    """Validate a signal instance against the truth registry."""
    signal_type = signal_instance.get('signal_type', '')
    group_key = signal_instance.get('group_key', '')
    brand_id = signal_instance.get('brand_id', '')
    
    if signal_type in ('CLAIM_SUBSTANTIATION_RISK', 'CLAIM_AGREEMENT_INVESTIGATION'):
        truth = check_claim_truth(con, group_key, brand_id)
        status = truth['status']
        matched_truth = truth['match']['claim_id'] if truth['match'] else None
    
    elif signal_type == 'READINESS_DETERIORATION':
        truth = check_content_asset(con, group_key, brand_id)
        status = truth['status']
        matched_truth = truth['match']['asset_id'] if truth['match'] else None
    
    elif signal_type in ('VISIBILITY_GAP', 'CROSS_LLM_INCONSISTENCY'):
        priority_check = check_prompt_priority(con, group_key, brand_id)
        if priority_check['is_priority']:
            truth = check_claim_truth(con, group_key, brand_id)
            status = truth['status']
            matched_truth = truth['match']['claim_id'] if truth['match'] else None
        else:
            status = 'NOT_BUSINESS_PRIORITY'
            matched_truth = None
    
    else:
        status = 'INSUFFICIENT_EVIDENCE'
        matched_truth = None
    
    next_step_map = {
        'APPROVED_TRUTH_EXISTS': 'READY_FOR_INTERVENTION',
        'TRUTH_EXISTS_NOT_PUBLIC': 'REQUEST_PUBLICATION',
        'TRUTH_EXISTS_NOT_MACHINE_READABLE': 'REQUEST_FORMATTING',
        'TRUTH_INCONSISTENT': 'REQUEST_CLARIFICATION',
        'TRUTH_MISSING': 'REQUEST_TRUTH_CREATION',
        'MLR_REVIEW_REQUIRED': 'AWAIT_MLR_APPROVAL',
        'NOT_BUSINESS_PRIORITY': 'DEPRIORITIZED',
        'INSUFFICIENT_EVIDENCE': 'INSUFFICIENT_DATA',
    }
    
    if status == 'APPROVED_TRUTH_EXISTS':
        confidence = 0.95
    elif status in ('TRUTH_MISSING', 'NOT_BUSINESS_PRIORITY'):
        confidence = 0.85
    elif status == 'MLR_REVIEW_REQUIRED':
        confidence = 0.70
    else:
        confidence = 0.50
    
    return {
        'signal_instance_id': signal_instance.get('signal_instance_id'),
        'validation_status': status,
        'matched_truth': matched_truth,
        'next_step': next_step_map.get(status, 'INSUFFICIENT_DATA'),
        'confidence': confidence,
    }
