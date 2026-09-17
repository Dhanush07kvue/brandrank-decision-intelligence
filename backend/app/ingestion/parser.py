from __future__ import annotations

import csv
import io
import json
import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass
class ParseResult:
    delimiter: str
    encoding: str
    headers: list[str]
    rows: list[dict[str, str]]
    rejected_rows: list[tuple[int, str, dict[str, Any]]]


def _decode_bytes(data: bytes) -> tuple[str, str]:
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1', errors='replace'), 'latin-1-replace'


def _detect_delimiter(sample: str) -> str:
    candidates = [',', '\t', ';', '|']
    counts = {c: sample.count(c) for c in candidates}
    return max(counts, key=counts.get) if any(counts.values()) else ','


def parse_delimited_bytes(data: bytes, filename: str) -> ParseResult:
    text, encoding = _decode_bytes(data)
    delimiter = '\t' if filename.lower().endswith('.tsv') else _detect_delimiter(text[:4096])

    stream = io.StringIO(text, newline='')
    reader = csv.DictReader(stream, delimiter=delimiter, quotechar='"', escapechar='\\')

    headers = [h.strip() if h else '' for h in (reader.fieldnames or [])]
    rows: list[dict[str, str]] = []
    rejected_rows: list[tuple[int, str, dict[str, Any]]] = []

    for idx, row in enumerate(reader, start=2):
        if row is None:
            rejected_rows.append((idx, 'empty_row', {}))
            continue
        if any(k is None for k in row.keys()):
            rejected_rows.append((idx, 'ragged_row', row))
            continue
        normalized = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        rows.append(normalized)

    return ParseResult(
        delimiter=delimiter,
        encoding=encoding,
        headers=headers,
        rows=rows,
        rejected_rows=rejected_rows,
    )


def row_hash(row: dict[str, Any]) -> str:
    packed = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(packed.encode('utf-8')).hexdigest()
