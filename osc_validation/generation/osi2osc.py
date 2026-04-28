import argparse
from datetime import datetime
from pathlib import Path
from typing import Literal, Union
import logging
import sys

import pandas as pd
from lxml import etree

from osi3 import osi_object_pb2

from osi_utilities import ChannelSpecification, MessageType, open_channel
from osc_validation.utils.utils import timestamp_osi_to_float, rotatePointZYX
from .init_transforms import compute_close_to_trajectory_start_xy
from .init_transforms.models import InitPoseOverride

XOSC_VERSION_MAJOR = 1
XOSC_VERSION_MINOR = 3
XOSC_AUTHOR = "OSC Validation OSI2OSC Converter"
XOSC_DESCRIPTION = ""
XOSC_LICENSE = ""
XOSC_LICENSE_RESOURCE = ""

# config parameters for osc structure
STOPTRIGGER = True
STOPTRIGGER_CONDITION = "SimulationTimeCondition"  # StoryboardElementStateCondition / SimulationTimeCondition
INITACTIONS = True


class OSI2OSCMovingObject:
    """
    Class containing relevant data to convert from OSI to OpenSCENARIO
    """

    osi_vehicle_type_to_osc_category: dict[int, str | None] = {
        0: None,  # unknown
        1: None,  # other
        2: "car",  # small car
        3: "car",  # compact car
        4: "car",  # car
        5: "car",  # luxury car
        6: "van",  # delivery van
        7: "truck",  # heavy truck
        8: None,  # semitrailer
        9: "trailer",  # trailer
        10: "motorbike",  # motorbike
        11: "bicycle",  # bicycle
        12: "bus",  # bus
        13: "tram",  # tram
        14: "train",  # train
        15: None,  # wheelchair
        16: None,  # semitractor
        17: None,  # standup scooter
    }
    """OSI 3.7.0 to OpenSCENARIO XML 1.3.0 Mapping"""

    def __init__(
        self,
        id: str,
        length_static: float,
        width_static: float,
        height_static: float,
        type: osi_object_pb2.MovingObject.Type,
        vehicle_type: osi_object_pb2.MovingObject.VehicleClassification.Type,  # TODO: pedestrians
        bbcenter_to_rear_x: Union[float, None] = None,
        bbcenter_to_rear_y: Union[float, None] = None,
        bbcenter_to_rear_z: Union[float, None] = None,
        host_vehicle: bool = False,
    ):
        self.id = id
        self.entity_ref = (
            f"osi_moving_object_{self.id}" if not host_vehicle else "Ego"
        )  # name of ScenarioObject
        self.length_static = length_static
        self.width_static = width_static
        self.height_static = height_static
        self.type = type
        self.vehicle_type = vehicle_type
        self.trajectory = pd.DataFrame(
            columns=["timestamp", "x", "y", "z", "h", "p", "r"]
        )
        if (
            bbcenter_to_rear_x == None
            and bbcenter_to_rear_y == None
            and bbcenter_to_rear_z == None
        ):
            self.bbcenter_to_rear_x = -self.length_static * 0.3  # default
            self.bbcenter_to_rear_y = 0  # default
            self.bbcenter_to_rear_z = -self.height_static * 0.5  # default
        elif (
            bbcenter_to_rear_x != None
            and bbcenter_to_rear_y != None
            and bbcenter_to_rear_z != None
        ):
            self.bbcenter_to_rear_x = bbcenter_to_rear_x
            self.bbcenter_to_rear_y = bbcenter_to_rear_y
            self.bbcenter_to_rear_z = bbcenter_to_rear_z
        else:
            raise RuntimeError("Problem with bbcenter_to_rear")

    def append_trajectory_row(self, timestamp, x, y, z, h, p, r):
        """Appends a new dataframe row to build a full trajectory.

        Positions are given in OSI coordinates and describe the center of the
        bounding box of the object.
        """
        new_row = pd.DataFrame(
            {
                "timestamp": [timestamp],
                "x": [x],
                "y": [y],
                "z": [z],
                "h": [h],
                "p": [p],
                "r": [r],
            }
        )
        if self.trajectory.empty:
            self.trajectory = new_row
        else:
            self.trajectory = pd.concat(
                [self.trajectory, new_row],
                ignore_index=True,
            )

    def build_osc_scenario_object(self):
        """
        Return OpenSCENARIO XML ScenarioObject element for this moving object
        """
        osc_vehicle_category = self.osi_vehicle_type_to_osc_category[self.vehicle_type]
        xml_scenario_object = etree.Element("ScenarioObject", name=self.entity_ref)
        assert (
            osc_vehicle_category != None
        ), "Missing OSI2OSC mapping for vehicle category."
        xml_vehicle = etree.SubElement(
            xml_scenario_object,
            "Vehicle",
            name=f"osi_moving_object_vehicle_{self.id}",
            vehicleCategory=osc_vehicle_category,
        )
        xml_bounding_box = etree.SubElement(xml_vehicle, "BoundingBox")
        xml_center = etree.SubElement(
            xml_bounding_box,
            "Center",
            x=str(-self.bbcenter_to_rear_x),
            y=str(-self.bbcenter_to_rear_y),
            z=str(self.height_static / 2),
        )
        xml_dimensions = etree.SubElement(
            xml_bounding_box,
            "Dimensions",
            height=str(self.height_static),
            length=str(self.length_static),
            width=str(self.width_static),
        )
        xml_performance = etree.SubElement(
            xml_vehicle,
            "Performance",
            maxAcceleration="4",
            maxDeceleration="9",
            maxSpeed="250",
        )
        xml_axles = etree.SubElement(xml_vehicle, "Axles")
        xml_front_axle = etree.SubElement(
            xml_axles,
            "FrontAxle",
            maxSteering="0.5",
            positionX="2.7",
            positionZ="0.4",
            trackWidth="1.63",
            wheelDiameter="0.8",
        )
        xml_rear_axle = etree.SubElement(
            xml_axles,
            "RearAxle",
            maxSteering="0.5",
            positionX="0",
            positionZ="0.4",
            trackWidth="1.63",
            wheelDiameter="0.8",
        )
        return xml_scenario_object

    def build_osc_polyline_trajectory(self):
        """
        Return OpenSCENARIO XML Trajectory element for this moving object
        """
        self.osc_trajectory_name = f"osi_moving_object_vehicle_{self.id}_trajectory"
        xml_trajectory = etree.Element(
            "Trajectory", closed="false", name=self.osc_trajectory_name
        )
        xml_shape = etree.SubElement(xml_trajectory, "Shape")
        xml_polyline = etree.SubElement(xml_shape, "Polyline")
        for i, point in self.trajectory.iterrows():
            xml_vertex = etree.SubElement(
                xml_polyline, "Vertex", time=str(point["timestamp"])
            )
            xml_position = etree.SubElement(xml_vertex, "Position")
            x, y, z, h, p, r = self._to_world_position(point)
            xml_world_position = etree.SubElement(
                xml_position,
                "WorldPosition",
                x=str(x),
                y=str(y),
                z=str(z),
                h=str(h),
                p=str(p),
                r=str(r),
            )
        return xml_trajectory

    def _to_world_position(self, point):
        x = point["x"]
        y = point["y"]
        z = point["z"]
        h = point["h"]
        p = point["p"]
        r = point["r"]
        rx, ry, rz = rotatePointZYX(
            self.bbcenter_to_rear_x,
            self.bbcenter_to_rear_y,
            -self.height_static / 2,  # projection onto ground plane of bounding box
            h,
            p,
            r,
        )
        x = x + rx
        y = y + ry
        z = z + rz
        return x, y, z, h, p, r

    def build_trajectory_start_override(self) -> InitPoseOverride:
        if self.trajectory.empty:
            raise RuntimeError(
                f"Object '{self.entity_ref}' has no trajectory samples."
            )
        first_point = self.trajectory.iloc[0]
        x, y, z, h, p, r = self._to_world_position(first_point)
        return InitPoseOverride(
            entity_ref=self.entity_ref,
            object_id=int(self.id),
            x=float(x),
            y=float(y),
            z=float(z),
            yaw=float(h),
            pitch=float(p),
            roll=float(r),
        )

    def build_act(self):
        """
        Return OpenSCENARIO XML Act element for this moving object

        Uses self.build_osc_polyline_trajectory to embed the corresponding trajectory.

        Creates one Act per object as follows:
        <Act name="x">
            <ManeuverGroup name="x">
                <Actors>
                    <EntityRef entityRef="<self.entity_ref>" />
                </Actors>
                <Maneuver name="x">
                    <Event name="x">
                        <Action name="x">
                            <PrivateAction>
                                <RoutingAction>
                                    <FollowTrajectoryAction>
                                        <TrajectoryRef>
                                            <Trajectory closed="false" name="x">
                                            ...
        """
        xml_act = etree.Element("Act", name=f"osi_moving_object_vehicle_{self.id}_act")
        xml_maneuver_group = etree.SubElement(
            xml_act,
            "ManeuverGroup",
            name=f"osi_moving_object_vehicle_{self.id}_maneuvergroup",
            maximumExecutionCount="1",
        )
        xml_actors = etree.SubElement(
            xml_maneuver_group, "Actors", selectTriggeringEntities="false"
        )
        xml_entity_ref1 = etree.SubElement(
            xml_actors, "EntityRef", entityRef=self.entity_ref
        )
        xml_maneuver = etree.SubElement(
            xml_maneuver_group, "Maneuver", name=f"{self.entity_ref}_maneuver"
        )
        xml_event = etree.SubElement(
            xml_maneuver,
            "Event",
            name=f"{self.entity_ref}_maneuver_event",
            priority="override",
        )
        xml_action = etree.SubElement(
            xml_event, "Action", name=f"{self.entity_ref}_maneuver_event_action"
        )
        xml_private_action = etree.SubElement(xml_action, "PrivateAction")
        xml_routing_action = etree.SubElement(xml_private_action, "RoutingAction")
        xml_follow_trajectory_action = etree.SubElement(
            xml_routing_action, "FollowTrajectoryAction"
        )
        xml_trajectory_ref = etree.SubElement(
            xml_follow_trajectory_action, "TrajectoryRef"
        )
        xml_time_reference = etree.SubElement(
            xml_follow_trajectory_action, "TimeReference"
        )
        xml_timing = etree.SubElement(
            xml_time_reference,
            "Timing",
            domainAbsoluteRelative="relative",
            offset="0.0",
            scale="1.0",
        )
        xml_trajectory_following_mode = etree.SubElement(
            xml_follow_trajectory_action,
            "TrajectoryFollowingMode",
            followingMode="position",
        )
        xml_trajectory = self.build_osc_polyline_trajectory()
        xml_trajectory_ref.append(xml_trajectory)
        return xml_act

    def build_init_action(self, init_pose: InitPoseOverride):
        xml_private = etree.Element("Private", entityRef=self.entity_ref)
        xml_private_action = etree.SubElement(xml_private, "PrivateAction")
        xml_teleport_action = etree.SubElement(xml_private_action, "TeleportAction")
        xml_position = etree.SubElement(xml_teleport_action, "Position")
        xml_world_position = etree.SubElement(
            xml_position,
            "WorldPosition",
            x=str(init_pose.x),
            y=str(init_pose.y),
            z=str(init_pose.z),
            h=str(init_pose.yaw),
            p=str(init_pose.pitch),
            r=str(init_pose.roll),
        )
        return xml_private


