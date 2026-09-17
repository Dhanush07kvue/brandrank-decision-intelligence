from pathlib import Path

from app.ingestion.pipeline import run_ingestion
from app.services.db import Database


def test_duplicate_payload_not_double_counted(tmp_path: Path):
    src = tmp_path / 'input'
    src.mkdir()
    payload = 'a,b\n1,2\n'
    (src / 'x1.csv').write_text(payload)
    (src / 'x2.csv').write_text(payload)

    db = Database(tmp_path / 'test.duckdb')
    out = tmp_path / 'out'
    summary = run_ingestion(src, db, out)

    assert summary.physical_files == 2
    assert summary.unique_payloads == 1
    assert summary.duplicate_files == 1


def test_unknown_non_empty_schema_quarantined(tmp_path: Path):
    src = tmp_path / 'input'
    src.mkdir()
    (src / 'unknown.csv').write_text('foo,bar\n1,2\n')

    db = Database(tmp_path / 'test2.duckdb')
    out = tmp_path / 'out'
    summary = run_ingestion(src, db, out)

    assert summary.quarantined_files == 1
