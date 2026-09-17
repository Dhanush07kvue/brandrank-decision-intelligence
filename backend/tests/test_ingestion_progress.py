import pytest

from app.ingestion.pipeline import run_ingestion
from app.models.schemas import IngestionProgressRecord
from app.services.db import Database


def test_completed_ingestion_progress_accepts_pipeline_summary_shape():
    progress = IngestionProgressRecord(
        job_id='ingest_test',
        status='COMPLETED',
        total_files=10,
        processed_files=10,
        percentage=100,
        stage='Ingestion complete',
        summary={
            'run_id': 'run_test',
            'physical_files': 10,
            'unique_payloads': 9,
            'total_rows': 100,
            'parsed_rows': 98,
            'rejected_rows': 2,
            'empty_files': 1,
            'duplicate_files': 1,
            'quarantined_files': 0,
            'archive_entries_discovered': 0,
        },
    )
    assert progress.summary is not None
    assert progress.summary.empty_files == 1
    assert progress.summary.duplicate_files == 1


def test_reingestion_requires_override_and_override_creates_new_run(tmp_path):
    input_dir = tmp_path / 'input'
    output_dir = tmp_path / 'output'
    input_dir.mkdir()
    (input_dir / 'aveeno_visibility.csv').write_text('rowType,searchTerm,brandName,rank\nranking,eczema,Aveeno,0.2\n', encoding='utf-8')
    db = Database(tmp_path / 'test.duckdb')
    first = run_ingestion(input_dir, db, output_dir)
    assert first.physical_files == 1
    with pytest.raises(RuntimeError, match='Existing input payloads'):
        run_ingestion(input_dir, db, output_dir, guard_existing=True)
    second = run_ingestion(input_dir, db, output_dir, guard_existing=True, override_existing=True)
    assert second.run_id != first.run_id
