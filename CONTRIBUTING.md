# Contributing

Use this guide when changing the suite, adding validations, or integrating a built-in tool wrapper.
For running validations or using an external wrapper, see the [README](README.md).

## Contents

- [Development setup and checks](#development-setup-and-checks)
- [Code organization](#code-organization)
- [Adding a validation test case](#adding-a-validation-test-case)
  - [Validation resources](#validation-resources)
  - [Scenario and reference preparation](#scenario-and-reference-preparation)
  - [Quality checkers](#quality-checkers)
  - [Validation metrics](#validation-metrics)
  - [OSI trace I/O](#osi-trace-io)
  - [Test case function](#test-case-function)
- [Compatibility of existing validations](#compatibility-of-existing-validations)
- [Adding a built-in tool wrapper](#adding-a-built-in-tool-wrapper)

## Development setup and checks

After cloning the repository, install its dependencies and development tools:

```bash
poetry install
```

Activate the Poetry environment or prefix commands with `poetry run`.
See [installation](README.md#installation) for the source checkout instructions.
Run the package's unit and smoke tests with:

```bash
pytest tests
```

These tests exercise the library and plugin rather than validate an external simulator.
Check validation collection separately, selecting the relevant OpenSCENARIO versions:

```bash
pytest osc_validation/validation --collect-only --osc-version 1.3.1 --osc-version 1.4.0
```

Run affected validations against the tool under test when changing generated scenarios, reference behavior, or acceptance checks.
See [running validations](README.md#run-validation) for tool and reporting options.

## Code organization

- `osc_validation/features/` groups scenario construction, transforms, reference calculations, and case data by the OpenSCENARIO feature they support.
  Keep these independent of pytest and simulator execution.
  Feature packages may import their own modules, `features/shared/`, and general library utilities, but must not import other feature packages.
  Keep feature-specific behavior and preparation in the owning feature package.
- `osc_validation/features/shared/` contains data models and preparation support used by multiple features.
  Shared support must not import feature-specific implementations.
- `osc_validation/reference/` contains reusable reference algorithms and trace utilities.
  These may depend on shared models, but must not import feature-specific implementations.
- `osc_validation/validation/scenario/` owns pytest integration, concrete inputs, simulator execution, compliance checks, scoring windows, metric settings and calls, tolerances, and acceptance assertions.
- `osc_validation/metrics/` implements reusable comparisons.
- `osc_validation/generation/` and `osc_validation/utils/` provide general scenario generation and utility functionality.
- `tests/` verifies the package and plugin, including reference calculations.
  Keep those checks separate from validations of external tools.

Write documentation with one sentence per line; do not hard-wrap sentences.
Keep code blocks, tables, and list structure intact.

## Adding a validation test case

A validation prepares scenario input and an expected reference, runs the tool, and checks its output using compliance checks, metrics, and explicit assertions.

The following sections explain how to combine these components when adding a validation test case.

### Validation resources

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

### Scenario and reference preparation

Choose a suitable way to obtain the expected reference; the [reference generation strategies](docs/reference_generation.md) describe existing approaches.
Prepare matching scenario input and expected reference data, reusing existing case builders or transforms where suitable and implementing new preparation logic where needed.
Reuse existing traces where suitable, transform them for focused behavior, or calculate a reference for a small deterministic example.

### Quality checkers

ASAM Quality Checker Bundles can be used to check the adherence of OSI trace files to certain OSI versions and/or rulesets.

Checker Bundles already integrated:

- [qc-osi-trace - OSI Trace Checker](https://github.com/OpenSimulationInterface/qc-osi-trace)

QC trace checks are opt-in for a validation run.
Test cases can call the `assert_osi_compliance` fixture where a generated trace should be checked.
The fixture is a no-op by default and runs qc-osi-trace only when `--assert-osi-compliance` or `--assert-osi-compliance-ruleset-preset omega-prime` is passed.

```python
def test_example(generate_tool_trace, assert_osi_compliance, tmp_path):
    tool_trace_channel_spec = generate_tool_trace(...)
    assert_osi_compliance(
        tool_trace_channel_spec,
        result_file=tmp_path / "qc_result.xqar",
        output_config=tmp_path / "qc_config.xml",
    )
```

Use `--assert-osi-compliance-version` and `--assert-osi-compliance-ruleset` to provide default checker settings for the run.
Use `--assert-osi-compliance-ruleset-preset omega-prime` to use the Omega Prime ruleset as the default ruleset.
A test can override those defaults per call with `osi_version=` and `ruleset=`.

When a QC check fails, the fixture assertion message includes the trace path, checker statuses, issue counts, and the first reported issues.
Pass `result_file=` to keep the full xqar result artifact for detailed analysis.

### Validation metrics

Validation metrics compare certain characteristics of tool-generated traces to reference traces.

- Must accept two OSI channel specifications: reference and tool output
- May enforce preconditions on the input traces (e.g., matching framerate)
- May include post-processing steps to ensure comparability of the compared subject

### OSI trace I/O

Use `asam-osi-utilities` (`osi_utilities`) for generic OSI trace reading and writing:

```python
from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
```

Project code should pass OSI traces around as `ChannelSpecification` instances.
Use `open_channel(...)` to read traces and `open_channel_writer(...)` to write traces.

### Test case function

The `generate_tool_trace` fixture supplies the selected wrapper's `run` callable.
Call it with scenario and map paths, an output `ChannelSpecification`, a log directory, and a sampling period (`rate`, in seconds).
It returns the tool-generated trace's channel specification.

Test cases are built using the previously described components and pytest's built-in functionality.

```python
@pytest.mark.osc_versions("1.4.0")
@pytest.mark.parametrize("moving_object_id", [1, 2, 3])
def test_example(scenario_contract, osi_trace, odr_file, generate_tool_trace, tmp_path, moving_object_id, tolerance=1e-6):
    ...
```

The `osc_versions` marker declares which OpenSCENARIO XML versions the case applies to; the run command selects which versions to run.
Pass `scenario_contract` to scenario generation.
See [version contracts](docs/version_contracts.md) for details.

- Integrate pytest fixtures' names in the test case function as function parameters
    - Resource fixtures (e.g., `osi_trace`, `odr_file`)
    - Tool execution fixture (`generate_tool_trace`)
    - Optional QC fixture (`assert_osi_compliance`)
    - Pytest built-in fixtures (e.g., `tmp_path`) and parametrized inputs (e.g., `moving_object_id`)
- Prepare matching scenario input and expected reference using the selected reference generation strategy
- Use `generate_tool_trace` callable and the OpenSCENARIO file to generate the corresponding OSI tool trace
- Calculate validation metrics from the reference and tool trace, and define assertions to be verified in the test case

For more information on **pytest fixtures** see:

- [docs.pytest.org / About fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html)
- [docs.pytest.org / Fixtures reference](https://docs.pytest.org/en/stable/reference/fixtures.html)
- [docs.pytest.org / How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html#how-to-fixtures)

## Compatibility of existing validations

Validation paths, function names, parametrization IDs, and version markers are used by test profiles and automation.
Preserve them during internal refactoring, along with generated behavior and acceptance criteria.
Changes to coverage or requirements should be intentional and documented, with migration guidance when profile selectors must change.

For new tests, parametrize behavioral variations that deserve separate results; keep fixed setup values and acceptance thresholds as local variables.
Use fixtures for resources and dependencies.
Preserve existing single-value parametrizations when removing them would change published IDs.
See [test profiles](README.md#test-profiles) and [version contracts](docs/version_contracts.md) for matching and version details.

## Adding a built-in tool wrapper

First implement the wrapper interface described in [tool validation setup](README.md#tool-validation-setup).
To include it in this repository:

- Add its implementation to `osc_validation/tools/`.
- Register the tool in `_make_tool` in `osc_validation/pytest_plugin.py`.
- Add the tool name to user-facing documentation and cover its selection and execution contract in the relevant plugin and CLI tests.

The same wrapper can also be used externally through `--tool-wrapper-module` without adding it to this repository.
