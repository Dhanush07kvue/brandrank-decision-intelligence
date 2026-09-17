from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import io
import zipfile


CSV_EXTS = {'.csv', '.tsv'}
ARCHIVE_EXTS = {'.zip'}


@dataclass
class DiscoveredFile:
    physical_path: Path
    archive_chain: str
    logical_name: str
    bytes_data: bytes
    archive_entries_discovered: int = 0

    @property
    def file_id(self) -> str:
        key = f"{self.physical_path}|{self.archive_chain}|{self.logical_name}".encode('utf-8')
        return hashlib.sha256(key).hexdigest()[:24]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.bytes_data).hexdigest()


def _iter_zip_bytes(data: bytes, chain: list[str]) -> list[tuple[list[str], str, bytes]]:
    out: list[tuple[list[str], str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            blob = zf.read(info)
            suffix = Path(name).suffix.lower()
            next_chain = [*chain, name]
            if suffix in CSV_EXTS:
                out.append((chain, name, blob))
            elif suffix in ARCHIVE_EXTS:
                out.extend(_iter_zip_bytes(blob, next_chain))
    return out


def _count_archive_entries(data: bytes) -> int:
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            count += 1
            if Path(info.filename).suffix.lower() in ARCHIVE_EXTS:
                count += _count_archive_entries(zf.read(info))
    return count


def discover_files(root: Path) -> list[DiscoveredFile]:
    files: list[DiscoveredFile] = []
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        # avoid scanning generated outputs
        if 'brand-activation-intelligence/data/' in str(p).replace('\\', '/'):
            continue
        suffix = p.suffix.lower()
        if suffix in CSV_EXTS:
            files.append(
                DiscoveredFile(
                    physical_path=p,
                    archive_chain='',
                    logical_name=p.name,
                    bytes_data=p.read_bytes(),
                )
            )
        elif suffix in ARCHIVE_EXTS:
            archive_bytes = p.read_bytes()
            archive_count = _count_archive_entries(archive_bytes)
            for chain, name, blob in _iter_zip_bytes(archive_bytes, [p.name]):
                files.append(
                    DiscoveredFile(
                        physical_path=p,
                        archive_chain=' > '.join(chain),
                        logical_name=name,
                        bytes_data=blob,
                        archive_entries_discovered=archive_count,
                    )
                )
    return files
