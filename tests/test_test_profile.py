"""Unit tests for osc_validation.test_profile."""

import textwrap
from pathlib import Path

import pytest

from osc_validation.test_profile import XFailEntry, Profile, load_test_profile


# ---------------------------------------------------------------------------
# XFailEntry.matches
# ---------------------------------------------------------------------------


def test_xfail_entry_exact_match():
    entry = XFailEntry(test="validation/scenario/foo.py::test_bar", reason="r")
    assert entry.matches("validation/scenario/foo.py::test_bar")


def test_xfail_entry_unparameterized_node_id_matches_parameterized_item():
    entry = XFailEntry(test="validation/scenario/foo.py::test_bar", reason="r")
    assert entry.matches("validation/scenario/foo.py::test_bar[data-set-1]")


def test_xfail_entry_no_match():
    entry = XFailEntry(test="validation/scenario/foo.py::test_bar", reason="r")
    assert not entry.matches("validation/scenario/foo.py::test_other")


def test_xfail_entry_glob_filename():
    entry = XFailEntry(
        test="validation/scenario/sequencing/val_split_*.py::*", reason="r"
    )
    assert entry.matches(
        "validation/scenario/sequencing/val_split_trajectory.py::test_something"
    )
    assert not entry.matches(
        "validation/scenario/trajectories/val_simple_trajectories.py::test_something"
    )


def test_xfail_entry_glob_wildcard_test():
    entry = XFailEntry(test="validation/scenario/foo.py::*", reason="r")
    assert entry.matches("validation/scenario/foo.py::test_a")
    assert entry.matches("validation/scenario/foo.py::test_b")
    assert not entry.matches("validation/scenario/bar.py::test_a")


def test_xfail_entry_strict_default():
    entry = XFailEntry(test="*", reason="r")
    assert entry.strict is False


# ---------------------------------------------------------------------------
# TestProfile.xfail_for
# ---------------------------------------------------------------------------


def test_test_profile_returns_first_match():
    profile = Profile(
        xfails=[
            XFailEntry(test="a/b.py::test_1", reason="first"),
            XFailEntry(test="a/b.py::*", reason="second"),
        ]
    )
    result = profile.xfail_for("a/b.py::test_1")
    assert result is not None
    assert result.reason == "first"


def test_test_profile_returns_none_when_no_match():
    profile = Profile(
        xfails=[
            XFailEntry(test="a/b.py::test_x", reason="r"),
        ]
    )
    assert profile.xfail_for("a/b.py::test_y") is None


def test_test_profile_empty():
    profile = Profile()
    assert profile.xfail_for("anything") is None


# ---------------------------------------------------------------------------
# load_test_profile
# ---------------------------------------------------------------------------


def _write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "profile.toml"
    p.write_text(textwrap.dedent(content))
    return p


def test_load_valid_profile(tmp_path):
    path = _write_toml(
        tmp_path,
        """\
        [[xfail]]
        test = "validation/scenario/foo.py::test_bar"
        reason = "Not supported"

        [[xfail]]
        test = "validation/scenario/seq/*.py::*"
        reason = "Known bug"
        strict = true
    """,
    )
    profile = load_test_profile(path)
    assert len(profile.xfails) == 2
    assert profile.xfails[0].test == "validation/scenario/foo.py::test_bar"
    assert profile.xfails[0].reason == "Not supported"
    assert profile.xfails[0].strict is False
    assert profile.xfails[1].strict is True


def test_load_empty_profile(tmp_path):
    path = _write_toml(tmp_path, "")
    profile = load_test_profile(path)
    assert profile.xfails == []


def test_load_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_test_profile(tmp_path / "nonexistent.toml")


def test_load_malformed_toml(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text("[[xfail]\ntest = unterminated")
    with pytest.raises(ValueError, match="Malformed test profile TOML"):
        load_test_profile(path)


def test_load_missing_test_field(tmp_path):
    path = _write_toml(
        tmp_path,
        """\
        [[xfail]]
        reason = "forgot the test field"
    """,
    )
    with pytest.raises(ValueError, match="missing required field 'test'"):
        load_test_profile(path)


def test_load_missing_reason_field(tmp_path):
    path = _write_toml(
        tmp_path,
        """\
        [[xfail]]
        test = "validation/scenario/foo.py::test_bar"
    """,
    )
    with pytest.raises(ValueError, match="missing required field 'reason'"):
        load_test_profile(path)


def test_load_accepts_string_path(tmp_path):
    path = _write_toml(
        tmp_path,
        """\
        [[xfail]]
        test = "a.py::t"
        reason = "r"
    """,
    )
    profile = load_test_profile(str(path))
    assert len(profile.xfails) == 1
