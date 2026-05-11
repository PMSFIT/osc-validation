import pathlib

import pytest


@pytest.fixture(scope="session")
def builtin_data_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent / "data" / "builtin"
