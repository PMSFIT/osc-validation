# osc-validation

This repository provides a validation suite for ASAM OpenSCENARIO XML engines based on comparing their OSI GroundTruth/SensorView output to known good references.

The validation is based on a [subset definition](specification/osc_subset_definition.md) that restricts the covered constructs of OpenSCENARIO XML to a minimal, unambiguous, validatable, but useful subset.

It derives from this subset a validation suite of representative test cases and metrics that can then be used to check an implementation for correct OSI ground truth generation for those cases.

## Contents

- [Repository structure](#repository-structure)
- [Installation](#installation)
- [Usage](#usage)
  - [Poetry environment](#poetry-environment)
  - [List available validation tests](#list-available-validation-tests)
  - [Run validation](#run-validation)
    - [osc-validate CLI](#osc-validate-cli)
    - [pytest (advanced usage)](#pytest-advanced-usage)
  - [Test profiles](#test-profiles)
- [Tool validation setup](#tool-validation-setup)
- [Contributing](#contributing)
- [File formats](#file-formats)

## Repository structure

The repository separates reusable validation support from concrete validation test cases:

- `osc_validation/` is the installable Python package.
  It provides low-level validation functionality such as tool wrappers, data providers, generation utilities, metrics, the pytest plugin entry point, and the packaged validation suite.
- `osc_validation/validation/` contains the actual validation test cases and any built-in local data needed by those cases.
  The validation suite is pytest-based, uses the `osc_validation` pytest plugin, and keeps its standalone pytest configuration in `osc_validation/validation/pytest.ini`.
- `osc_validation/cases/` groups feature-specific scenario generation, reference calculations, and coordinated case builders.
  See the [reference generation strategies](docs/reference_generation.md).
- `tests/` contains unit and smoke tests for the reusable `osc_validation` package and plugin behavior.
  These tests do not run the first-level OpenSCENARIO validation suite against a tool.

## Installation

Clone the repository and use [Poetry](https://python-poetry.org/) to install it into a virtual environment.
This requires Poetry 2.0 or newer.

```bash
git clone https://github.com/PMSFIT/osc-validation
cd osc-validation
poetry install
```

This installs the Python API, pytest plugin module, `osc-validate` command, built-in validation test cases, and reference data.
You can run the suite using `poetry run osc-validate`, import functionality from `osc_validation`, or explicitly load `osc_validation.pytest_plugin` in your pytest setup.
See [Run validation](#run-validation) for commands and options.

If you already manage another application's Python environment, you can instead install the local source checkout into it with `python -m pip install /path/to/osc-validation` (or `python -m pip install .` from the source directory).

## Usage

### Poetry environment

When using Poetry as your dependency manager, you can either activate the virtual environment once, or prefix each command with `poetry run` to execute it inside the environment.
For brevity, the `poetry run` prefix is omitted in the rest of this documentation.

### List available validation tests

```bash
pytest osc_validation/validation --collect-only
```

List tests for a specific OpenSCENARIO XML release:

```bash
pytest osc_validation/validation --collect-only -q --osc-version 1.3.1
```

Add `--include-exploratory` to include exploratory cases.

### Run validation

#### osc-validate CLI

Use `osc-validate` for standard validation runs and reports.

Run the installed validation suite with an installed OpenSCENARIO engine:

```bash
osc-validate --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

- `<TOOL_NAME>`: Name of the OpenSCENARIO engine to test (e.g., `ESMini`, `GTGen`)
- `<PATH_TO_TOOL_EXECUTABLE>`: Path to the tool's executable

> [!NOTE]
> You can omit `--toolpath` if your OpenSCENARIO engine's cli command is on PATH.

The default OpenSCENARIO XML version is 1.4.0.
Select a different version, or run a version matrix, with `--osc-version`:

```bash
osc-validate --tool ESMini --osc-version 1.3.1
osc-validate --tool ESMini --osc-version 1.3.1 --osc-version 1.4.0
```

Only cases explicitly declared for a selected version run.
The version is part of each test ID and the generated XOSC header.
The selected version is also passed to the reference logic, allowing the same test case to define different expected behavior for different OpenSCENARIO XML versions.

Add `--include-exploratory` to include checks for behavior that is not asserted as a conformance requirement.
See [OpenSCENARIO XML version handling](docs/version_contracts.md) for authoring and reporting details.

Generate a self-contained HTML validation report with:

```bash
osc-validate --tool <TOOL_NAME> --html validation-report.html
```

Generate a JUnit XML results file with:

```bash
osc-validate --tool <TOOL_NAME> --junitxml validation-results.xml
```

Enable QC OSI trace checks at test case call sites with:

```bash
osc-validate --tool ESMini --toolpath C:/path/to/esmini/bin/esmini.exe --assert-osi-compliance --assert-osi-compliance-version 3.7.0
```

Use the Omega Prime ruleset with:

```bash
osc-validate --tool ESMini --toolpath C:/path/to/esmini/bin/esmini.exe --assert-osi-compliance-ruleset-preset omega-prime
```

For more information on available command-line options, run:

```bash
osc-validate --help
```

#### pytest (advanced usage)

Use `pytest` directly if you need to run a specific part of the suite (e.g. when developing test cases) or if you need specific pytest features that are not provided through the `osc-validate` command.
Run pytest against paths inside `osc_validation/validation` so the validation suite's pytest configuration and plugin are loaded:

```bash
pytest osc_validation/validation/scenario/trajectories --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

From outside the repository root, pass the validation suite config explicitly:

```bash
pytest <PATH_TO_REPOSITORY_ROOT>/osc_validation/validation/scenario/trajectories --config-file <PATH_TO_REPOSITORY_ROOT>/osc_validation/validation/pytest.ini --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

The version-selection, reporting, test-profile, and compliance options described above are also available when running pytest directly.
Use pytest options to filter cases or control execution, for example:

```bash
pytest osc_validation/validation/scenario/triggers --tool ESMini -k condition_delay -x
```

This runs matching condition-delay cases and stops after the first failure.
For all available pytest and validation-plugin options, run:

```bash
pytest osc_validation/validation --help
```

### Test profiles

A **test profile** is a TOML file that declares expected failures for a specific validation run — for example, features not yet supported by a particular tool version.
It is designed to be maintained by tool CI pipelines and passed to the suite externally, without modifying this repository.

Pass a profile with `--test-profile`:

```bash
osc-validate --tool ESMini --toolpath /path/to/esmini --test-profile /path/to/my_profile.toml
```

Profile format:

```toml
[[xfail]]
test = "scenario/triggers/val_condition_delay.py::test_condition_delay"
reason = "ConditionDelay not supported in v1.2"

[[xfail]]
test = "scenario/sequencing/val_split_*.py::*"
reason = "Sequencing not implemented"
strict = true  # optional, default false — if true, an unexpected pass is a failure

[[xfail]]
test = "scenario/init_actions/val_init_actions.py::test_init_speed_action_sets_expected_motion[osc-1.3.1]"
reason = "Init speed is unsupported for OpenSCENARIO XML 1.3.1"
```

Each `[[xfail]]` entry requires:
- `test` — pytest node ID or `fnmatch` glob pattern matching one or more node IDs
- `reason` — human-readable explanation shown in the report

A function-level node ID without a parametrization suffix also matches all parametrized instances of that test.
For example, `scenario/foo.py::test_bar` matches collected items such as `scenario/foo.py::test_bar[data-set-1]`.

Optional:
- `strict` (bool, default `false`) — when `true`, the test is marked as failed if it unexpectedly passes
- `except` (list of strings) — patterns selected by `test` that should not be marked xfail.
  Patterns containing `::` match full pytest node IDs; bare patterns match only parametrization IDs inside `[...]`.

Existing patterns without a version continue to match versioned test IDs.
Use a version in the parameter ID (for example `*osc-1.4.0*`) to restrict a profile rule or exception to a particular OpenSCENARIO XML version.
Exploratory test failures are reported as test failures when explicitly included, so keep them separate from a conformance-only run when interpreting results.

## Tool validation setup

To automate and harmonize the invocation of different tools in the validation process, tool wrapper classes can be created.
Tool wrappers should derive from the base class `OSCTool`:

This wrapper should:

- Launch the tool with the given input files (and desired parameters)
- Return the `ChannelSpecification` to the tool-generated OSI output
- Optionally internally post-process traces (e.g., converting formats, fix tool-specific issues)
- Optionally provide a get_version() method that returns tool version information

Tools already integrated:

- ESMini
- GTGen Simulator (via gtgen_cli)
- OscSimulator

To integrate a custom tool without modifying this repository:

- Implement a wrapper subclass of `OSCTool`
- Expose a `create_tool(toolpath)` function from a Python module or `.py` file:

    ```python
    from pathlib import Path

    from osi_utilities import ChannelSpecification
    from osc_validation.tools import OSCTool


    class YourToolWrapper(OSCTool):
        def __init__(self, toolpath):
            super().__init__(Path(toolpath) if toolpath else None)

        def get_version(self):
            return ["your-tool 1.0"]

        def run(
            self,
            osc_path: Path,
            odr_path: Path,
            osi_output_spec: ChannelSpecification,
            log_path: Path = None,
            rate: float = 0.05,
        ) -> ChannelSpecification:
            # Launch your tool, write or convert the OSI trace, and return
            # the resulting channel specification.
            return osi_output_spec


    def create_tool(toolpath):
        return YourToolWrapper(toolpath)
    ```
- Pass the module to `osc-validate` with `--tool-wrapper-module`:

    ```bash
    osc-validate --tool YourToolName --tool-wrapper-module your_package.your_wrapper --toolpath /path/to/your/tool
    ```

    You can also pass a local `.py` file:

    ```bash
    osc-validate --tool YourToolName --tool-wrapper-module /path/to/your_wrapper.py --toolpath /path/to/your/tool
    ```

To contribute a built-in tool wrapper, see [the contributor guide](CONTRIBUTING.md#adding-a-built-in-tool-wrapper).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and checks, code organization, adding validations, compatibility requirements, and built-in tool integration.
The [reference generation strategies](docs/reference_generation.md) explain how to obtain expected behavior for a validation.

## File formats

This validation suite is based on the following file formats and standard interfaces:
- ASAM OSI single/-multi-channel trace files (`.mcap`, `.osi`)
- ASAM OpenSCENARIO XML
- ASAM OpenDRIVE
- ASAM Quality Checker Framework (Configuration, Results)