def parse_moving_objects(
    osi_trace_spec: ChannelSpecification, host_vehicle_id: int | None
) -> list[OSI2OSCMovingObject]:
    """
    Extracts all moving objects from an OSI SensorView or GroundTruth trace.
    """
    my_moving_objects = []
    with open_channel(osi_trace_spec) as channel_reader:
        message_type = channel_reader.get_channel_specification().message_type
        assert message_type in (MessageType.SENSOR_VIEW, MessageType.GROUND_TRUTH)
        for osi_message in channel_reader:
            current_timestamp = timestamp_osi_to_float(osi_message.timestamp)
            osi_moving_object_list = (
                osi_message.global_ground_truth.moving_object
                if message_type == MessageType.SENSOR_VIEW
                else osi_message.moving_object
            )
            for osi_moving_object in osi_moving_object_list:
                current_moving_object_id = osi_moving_object.id.value
                if not any(
                    obj.id == current_moving_object_id for obj in my_moving_objects
                ):
                    object_to_add = OSI2OSCMovingObject(
                        id=current_moving_object_id,
                        length_static=osi_moving_object.base.dimension.length,  # use first occurrence
                        width_static=osi_moving_object.base.dimension.width,  # use first occurrence
                        height_static=osi_moving_object.base.dimension.height,  # use first occurrence
                        type=osi_moving_object.type,
                        vehicle_type=osi_moving_object.vehicle_classification.type,
                        bbcenter_to_rear_x=osi_moving_object.vehicle_attributes.bbcenter_to_rear.x,
                        bbcenter_to_rear_y=osi_moving_object.vehicle_attributes.bbcenter_to_rear.y,
                        bbcenter_to_rear_z=osi_moving_object.vehicle_attributes.bbcenter_to_rear.z,
                        host_vehicle=(osi_moving_object.id.value == host_vehicle_id),
                    )
                    object_to_add.append_trajectory_row(
                        current_timestamp,
                        osi_moving_object.base.position.x,
                        osi_moving_object.base.position.y,
                        osi_moving_object.base.position.z,
                        osi_moving_object.base.orientation.yaw,
                        osi_moving_object.base.orientation.pitch,
                        osi_moving_object.base.orientation.roll,
                    )
                    my_moving_objects.append(object_to_add)
                else:
                    object_to_modify = next(
                        (
                            obj
                            for obj in my_moving_objects
                            if obj.id == current_moving_object_id
                        ),
                        None,
                    )
                    object_to_modify.append_trajectory_row(
                        current_timestamp,
                        osi_moving_object.base.position.x,
                        osi_moving_object.base.position.y,
                        osi_moving_object.base.position.z,
                        osi_moving_object.base.orientation.yaw,
                        osi_moving_object.base.orientation.pitch,
                        osi_moving_object.base.orientation.roll,
                    )
    return my_moving_objects


