# osc-validation

This repository provides a validation suite for ASAM OpenSCENARIO XML engines based on comparing their OSI GroundTruth/SensorView output to known good references.

The validation is based on a [subset definition](specification/osc_subset_definition.md) that restricts the covered constructs of OpenSCENARIO XML to a minimal, unambiguous, validatable, but useful subset.

It derives from this subset a validation suite of representative test cases and metrics that can then be used to check an implementation for correct OSI ground truth generation for those cases.

## Repository structure

The repository separates reusable validation support from concrete validation test cases:

- `osc_validation/` is the installable Python package. It provides low-level validation functionality such as tool wrappers, data providers, generation utilities, metrics, the pytest plugin entry point, and the packaged validation suite.
- `tests/` contains unit and smoke tests for the reusable `osc_validation` package and plugin behavior. These tests do not run the first-level OpenSCENARIO validation suite against a tool.
- `osc_validation/validation/` contains the actual validation test cases and any built-in local data needed by those cases. The validation suite is pytest-based, uses the `osc_validation` pytest plugin, and keeps its standalone pytest configuration in `osc_validation/validation/pytest.ini`.

## Installation

> [!NOTE]
> If you choose to manage this project with Poetry, be aware that it requires **Poetry 2.0 or newer**.

### Install from source with Poetry

