from pathlib import Path

from osc_validation.metrics.qccheck import _format_qc_result_summary


class _FakeChannelSpec:
    path = Path("trace.osi")


CHECKER_ID = "qc.test.checker"


class _FakeIssue:
    level = "ERROR"
    issue_id = "issue-1"
    rule_uid = "rule-1"
    description = "trace has an invalid OSI header"


class _FakeChecker:
    checker_id = CHECKER_ID
    status = "COMPLETED"
    issues = [_FakeIssue()]


class _FakeResult:
    def get_checker_results(self, bundle_name):
        return [_FakeChecker()]


def test_format_qc_result_summary_includes_checker_details_and_artifacts():
    summary = _format_qc_result_summary(
        result=_FakeResult(),
        channel_spec=_FakeChannelSpec(),
        result_file=Path("qc_result.xqar"),
        output_config=Path("qc_config.xml"),
    )

    assert "QC OSI trace check failed." in summary
    assert "Trace: trace.osi" in summary
    assert "Result file: qc_result.xqar" in summary
    assert "Output config: qc_config.xml" in summary
    assert f"- {CHECKER_ID}: status=COMPLETED, issues=1" in summary
    assert f"[{CHECKER_ID}] ERROR | issue-1 | rule-1" in summary
    assert "trace has an invalid OSI header" in summary


def test_format_qc_result_summary_uses_checker_results_from_qc_baselib():
    summary = _format_qc_result_summary(
        result=_FakeResult(),
        channel_spec=_FakeChannelSpec(),
        result_file=None,
        output_config=None,
    )

    assert f"- {CHECKER_ID}: status=COMPLETED, issues=1" in summary
