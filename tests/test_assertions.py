from pathlib import Path

import pytest

from osc_validation.assertions import make_assert_osi_compliance


class _FakeCheckResult:
    def __init__(self, passed=True, summary="QC summary"):
        self.passed = passed
        self.summary = summary


class _FakeChecker:
    instances = []

    def __init__(self, osi_version=None, ruleset=None):
        self.osi_version = osi_version
        self.ruleset = ruleset
        self.calls = []
        self.result = _FakeCheckResult()
        self.instances.append(self)

    def run(self, channel_spec, result_file=None, output_config=None):
        self.calls.append(
            {
                "channel_spec": channel_spec,
                "result_file": result_file,
                "output_config": output_config,
            }
        )
        return self.result


@pytest.fixture(autouse=True)
def _reset_fake_checker():
    _FakeChecker.instances = []


def test_assert_osi_compliance_noops_when_disabled():
    assert_osi_compliance = make_assert_osi_compliance(
        qc_enabled=False,
        checker_cls=_FakeChecker,
    )

    assert_osi_compliance(object())

    assert _FakeChecker.instances == []


def test_assert_osi_compliance_uses_cli_defaults_when_enabled():
    assert_osi_compliance = make_assert_osi_compliance(
        qc_enabled=True,
        default_osi_version="3.7.0",
        default_ruleset="rules.yml",
        checker_cls=_FakeChecker,
    )

    channel_spec = object()
    result_file = Path("result.xqar")
    output_config = Path("config.xml")
    assert_osi_compliance(
        channel_spec,
        result_file=result_file,
        output_config=output_config,
    )

    checker = _FakeChecker.instances[0]
    assert checker.osi_version == "3.7.0"
    assert checker.ruleset == Path("rules.yml")
    assert checker.calls == [
        {
            "channel_spec": channel_spec,
            "result_file": result_file,
            "output_config": output_config,
        }
    ]


def test_assert_osi_compliance_call_options_override_cli_defaults():
    assert_osi_compliance = make_assert_osi_compliance(
        qc_enabled=True,
        default_osi_version="3.6.0",
        default_ruleset="default.yml",
        checker_cls=_FakeChecker,
    )

    assert_osi_compliance(
        object(),
        osi_version="3.7.0",
        ruleset=Path("override.yml"),
    )

    checker = _FakeChecker.instances[0]
    assert checker.osi_version == "3.7.0"
    assert checker.ruleset == Path("override.yml")


def test_assert_osi_compliance_fails_when_qc_fails():
    class _FailingChecker(_FakeChecker):
        def __init__(self, osi_version=None, ruleset=None):
            super().__init__(osi_version=osi_version, ruleset=ruleset)
            self.result = _FakeCheckResult(
                passed=False,
                summary="QC OSI trace check failed.\n- deserialization: issue",
            )

    assert_osi_compliance = make_assert_osi_compliance(
        qc_enabled=True,
        checker_cls=_FailingChecker,
    )

    with pytest.raises(AssertionError, match="deserialization: issue"):
        assert_osi_compliance(object())


def test_assert_osi_compliance_supports_legacy_boolean_checker():
    class _FakeLegacyChecker:
        def __init__(self, osi_version=None, ruleset=None):
            self.osi_version = osi_version
            self.ruleset = ruleset

        def check(self, channel_spec, result_file=None, output_config=None):
            return False

    assert_osi_compliance = make_assert_osi_compliance(
        qc_enabled=True,
        checker_cls=_FakeLegacyChecker,
    )

    with pytest.raises(AssertionError, match="QC OSI trace check failed"):
        assert_osi_compliance(object())
