# ASAM OpenSCENARIO XML Subset Definition

This document is the entry point for a succeeding set of subsets of ASAM OpenSCENARIO XML 1.3.0 that form the basis of a validation suite approach for validating ASAM OpenSCENARIO implementations.
The subsets are defined in order to avoid ambiguous or hard to validate aspects of OpenSCENARIO, while remaining useful for the exchange of recorded or otherwise generated scenarios in actual practice.
With increasing functionality of the validation suite, increased subsets of OpenSCENARIO can be defined and validated.

## Subset Iterations

- [Subset Definition: Most Minimal Subset (Iteration 1)](./osc_subset_definition_iteration_1.md)
- [Subset Definition: Release Subset (Iteration 2)](./osc_subset_definition_iteration_2.md)

## Future Extensions

- Expand on time requirements (Trajectory/Vertex timestamps), e.g. check monotonic increasing of timestamps in Quality Checker
- Expand trigger coverage beyond the currently validated start and stop trigger cases
- Add trajectory time reference scaling and additional relative timing variants
- Add relative positioning for trajectories and other more complex position types (e.g. TrajectoryPosition to test s-/t-coordinates)
- Add trajectory follow mode 'follow'
- Add clothoid, spline, nurbs trajectories
