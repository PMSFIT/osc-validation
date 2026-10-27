# Feature-oriented validation case architecture

Case-specific code lives together under `osc_validation/cases/`. Generation,
reference calculations, and orchestration remain separate responsibilities within
that feature, rather than separate top-level package trees.

```text
osc_validation/
  cases/
    interpolation/                  # generation.py, reference.py, oracle.py
    follow_trajectory_teleport/      # generation.py, reference.py, oracle.py
    follow_trajectory_future_time_reference/
    init_actions/                   # models.py, generation.py, reference.py, oracle.py
    triggers/                       # one module per trigger plus shared dispatch/models
    sequencing/                     # trajectory splitting and models
    trajectory.py                   # neutral data shared by trajectory features
  generation/
    osi2osc.py                      # reusable converter
    xosc_builders.py                # reusable XML construction
    init_transforms/                # pose utilities used by converter and trigger cases
  reference/
    trace_kinematics.py              # reusable trace utility
  metrics/                          # generic comparisons
  validation/scenario/              # stable pytest entry points and case assertions
```

## Ownership and dependencies

Keep code used by one feature inside that feature. Small features may use a
single module with clearly separated functions; split files when that improves
readability. Extract shared code only when several features need it.

- `generation.py` creates or modifies XOSC inputs.
- `reference.py` independently calculates expected behavior or trace data.
- `oracle.py` coordinates the two from a shared case description.
- Models contain case data, without XML or expected-behavior algorithms.
- Metrics compare supplied outputs and expectations without generating scenarios.

Generation and reference code can share neutral data and generic utilities, but
should not share the algorithm that decides whether the engine is correct.
Tests keep input settings and tolerances visible and use the feature's public
case builder. For example:

```python
from osc_validation.cases.interpolation import (
    TrajectoryInterpolationCaseSpec,
    build_trajectory_interpolation_case,
)
from osc_validation.cases.trajectory import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
```

The existing trigger modules already keep their XML edits, reference derivation,
and coordinating transformer adjacent. They remain intact within `cases/triggers/`;
relocation does not require splitting their internals. Init-pose transforms remain
shared because both the converter and trigger cases consume them.

## Test flow

1. Select resources, parameters, and expectations.
2. Generate a baseline XOSC with `osi2osc` when needed.
3. Call the feature's oracle or coordinated transform.
4. Run the engine.
5. Compare its OSI output with the expectation using metrics and explicit assertions.

Use exact reference traces for deterministic behavior. Use activation/profile
checks when timing or speed is the contract, and property/tolerant checks when
multiple trajectories are valid. Keep reference implementations scoped rather
than building a second general OpenSCENARIO engine.

## Imports and behavior

Import case-specific APIs directly from their owning `osc_validation.cases`
feature package. Shared helpers use explicit module imports such as
`osc_validation.generation.osi2osc` and
`osc_validation.reference.trace_kinematics`. There are no legacy case-module
aliases or lazy aggregate exports.

Validation file paths, test names, parameter IDs, XML, reference algorithms, and
assertions remain unchanged by this reorganization.

Version contracts and interpolation behavior changes are deferred to a subsequent
change. The interpolation case currently retains its original two reference
variants; this layout does not add version selection or change their semantics.
