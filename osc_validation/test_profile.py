"""Test profile support for the OSC validation suite.

A test profile is a TOML file that declares per-run test expectations (e.g.
expected failures) without modifying the validation suite itself. It is
intended to be authored and maintained by tool CI pipelines and passed via the
``--test-profile`` pytest option.

Example profile file::

    [[xfail]]
    test = "scenario/triggers/val_condition_delay.py::test_foo"
    reason = "ConditionDelay not supported in this version"

    [[xfail]]
    test = "scenario/sequencing/val_split_*.py::*"
    reason = "Sequencing not implemented"
    strict = true
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class XFailEntry:
    """A single expected-failure declaration from a test profile."""

    test: str
    reason: str
    strict: bool = False
    except_patterns: list[str] = field(default_factory=list)

    def matches(self, node_id: str) -> bool:
        """Return True if *node_id* matches this entry's test pattern."""
        return _matches_node_id_pattern(node_id, self.test) and not any(
            _matches_except_pattern(node_id, pattern) for pattern in self.except_patterns
        )


def _matches_node_id_pattern(node_id: str, pattern: str) -> bool:
    """Return True if *node_id* matches a full pytest node ID pattern."""
    return (
        node_id == pattern
        or _unparameterized_node_id(node_id) == pattern
        or fnmatch(node_id, pattern)
        or fnmatch(node_id, _escape_parameter_bracket_glob(pattern))
    )


def _parameter_id(node_id: str) -> str | None:
    """Return the trailing pytest parameter ID, if present."""
    if not node_id.endswith("]"):
        return None
    base_node_id, separator, parameter_id = node_id.rpartition("[")
    if separator and "::" in base_node_id:
        return parameter_id[:-1]
    return None


def _matches_except_pattern(node_id: str, pattern: str) -> bool:
    """Return True if *pattern* exempts *node_id* from an xfail entry."""
    if "::" in pattern:
        return _matches_node_id_pattern(node_id, pattern)

    parameter_id = _parameter_id(node_id)
    return parameter_id is not None and fnmatch(parameter_id, pattern)


def _unparameterized_node_id(node_id: str) -> str:
    """Return the base test node ID without a trailing pytest parameter suffix."""
    if not node_id.endswith("]"):
        return node_id
    base_node_id, separator, _ = node_id.rpartition("[")
    if separator and "::" in base_node_id:
        return base_node_id
    return node_id


def _escape_parameter_bracket_glob(pattern: str) -> str:
    """Escape pytest's parameter ``[`` suffix for fnmatch patterns."""
    if not pattern.endswith("]"):
        return pattern
    base_pattern, separator, parameters = pattern.rpartition("[")
    if separator and "::" in base_pattern:
        return f"{base_pattern}[[]{parameters}"
    return pattern


@dataclass
class Profile:
    """Parsed representation of a test profile TOML file."""

    xfails: list[XFailEntry] = field(default_factory=list)

    def xfail_for(self, node_id: str) -> XFailEntry | None:
        """Return the first matching XFailEntry for *node_id*, or None."""
        for entry in self.xfails:
            if entry.matches(node_id):
                return entry
        return None


def load_test_profile(path: str | Path) -> Profile:
    """Load a test profile from a TOML file at *path*.

    Raises:
        FileNotFoundError: if *path* does not exist.
        ValueError: if the TOML is malformed or fails schema validation.
    """
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Malformed test profile TOML at '{path}': {exc}") from exc

    xfails = []
    for i, entry in enumerate(data.get("xfail", [])):
        if "test" not in entry:
            raise ValueError(
                f"xfail entry {i} in '{path}' is missing required field 'test'"
            )
        if "reason" not in entry:
            raise ValueError(
                f"xfail entry {i} in '{path}' is missing required field 'reason'"
            )
        except_patterns = entry.get("except", [])
        if not isinstance(except_patterns, list) or not all(
            isinstance(pattern, str) for pattern in except_patterns
        ):
            raise ValueError(
                f"xfail entry {i} in '{path}' field 'except' must be a list of strings"
            )
        xfails.append(
            XFailEntry(
                test=entry["test"],
                reason=entry["reason"],
                strict=entry.get("strict", False),
                except_patterns=except_patterns,
            )
        )

    return Profile(xfails=xfails)
