import io
from pathlib import Path
import zipfile

import pytest

from osc_validation.dataproviders.dataprovider import (
    BuiltinDataProvider,
    DataProvider,
    DownloadDataProvider,
    DownloadZIPDataProvider,
)


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content


def test_data_provider_raises_for_missing_path(tmp_path):
    provider = DataProvider(tmp_path, "base")
    provider.ensure_base_path()

    with pytest.raises(FileNotFoundError, match="does not exist"):
        provider.ensure_data_path("missing.txt")


def test_builtin_data_provider_resolves_known_builtin_trace(tmp_path):
    fake_file = tmp_path / "simple_trajectories" / "trace.mcap"
    fake_file.parent.mkdir()
    fake_file.touch()

    provider = BuiltinDataProvider(tmp_path)
    resolved = provider.ensure_data_path("simple_trajectories/trace.mcap")

    assert resolved.exists()
    assert resolved.name == "trace.mcap"


def test_download_data_provider_skips_download_when_cached(tmp_path, monkeypatch):
    base = tmp_path / "download"
    provider = DownloadDataProvider(
        uri="https://example.com/file.txt",
        base_path=base,
        force_download=False,
    )
    provider.base_path.mkdir(parents=True, exist_ok=True)
    provider.file_path.write_text("cached", encoding="utf-8")
    provider.loaded = True

    def _unexpected_download(*args, **kwargs):
        raise AssertionError("download should not be called for cached file")

    monkeypatch.setattr(provider, "download", _unexpected_download)

    assert provider.ensure_data_path("file.txt") == provider.file_path


def test_download_zip_data_provider_extracts_archive(tmp_path, monkeypatch):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("nested/file.txt", "payload")

    monkeypatch.setattr(
        "osc_validation.dataproviders.dataprovider.requests.get",
        lambda uri: _FakeResponse(archive.getvalue()),
    )

    provider = DownloadZIPDataProvider(
        uri="https://example.com/archive.zip",
        base_path=tmp_path / "zip",
    )

    extracted = provider.ensure_data_path("nested/file.txt")

    assert extracted.read_text(encoding="utf-8") == "payload"
    assert provider.loaded is True
    provider.cleanup()
    assert not provider.base_path.exists()
