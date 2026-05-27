"""Tests for the process-global lookup-file cache."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pdf_cmap_fix import tounicode_core


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    tounicode_core._LOOKUP_FILE_CACHE.clear()
    yield
    tounicode_core._LOOKUP_FILE_CACHE.clear()


def _write_lookup(tmp_path: Path, gid_to_uni: dict[int, str]) -> Path:
    payload = {
        "_meta": {"lookup_kind": "gid"},
        "myfont": {str(g): u for g, u in gid_to_uni.items()},
    }
    p = tmp_path / "myfont.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_cache_hit_avoids_re_reading_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _write_lookup(tmp_path, {16: "A", 17: "B"})

    calls: list[Path] = []
    real = tounicode_core._load_lookup_file

    def counting(path: Path) -> Any:
        calls.append(Path(path))
        return real(path)

    monkeypatch.setattr(tounicode_core, "_load_lookup_file", counting)

    a = tounicode_core._load_lookup_file_cached(p)
    b = tounicode_core._load_lookup_file_cached(p)
    c = tounicode_core._load_lookup_file_cached(p)
    assert a == b == c
    assert len(calls) == 1, "second/third call should hit the cache"
    assert a is not None
    assert a[0] == "gid"
    assert a[1] == {"16": "A", "17": "B"}


def test_cache_invalidates_on_mtime_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _write_lookup(tmp_path, {1: "X"})
    first = tounicode_core._load_lookup_file_cached(p)
    assert first is not None and first[1] == {"1": "X"}

    # Rewrite with new content and bump mtime so the cache key invalidates.
    p.write_text(
        json.dumps({"_meta": {"lookup_kind": "gid"}, "myfont": {"1": "Y"}}),
        encoding="utf-8",
    )
    import os
    new_mtime = p.stat().st_mtime + 5
    os.utime(p, (new_mtime, new_mtime))

    second = tounicode_core._load_lookup_file_cached(p)
    assert second is not None and second[1] == {"1": "Y"}


def test_cache_falls_back_when_path_unstattable(monkeypatch: pytest.MonkeyPatch) -> None:
    # If stat() fails we just call through to _load_lookup_file each time
    # (no cache key to use). Confirm that path is exercised cleanly.
    fake = Path("/nonexistent/myfont.json")
    out = tounicode_core._load_lookup_file_cached(fake)
    assert out is None
