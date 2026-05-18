import logging
from dataclasses import dataclass
from pathlib import Path

from qc_baselib import Configuration

from qc_ositrace import constants
from qc_ositrace.main import run_checker_bundle
from qc_ositrace.checks.osirules import osirules_constants
from qc_ositrace.checks.deserialization import deserialization_constants

from osi_utilities import ChannelSpecification


CHECKER_IDS = [
    deserialization_constants.CHECKER_ID,
    osirules_constants.CHECKER_ID,
]


@dataclass(frozen=True)
class QCOSITraceCheckResult:
    """
    Result summary for an executed QC OSI trace check.
    """

    passed: bool
    summary: str
    issue_count: int
    result_file: Path | None = None
    output_config: Path | None = None


class TraceChecker:
    """
    Base class for checking OSI traces.
    """

    def __init__(self, osi_version: str):
        self.osi_version = osi_version

    def check(self, channel_spec: ChannelSpecification):
        raise NotImplementedError("Subclasses should implement this method.")


class QCOSITraceChecker(TraceChecker):
    """
    Class to perform OSI trace checker bundle using the QC framework.

    Args:
        osi_version (str, optional): OSI version ruleset to be checked against. Defaults to None.
        ruleset (Path, optional): Path to the custom ruleset for OSITrace quality checks (osiRulesFile). If None, only the OSI version ruleset is checked.
    """

    def __init__(self, osi_version: str = None, ruleset: Path = None):
        super().__init__(osi_version)
        self.checker_bundle_name = constants.BUNDLE_NAME
        self.ruleset = ruleset

    def run(
        self,
        channel_spec: ChannelSpecification,
        result_file: Path = None,
        output_config: Path = None,
    ) -> QCOSITraceCheckResult:
        """
        Executes the configured OSI trace checker bundle on the provided OSI trace file.

        Args:
            trace (ChannelSpecification): Path to the OSI trace file to be checked.
            result_file (Path, optional): Path to the xqar output file where results will be written. If None, results will not be written to a file.
            output_config (Path, optional): Path to the output configuration xml file where the configuration will be written. If None, configuration will not be written to a file.

        Returns:
            QCOSITraceCheckResult: Structured pass/fail status and diagnostic summary.
        """

        config = Configuration()
        config.set_config_param("InputFile", str(channel_spec.path))
        config.set_config_param("osiType", "SensorView")
        if self.osi_version:
            config.set_config_param("osiVersion", self.osi_version)
        if self.ruleset is not None:
            config.set_config_param("osiRulesFile", str(self.ruleset))
        config.register_checker_bundle(self.checker_bundle_name)
        if result_file:
            config.set_checker_bundle_param(
                checker_bundle_name=self.checker_bundle_name,
                name="resultFile",
                value=str(result_file),
            )

        result = run_checker_bundle(config)

        if config.get_checker_bundle_param(
            checker_bundle_name=constants.BUNDLE_NAME, param_name="resultFile"
        ):
            logging.info(f"Writing results to {result_file}")

            result.write_to_file(
                config.get_checker_bundle_param(
                    checker_bundle_name=constants.BUNDLE_NAME, param_name="resultFile"
                )
            )
        else:
            logging.info(
                "No result file specified, results will not be written to file"
            )

        if output_config:
            logging.info(f"Writing configuration to file: {output_config}")
            config.write_to_file(output_config)

        passed = result.all_checkers_completed_without_issue(CHECKER_IDS)
        issue_count = _issue_count(result, CHECKER_IDS)
        return QCOSITraceCheckResult(
            passed=passed,
            summary=_format_qc_result_summary(
                result=result,
                channel_spec=channel_spec,
                result_file=result_file,
                output_config=output_config,
            ),
            issue_count=issue_count,
            result_file=result_file,
            output_config=output_config,
        )

    def check(
        self,
        channel_spec: ChannelSpecification,
        result_file: Path = None,
        output_config: Path = None,
    ) -> bool:
        """
        Executes the configured OSI trace checker bundle on the provided OSI trace file.

        Returns:
            bool: True if all checkers completed without issues, False otherwise.
        """

        return self.run(
            channel_spec=channel_spec,
            result_file=result_file,
            output_config=output_config,
        ).passed


def _format_qc_result_summary(
    *,
    result,
    channel_spec: ChannelSpecification,
    result_file: Path | None,
    output_config: Path | None,
    max_issues: int = 10,
) -> str:
    lines = [
        "QC OSI trace check failed.",
        f"Trace: {channel_spec.path}",
    ]
    if result_file is not None:
        lines.append(f"Result file: {result_file}")
    if output_config is not None:
        lines.append(f"Output config: {output_config}")

    lines.append("Checker summary:")
    for checker_id in CHECKER_IDS:
        status = _checker_status(result, checker_id)
        count = _checker_issue_count(result, checker_id)
        count_text = "unknown" if count is None else str(count)
        lines.append(f"- {checker_id}: status={status}, issues={count_text}")

    issue_lines, omitted_count = _issue_lines(result, max_issues=max_issues)
    if issue_lines:
        lines.append("Issues:")
        lines.extend(issue_lines)
        if omitted_count > 0:
            lines.append(
                f"- ... {omitted_count} more issue(s); see the result file for details."
            )
    else:
        lines.append(
            "No issues were reported, but one or more checkers did not complete without issues."
        )

    return "\n".join(lines)


def _issue_count(result, checker_ids: list[str]) -> int:
    count = 0
    for checker_id in checker_ids:
        checker_count = _checker_issue_count(result, checker_id)
        if checker_count is not None:
            count += checker_count
    return count


def _checker_status(result, checker_id: str) -> str:
    try:
        status = result.get_checker_status(checker_id)
    except Exception:
        return "unknown"
    return (
        getattr(status, "value", None) or getattr(status, "name", None) or str(status)
    )


def _checker_issue_count(result, checker_id: str) -> int | None:
    try:
        return result.get_checker_issue_count(constants.BUNDLE_NAME, checker_id)
    except Exception:
        try:
            return len(result.get_issues(constants.BUNDLE_NAME, checker_id))
        except Exception:
            return None


def _issue_lines(result, max_issues: int) -> tuple[list[str], int]:
    lines = []
    total_count = 0
    for checker_id in CHECKER_IDS:
        try:
            issues = result.get_issues(constants.BUNDLE_NAME, checker_id)
        except Exception:
            continue
        total_count += len(issues)
        for issue in issues:
            if len(lines) >= max_issues:
                continue
            lines.append(f"- [{checker_id}] {_format_issue(issue)}")
    return lines, max(0, total_count - len(lines))


def _format_issue(issue) -> str:
    fields = []
    for name in ("level", "issue_id", "rule_uid"):
        value = getattr(issue, name, None)
        if value is not None:
            fields.append(str(value))

    description = (
        getattr(issue, "description", None)
        or getattr(issue, "message", None)
        or str(issue)
    )
    if fields:
        return f"{' | '.join(fields)}: {description}"
    return str(description)
