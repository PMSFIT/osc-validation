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

The project has three main layers:

1. **`osc_validation/`** — Core library
   - `tools/` — Tool wrappers (`OSCTool` base class). Each wraps an OpenSCENARIO engine (ESMini, GTGen) to run simulations and produce OSI traces.
   - `generation/` — Reference implementation. `osi2osc` converts an OSI reference trace into an OpenSCENARIO XML file that can be fed to the tool under test.
   - `metrics/` — Validation metrics (`OSIMetric` base class). Compare tool-generated traces to reference traces (e.g., `TrajectorySimilarityMetric`).
   - `dataproviders/` — Data sourcing (`DataProvider` base class). `BuiltinDataProvider` serves local files from `data/builtin/`; `DownloadDataProvider`/`DownloadZIPDataProvider` fetch remote resources.
   - `utils/` — Project utility functions such as trace conversion helpers, SensorView stripping, GroundTruth-to-SensorView conversion, trajectory extraction, and channel specification helpers. Generic OSI trace I/O is provided by `asam-osi-utilities` (`osi_utilities`).

2. **`validation/`** — Pytest-based validation test cases
   - Tests live under `validation/scenario/` and are discovered via `validation/scenario/pytest.ini`.
   - `conftest.py` registers `--tool` and `--toolpath` CLI options and provides the `generate_tool_trace` session fixture.

3. **`data/`** and **`specification/`** — Reference trace files and the OpenSCENARIO subset definition.

### Validation Flow

```
Reference OSI trace → osi2osc → OpenSCENARIO XML → Tool under test → Tool OSI trace
                                                                          ↓
                                           Reference OSI trace → Metrics (similarity, QC checks) → Pass/Fail
```

## Key Conventions

- **Test file naming**: Validation test files are prefixed `val_` (not the standard `test_`). This is configured in `validation/scenario/pytest.ini` via `python_files = val_*.py`.
- **`ChannelSpecification`** (from `osi_utilities`) is the central data class for referring to OSI trace files. It wraps a file path with message type, topic, and metadata. Use its builder-style methods (`with_trace_file_format`, `with_message_type`) to derive variants.
- **OSI trace I/O**: Use `osi_utilities.open_channel` and `osi_utilities.open_channel_writer` for reading and writing traces.
- **Tool wrappers** must subclass `OSCTool` and implement `run()`, which accepts an OpenSCENARIO path, OpenDRIVE path, and `ChannelSpecification` for the desired output, and returns the resulting `ChannelSpecification`.
- **Metrics** must subclass `OSIMetric` and implement `compute()`, taking reference and tool `ChannelSpecification` instances.
- **Data providers** must subclass `DataProvider`. Use `BuiltinDataProvider` for files in `data/builtin/`. Use `DownloadDataProvider` or `DownloadZIPDataProvider` for remote resources; these handle download, caching, and cleanup.
- **Testing scope**: Keep tests focused on project-owned behavior. Avoid testing thin wrappers around external packages or tools unless the test covers meaningful project logic. Use `tests/` for unit and smoke coverage, and `validation/` for real tool validation against ESMini, GTGen, or other OpenSCENARIO engines.
- **Formatter**: The project uses `black` for code formatting.
- **Python**: Requires Python 3.10+.
