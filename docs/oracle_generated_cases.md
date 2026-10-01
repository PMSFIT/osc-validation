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

## RoutePosition behavior characterization

`scenario/positions/val_route_position.py` runs 20 Init/TeleportAction cases
on a straight road whose
lanes -1 and +1 both widen as `4 + 0.4s`. Forward/reverse inline routes use ordered road
waypoints at s=10/90, t=-1, with explicit absolute traversal headings. The road is
100 m long and the route spans projected road s=10..90; route pathS is measured
from the first projected waypoint. At pathS=20, target road s is 30 forward or
70 reverse, so x is 30/70. The route reference line is the cropped road reference
line at y=0; waypoint t=-1 does not shift that line. Lane -1 is centered at y=-8/-16
and lane +1 at y=8/16 (forward/reverse). For FromRoadCoordinates, omitted orientation follows the
route's positive s-direction: yaw 0 forward and pi reverse. Positive route t
points left along that direction, giving y=t forward and y=-t reverse.
Lane-coordinate headings remain tied to the referenced lane centerline:
lane -1 tangent -atan(0.2) and lane +1 tangent atan(0.2), in both route directions.

Each scenario runs the engine once. Local comparison helpers use stationary
references and `ObjectStateMetric` to compare against one expected pose per case.
All cases omit RoutePosition orientation: six zero-offset heading cases and 12
offset cases using -2 m and +2 m for both road and lane coordinates, plus two
cross-lane cases, all on the varying-width map. In
[OpenSCENARIO XML 1.3.1](https://publications.pages.asam.net/standards/ASAM_OpenSCENARIO/ASAM_OpenSCENARIO_XML/v1.3.1/generated/content/RoutePosition.html),
omission means relative `h=p=r=0`, so explicit relative-zero engine cases are
redundant for this matrix. Builder unit tests retain both XML forms. Absolute
and nonzero relative RoutePosition headings are excluded.
The test deliberately interprets the road-coordinate relative orientation as
route-relative. This differs from the linked specification's wording, which
refers to the referenced road's s and t coordinates; it represents the intended
interpretation of a suspected specification defect, not a confirmed erratum.
The absolute waypoint headings establish route traversal direction.
Lane offsets use the referenced lane's positive-s left normal: `(0.2, 1) / sqrt(1.04)` for lane -1
and `(-0.2, 1) / sqrt(1.04)` for lane +1, independent of route direction.
For either lane and either 2 m offset sign, road-normal placement differs by
approximately 0.394 m, exceeding the 0.1 m position tolerance.
The two forward cross-lane cases reference lane +1 with offset -10 m and lane -1
with offset +10 m. Their targets are approximately (31.961161, -1.805807) and
(31.961161, 1.805807), respectively, inside the opposite lane. Expected yaw remains
the referenced lane's tangent: +atan(0.2) and -atan(0.2). Selecting the destination
lane's tangent instead produces a 0.394791 rad error, exceeding the yaw tolerance.
Time error must be <=0.01 s, planar error <0.1 m, and wrapped yaw error <0.01 rad
across every frame. The case matrix and candidate poses are generated from explicit
coordinate and interpretation choices in `val_route_position.py`.

Unmatched behavior produces a
pytest assertion with the measured initial/final poses, expected pose, and time,
planar and yaw errors. Engine errors and invalid traces fail directly. Reporting
uses ordinary pytest output; no additional JSON report or custom properties are generated.
Matching an interpretation does not establish standards compliance; the route line
is explicitly a diagnostic construction, not a normative route definition.

Example engine run:

```powershell
python -m pytest -c osc_validation/validation/pytest.ini osc_validation/validation/scenario/positions/val_route_position.py --tool ESMini --toolpath C:/path/to/esmini.exe -s
```

Unit coverage is in `tests/test_route_position_behavior.py`. These cases exclude
fromCurrentEntity and road transitions.
