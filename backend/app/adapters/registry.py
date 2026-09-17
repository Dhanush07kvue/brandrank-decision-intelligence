from __future__ import annotations

from typing import Iterable

from app.ingestion.contracts import classify_contract


def normalize_headers(headers: Iterable[str]) -> tuple[str, ...]:
    return tuple(h.strip().lower() for h in headers if h is not None and h.strip())


def fingerprint(headers: Iterable[str]) -> str:
    return '|'.join(normalize_headers(headers))


def classify_schema(headers: Iterable[str], filename: str) -> tuple[str, str, str]:
    _ = filename
    match = classify_contract(list(headers))
    if match.status == 'MATCHED' and match.contract is not None:
        adapter_name = f"{match.contract.contract_id.lower()}_adapter"
        return match.contract.schema_family, adapter_name, match.contract.version
    return 'unsupported_schema', 'unknown_adapter', '0.0.0'
