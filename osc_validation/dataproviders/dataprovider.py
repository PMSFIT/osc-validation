from pathlib import Path
import io
import requests
import zipfile
import shutil

from urllib.parse import urlparse


class DataProvider:
    def __init__(self, root_path: str | Path, base_path: str | Path):
        self.root_path = Path(root_path)
        self.base_path = self.root_path / base_path

    def ensure_base_path(self):
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)
        return self.base_path

    def ensure_data_path(self, path: str | Path):
        data_path = self.base_path / path
        if not data_path.exists():
            raise FileNotFoundError(f"The path {data_path} does not exist.")
        return data_path

    def cleanup(self):
        return True


class BuiltinDataProvider(DataProvider):
    def __init__(self):
        super().__init__(Path(__file__).parent.parent.parent, "data/builtin")


class BaseDownloadDataProvider(DataProvider):
    def __init__(self, uri: str, base_path: str | Path, force_download: bool = True):
        super().__init__(Path(__file__).parent.parent.parent, Path("data") / base_path)

        self.uri = uri
        self.force_download = force_download
        self.loaded = False

    def ensure_data_path(self, path: str | Path):
        self.ensure_base_path()
        if not self.loaded:
            self.download()
        return super().ensure_data_path(path)

    def cleanup(self):
        try:
            if self.base_path.exists():
                shutil.rmtree(self.base_path)
        except Exception as e:
            print(f"Cleanup failed: {e}")
        return True

    def download(self):
        raise NotImplementedError


class DownloadDataProvider(BaseDownloadDataProvider):
    def __init__(self, uri: str, base_path: str | Path, force_download: bool = True):
        super().__init__(uri, base_path, force_download)

        self.filename = Path(
            urlparse(self.uri).path
        ).name  # does not support indirect uri's
        self.file_path = self.base_path / self.filename
        self.loaded = False if self.force_download else self.file_path.exists()

    def download(self):
        self.ensure_base_path()

        tmp_file = self.base_path / (self.filename + ".tmp")
        try:
            with requests.get(self.uri, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(tmp_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            tmp_file.replace(self.file_path)
            self.loaded = True
        finally:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)


class DownloadZIPDataProvider(DownloadDataProvider):
    def __init__(self, uri: str, base_path: str | Path, force_download: bool = True):
        super().__init__(uri, base_path, force_download)
        self.loaded = False if self.force_download else any(self.base_path.iterdir())

    def download(self):
        req = requests.get(self.uri)
        zip = zipfile.ZipFile(io.BytesIO(req.content))
        zip.extractall(self.base_path)
        self.loaded = True
