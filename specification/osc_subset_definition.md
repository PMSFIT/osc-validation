# ASAM OpenSCENARIO XML Subset Definition

This document specifies a succeeding set of subsets of ASAM OpenSCENARIO XML 1.3.0 that form the basis of a validation suite approach for validating ASAM OpenSCENARIO implementations.
The subsets are defined in order to avoid ambiguous or hard to validate aspects of OpenSCENARIO, while remaining useful for the exchange of recorded or otherwise generated scenarios in actual practice.
With increasing functionality of the validation suite, increased subsets of OpenSCENARIO can be defined and validated.

## Subset Definition: Most Minimal Subset (Iteration 1)

The most minimal subset aims to minimally represent the content of a basic OSI SensorView trace.
Only basic vehicles with two axles and a corresponding polyline-based trajectory are allowed.
The OpenSCENARIO storyboard elements overhead is reduced to a minimum and a major part of optional OpenSCENARIO features like parameters, triggers or complex coordinate systems are excluded.

### General Constraints

This subset specification only allows OpenSCENARIO XML 1.3.0 scenario definitions.
All optional elements and attributes not explicitly included in this specification are excluded.
Only explicitly included action types are allowed; all others are excluded.
Only explicitly included position types are allowed; all others are excluded.

### Included Features

#### Storyboard

The storyboard must consist of a single story.
Each scenario object's behavior must be defined by a single action.
Maximum execution count of maneuver groups and events must be set to '1'.
The priority of events must be set to 'override'; parallel events for the same scenario object are not allowed.
The storyboard stop trigger must terminate the execution after the last story ends.

#### Scenario Objects

Only scenario objects of type 'vehicle' are allowed.
Only vehicles of category 'car' are allowed.
For each car a front axle and a rear axle must be defined.

#### Actions, Trajectories and Coordinate Systems

This subset allows only trajectory-based behaviours using FollowTrajectoryAction with Polyline shape in the storyboard.
Coordinates for polyline trajectories must be defined using WorldPosition elements.
If global coordinates (e.g. UTM coordinates) are used, large values must be offset to be near the origin of the coordinate system.
The time reference domain of FollowTrajectoryAction must be set to 'absolute'.
The time reference scale must be set to '1.0'.
The time reference offset must be set to '0.0'.
The trajectory following mode must be set to 'position'.
Each vertex point of a trajectory must contain a corresponding timestamp.

### Excluded Features

This section lists certain OpenSCENARIO features that are explicitly excluded from the subset.

- InitActions (Note: Action initialization is not required for the defined set of actions in this subset.)
- Triggers with the exception of the storyboard stop trigger
- Catalogs, CatalogReference
- Parameters, ParameterDeclaration
- Variables, VariableDeclaration
- Monitors, MonitorDeclaration
- EntitySelection
- ObjectController

### Exceptions

For the successful interpretation of a scenario with specific OpenSCENARIO implementations, exceptions to the above minimal subset definition must be made.

#### esmini
Esmini requires 'InitActions' to ensure successful spawning of scenario objects.
In that case, the definition of one 'TeleportAction' with position type 'WorldPosition' per contained scenario object in 'InitActions' is allowed.

#### gt-gen-simulator
- Requires empty \<Properties/\> in vehicle definition even though not required by OpenSCENARIO.
- Requires one vehicle to be named 'Ego' or 'Host'.
- Requires a specification of a road network (e.g. OpenDRIVE map) in the scenario definition.
- Does not support StoryboardElementStateCondition to end the storyboard when the story ends.
- Stops the simulation when the last polyline point is reached with unhandled exception.

### OSC Generation

To generate a scenario from an OSI SensorView trace file, the following OSI attributes are required or the corresponding information has to be added in other ways to the scenario file:
- timestamp
- global_ground_truth / timestamp
- global_ground_truth / moving_object / id / value
- global_ground_truth / moving_object / base / dimension
- global_ground_truth / moving_object / base / position
- global_ground_truth / moving_object / base / orientation
- global_ground_truth / moving_object / vehicle_attributes / bbcenter_to_rear
- global_ground_truth / moving_object / vehicle_attributes / bbcenter_to_front
- global_ground_truth / moving_object / wheel_data / wheel_radius

The information for certain required OpenSCENARIO attributes is not covered by OSI.
This is the case for vehicle performance parameters (maximum acceleration, maximum deceleration, maximum speed) and axle information (track width).
For the above-specified minimal subset definition these attributes should not influence the scenario execution.
Nevertheless, realistic parameters are chosen and set in the scenario file.

For each scenario object's trajectory, the vertex point timestamps must match the timestamps of the OSI trace file.

## Example Scenarios

- [Shortened minimal subset scenario example](./../example/20240603T143803.535904Z_osc_pmsf_dronetracker_119_cutout_shortened.xosc).

## Validation with OSC Quality Checker

The validation of adherence to this subset specification can be checked with the corresponding extension of the OSC Quality Checker:

<https://github.com/PMSFIT/qc-openscenarioxml/tree/checker-minsubset>

## Future Extensions

- Expand on time requirements (Trajectory/Vertex timestamps), e.g. check monotonic increasing of timestamps in Quality Checker
- Include basic start and stop triggers
- Add relative timing and/or scaling for trajectories
- Add relative positioning for trajectories and other more complex position types (e.g. TrajectoryPosition to test s-/t-coordinates)
- Add trajectory follow mode 'follow'
- Add clothoid, spline, nurbs trajectories
- Add more complex actions (e.g. SpeedAction)

### Outcome for OpenSCENARIO

The following section presents issues, especially regarding the clarity of the documentation, that arose during the development of the minimal subset of OpenSCENARIO XML 1.3.0.

#### Init Actions

The OpenSCENARIO documentation does not clearly state which actions require prior initialization using InitActions.
Note: 10.3: "ASAM OpenSCENARIO does not enforce specifying the initial position and speed of entities, but it is considered best practice to do so. Most actions and conditions require those values to be set."
What does "most actions/conditions" mean?
For some actions it may not even make sense to be initialized with some position because it is not known (e.g. polyline trajectory with fixed timestamps).
Therefore, the best practice of always defining InitActions is not adequate.

#### Coordinate System Documentation

The information with which reference point a scenario object is placed in the superordinated coordinate system (e.g. a vehicle is placed at the ground projection of its rear axle) is not stated clearly in the documentation.

There should be a note that the attribute 'positionX' should always be set to 0 for a vehicle's rear axle.

#### Documentation of Storyboard Stop Trigger

8.4.7 Execution of a storyboard: "Simulation tools can use this behavior to explicitly stop the simulation." Unclear meaning.

#### Maximum Execution Count of Events

The attribute 'maximumExecutionCount' in the class Event is optional (cardinality 0..1).
A default value of '1' is defined.
It is not clearly stated that the default value of 1 applies if the attribute is not set.
There is also a default value defined for 'maximumExecutionCount' in the class ManeuverGroup which is not optional.
The general meaning of a 'default value' is unclear.

#### Inconsistent Naming

- TODO: List found issues

### Outcome for OSC Quality Checker

There should be a rule checking that all vehicles except trailers contain a front axle.
This restriction is documented in the model reference (Vehicle / Axles).

There should be a rule to check if the attribute 'positionX' is set to 0 for a vehicle's rear axle.
