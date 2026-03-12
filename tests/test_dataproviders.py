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


class _FakeStreamingResponse:
    def __init__(self, content: bytes):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        for start in range(0, len(self._content), chunk_size):
            yield self._content[start : start + chunk_size]


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content


def test_data_provider_raises_for_missing_path(tmp_path):
    provider = DataProvider(tmp_path, "base")
    provider.ensure_base_path()

    with pytest.raises(FileNotFoundError, match="does not exist"):
        provider.ensure_data_path("missing.txt")


def test_builtin_data_provider_resolves_known_builtin_trace():
    provider = BuiltinDataProvider()
    trace_path = provider.ensure_data_path(
        "simple_trajectories/20240603T152322.095000Z_sv_370_3200_618_dronetracker_135_swerve.mcap"
    )

    assert trace_path.exists()
    assert trace_path.name.endswith(".mcap")


def test_download_data_provider_downloads_file_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "osc_validation.dataproviders.dataprovider.requests.get",
        lambda uri, stream=True, timeout=30: _FakeStreamingResponse(b"payload"),
    )

    provider = DownloadDataProvider(
        uri="https://example.com/file.txt",
        base_path="download/test",
    )
    provider.root_path = tmp_path
    provider.base_path = tmp_path / "download"
    provider.file_path = provider.base_path / provider.filename

    path = provider.ensure_data_path("file.txt")

    assert path.read_bytes() == b"payload"
    assert provider.loaded is True
    assert provider.cleanup() is True
    assert not provider.base_path.exists()


def test_download_data_provider_skips_download_when_cached(tmp_path, monkeypatch):
    provider = DownloadDataProvider(
        uri="https://example.com/file.txt",
        base_path="download/test",
        force_download=False,
    )
    provider.root_path = tmp_path
    provider.base_path = tmp_path / "download"
    provider.base_path.mkdir(parents=True, exist_ok=True)
    provider.file_path = provider.base_path / provider.filename
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
        base_path="download/zip",
    )
    provider.root_path = tmp_path
    provider.base_path = tmp_path / "zip"
    provider.file_path = provider.base_path / provider.filename

    extracted = provider.ensure_data_path("nested/file.txt")

    assert extracted.read_text(encoding="utf-8") == "payload"
    assert provider.loaded is True
    provider.cleanup()
    assert not provider.base_path.exists()
