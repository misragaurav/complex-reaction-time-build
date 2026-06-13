"""CSV/ZIP export helpers (FR-57)."""

from __future__ import annotations

import csv
import datetime
import io
import re
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("_", name.strip().lower()).strip("_")
    return slug or "study"


def csv_filename(study_name: str, scope: str, ext: str = "csv") -> str:
    """`{study_name_slug}_{scope}_{YYYYMMDD-HHMM}.csv|zip` per FR-57."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M")
    return f"{slugify(study_name)}_{scope}_{timestamp}.{ext}"


def build_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """RFC 4180 CSV with header row, comma-separated, empty string for None (FR-57)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return buf.getvalue()


def iso_utc(dt: datetime.datetime | None) -> str:
    """ISO-8601 UTC timestamp (ends in `+00:00`), empty string for None (FR-57)."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).isoformat()


def content_disposition(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def build_zip(files: Mapping[str, str]) -> bytes:
    """Build a ZIP archive of named UTF-8 text files (FR-55)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()
