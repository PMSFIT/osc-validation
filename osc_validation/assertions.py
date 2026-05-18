import pathlib

from osi_utilities import ChannelSpecification

from osc_validation.tools.metadata import OSC_ENGINE_ERRORS_METADATA_KEY


def assert_no_osc_engine_errors(channel_spec: ChannelSpecification) -> None:
    errors = channel_spec.metadata.get(OSC_ENGINE_ERRORS_METADATA_KEY)
    assert not errors, f"Tool reported OSC engine errors:\n{errors}"


def _optional_path(path):
    if path is None:
        return None
    return pathlib.Path(path)


def make_assert_osi_trace_compliance(
    *,
    qc_enabled: bool,
    default_osi_version: str | None = None,
    default_ruleset=None,
    checker_cls=None,
):
    default_ruleset = _optional_path(default_ruleset)

    def assert_osi_trace_compliance(
        channel_spec,
        *,
        result_file=None,
        output_config=None,
        osi_version=None,
        ruleset=None,
    ) -> None:
        if not qc_enabled:
            return

        resolved_checker_cls = checker_cls
        if resolved_checker_cls is None:
            from osc_validation.metrics.qccheck import QCOSITraceChecker

            resolved_checker_cls = QCOSITraceChecker

        checker = resolved_checker_cls(
            osi_version=(
                osi_version if osi_version is not None else default_osi_version
            ),
            ruleset=_optional_path(ruleset) if ruleset is not None else default_ruleset,
        )
        run_check = getattr(checker, "run", None)
        if callable(run_check):
            result = run_check(
                channel_spec=channel_spec,
                result_file=result_file,
                output_config=output_config,
            )
            assert result.passed, result.summary or "QC OSI trace check failed."
            return

        result = checker.check(
            channel_spec=channel_spec,
            result_file=result_file,
            output_config=output_config,
        )
        assert result, "QC OSI trace check failed."

    return assert_osi_trace_compliance