def osi2osc(
    osi_trace_spec: ChannelSpecification,
    path_xosc: Path,
    path_xodr: Path = None,
    init_pose_policy: Literal[
        "origin",
        "from_trajectory_start",
        "close_to_trajectory_start",
    ] = "origin",
    init_pose_close_threshold_m: float | None = None,
) -> Path:
    """
    Converts an OSI GroundTruth or SensorView trace to an OpenSCENARIO XML file
    at the specified path.

    Args:
        osi_trace_spec (ChannelSpecification): Input OSI trace file.
        path_xosc (Path): Output OpenSCENARIO file path.
        path_xodr (Path, optional): Optional OpenDRIVE map path to be integrated in the output OpenSCENARIO file.
        init_pose_policy: Optional init pose policy. Default "origin" preserves
            converter defaults (`0,0,0` teleport init).
        init_pose_close_threshold_m: Threshold distance in meters for the "close_to_trajectory_start" init pose policy. Default is 0.5 meters.
    Returns:
        Path: Valid path to the output OpenSCENARIO file if the conversion was successful.
    Raises:
        AssertionError: If the input OSI trace is not of type SensorView or GroundTruth.
    """

    with open_channel(osi_trace_spec) as osi_trace_channel_reader:
        resolved_spec = osi_trace_channel_reader.get_channel_specification()
        assert resolved_spec.message_type in (
            MessageType.SENSOR_VIEW,
            MessageType.GROUND_TRUTH,
        )
        osi_trace_iterator = iter(osi_trace_channel_reader)
        msg = next(osi_trace_iterator, None)
        if msg is None:
            raise ValueError(f"Input OSI trace ({resolved_spec.path}) is empty.")
        stop_timestamp = timestamp_osi_to_float(msg.timestamp)
        for stop_message in osi_trace_iterator:
            stop_timestamp = timestamp_osi_to_float(stop_message.timestamp)
        host_vehicle_id = msg.host_vehicle_id.value if msg else None
        if host_vehicle_id is None:
            logging.warning(
                f"Input OSI trace ({resolved_spec.path}) has no specified host_vehicle_id. The output OpenSCENARIO file will not have a specified ego vehicle."
            )

    my_moving_objects = parse_moving_objects(osi_trace_spec, host_vehicle_id)
    # Order objects so that Ego is always added first (in entities and init actions)
    ego_objs = [obj for obj in my_moving_objects if obj.entity_ref == "Ego"]
    other_objs = [obj for obj in my_moving_objects if obj.entity_ref != "Ego"]
    my_moving_objects = ego_objs + other_objs

    xml_scenario_objects = []
    xml_acts = []
    for obj in my_moving_objects:
        xml_scenario_objects.append(obj.build_osc_scenario_object())
        xml_acts.append(obj.build_act())

    xml_root = etree.Element("OpenSCENARIO")
    xml_file_header = etree.SubElement(
        xml_root,
        "FileHeader",
        revMajor=str(XOSC_VERSION_MAJOR),
        revMinor=str(XOSC_VERSION_MINOR),
        date=datetime.today().strftime("%Y-%m-%dT%H:%M:%S"),
        author=XOSC_AUTHOR,
        description=XOSC_DESCRIPTION,
    )
    xml_license = etree.SubElement(
        xml_file_header, "License", name=XOSC_LICENSE, resource=XOSC_LICENSE_RESOURCE
    )
    xml_catalog_locations = etree.SubElement(xml_root, "CatalogLocations")
    xml_road_network = etree.SubElement(xml_root, "RoadNetwork")
    if path_xodr is not None:
        xml_road_network.append(etree.Element("LogicFile", filepath=str(path_xodr)))
    xml_entities = etree.SubElement(xml_root, "Entities")
    for xml_scenario_object in xml_scenario_objects:
        xml_entities.append(xml_scenario_object)
    xml_storyboard = etree.SubElement(xml_root, "Storyboard")
    xml_init = etree.SubElement(xml_storyboard, "Init")
    xml_init_actions = etree.SubElement(xml_init, "Actions")
    if INITACTIONS:
        for obj in my_moving_objects:
            origin_override = InitPoseOverride(
                entity_ref=obj.entity_ref,
                object_id=int(obj.id),
                x=0.0,
                y=0.0,
                z=0.0,
                yaw=0.0,
                pitch=0.0,
                roll=0.0,
            )
            if init_pose_policy == "origin":
                resolved_override = origin_override
            elif init_pose_policy == "from_trajectory_start":
                trajectory_start_override = obj.build_trajectory_start_override()
                resolved_override = InitPoseOverride(
                    entity_ref=origin_override.entity_ref,
                    object_id=origin_override.object_id,
                    x=trajectory_start_override.x,
                    y=trajectory_start_override.y,
                    z=trajectory_start_override.z,
                    yaw=trajectory_start_override.yaw,
                    pitch=trajectory_start_override.pitch,
                    roll=trajectory_start_override.roll,
                )
            elif init_pose_policy == "close_to_trajectory_start":
                if init_pose_close_threshold_m is None:
                    init_pose_close_threshold_m = 0.5
                trajectory_start_override = obj.build_trajectory_start_override()
                target_x, target_y = compute_close_to_trajectory_start_xy(
                    init_x=origin_override.x,
                    init_y=origin_override.y,
                    start_x=trajectory_start_override.x,
                    start_y=trajectory_start_override.y,
                    threshold_m=init_pose_close_threshold_m,
                )
                resolved_override = InitPoseOverride(
                    entity_ref=origin_override.entity_ref,
                    object_id=origin_override.object_id,
                    x=target_x,
                    y=target_y,
                    z=trajectory_start_override.z,
                    yaw=trajectory_start_override.yaw,
                    pitch=trajectory_start_override.pitch,
                    roll=trajectory_start_override.roll,
                )
            else:
                raise ValueError(f"Unsupported init_pose_policy '{init_pose_policy}'.")
            xml_init_actions.append(
                obj.build_init_action(resolved_override)
            )
    story_name = "Story1"
    xml_story = etree.SubElement(xml_storyboard, "Story", name=story_name)
    for xml_act in xml_acts:
        xml_story.append(xml_act)
    if STOPTRIGGER:
        if STOPTRIGGER_CONDITION == "StoryboardElementStateCondition":
            xml_storyboard_stop_trigger = etree.SubElement(
                xml_storyboard, "StopTrigger"
            )
            xml_stop_trigger_condition_group = etree.SubElement(
                xml_storyboard_stop_trigger, "ConditionGroup"
            )
            xml_stop_trigger_condition = etree.SubElement(
                xml_stop_trigger_condition_group,
                "Condition",
                name="QuitCondition",
                delay="0",
                conditionEdge="rising",
            )
            xml_stop_trigger_byvalue_condition = etree.SubElement(
                xml_stop_trigger_condition, "ByValueCondition"
            )
            xml_stop_trigger_state_condition = etree.SubElement(
                xml_stop_trigger_byvalue_condition,
                "StoryboardElementStateCondition",
                storyboardElementType="story",
                storyboardElementRef=story_name,
                state="completeState",
            )
        elif STOPTRIGGER_CONDITION == "SimulationTimeCondition":
            xml_storyboard_stop_trigger = etree.SubElement(
                xml_storyboard, "StopTrigger"
            )
            xml_stop_trigger_condition_group = etree.SubElement(
                xml_storyboard_stop_trigger, "ConditionGroup"
            )
            xml_stop_trigger_condition = etree.SubElement(
                xml_stop_trigger_condition_group,
                "Condition",
                name="End",
                delay="0",
                conditionEdge="rising",
            )
            xml_stop_trigger_byvalue_condition = etree.SubElement(
                xml_stop_trigger_condition, "ByValueCondition"
            )
            xml_stop_trigger_simulation_time_condition = etree.SubElement(
                xml_stop_trigger_byvalue_condition,
                "SimulationTimeCondition",
                value=str(stop_timestamp),
                rule="greaterOrEqual",
            )

    xml_tree = etree.ElementTree(xml_root)
    xml_tree.write(path_xosc, encoding="utf-8", xml_declaration=True, pretty_print=True)
    return path_xosc


