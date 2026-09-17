from pathlib import Path
import zipfile
import io

from app.ingestion.discovery import discover_files
from app.ingestion.parser import parse_delimited_bytes


def test_multiline_csv_parse():
    payload = b'col1,col2\n"hello\nworld",42\n'
    parsed = parse_delimited_bytes(payload, 'x.csv')
    assert len(parsed.rows) == 1
    assert parsed.rows[0]['col1'] == 'hello\nworld'


def test_nested_zip_discovery(tmp_path: Path):
    inner_csv = b'a,b\n1,2\n'
    inner_zip_bytes = io.BytesIO()
    with zipfile.ZipFile(inner_zip_bytes, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('inner.csv', inner_csv)

    outer = tmp_path / 'outer.zip'
    with zipfile.ZipFile(outer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('nested.zip', inner_zip_bytes.getvalue())

    files = discover_files(tmp_path)
    assert len(files) == 1
    assert files[0].logical_name == 'inner.csv'


def test_encoding_fallback_latin1():
    payload = 'café,1\n'.encode('latin-1')
    parsed = parse_delimited_bytes(payload, 'x.csv')
    assert parsed.encoding.startswith('latin-1') or parsed.encoding == 'utf-8-sig'