Use [poetry](https://python-poetry.org/) to install the validation suite into a new virtual environment:

```bash
git clone https://github.com/PMSFIT/osc-validation
cd osc-validation
poetry install
```

### Install the package

The `osc-validation` package can also be installed standalone:

```bash
pip install osc-validation
```

This installs the reusable `osc_validation` API, the pytest plugin, the `osc-validate` command, and the built-in validation test cases and reference data.

## Usage

### Poetry environment

When using Poetry as your dependency manager, you can either activate the virtual environment once, or prefix each command with `poetry run` to execute it inside the environment.
For brevity, the `poetry run` prefix is omitted in the rest of this documentation.

### List available validation tests

```bash
pytest osc_validation/validation --collect-only
```

### Run validation

Run the installed validation suite with an installed OpenSCENARIO engine:

```bash
osc-validate --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

- `<TOOL_NAME>`: Name of the OpenSCENARIO engine to test (e.g., `ESMini`, `GTGen`)
- `<PATH_TO_TOOL_EXECUTABLE>`: Path to the tool's executable

> [!NOTE]
> You can omit `--toolpath` if your OpenSCENARIO engine's cli command is on PATH.

Use `pytest` directly if you need to run a specific part of the suite (e.g. when developing test cases) or if you need specific pytest features that are not provided through the `osc-validate` command.
Run pytest against paths inside `osc_validation/validation` so the validation suite's pytest configuration and plugin are loaded:

```bash
pytest osc_validation/validation/scenario/trajectories --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

From outside the repository root, pass the validation suite config explicitly:

```bash
pytest <PATH_TO_REPOSITORY_ROOT>/osc_validation/validation/scenario/trajectories --config-file <PATH_TO_REPOSITORY_ROOT>/osc_validation/validation/pytest.ini --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

Generate a self-contained HTML validation report with:

```bash
osc-validate --tool <TOOL_NAME> --html validation-report.html
```

For more information on available command-line options, run:

```bash
osc-validate --help
```

### Test profiles

A **test profile** is a TOML file that declares expected failures for a specific validation run — for example, features not yet supported by a particular tool version. It is designed to be maintained by tool CI pipelines and passed to the suite externally, without modifying this repository.

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
```

Each `[[xfail]]` entry requires:
- `test` — pytest node ID or `fnmatch` glob pattern matching one or more node IDs
- `reason` — human-readable explanation shown in the report

Optional:
- `strict` (bool, default `false`) — when `true`, the test is marked as failed if it unexpectedly passes

### Development checks

The repository also contains a small unit and smoke test suite for development and maintenance work:

```bash
pytest tests
```

## Tool validation setup

To automate and harmonize the invocation of different tools in the validation process, tool wrapper classes can be created.
Each tool wrapper must be derived from the base class `OSCTool`:

This wrapper should:

- Launch the tool with the given input files (and desired parameters)
- Return the `ChannelSpecification` to the tool-generated OSI output
- Optionally internally post-process traces (e.g., converting formats, fix tool-specific issues)

Tools already integrated:

- ESMini
- GTGen Simulator (via gtgen_cli)
- OscSimulator

To integrate a custom tool:

- Implement a wrapper subclass of `OSCTool`
- Register it in `osc_validation/pytest_plugin.py` → `_make_tool`:

    ```python
    def _make_tool(config):
        tool_name = config.getoption("--tool")
        toolpath = config.getoption("--toolpath")

        if tool_name == "ESMini":
            return ESMini(toolpath)
        elif tool_name == "GTGen":
            return GTGen_Simulator(toolpath)
        elif tool_name == "YourToolName":
            return YourToolWrapperClass(toolpath)
        raise ValueError("Tool not found")
    ```
    The pytest fixture `generate_tool_trace` then yields the `run` function callable of the selected tool wrapper:
    ```python
    @pytest.fixture(scope="session")
    def generate_tool_trace(request):
        yield request.config._osc_tool.run
    ```
    Using the `generate_tool_trace` fixture in a test case function enables to inject the tool execution process into test cases.
    Note that the fixture `generate_tool_trace` is a callable and accepts the corresponding function parameters of the `run` function.

## Test case design

Test cases are constructed using reference resources, a reference implementation, automated trace generation, quality checkers, validation metrics and corresponding test parameters.

The following sections briefly summarize how to combine and utilize these components to create a test case. 

### 1. Validation resources

OSC Validation Suite provides a flexible data provider system that can supply test or validation data from local built-in directories or by downloading and extracting remote ZIP archives on demand.
Such resources are prepared for provision to a test case via pytest fixtures:

```python
@pytest.fixture(
    scope="module",
    params=["simple_trajectories/sv_trace1.osi", "simple_trajectories/sv_trace2.osi"],
)
def osi_trace(request, builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path(request.param)
    provider.cleanup()
```

The `builtin_data_path` session fixture is provided by `osc_validation/validation/scenario/conftest.py` and resolves to `osc_validation/validation/data/builtin/`.

### 2. Reference implementation

A reference implementation is responsible for generating a baseline for correctness and defines the expected outcome of the tool under test.

- Must provide the functionality covered by the test cases using it.
- Not required to provide full feature coverage beyond the test scope.

The provided [OSI to OpenSCENARIO XML Converter](./osc_validation/generation/osi2osc.py) uses an OSI reference trace (SensorView or GroundTruth) as input and generates a corresponding OpenSCENARIO XML file to be consumed by the tool under test.
It covers the OpenSCENARIO XML functionality specified by the [OpenSCENARIO subset definition](./specification/osc_subset_definition.md).
As such, any test cases based on this reference implementation must conform to the specified subset.

### 3. Quality Checkers

ASAM Quality Checker Bundles can be used to check the adherence of OSI trace files to certain OSI versions and/or rulesets.

Checker Bundles already integrated:
- [qc-osi-trace - OSI Trace Checker](https://github.com/OpenSimulationInterface/qc-osi-trace)

### 4. Validation metrics

Validation metrics compare certain characteristics of tool-generated traces to reference traces.

- Must accept two OSI channel specifications: reference and tool output
- May enforce preconditions on the input traces (e.g., matching framerate)
- May include post-processing steps to ensure comparability of the compared subject

### 5. OSI trace I/O

Use `asam-osi-utilities` (`osi_utilities`) for generic OSI trace reading and writing:

```python
from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
```

Project code should pass OSI traces around as `ChannelSpecification` instances. Use `open_channel(...)` to read traces and `open_channel_writer(...)` to write traces.

### 6. Test case function

Test cases are built using the previously described components and pytest's built-in functionality.

```python
@pytest.mark.parametrize("moving_object_id", [1, 2, 3])
def example_test_case(osi_trace, odr_file, generate_tool_trace, tmp_path, moving_object_id, tolerance=1e-6):
    [...]
```

- Integrate pytest fixtures' names in the test case function as function parameters
    - Resource fixtures (e.g., `osi_trace`, `odr_file`)
    - Tool execution fixture (`generate_tool_trace`)
    - Pytest built-in fixtures (e.g., `tmp_path`, pytest markers such as `moving_object_id`)
- Integrate a reference implementation (e.g., the OSI to OpenSCENARIO XML Converter osi2osc) to generate an OpenSCENARIO file from a baseline OSI reference trace
- Use `generate_tool_trace` callable and the OpenSCENARIO file to generate the corresponding OSI tool trace
- Calculate validation metrics from the reference and tool trace, and define assertions to be verified in the test case

For more information on **pytest fixtures** see:
- [docs.pytest.org / About fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html)
- [docs.pytest.org / Fixtures reference](https://docs.pytest.org/en/stable/reference/fixtures.html)
- [docs.pytest.org / How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html#how-to-fixtures)

## File formats

This validation suite is based on the following file formats and standard interfaces:
- ASAM OSI single/-multi-channel trace files (`.mcap`, `.osi`)
- ASAM OpenSCENARIO XML
- ASAM OpenDRIVE
- ASAM Quality Checker Framework (Configuration, Results)
