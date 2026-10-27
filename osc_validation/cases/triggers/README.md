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

Each trigger module typically provides:

- `apply_*_start_trigger(...)`: modifies the OpenSCENARIO XML structure for that trigger.
- `build_*_comparison_trace(...)`: builds the corresponding reference OSI trace behavior.
- `*TriggerTransformer.apply(...)`: orchestrates both sides for `apply_trigger_transform(...)`.
