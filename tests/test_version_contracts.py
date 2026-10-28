"""Exercise version contracts across pytest collection and XML generation."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

from lxml import etree
import pytest
from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.versioning import OscVersion, ScenarioContract
from osc_validation.test_profile import XFailEntry
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.cases.init_actions.oracle import (
    InitActionCaseSpec,
    InitActionOracleActor,
    build_init_teleport_action_case,
    build_init_add_entity_action_case,
    build_init_speed_action_case,
)
from osc_validation.cases.interpolation.oracle import (
    TrajectoryInterpolationCaseSpec,
    build_trajectory_interpolation_case,
)
from osc_validation.cases.follow_trajectory_teleport.oracle import (
    FollowTrajectoryTeleportCaseSpec,
    build_follow_trajectory_teleport_case,
)
from osc_validation.cases.follow_trajectory_future_time_reference.oracle import (
    FollowTrajectoryFutureTimeReferenceCaseSpec,
    build_follow_trajectory_future_time_reference_case,
)
from osc_validation.cases.shared.trajectory_models import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from tests.conftest import _make_sensor_view


def _run_pytest(tmp_path, source, *args):
    (tmp_path / "val_contract.py").write_text(textwrap.dedent(source))
    (tmp_path / "pytest.ini").write_text("[pytest]\npython_files = val_*.py\n")
    env = dict(os.environ)
    repo = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = repo + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "osc_validation.pytest_plugin",
            "-q",
            *args,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_version_matrix_runs_once_per_contract_and_excludes_exploratory(tmp_path):
    result = _run_pytest(
        tmp_path,
        """
        import pytest
        @pytest.mark.osc_versions("1.3.0", "1.4.0")
        def test_shared(scenario_contract, osc_version, tmp_path):
            assert scenario_contract.osc_version == osc_version
            assert tmp_path.name
        @pytest.mark.osc_versions("1.3.0")
        def test_legacy(osc_version):
            assert str(osc_version) == "1.3.0"
        @pytest.mark.osc_versions("1.4.0")
        @pytest.mark.exploratory
        def test_exploratory():
            raise AssertionError("must be deselected")
    """,
        "--osc-version",
        "1.3.0",
        "--osc-version",
        "1.4.0",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 passed, 3 deselected" in result.stdout


def test_default_contract_and_exploratory_opt_in(tmp_path):
    result = _run_pytest(
        tmp_path,
        """
        import pytest
        @pytest.mark.osc_versions("1.3.0", "1.4.0")
        @pytest.mark.exploratory
        def test_behavior(osc_version):
            assert str(osc_version) == "1.4.0"
    """,
        "--include-exploratory",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


@pytest.mark.parametrize(
    "declaration, message",
    [
        ("", "missing osc_versions"),
        ('@pytest.mark.osc_versions("1.5.0")', "unsupported OpenSCENARIO version"),
        ("@pytest.mark.osc_versions()", "explicit list"),
        ('@pytest.mark.osc_versions("1.4.0", "1.4.0")', "duplicate osc_versions"),
        (
            '@pytest.mark.osc_versions("1.3.0")\n@pytest.mark.osc_versions("1.4.0")',
            "multiple osc_versions",
        ),
    ],
)
def test_invalid_contract_is_collection_error(tmp_path, declaration, message):
    source = f"import pytest\n{declaration}\ndef test_case():\n    pass\n"
    result = _run_pytest(tmp_path, source, "--collect-only")
    assert result.returncode != 0
    assert message in result.stdout + result.stderr


def test_profiles_can_target_one_version_and_reports_keep_contract(tmp_path):
    (tmp_path / "profile.toml").write_text(
        """
