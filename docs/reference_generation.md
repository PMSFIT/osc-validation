# Reference Generation Strategies

A validation needs a scenario input, an expected reference, and checks that compare the tool output with that reference.
This document categorizes how the reference is obtained.
Scenario construction and evaluation are separate choices: changing a scenario does not always require changing its reference, and the same scenario could be evaluated against references obtained in different ways.

The suite currently reuses existing traces, transforms traces, and calculates references directly.
Reference simulation is a possible future option.

## 1. Existing Reference Trace

A recorded or pre-generated OSI trace is reused as the expected reference.
Within the validation suite, no behavior model needs to calculate the expected motion.
The trace supplies the object states and attributes against which the tool output is compared, even if only selected characteristics are checked.

The current replay cases use `osi2osc` to construct matching OpenSCENARIO inputs from the trace.
However, deriving the scenario from the reference is a scenario construction choice, not a requirement of this reference strategy.
A scenario can also be modified while retaining the original expectation: trajectory sequencing changes the storyboard structure but preserves the reference motion.

Use an existing trace when it already describes the expected behavior.
This preserves realistic motion and avoids implementing a separate reference model.
The trace's origin and suitability must be understood; a recording is not necessarily the correct expectation for every scenario derived from it.
For example, the OpenSCENARIO version and interpolation policy determine whether path, timing, and kinematics should all match.

Existing cases: simple trajectory replay, vehicle dimensions, and trajectory sequencing.
Sequencing transforms the scenario, but uses this reference strategy because its expected trace remains unchanged.

## 2. Transformed Reference Trace

An existing OSI trace supplies a baseline, and a reference-side transformation changes selected behavior to match the scenario under test.
Unaffected parts of the trace remain the source of expected states, so the calculation only needs to model the behavior introduced by the change.

Current trigger cases use this approach.
They construct a baseline scenario with `osi2osc`, add a trigger, and transform the reference motion to describe the expected hold and subsequent movement.
Scenario and reference changes must agree on actor identity, initial poses, condition activation, and timing offsets.
Some cases also calculate velocity and acceleration from the source positions before deriving the trigger behavior.

Use this strategy when a reference is already useful and the additional behavior can be expressed as a focused transformation.
Its assumptions must be explicit: current trigger transforms rely on names and structure produced by `osi2osc`, so they do not support arbitrary user-authored scenarios.
Independently check the reference changes; consistent but incorrect edits to the scenario and reference can conceal a mistaken expectation.

Existing cases: simulation-time, speed, distance-to-position, traveled-distance, and time-to-collision triggers, including the condition-delay checks.

## 3. Calculated Reference

A reference calculation derives expected behavior directly from a case description, rather than adapting an existing trace.
Inputs such as actor poses, speeds, trajectory vertices, and duration determine the expected object states, which are sampled into an OSI trace.

Current builders coordinate scenario generation and reference calculation from one shared description.
These builders are called oracles in the implementation.
The reference calculation uses the description directly; it does not interpret the generated OpenSCENARIO file.
Scenario generation and reference calculation have separate responsibilities, even though they share neutral input data and utilities.

Use this strategy for small deterministic examples whose expected behavior can be calculated and reviewed directly, especially boundary conditions that are hard to obtain from recordings.
Each calculation should state its supported behavior and assumptions.
Sharing inputs does not guarantee correctness: reference algorithms need independently derived examples and should not simply copy the scenario generator's logic.
Keep calculations focused on the feature instead of gradually building an implicit simulator.

Existing cases: init actions, trajectory teleport, future trajectory time references, and interpolation.

## 4. Reference Simulation (Future Option)

A reference simulator would execute the scenario input and generate the expected OSI output.
Unlike a direct reference calculation, it would interpret the OpenSCENARIO file, including the interactions of its supported constructs.
The tool under test and the reference simulator would receive the same scenario.

The scenario could originate from a trace, a scenario transform, a focused generator, or another source.
Choosing reference simulation changes how the expectation is obtained; it does not prescribe scenario construction or the metrics used to compare outputs.

This could be useful when many cases need the same execution semantics or when feature interactions become difficult to express with isolated calculations.
It centralizes those semantics, but requires maintaining and validating an interpreter.
Agreement between two simulators alone is not proof of conformance: the reference needs independently checked examples and documented decisions about ambiguous or implementation-defined behavior.
Its supported subset must be explicit, with unsupported constructs rejected rather than silently approximated.
This strategy is not currently used by the validation cases.
