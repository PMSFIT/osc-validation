# OpenSCENARIO XML validation subset

Status: working definition for the tests in this checkout. See the
[release index](releases.md) for immutable released definitions and the
[coverage matrix](coverage.md) for exact test identifiers and assertions.

## Contract and version

The suite validates selected OpenSCENARIO XML behavior by running an engine and
comparing its OSI output with recorded or generated references. Scenario inputs
target XML 1.3.0. Selected trajectory cases use expectations described by XML
1.4.0; this does not expand the contract to all XML 1.4.0 features.

Only behavior and
combinations explicitly included here and in the matrix are covered. Required
XML scaffolding and optional elements emitted for compatibility may be present
without their semantics being independently validated. Generator support and
unit-test coverage alone do not establish engine validation coverage.

## Entities, geometry, and coordinates

- Scenario objects are vehicles of category `car`, with front and rear axles.
- Vehicle length, width, and height are compared with OSI reference dimensions.
  Bounding-box center and axle information support conversion between vehicle
  reference points and OSI object poses; they do not have separate exhaustive tests.
- Positions use `WorldPosition`. Recorded global coordinates are shifted near
  the origin during conversion. Road networks are supplied as OpenDRIVE inputs;
  road topology and road-relative positioning are not independently validated.
- Required vehicle performance and axle values may be populated by generators.
  Their dynamic effects are outside this contract.

## Initialization

The following actions are included in `Init`:

- Private `TeleportAction` to a world position with heading, pitch, and roll.
  The oracle case checks planar position and full orientation.
- Global `EntityAction` / `AddEntityAction` at a world pose. The oracle checks
  the resulting pose, not a general entity creation/removal lifecycle.
- Private `SpeedAction` with `AbsoluteTargetSpeed`, checked at 5 m/s in a short
  initialized-motion case. It does not cover storyboard speed transitions,
  relative speed targets, or general acceleration dynamics.

Cases may also initialize poses near trajectory starts or use explicit pose
overrides to isolate the feature under test. Those setup choices are not an
additional position-type coverage claim.

## Trajectory actions and time

Storyboard motion uses `FollowTrajectoryAction` with an inline, non-closed
`Polyline`, timed `Vertex` elements, `WorldPosition`, and
`TrajectoryFollowingMode followingMode="position"`.

Included timing combinations are:

- Relative time references used by recorded replay and split trajectories.
- Absolute time references for activation at an existing trajectory time,
  including an exact vertex and a time between vertices. An actor initially off
  the trajectory must join the position for that trajectory time.
- Absolute future first-vertex timing: the actor continues its initialized speed
  before the first vertex, then joins the trajectory at that time.

Time-reference scale is `1.0` and offset is `0.0`. Arbitrary scale/offset
combinations, untimed trajectories, and other following modes are excluded.
Recorded replay uses source timestamps; transforms and synthetic oracles derive
the timestamps needed for their specific cases.

Two interpolation reference variants are collected: linear position and constant
acceleration from initial speed. The latter represents the XML 1.4.0 expectation
used by this suite. Linear interpolation is a compatibility expectation for
older behavior, not a general XML 1.3.0 requirement. Passing both variants is not
a universal conformance requirement: the run's declared version expectations and
test profile must identify which variant applies.

## Triggers and conditions

Event start triggers activate the covered trajectory actions. The matrix limits
the scope to these concrete settings:

| Condition | Covered settings |
| --- | --- |
| `SimulationTimeCondition` | `greaterOrEqual`, rising edge, 10 s replay delay; also used for synthetic action activation |
| `SpeedCondition` | `greaterOrEqual`; rising, falling, and `none` edges; `none` includes initially true activation |
| `TraveledDistanceCondition` | 55 m threshold, rising edge |
| `DistanceCondition` to `WorldPosition` | `lessOrEqual`, 10 m, rising edge, `coordinateSystem="entity"`, `freespace="false"`; `relativeDistanceType="euclidianDistance"` or `"longitudinal"` |
| `TimeToCollisionCondition` to `WorldPosition` | `lessOrEqual`, 5 s, rising edge, entity coordinates, `freespace="false"`, `relativeDistanceType="euclidianDistance"` |
| `Condition delay` | 1 s on the rising speed and longitudinal-distance cases |

Entity-triggered cases use one triggering entity. General condition-group logic,
multi-entity aggregation, other comparison rules and edges, and delay reset or
transient-condition behavior are outside the tested combinations. In particular,
the falling speed case observes the predicate `speed >= threshold` becoming
false; it does not change the comparison rule.

Trigger assertions compare transformed post-activation motion and permit small
frame differences. They do not establish exact activation-frame semantics for
every engine. See the matrix for timing and comparison limits.

## Storyboard and execution

Baseline replay assigns trajectory actions to individual vehicles. Split cases
divide one actor's trajectory into two sequential fragments at each of these
levels: `Event`, `Maneuver`, `ManeuverGroup`, `Act`, and `Story`. Completion-based
sequencing uses `StoryboardElementStateCondition state="completeState"`.
The assertion is preservation of the reference motion across the split.

Maneuver groups execute once. Events use `priority="override"` and single
execution behavior; generated events may rely on the default execution count
instead of explicitly setting it. Repetition, priority arbitration, competing
actions for the same actor, and comprehensive storyboard state transitions are
not covered. Independent vehicles can execute their actions concurrently.

`SimulationTimeCondition` is used for storyboard termination. Synthetic cases
also assert expected sample counts and time alignment. This exercises stopping
for those scenarios, not all stop-trigger semantics. Stopping on story completion
is not a separate current validation case.

## Validation evidence and limitations

Recorded replay, trigger, sequencing, and dimensions cases reuse one two-vehicle
swerve trace and its map. Synthetic oracle cases use small deterministic inputs.
The suite does not claim broad variation across roads, vehicles, speeds, or
boundary conditions.

Replay metrics primarily check 2D motion. Selected oracle assertions additionally
check orientation, dimensions, speed, timestamps, and sample counts. Full 3D
kinematics and every OSI field are not implied. OSI quality checks are opt-in;
they do not replace OpenSCENARIO semantic assertions.

## Outside the subset

- Other entity types and vehicle categories; entity selections.
- Catalog references, parameter/variable/monitor semantics, and object controllers.
- Lane following, lane changes, routes, and general longitudinal/lateral dynamics.
- Road/lane/relative/trajectory position types and relative trajectory coordinates.
- `followingMode="follow"`, clothoid, spline, and NURBS trajectories.
- General timing scaling, offsets, relative-timing variants beyond the recorded
  replay and sequencing cases, repeated execution, and arbitrary trigger logic.
- General environment, traffic, user-defined actions, and entity lifecycle actions
  beyond the included init case.