def create_argparser():
    parser = argparse.ArgumentParser(
        description="Convert an OSI GroundTruth or SensorView trace file to an OpenScenario XML file."
    )
    parser.add_argument(
        "ositrace",
        help="Path to the input OSI SensorView or OSI GroundTruth trace file.",
    )
    parser.add_argument(
        "ositype",
        help="Type of the input OSI trace.",
        choices=["SensorView", "GroundTruth"],
    )
    parser.add_argument("xosc", help="Path to the output OpenScenario XML file.")
    parser.add_argument(
        "--init-pose-policy",
        choices=["origin", "from_trajectory_start", "close_to_trajectory_start"],
        default="origin",
        help=(
            "Optional init pose policy. "
            "'origin' preserves default converter init positions (0,0,0)."
        ),
    )
    parser.add_argument(
        "--init-pose-close-threshold-m",
        type=float,
        default=None,
        help=(
            "Maximum XY distance from trajectory start when using "
            "--init-pose-policy close_to_trajectory_start."
        ),
    )
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    try:
        path_ositrace = Path(args.ositrace)
        if not path_ositrace.exists():
            raise FileNotFoundError(
                f"Input OSI trace file '{path_ositrace}' does not exist."
            )

        osi_trace_spec = ChannelSpecification(
            path=path_ositrace,
            message_type=(
                MessageType.SENSOR_VIEW
                if args.ositype == "SensorView"
                else MessageType.GROUND_TRUTH
            ),
        )
        path_xosc = Path(args.xosc)
        osi2osc(
            osi_trace_spec=osi_trace_spec,
            path_xosc=path_xosc,
            init_pose_policy=args.init_pose_policy,
            init_pose_close_threshold_m=args.init_pose_close_threshold_m,
        )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0
