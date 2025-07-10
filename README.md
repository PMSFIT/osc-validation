# osc-validation

This repository provides a validation suite for ASAM OpenSCENARIO XML engines based on comparing their OSI GroundTruth/SensorView output to known good references.

The validation is based on a [subset definition](specification/osc_subset_definition.md) that restricts the covered constructs of OpenSCENARIO XML to a minimal, unambiguous, validatable, but useful subset.

It derives from this subset a validation suite of representative test cases and metrics that can then be used to check an implementation for correct OSI ground truth generation for those cases.

## Installation

Use [poetry](https://python-poetry.org/) to install the validation suite into a new virtual environment:

```bash
poetry install
```

## Usage

### Run tests using pytest

Run the following command to execute the test suite using the specified test directory with the chosen tool to be validated.

```bash
pytest file_or_dir --tool <TOOL_NAME> --toolpath <PATH_TO_TOOL_EXECUTABLE>
```

The first positional argument (`file_or_dir`) specifies the test directory (or file) to run. Pytest will recursively discover and execute all test files within a given folder based on a contained `pytest.ini` configuration, using it as the root for test collection.

- `<TOOL_NAME>`: Name of the OpenSCENARIO engine to test (e.g., `ESMini`, `GTGen`)
- `<PATH_TO_TOOL_EXECUTABLE>`: Path to the tool's executable

Example:

```bash
pytest validation/scenario --tool ESMini --toolpath C:/path/to/esmini/bin/esmini.exe
```

For more information on available command-line options, run:

```bash
pytest --help
```

## Tool validation setup

To automate and harmonize the invocation of different tools in the validation process, tool wrapper classes can be created.
Each tool wrapper must be derived from the base class `OSCTool`:

This wrapper should:

- Launch the tool with the given input files (and desired parameters)
- Return the `OSIChannelSpecification` to the tool-generated OSI output
- Optionally internally post-process traces (e.g., converting formats, fix tool-specific issues)

Tools already integrated:

- ESMini
- GTGen Simulator (via gtgen_cli)

To integrate a custom tool:

- Implement a wrapper subclass of `OSCTool`
- Extend conftest.py to register your tool in the CLI options and generate_tool_trace fixture

    ```python
    def pytest_addoption(parser):
        # [...]
        group.addoption(
            "--tool", action="store", default="ESMini", help="Tool to Validate: ESMini, GTGen, YourToolName"
        )
        # [...]

    @pytest.fixture(scope="session")
    def generate_tool_trace(request):
    # [...]
        if tool_name == "ESMini":
            tool = ESMini(request.config.getoption("--toolpath"))
        elif tool_name == "GTGen":
            tool = GTGen_Simulator(request.config.getoption("--toolpath"))
        elif tool_name == "YourToolName":
            tool = YourToolWrapperClass(request.config.getoption("--toolpath"))
        else:
            tool = None
        # [...]
    ```
    The pytest fixture `generate_tool_trace` then yields the `run` function callable of the selected tool wrapper:
    ```python
        # [...]
        if tool:
            yield tool.run
        else:
            raise ValueError("Tool not found")
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
def osi_trace(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()
```

### 2. Reference implementation

A reference implementation is responsible for generating a baseline for correctness and defines the expected outcome of the tool under test.

- Must provide the functionality covered by the test cases using it.
- Not required to provide full feature coverage beyond the test scope.

The provided [OSI to OpenSCENARIO XML Converter](./osc_validation/generation/osi2osc.py) uses an OSI reference trace as input and generates a corresponding OpenSCENARIO XML file to be consumed by the tool under test.
It covers the OpenSCENARIO XML functionality specified by the [OpenSCENARIO subset definition](./specification/osc_subset_definition.md).
As such, any test cases based on this reference implementation must conform to the specified subset.

### 3. Quality Checkers

ASAM Quality Checker Bundles can be used to check the adherence of OSI trace files to certain OSI versions and/or rulesets.

Checker Bundles already integrated:
- [qc-osi-trace - OSI Trace Checker](https://github.com/PMSFIT/qc-osi-trace.git)

### 4. Validation metrics

Validation metrics compare certain characteristics of tool-generated traces to reference traces.

- Must accept two OSI channel specifications: reference and tool output
- May enforce preconditions on the input traces (e.g., matching framerate)
- May include post-processing steps to ensure comparability of the compared subject

### 5. Test case function

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