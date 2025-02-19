from pathlib import Path
import os
import io
import requests
import zipfile


class DataProvider:
    def __init__(self, root_path, base_path):
        self.root_path = Path(root_path)
        self.base_path = root_path / base_path

    def ensure_data_path(self, path):
        data_path = self.base_path / path
        if not data_path.exists():
            raise FileNotFoundError(f"The path {data_path} does not exist.")
        return data_path

    def cleanup(self):
        return True


class BuiltinDataProvider(DataProvider):
    def __init__(self):
        super().__init__(Path(__file__).parent.parent.parent, "data/builtin")


class DownloadDataProvider(DataProvider):
    def __init__(self, uri, base_path):
        super().__init__(Path(__file__).parent.parent.parent, "data" / base_path)
        self.uri = uri
        self.loaded = False

    def ensure_data_path(self, path):
        if not self.loaded:
            self.download()
        return super().ensure_data_path(path)

    def cleanup(self):
        if self.loaded:
            os.remove(self.base_path)
        return True


class DownloadZIPDataProvider(DownloadDataProvider):

    def download(self):
        req = requests.get(self.uri)
        zip = zipfile.ZipFile(io.BytesIO(req.content))
        zip.extractall(self.base_path)
        self.loaded = True
