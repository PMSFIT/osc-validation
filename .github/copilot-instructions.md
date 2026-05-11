# Copilot Instructions for osc-validation

## Project Overview

This is a validation suite for ASAM OpenSCENARIO XML engines. It validates tools (like ESMini, GTGen) by comparing their OSI (Open Simulation Interface) GroundTruth/SensorView output traces against known-good reference traces. The validation is scoped to a [restricted OpenSCENARIO XML subset](specification/osc_subset_definition.md).

## Build & Test Commands

```bash
# Install dependencies (requires Poetry 2.0+)
poetry install

# Run the unit/smoke test suite
poetry run pytest tests

# Run the full validation suite against a tool
poetry run pytest validation/scenario --tool ESMini --toolpath /path/to/esmini

# Run a single test file
poetry run pytest validation/scenario/trajectories/val_simple_trajectories.py --tool ESMini --toolpath /path/to/esmini

# Run a single test by name
poetry run pytest validation/scenario -k "test_trajectory_and_osi_compliance" --tool ESMini --toolpath /path/to/esmini

# Format code
poetry run black <changed files>
```

## Architecture

The project separates reusable validation support from concrete validation test cases. Keep dependency direction one-way: `tests/` and `validation/` may import `osc_validation`, but `osc_validation` should not import from `validation/`.

1. **`osc_validation/`** — Reusable Python package + pytest plugin (installable via `pip install osc-validation`)
   - `tools/` — Tool wrappers (`OSCTool` base class). Each wraps an OpenSCENARIO engine (ESMini, GTGen) to run simulations and produce OSI traces.
   - `generation/` — Reference implementation. `osi2osc` converts an OSI reference trace into an OpenSCENARIO XML file that can be fed to the tool under test.
   - `metrics/` — Validation metrics (`OSIMetric` base class). Compare tool-generated traces to reference traces (e.g., `TrajectorySimilarityMetric`).
   - `dataproviders/` — Data sourcing (`DataProvider` base class). `BuiltinDataProvider(data_root)` serves local files from a provided data root path; `DownloadDataProvider`/`DownloadZIPDataProvider` fetch remote resources.
   - `utils/` — Project utility functions such as trace conversion helpers, SensorView stripping, GroundTruth-to-SensorView conversion, trajectory extraction, and channel specification helpers. Generic OSI trace I/O is provided by `asam-osi-utilities` (`osi_utilities`).
   - `pytest_plugin.py` — Registers `--tool`, `--toolpath`, `--test-profile` CLI options; provides `generate_tool_trace` session fixture; handles validation test collection/profile metadata/report header behavior.

2. **`tests/`** — Unit and smoke tests for `osc_validation`
   - Tests package/plugin behavior and project-owned utility logic.
   - Does not contain first-level OpenSCENARIO validation suite tests against ESMini, GTGen, or other engines.

3. **`validation/`** — Standalone validation suite built on `osc_validation`
   - Tests live under `validation/scenario/` and are discovered via `validation/pytest.ini`.
   - `validation/scenario/conftest.py` provides the `builtin_data_path` session fixture (resolves to `validation/data/builtin/`) and sets the HTML report title.
   - `validation/data/builtin/` — Built-in local data and reference OSI trace files used by validation cases.
   - Validation test files consume the `osc_validation` pytest plugin fixtures and CLI options.

4. **`specification/`** — OpenSCENARIO subset definition.

### Validation Flow

```
Reference OSI trace → osi2osc → OpenSCENARIO XML → Tool under test → Tool OSI trace
                                                                          ↓
                                           Reference OSI trace → Metrics (similarity, QC checks) → Pass/Fail
```

## Key Conventions

- **Test file naming**: Validation test files are prefixed `val_` (not the standard `test_`). This is configured in `validation/pytest.ini` via `python_files = val_*.py`.
- **`ChannelSpecification`** (from `osi_utilities`) is the central data class for referring to OSI trace files. It wraps a file path with message type, topic, and metadata. Use its builder-style methods (`with_trace_file_format`, `with_message_type`) to derive variants.
- **OSI trace I/O**: Use `osi_utilities.open_channel` and `osi_utilities.open_channel_writer` for reading and writing traces.
- **Tool wrappers** must subclass `OSCTool` and implement `run()`, which accepts an OpenSCENARIO path, OpenDRIVE path, and `ChannelSpecification` for the desired output, and returns the resulting `ChannelSpecification`.
- **Metrics** must subclass `OSIMetric` and implement `compute()`, taking reference and tool `ChannelSpecification` instances.
- **Data providers** must subclass `DataProvider`. Use `BuiltinDataProvider(builtin_data_path)` for files in `validation/data/builtin/` (the `builtin_data_path` fixture provides the root path). Use `DownloadDataProvider` or `DownloadZIPDataProvider` for remote resources; these handle download, caching, and cleanup.
- **`builtin_data_path` fixture**: Session-scoped fixture defined in `validation/scenario/conftest.py`. Always accept it as a parameter in `osi_trace`-style fixtures that use `BuiltinDataProvider`.
- **Testing scope**: Keep tests focused on project-owned behavior. Avoid testing thin wrappers around external packages or tools unless the test covers meaningful project logic. Use `tests/` for unit and smoke coverage, and `validation/` for real tool validation against ESMini, GTGen, or other OpenSCENARIO engines.
- **Formatter**: The project uses `black` for code formatting.
- **Python**: Requires Python 3.10+.
