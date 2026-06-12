# Validation Case Strategy Summary

The validation suite currently uses several strategies for defining test inputs and expected results.

## 1. Recorded Trace Replay

A pre-generated or recorded OSI reference trace is used as the source of truth.
The suite generates a corresponding OpenSCENARIO file from that trace with `osi2osc`, runs the tool under test, and compares the tool-generated OSI output against the original reference trace.

This strategy is best suited for validating concrete trajectory replay behavior.

## 2. Trace And Scenario Transforms

A recorded OSI reference trace is first converted to OpenSCENARIO with `osi2osc`.
The suite then applies coordinated transforms to the generated XOSC file and, when needed, to the OSI reference trace.

This allows focused validation of additional behavior, such as trigger timing or trajectory sequencing, while keeping the scenario input and expected reference behavior aligned.

## 3. Oracle-Generated Cases

An oracle module generates both the OpenSCENARIO file and the expected OSI reference trace from one shared case description.

This strategy is useful when the expected behavior is easier to define directly than to derive from a recorded trace, for example small deterministic checks around init actions, poses, or simple speed behavior.

## 4. Property Or Tolerant Checks

Some OpenSCENARIO behavior should not be validated against one exact OSI reference trace.
For features where multiple valid realizations are possible, the suite can instead check properties, envelopes, timing windows, final states, or tolerances.

This strategy is useful for behavior such as lane following, lane changes, controller-like behavior, or interpolation modes where the standard may define constraints without requiring one unique trajectory.

## 5. Reference Simulator

A possible future strategy is to implement a scoped reference simulator or scenario engine.
It would consume OpenSCENARIO input and produce OSI output, and could be integrated into the validation suite like any other simulator backend.

This would centralize expected behavior for a declared deterministic subset of OpenSCENARIO.
It should remain explicitly scoped and fail clearly for unsupported constructs, so it does not silently become an incomplete or ambiguous full simulator.

See [PMSFIT / osc-simulator](https://github.com/PMSFIT/osc-simulator)
