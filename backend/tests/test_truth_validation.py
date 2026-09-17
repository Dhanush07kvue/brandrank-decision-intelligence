"""Tests for truth validation service."""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from app.analytics.truth_validation import (
    check_claim_truth,
    check_content_asset,
    check_prompt_priority,
    validate_signal_truth,
)
from app.services.db import Database


@pytest.fixture()
def con(tmp_path):
    db = Database(tmp_path / 'test.duckdb')
    connection = db.connect()
    yield connection
    connection.close()


def test_check_claim_truth_approved(con):
    """Truth validation returns APPROVED_TRUTH_EXISTS when claim has approved status."""
    con.execute(
        '''insert into claim_truth (claim_id, brand_id, claim_text, approval_status)
           values (?, ?, ?, ?)''',
        ['claim1', 'aveeno', 'Hypoallergenic formulation', 'APPROVED'],
    )
    
    result = check_claim_truth(con, 'Hypoallergenic formulation', 'aveeno')
    assert result['status'] == 'APPROVED_TRUTH_EXISTS'
    assert result['approval_status'] == 'APPROVED'
    assert result['match'] is not None


def test_check_claim_truth_missing(con):
    """Truth validation returns TRUTH_MISSING when no claim found."""
    result = check_claim_truth(con, 'Unknown claim', 'aveeno')
    assert result['status'] == 'TRUTH_MISSING'
    assert result['match'] is None


def test_check_claim_truth_pending_mlr(con):
    """Truth validation returns MLR_REVIEW_REQUIRED for pending claims."""
    con.execute(
        '''insert into claim_truth (claim_id, brand_id, claim_text, approval_status)
           values (?, ?, ?, ?)''',
        ['claim2', 'aveeno', 'SPF protection claim', 'PENDING'],
    )
    
    result = check_claim_truth(con, 'SPF protection claim', 'aveeno')
    assert result['status'] == 'MLR_REVIEW_REQUIRED'
    assert result['approval_status'] == 'PENDING'


def test_check_content_asset_ready(con):
    """Content asset returns APPROVED_TRUTH_EXISTS when ready to publish."""
    con.execute(
        '''insert into content_assets 
           (asset_id, brand_id, canonical_url, readiness_status, approver)
           values (?, ?, ?, ?, ?)''',
        ['asset1', 'aveeno', 'https://aveeno.com/product/page', 'READY_TO_PUBLISH', 'alice@aveeno.com'],
    )
    
    result = check_content_asset(con, 'https://aveeno.com/product/page', 'aveeno')
    assert result['status'] == 'APPROVED_TRUTH_EXISTS'
    assert result['readiness'] == 'READY_TO_PUBLISH'


def test_check_content_asset_missing(con):
    """Content asset returns TRUTH_MISSING when not found."""
    result = check_content_asset(con, 'https://unknown.com/page', 'aveeno')
    assert result['status'] == 'TRUTH_MISSING'
    assert result['match'] is None


def test_check_prompt_priority_hero(con):
    """Prompt priority check returns is_hero=True for hero prompts."""
    con.execute(
        '''insert into prompt_priorities 
           (prompt_id, brand_id, prompt_text, priority_level, is_hero)
           values (?, ?, ?, ?, ?)''',
        ['p1', 'aveeno', 'What is the best lotion for dry skin?', 'HIGH', True],
    )
    
    result = check_prompt_priority(con, 'What is the best lotion for dry skin?', 'aveeno')
    assert result['is_priority'] is True
    assert result['priority_level'] == 'HIGH'
    assert result['is_hero'] is True


def test_check_prompt_priority_not_found(con):
    """Prompt priority check returns False when prompt not marked as priority."""
    result = check_prompt_priority(con, 'Unknown prompt', 'aveeno')
    assert result['is_priority'] is False
    assert result['is_hero'] is False


def test_validate_signal_truth_claim_risk_approved(con):
    """Signal validation routes CLAIM_SUBSTANTIATION_RISK to claim truth check."""
    con.execute(
        '''insert into claim_truth (claim_id, brand_id, claim_text, approval_status)
           values (?, ?, ?, ?)''',
        ['c1', 'aveeno', 'Dermatologist tested', 'APPROVED'],
    )
    
    signal = {
        'signal_instance_id': 'sig1',
        'signal_type': 'CLAIM_SUBSTANTIATION_RISK',
        'group_key': 'Dermatologist tested',
        'brand_id': 'aveeno',
    }
    
    result = validate_signal_truth(con, signal)
    assert result['signal_instance_id'] == 'sig1'
    assert result['validation_status'] == 'APPROVED_TRUTH_EXISTS'
    assert result['next_step'] == 'READY_FOR_INTERVENTION'
    assert result['confidence'] == 0.95


def test_validate_signal_truth_visibility_gap_priority_mismatch(con):
    """Signal validation returns NOT_BUSINESS_PRIORITY when prompt not marked priority."""
    # Prompt is NOT in the priority list
    signal = {
        'signal_instance_id': 'sig2',
        'signal_type': 'VISIBILITY_GAP',
        'group_key': 'random low-priority question',
        'brand_id': 'aveeno',
    }
    
    result = validate_signal_truth(con, signal)
    assert result['validation_status'] == 'NOT_BUSINESS_PRIORITY'
    assert result['next_step'] == 'DEPRIORITIZED'


def test_validate_signal_truth_visibility_gap_with_priority(con):
    """Signal validation checks truth for priority prompts."""
    # Mark prompt as priority
    con.execute(
        '''insert into prompt_priorities 
           (prompt_id, brand_id, prompt_text, priority_level, is_hero)
           values (?, ?, ?, ?, ?)''',
        ['p1', 'aveeno', 'Is Aveeno good for eczema?', 'HIGH', True],
    )
    
    # But no approved truth exists for the claim yet
    signal = {
        'signal_instance_id': 'sig3',
        'signal_type': 'VISIBILITY_GAP',
        'group_key': 'Is Aveeno good for eczema?',
        'brand_id': 'aveeno',
    }
    
    result = validate_signal_truth(con, signal)
    assert result['validation_status'] == 'TRUTH_MISSING'
    assert result['next_step'] == 'REQUEST_TRUTH_CREATION'
    assert result['confidence'] == 0.85


def test_validate_signal_truth_readiness(con):
    """Signal validation routes READINESS_DETERIORATION to content asset check."""
    con.execute(
        '''insert into content_assets 
           (asset_id, brand_id, canonical_url, readiness_status, approver)
           values (?, ?, ?, ?, ?)''',
        ['a1', 'aveeno', 'https://aveeno.com/skincare/eczema', 'READY_TO_PUBLISH', 'bob'],
    )
    
    signal = {
        'signal_instance_id': 'sig4',
        'signal_type': 'READINESS_DETERIORATION',
        'group_key': 'https://aveeno.com/skincare/eczema',
        'brand_id': 'aveeno',
    }
    
    result = validate_signal_truth(con, signal)
    assert result['validation_status'] == 'APPROVED_TRUTH_EXISTS'
    assert result['next_step'] == 'READY_FOR_INTERVENTION'


def test_validate_signal_truth_unknown_type(con):
    """Signal validation returns INSUFFICIENT_EVIDENCE for unknown signal types."""
    signal = {
        'signal_instance_id': 'sig5',
        'signal_type': 'UNKNOWN_TYPE',
        'group_key': 'something',
        'brand_id': 'aveeno',
    }
    
    result = validate_signal_truth(con, signal)
    assert result['validation_status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['next_step'] == 'INSUFFICIENT_DATA'
