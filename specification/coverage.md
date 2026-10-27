# Validation coverage matrix

Read with the [subset](subset.md) at the same revision. The suite collects **28
instances in 14 modules**. Counts include fixture/test parameters, not a percentage
of OpenSCENARIO. Unit tests in `tests/` do not expand engine validation coverage.

**Direct** means the test asserts resulting behavior within the stated limits.
**Exercised** means a construct is used without an independent semantic check.
Everything else is outside the validation claim.

## Direct behavior checks

Links identify modules relative to `osc_validation/validation/scenario/`.
Combine a module with each function below to obtain the function-level pytest ID
`scenario/<module>::<function>`, including all parameter variants.

| Module / function | Instances | Settings and assertion limits |
| --- | ---: | --- |
| [trajectories/val_simple_trajectories.py](../osc_validation/validation/scenario/trajectories/val_simple_trajectories.py): `test_trajectory_and_osi_compliance` | 2 | Recorded timed polyline replay, relative timing, objects 1 and 2; 2D trajectory similarity |
| [trajectories/val_interpolation.py](../osc_validation/validation/scenario/trajectories/val_interpolation.py): `test_timed_polyline_trajectory_interpolation` | 2 | Linear position or constant acceleration from initial speed 0; three vertices; five samples at 1 Hz over 0–4 s; time, XY, orientation, dimensions |
| [trajectories/val_follow_trajectory_teleport.py](../osc_validation/validation/scenario/trajectories/val_follow_trajectory_teleport.py): `test_follow_trajectory_position_mode_teleports_to_current_trajectory_time` | 2 | Absolute timing, off-trajectory init, activation at 2 s (vertex) or 1 s (between vertices); five samples over 0–4 s; time, XY, orientation, dimensions |
| [trajectories/val_follow_trajectory_future_time_reference.py](../osc_validation/validation/scenario/trajectories/val_follow_trajectory_future_time_reference.py): `test_follow_trajectory_future_time_reference_continues_init_speed_until_first_vertex` | 1 | Absolute timing, vertices at 4 and 6 s, initial speed 4 m/s; seven samples over 0–6 s, time/pose/dimensions, selected pre-join speed samples and join frame |
| [init_actions/val_init_actions.py](../osc_validation/validation/scenario/init_actions/val_init_actions.py): `test_init_teleport_action_places_actor_at_expected_pose` | 1 | World pose with yaw 0.5, pitch 0.3, roll -0.2 rad; XY and full orientation, no independent Z-error assertion |
| Same module: `test_init_add_entity_action_places_actor_at_expected_pose` | 1 | Add entity at known world pose; XY and full orientation, no general lifecycle or independent entity-count assertion |
| Same module: `test_init_speed_action_sets_expected_motion` | 1 | Absolute speed 5 m/s; planar speed error < 0.75 m/s, time error <= 0.01 s; first speed sample ignored |
| [object_state/val_vehicle_dimensions.py](../osc_validation/validation/scenario/object_state/val_vehicle_dimensions.py): `test_vehicle_dimensions_match_reference` | 2 | Recorded objects 1 and 2; length/width/height errors < 0.1 m; no dedicated bounding-box-center/axle assertion |
| [sequencing/val_split_trajectory.py](../osc_validation/validation/scenario/sequencing/val_split_trajectory.py): `test_split_ego_trajectory_preserves_reference_motion` | 5 | Two Ego fragments at Event, Maneuver, ManeuverGroup, Act, or Story level; 2D similarity measures < 0.1; no repetition/priority competition |
| [triggers/val_simulation_time_start_trigger.py](../osc_validation/validation/scenario/triggers/val_simulation_time_start_trigger.py): `test_simulation_time_start_trigger_delays_actor_trajectory` | 2 | 10 s delay, `greaterOrEqual`, objects 1 and 2; aligned trajectory similarity < 0.2 |
| [triggers/val_speed_start_trigger.py](../osc_validation/validation/scenario/triggers/val_speed_start_trigger.py): `test_speed_start_trigger_activates_target_actor` | 1 | `speed >= 50/3.6` m/s, rising; post-activation similarity < 0.25, alignment lag <= 2 frames |
| Same module: `test_speed_start_trigger_condition_edge_none_activates_when_initially_true` | 1 | `speed >= 0`, edge `none`; initially true activation through resulting motion |
| Same module: `test_speed_start_trigger_condition_edge_falling_activates` | 1 | `speed >= 20/3.6` m/s, falling; activation as predicate becomes false, through resulting motion |
| [triggers/val_distance_euclidian_start_trigger.py](../osc_validation/validation/scenario/triggers/val_distance_euclidian_start_trigger.py): `test_distance_euclidian_start_trigger_activates_target_actor` | 1 | Fixed world target, <= 10 m, Euclidean/entity coordinates/no freespace; post-activation similarity < 0.1, lag <= 2 frames |
| [triggers/val_distance_longitudinal_start_trigger.py](../osc_validation/validation/scenario/triggers/val_distance_longitudinal_start_trigger.py): `test_distance_longitudinal_start_trigger_activates_target_actor` | 1 | Fixed world target, <= 10 m, longitudinal/entity coordinates/no freespace; post-activation similarity < 0.1, lag <= 2 frames |
| [triggers/val_time_to_collision_start_trigger.py](../osc_validation/validation/scenario/triggers/val_time_to_collision_start_trigger.py): `test_time_to_collision_start_trigger_activates_target_actor` | 1 | Fixed world target, TTC <= 5 s, Euclidean/entity coordinates/no freespace; calculated kinematics; post-activation similarity < 0.3, lag <= 2 frames |
| [triggers/val_traveled_distance_start_trigger.py](../osc_validation/validation/scenario/triggers/val_traveled_distance_start_trigger.py): `test_traveled_distance_start_trigger_activates_target_actor` | 1 | 55 m traveled; post-activation similarity < 0.2, lag <= 2 frames |
| [triggers/val_condition_delay.py](../osc_validation/validation/scenario/triggers/val_condition_delay.py): `test_distance_longitudinal_start_trigger_respects_condition_delay` | 1 | Longitudinal case with 1 s delay; reused motion assertions, no transient/reset test |
| Same module: `test_speed_start_trigger_respects_condition_delay` | 1 | Rising speed case with 1 s delay; reused motion assertions, no transient/reset test |
| **Total** | **28** | |

