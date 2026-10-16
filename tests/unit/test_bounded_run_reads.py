"""Performance change must preserve bounded reads and all JSON rejection rules."""

import io
from pathlib import Path

import pytest

from mn_land import runs


@pytest.mark.parametrize("body,limit", [
    (b"", 0), (b"", 10), (b"abc", 3), (b"a" * 65536, 65536),
    (b"a" * 65537, 65537), (b"a" * 150000, 200000),
], ids=["empty-zero", "empty", "exact-small", "exact-chunk", "over-chunk", "multi-chunk"])
def test_bounded_chunks_return_exact_original_bytes(tmp_path, body, limit):
    path = tmp_path / "bytes.json"
    path.write_bytes(body)
    assert runs._read_bytes(path, limit) == body


@pytest.mark.parametrize("limit", [0, 3, 65535, 65536, 150000])
def test_over_budget_still_rejected(tmp_path, limit):
    path = tmp_path / "large.json"
    path.write_bytes(b"a" * (limit + 1))
    with pytest.raises(runs.RunValidationError, match="exceeds read budget"):
        runs._read_bytes(path, limit)


@pytest.mark.parametrize("short_reads", [False, True])
def test_read_requests_are_small_and_never_trust_initial_file_size(monkeypatch, short_reads):
    requests = []

    class Stream(io.BytesIO):
        def read(self, size=-1):
            requests.append(size)
            assert 0 < size <= 65536
            return super().read(min(size, 7) if short_reads else size)

    body = b"a" * 150001
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: Stream(body))
    # No stat-sized allocation or assumed EOF: keep reading to the real limit.
    monkeypatch.setattr(Path, "stat", lambda *args, **kwargs: pytest.fail("Do not trust stat"))
    with pytest.raises(runs.RunValidationError, match="exceeds read budget"):
        runs._read_bytes(Path("growing.json"), len(body) - 1)
    assert len(requests) > 1


@pytest.mark.parametrize("body", [b'{"x":1,"x":2}', b'{"broken":', b'\xff'],
                         ids=["duplicate", "malformed", "encoding"])
def test_json_duplicate_malformed_and_encoding_checks_still_run(tmp_path, body):
    path = tmp_path / "bad.json"
    path.write_bytes(body)
    with pytest.raises(runs.RunValidationError):
        runs.read_json(path)
