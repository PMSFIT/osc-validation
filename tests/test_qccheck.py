from pathlib import Path

from osc_validation.metrics.qccheck import CHECKER_IDS, _format_qc_result_summary


class _FakeChannelSpec:
    path = Path("trace.osi")


class _FakeIssue:
    level = "ERROR"
    issue_id = "issue-1"
    rule_uid = "rule-1"
    description = "trace has an invalid OSI header"


class _FakeResult:
    def get_checker_status(self, checker_id):
        return "COMPLETED"

    def get_checker_issue_count(self, bundle_name, checker_id):
        return 1 if checker_id == CHECKER_IDS[0] else 0

    def get_issues(self, bundle_name, checker_id):
        if checker_id == CHECKER_IDS[0]:
            return [_FakeIssue()]
        return []


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
    assert f"- {CHECKER_IDS[0]}: status=COMPLETED, issues=1" in summary
    assert "[{}] ERROR | issue-1 | rule-1".format(CHECKER_IDS[0]) in summary
    assert "trace has an invalid OSI header" in summary


def test_format_qc_result_summary_falls_back_to_issue_list_for_issue_count():
    class _IssueCountRaisesResult(_FakeResult):
        def get_checker_issue_count(self, bundle_name, checker_id):
            raise TypeError("unsupported")

    summary = _format_qc_result_summary(
        result=_IssueCountRaisesResult(),
        channel_spec=_FakeChannelSpec(),
        result_file=None,
        output_config=None,
    )

    assert f"- {CHECKER_IDS[0]}: status=COMPLETED, issues=1" in summary
