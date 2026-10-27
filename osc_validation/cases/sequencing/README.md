# Sequencing Transforms

## Purpose

Sequencing transforms rewrite an `osi2osc` generated scenario so that one actor's single trajectory is represented as multiple sequential OpenSCENARIO elements. The resulting scenario should replay the same reference motion while exercising different OpenSCENARIO hierarchy levels.

The reference trace is intentionally not modified. Validation compares the tool output against the original trace to check whether the sequenced scenario preserves the same motion within the configured metric tolerances.

## Supported Sequencing Levels

The current transform supports splitting a trajectory across:

- `Event`
- `Maneuver`
- `ManeuverGroup`
- `Act`
- `Story`

Later segments are started with `StoryboardElementStateCondition` triggers that wait for the previous segment-level element to reach `completeState`. The start trigger is placed on an element that can carry the trigger, while the referenced storyboard element matches the selected sequencing level.

- `Event`: the next event starts after the previous event reaches `completeState`.
- `Maneuver`: the next maneuver's event starts after the previous maneuver reaches `completeState`.
- `ManeuverGroup`: the next maneuver group's event starts after the previous maneuver group reaches `completeState`.
- `Act`: the next act starts after the previous act reaches `completeState`.
- `Story`: the next story's act starts after the previous story reaches `completeState`.

## Timing Model

Each split trajectory segment uses segment-local vertex times. The first vertex of every segment is normalized to `0.0`, because `FollowTrajectoryAction` uses relative timing in the generated scenarios. Without this normalization, later segments would apply their original absolute timestamps again after being started, adding unintended delays.

## Limitations

Not every OpenSCENARIO tag is a useful sequencing boundary:

- Multiple `Action` elements in one `Event` are not represented as sequencing, because actions in the same event start together.
- Multiple trajectories in one `FollowTrajectoryAction` are not currently used, because the generated structure has one `TrajectoryRef` per action.

The helpers currently target the naming and structure produced by `osi2osc` for generated simple trajectory scenarios.
