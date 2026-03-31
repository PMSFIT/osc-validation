from pathlib import Path

from osi_utilities import ChannelSpecification

import osc_validation.metrics.qccheck as qccheck_module


class _FakeConfiguration:
    def __init__(self):
        self.config_params = {}
        self.bundle_params = {}
        self.registered_bundles = []
        self.written_to = None

    def set_config_param(self, name, value):
        self.config_params[name] = value

    def register_checker_bundle(self, checker_bundle_name):
        self.registered_bundles.append(checker_bundle_name)

    def set_checker_bundle_param(self, checker_bundle_name, name, value):
        self.bundle_params[(checker_bundle_name, name)] = value

    def get_checker_bundle_param(self, checker_bundle_name, param_name):
        return self.bundle_params.get((checker_bundle_name, param_name))

    def write_to_file(self, path):
        self.written_to = Path(path)
        self.written_to.write_text("<config/>", encoding="utf-8")


class _FakeResult:
    def __init__(self, success: bool):
        self.success = success
        self.written_to = None
        self.checked_ids = None

    def write_to_file(self, path):
        self.written_to = Path(path)
        self.written_to.write_text("result", encoding="utf-8")

    def all_checkers_completed_without_issue(self, checker_ids):
        self.checked_ids = list(checker_ids)
        return self.success


def test_qc_checker_wires_configuration_and_writes_outputs(tmp_path, monkeypatch):
    captured = {}
    fake_result = _FakeResult(success=True)

    monkeypatch.setattr(qccheck_module, "Configuration", _FakeConfiguration)

    def _fake_run_checker_bundle(config):
        captured["config"] = config
        return fake_result

    monkeypatch.setattr(qccheck_module, "run_checker_bundle", _fake_run_checker_bundle)

    ruleset = tmp_path / "rules.yml"
    checker = qccheck_module.QCOSITraceChecker(osi_version="3.7.0", ruleset=ruleset)
    channel_spec = ChannelSpecification(path=tmp_path / "trace.mcap")
    result_file = tmp_path / "qc_result.xqar"
    output_config = tmp_path / "qc_config.xml"

    assert (
        checker.check(
            channel_spec=channel_spec,
            result_file=result_file,
            output_config=output_config,
        )
        is True
    )

    config = captured["config"]
    assert config.config_params["InputFile"] == str(channel_spec.path)
    assert config.config_params["osiType"] == "SensorView"
    assert config.config_params["osiVersion"] == "3.7.0"
    assert config.config_params["osiRulesFile"] == str(ruleset)
    assert config.registered_bundles == [qccheck_module.constants.BUNDLE_NAME]
    assert config.bundle_params[
        (qccheck_module.constants.BUNDLE_NAME, "resultFile")
    ] == str(result_file)
    assert config.written_to == output_config
    assert fake_result.written_to == result_file
    assert fake_result.checked_ids == [
        qccheck_module.osirules_constants.CHECKER_ID,
        qccheck_module.deserialization_constants.CHECKER_ID,
    ]


def test_qc_checker_returns_false_without_optional_outputs(tmp_path, monkeypatch):
    captured = {}
    fake_result = _FakeResult(success=False)

    monkeypatch.setattr(qccheck_module, "Configuration", _FakeConfiguration)

    def _fake_run_checker_bundle(config):
        captured["config"] = config
        return fake_result

    monkeypatch.setattr(qccheck_module, "run_checker_bundle", _fake_run_checker_bundle)

    checker = qccheck_module.QCOSITraceChecker()
    channel_spec = ChannelSpecification(path=tmp_path / "trace.mcap")

    assert checker.check(channel_spec=channel_spec) is False

    config = captured["config"]
    assert config.config_params["InputFile"] == str(channel_spec.path)
    assert config.config_params["osiType"] == "SensorView"
    assert "osiVersion" not in config.config_params
    assert "osiRulesFile" not in config.config_params
    assert fake_result.written_to is None
    assert config.written_to is None
