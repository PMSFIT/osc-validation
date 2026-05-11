"""Test profile support for the OSC validation suite.

A test profile is a TOML file that declares per-run test expectations (e.g.
expected failures) without modifying the validation suite itself. It is
intended to be authored and maintained by tool CI pipelines and passed via the
``--test-profile`` pytest option.

Example profile file::

    [[xfail]]
    test = "validation/scenario/triggers/val_condition_delay.py::test_foo"
    reason = "ConditionDelay not supported in this version"

    [[xfail]]
    test = "validation/scenario/sequencing/val_split_*.py::*"
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

    def matches(self, node_id: str) -> bool:
        """Return True if *node_id* matches this entry's test pattern."""
        return fnmatch(node_id, self.test)


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
        xfails.append(
            XFailEntry(
                test=entry["test"],
                reason=entry["reason"],
                strict=entry.get("strict", False),
            )
        )

    return Profile(xfails=xfails)
