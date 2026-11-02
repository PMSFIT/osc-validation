# Trigger Transform Modules

This package contains trigger-specific transform modules for the validation suite.

## Disclaimer

Use these transforms only with OSC/OSI input pairs where the OpenSCENARIO file was generated from the OSI trace via `osi2osc`.

The modules rely on that generation contract (naming and structural conventions) to keep scenario-side and reference-trace-side modifications aligned.

## Core Concept

Each trigger module keeps both sides of the trigger behavior in one place:

1. OpenSCENARIO structure modification (XOSC)
2. OSI reference-trace modification (MCAP/OSI channel)

This is intentional and important for this validation suite:

- The scoped reference implementation for a trigger feature is contained in one module.
- The implementation scope is defined by the OpenSCENARIO structure that is added/modified there.
- Scenario-side and reference-trace-side behavior stay synchronized and reviewable together.

## Module Pattern

Trigger logic is grouped by feature in `speed/`, `distance_to_position/`, `simulation_time/`, `time_to_collision/`, and `traveled_distance/`:

- `transform.py` edits the scenario and constructs the corresponding reference trace.
- `case.py` prepares the scenario, reference trace, and activation information without pytest dependencies.
- `__init__.py` exposes the public transform functions at the existing feature import path.

Distance-to-position cases share a package, with separate preparation functions for longitudinal and Euclidean checks so their generation and init-pose policies remain explicit.
The longitudinal delay validation uses the same preparation function with an explicit condition delay.

The validation modules select inputs, execute the simulator, check compliance, choose scoring windows and metric settings, calculate metrics, and assert acceptance thresholds.
Metric algorithms live in `osc_validation/metrics/`; case modules do not invoke them.

All preparation functions return `TriggerCaseResult` from `triggers/models.py`, containing the scenario path, reference channel, and condition activation time.

The shared `transform.py` handles initial-pose preparation and dispatches to the feature's transformer.
Case modules import `apply_trigger_transform` directly from `osc_validation.features.triggers.transform`, and specs from `osc_validation.features.triggers.models`.
Feature transformers use shared utilities without importing the dispatcher.
The root `__init__.py` contains no re-exports.

`TriggerTransformer` in the shared `transform.py` defines the static `apply(request) -> TriggerTransformResult` contract.
The dispatch registry uses this protocol in its type annotation, so type checkers can verify registered transformers without requiring them to inherit from it.

Each trigger module typically provides:

- `apply_*_start_trigger(...)`: modifies the OpenSCENARIO XML structure for that trigger.
- `build_*_comparison_trace(...)`: builds the corresponding reference OSI trace behavior.
- `*TriggerTransformer.apply(...)`: orchestrates both sides for `apply_trigger_transform(...)`.