Replay-derived cases share one two-vehicle swerve recording and its map. Synthetic
cases use the example map. These are representative settings, not exhaustive
attribute combinations. Interpolation variants are alternative version/profile
expectations; passing both is not a universal conformance requirement.

## Comparison semantics

Trajectory similarity checks 2D area between curves, curve-length measure, and
mean absolute error. A common numeric threshold for these different measures is
not a uniform maximum position tolerance. Trigger tests generally skip the
activation boundary or use a guard window, and search a small alignment lag.
They establish post-trigger motion within timing tolerance, not exact
activation-frame equality. Typical replay-derived sampling is 0.05 s.

Object-state trajectory oracle checks require XY error < 0.1 m, orientation
component errors < 0.01 rad, dimension error < 0.01 m, and time error <= 0.01 s.
Init pose cases check XY, full orientation, and time. Only asserted fields form
the contract: computing a metric does not assert every returned field. Object
matching may use closest initial XY rather than identical IDs.

## Exercised supporting constructs

| Construct | Evidence boundary |
| --- | --- |
| `StoryboardElementStateCondition completeState` | Fragment sequencing; motion continuity, not every state transition |
| Simulation-time storyboard stop | Termination; synthetic trajectory sample counts/time checked, no comprehensive stop-trigger suite |
| Bounding-box center and axle data | Vehicle construction/pose conversion, no isolated attribute-variation tests |
| OpenDRIVE road network | Supplied to engines, no independent road-semantic validation |
| Single execution, override priority, actor assignment | Scaffolding, no repeat/arbitration/competing-action tests |
| OSI compliance | Optional fixture calls enabled by run options, not unconditional |

## Inventory and result claims

```sh
pytest osc_validation/validation --collect-only -q
```

Collection establishes identifiers/counts, not engine results. Record the suite
commit, engine version, selected tests, options, interpolation expectation,
profile/expected failures, and optional OSI checks with results. See the
[excluded features](subset.md#outside-the-subset) and [release rules](releases.md).
