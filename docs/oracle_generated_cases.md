# Oracle-based Validation Case Architecture

## Goal

Validation cases should keep the OpenSCENARIO input change and the expected OSI behavior aligned without turning the project into a second full OSC engine.

Use small, reviewable reference logic for one validation feature at a time.
Prefer property checks or tolerant metrics when the OpenSCENARIO behavior is not specified tightly enough for one exact reference trace.

## Recommended Layers

### Generation

`osc_validation/generation` should own creation or modification of OpenSCENARIO inputs.

Examples:

- `osi2osc.py`
- XOSC transforms that inject a trigger
- XOSC transforms that rewrite relative positions
- XOSC transforms that split trajectories across storyboard elements

This layer should not contain reusable OSI trace-editing primitives unless they are purely local implementation details of an existing legacy case.

### Reference

`osc_validation/reference` should own reusable logic for deriving expected reference-side behavior.

Examples:

- trace editing: hold, delay, crop, repeat, override init pose
- activation detection: speed, distance, time-to-collision
- expected profiles: speed profile, interpolation profile

The reference layer should remain narrow.
It should provide primitives that are easy to test and audit, not a general OpenSCENARIO executor.

### Oracles

`osc_validation/oracles` should own validation-case builders that harmonize the OpenSCENARIO edit with the corresponding expected reference behavior.

An oracle answers:

> Given this validation scenario, what input should the tool run and what output should a correct tool produce or satisfy?

An oracle may produce:

- a modified XOSC file plus an expected OSI reference trace
- a modified XOSC file plus expected activation timestamps or frame indices
- a modified XOSC file plus a velocity/profile expectation
- a modified XOSC file plus property-check parameters

Prefer function names that describe the validation case, for example:

```python
build_simulation_time_trigger_case(...)
build_speed_action_case(...)
build_relative_position_case(...)
```

Avoid introducing classes with only one static `apply()` method unless there is a real need for polymorphic state or inheritance.

### Metrics

`osc_validation/metrics` should compare tool output against the expectation.

Examples:

- trajectory similarity
- activation timing
- duration/final timestamp
- velocity profile checks
- property checks

Metrics should not modify XOSC files and should not derive feature-specific OSC semantics beyond what is needed for comparison.

## Typical New Test Flow

```text
source OSI trace
  -> osi2osc
  -> oracle builds validation case
       -> generation layer edits XOSC
       -> reference layer derives expected behavior
  -> tool runs modified XOSC
  -> metric compares tool output to expectation
```

The test function should remain mostly orchestration:

1. Select input resources and parameters.
2. Generate the baseline XOSC.
3. Call one oracle/case builder.
4. Run the tool under test.
5. Assert one or more metrics.

The test should not separately edit XOSC and OSI reference traces inline.
That logic belongs in the oracle so both sides stay synchronized and reviewable.

## When to Use Which Expectation Style

Use a full reference trace when the expected behavior is deterministic and concrete, such as:

- simulation-time trigger delay
- relative position converted back to absolute world position
- init pose override
- repeated trajectory segment with a defined count

Use activation/profile expectations when the full position trace is not the main contract, such as:

- condition edge behavior
- stop trigger duration
- speed action target profile

Use property checks or tolerant metrics when the standard allows multiple valid realizations, such as:

- lane following
- lane changes
- controller-like behavior
- interpolation modes with tool-specific but valid smoothing

## Migration Guidance

Do not migrate existing tests just to match this structure.
The current trigger transform modules intentionally keep XOSC edits and reference-trace edits close together, and that is acceptable for existing cases.

For new validation cases, prefer the layered structure above.
For existing cases, extract reusable reference primitives only when they are needed by a new case or when the existing code is already being changed for a concrete reason.
