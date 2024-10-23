# ASAM OpenSCENARIO XML Subset Definition

This document specifies a succeeding set of subsets of ASAM OpenSCENARIO XML 1.3.0 that form the basis of a validation suite approach for validating ASAM OpenSCENARIO implementations.
The subsets are defined in order to avoid ambiguous or hard to validate aspects of OpenSCENARIO, while remaining useful for the exchange of recorded or otherwise generated scenarios in actual practice.
With increasing functionality of the validation suite, increased subsets of OpenSCENARIO can be defined and validated.

## Subset Definition: Most Minimal Subset (Iteration 1)

- Very simple OpenSCENARIO representation of an OSI Trace
- Only vehicle bounding box/axles and one corresponding polyline trajectory are allowed
- Coordinate system: World coordinates (UTM), (maybe with offset?), no S-/T-coordinates, no relative coordinates
- Corresponding quality checks: <https://github.com/PMSFIT/qc-openscenarioxml/tree/checker-minsubset>

### Exclusive OpenSCENARIO content

(see complete structure in [xosc example file](./../example/20240603T143803.535904Z_osc_pmsf_dronetracker_119_cutout_shortened.xosc))

- FileHeader, License
- Entities/ScenarioObject/Vehicle
  - BoundingBox: Center + Dimensions
  - Axles:
    - RearAxle (for position) (missing information in exemplary OSI trace)
    - FrontAxle because required in OSC (missing information in exemplary OSI trace)
  - Performance (1..1 cardinality); required OSC classes but not given in OSI trace
- Storyboard
  - No Init Actions
  - One Story only
    - One Act per vehicle only
    - One Maneuver per vehicle only
    - RoutingAction/FollowTrajectoryAction
      - Trajectory/Shape: Polyline only
      - TrajectoryFollowingMode: followingMode="position"
      - TimeReference/Timing: domainAbsoluteRelative="absolute", scale="1.0", offset="0.0"
      - Vertex time (use resampled OSI trace to have consistent frame rate)
      - Position: WorldPosition only (global xyz/hpr, probably UTM coordinates)
  - No Triggers (Triggers not required in OpenSCENARIO 1.3) except stop trigger of storyboard (see OSC documentation 8.4.7)

### Open points (Subset Definition/Quality Checker Features/...)

- OSC does not require Init Actions officially
  - Problem: esmini requires Init Actions, otherwise "entity is not in focus"
  - InitActions are probably not required for a minimal subset with FollowTrajectoryAction
- Center of rear axle has to be known/contained in OSI trace
- Front axle position is required and has to be known (OSC technically requires two axles for vehicles except trailers)
- World coordinate system offset to prevent potential floating-point errors of simulators
- Expand on time requirements (Vertex timestamps)
  - E.g. maybe check continuity of timestamps in QC

### Outcome/conclusions for OpenSCENARIO

1. Init Actions: Unclear when required
    - Note: 10.3: "ASAM OpenSCENARIO does not enforce specifying the initial position and speed of entities, but it is considered best practice to do so. Most actions and conditions require those values to be set."
        - What does "most actions/conditions" mean? Unclear.
        - For some actions it may not even make sense to be initialized with some position because not known (e.g. Polyline trajectory with fixed timestamps) -> Best practice to always define Init Actions is also not useful
2. Better coordinate system documentation in OSC:
    - RearAxle: positionX should always be 0 for rear axle?
    - Definition of reference position of a entity is not clearly documented.
        - e.g. link between position of entity and how the entity is placed at this position (apparently it is placed at the ground projection of rear axle; but very unclear in documentation and model reference documentation)
3. 8.4.7 Execution of a storyboard: "Simulation tools can use this behavior to explicitly stop the simulation." Unclear meaning.
4. General: Use of consistent names in OSC