[[xfail]]
test = "val_contract.py::test_shared[osc-1.3.0]"
reason = "legacy implementation gap"
strict = true
"""
    )
    # Profiles are loaded when a tool is configured; no simulator is needed.
    (tmp_path / "wrapper.py").write_text(
        "class Tool:\n    def run(self, **kwargs): pass\n"
        "def create_tool(toolpath): return Tool()\n"
    )
    result = _run_pytest(
        tmp_path,
        """
        import pytest
        @pytest.mark.osc_versions("1.3.0", "1.4.0")
        def test_shared(osc_version):
            assert str(osc_version) == "1.4.0"
    """,
        "--osc-version",
        "1.3.0",
        "--osc-version",
        "1.4.0",
        "--tool",
        "fake",
        "--tool-wrapper-module",
        str(tmp_path / "wrapper.py"),
        "--test-profile",
        str(tmp_path / "profile.toml"),
        "--junitxml",
        str(tmp_path / "results.xml"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 xfailed" in result.stdout
    report = etree.parse(str(tmp_path / "results.xml"))
    assert report.xpath("//property[@name='osc_version']/@value") == ["1.3.0", "1.4.0"]


@pytest.mark.parametrize("version", list(OscVersion))
@pytest.mark.parametrize(
    "case",
    [
        "teleport",
        "add_entity",
        "speed",
        "interpolation",
        "trajectory_teleport",
        "future",
        "converter",
    ],
)
def test_contract_reaches_generated_xml(tmp_path, version, case):
    contract = ScenarioContract(version)
    output = tmp_path / "scenario.xosc"
    trace = ChannelSpecification(tmp_path / "reference.mcap", message_type="SensorView")
    if case == "converter":
        with open_channel_writer(trace) as writer:
            for timestamp in (0.0, 1.0):
                message = _make_sensor_view(timestamp)
                message.global_ground_truth.moving_object[
                    0
                ].vehicle_classification.type = 4
                writer.write_message(message)
        osi2osc(trace, output, contract=contract)
    elif case in {"teleport", "add_entity", "speed"}:
        actor = InitActionOracleActor(
            entity_ref="Ego",
            object_id=1,
            x=0,
            y=0,
            z=0,
            yaw=0,
            bounding_box_center_x=0,
            bounding_box_center_y=0,
            bounding_box_center_z=0,
            speed_mps=1,
        )
        builder = {
            "teleport": build_init_teleport_action_case,
            "add_entity": build_init_add_entity_action_case,
            "speed": build_init_speed_action_case,
        }[case]
        builder(InitActionCaseSpec(output, trace, [actor], 1.0, 0.5, contract=contract))
    else:
        actor = TrajectoryInterpolationActor(
            entity_ref="Ego",
            object_id=1,
            vertices=[
                TrajectoryInterpolationVertex(time_s=t, x=t, y=0, z=0)
                for t in ((1.0, 2.0) if case == "future" else (0.0, 1.0))
            ],
        )
        if case == "interpolation":
            build_trajectory_interpolation_case(
                TrajectoryInterpolationCaseSpec(
                    output, trace, actor, 1.0, 0.5, contract=contract
                )
            )
        else:
            pose = TrajectoryInterpolationVertex(time_s=0, x=0, y=0, z=0)
            if case == "trajectory_teleport":
                build_follow_trajectory_teleport_case(
                    FollowTrajectoryTeleportCaseSpec(
                        output, trace, actor, pose, 0.0, 1.0, 0.5, contract=contract
                    )
                )
            else:
                build_follow_trajectory_future_time_reference_case(
                    FollowTrajectoryFutureTimeReferenceCaseSpec(
                        output,
                        trace,
                        actor,
                        pose,
                        1.0,
                        0.0,
                        2.0,
                        0.5,
                        contract=contract,
                    )
                )
    header = etree.parse(str(output)).find("FileHeader")
    assert (header.get("revMajor"), header.get("revMinor")) == ("1", str(version.minor))


def test_contract_rejects_unknown_future_release():
    with pytest.raises(ValueError):
        ScenarioContract("1.5.0")


def test_existing_profile_patterns_match_versioned_parameter_ids():
    old = XFailEntry(
        "test_cases.py::test_case[linear-*]",
        "known",
        except_patterns=["linear-allowed*"],
    )
    assert old.matches("test_cases.py::test_case[osc-1.4.0-linear-other]")
    assert not old.matches("test_cases.py::test_case[osc-1.4.0-linear-allowed]")
    specific = XFailEntry("test_cases.py::test_case[osc-1.3.0-linear-other]", "legacy")
    assert specific.matches("test_cases.py::test_case[osc-1.3.0-linear-other]")
    assert not specific.matches("test_cases.py::test_case[osc-1.4.0-linear-other]")
    minor = XFailEntry("test_cases.py::test_case[osc-1.3-linear-other]", "legacy")
    assert minor.matches("test_cases.py::test_case[osc-1.3.0-linear-other]")
    assert minor.matches("test_cases.py::test_case[osc-1.3.1-linear-other]")
    assert not specific.matches("test_cases.py::test_case[osc-1.3.1-linear-other]")


def test_patch_versions_are_distinct_in_selection_and_contract(tmp_path):
    result = _run_pytest(
        tmp_path,
        """
        import pytest
        @pytest.mark.osc_versions("1.3.0", "1.3.1")
        def test_release(scenario_contract):
            assert scenario_contract.osc_version.patch in (0, 1)
        """,
        "--osc-version",
        "1.3.0",
        "--osc-version",
        "1.3.1",
        "--junitxml",
        str(tmp_path / "patches.xml"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    names = etree.parse(str(tmp_path / "patches.xml")).xpath("//testcase/@name")
    assert names == ["test_release[osc-1.3.0]", "test_release[osc-1.3.1]"]


def test_packaged_init_cases_run_for_both_versions_with_fake_engine(tmp_path):
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        textwrap.dedent(
            """
        import shutil
        from lxml import etree
        class Tool:
            def run(self, osc_path, odr_path, osi_output_spec, **kwargs):
                header = etree.parse(str(osc_path)).find("FileHeader")
                assert header.get("revMajor") == "1"
                assert header.get("revMinor") in {"3", "4"}
                output = osi_output_spec.path
                reference = output.with_name(output.name.replace("tool_trace_", "reference_"))
                shutil.copyfile(reference, output)
                return osi_output_spec
        def create_tool(toolpath): return Tool()
    """
        )
    )
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(repo / "osc_validation/validation/scenario/init_actions"),
            "--tool",
            "fake",
            "--tool-wrapper-module",
            str(wrapper),
            "--osc-version",
            "1.3.0",
            "--osc-version",
            "1.4.0",
            "-q",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "6 passed" in result.stdout


def test_cli_forwards_version_matrix_and_exploratory_selection():
    from osc_validation.cli import _parse_args, _pytest_args

    args = _parse_args(
        [
            "--tool",
            "fake",
            "--osc-version",
            "1.3.0",
            "--osc-version",
            "1.4.0",
            "--include-exploratory",
        ]
    )
    forwarded = _pytest_args(args, Path("validation"))
    assert forwarded.count("--osc-version") == 2
    assert forwarded[forwarded.index("--osc-version") + 1] == "1.3.0"
    assert (
        forwarded[
            forwarded.index("--osc-version", forwarded.index("--osc-version") + 1) + 1
        ]
        == "1.4.0"
    )
    assert "--include-exploratory" in forwarded


def test_header_mismatch_is_rejected_before_engine_execution(tmp_path):
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        "class Tool:\n    def run(self, **kwargs): raise AssertionError('engine called')\n"
        "def create_tool(toolpath): return Tool()\n"
    )
    result = _run_pytest(
        tmp_path,
        """
        import pytest
        @pytest.mark.osc_versions("1.4.0")
        def test_bad_header(generate_tool_trace, tmp_path):
            path = tmp_path / "bad.xosc"
            path.write_text('<OpenSCENARIO><FileHeader revMajor="1" revMinor="3"/></OpenSCENARIO>')
            generate_tool_trace(osc_path=path)
    """,
        "--osc-version",
        "1.4.0",
        "--tool",
        "fake",
        "--tool-wrapper-module",
        str(wrapper),
    )
    assert result.returncode != 0
    assert "selected contract is 1.4.0" in result.stdout
    assert "engine called" not in result.stdout
