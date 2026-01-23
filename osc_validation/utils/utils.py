from pathlib import Path
import math

import pandas as pd

from osi3 import osi_common_pb2, osi_sensordata_pb2
from osi3trace.osi_trace import OSITrace

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter


def timestamp_osi_to_float(osi_timestamp: osi_common_pb2.Timestamp) -> float:
    return (osi_timestamp.seconds * 1000000000 + osi_timestamp.nanos) / 1000000000


def timestamp_float_to_osi(float_timestamp: float) -> osi_common_pb2.Timestamp:
    osi_timestamp = osi_common_pb2.Timestamp()
    osi_timestamp.seconds = math.floor(float_timestamp)
    osi_timestamp.nanos = int(
        (float_timestamp - math.floor(float_timestamp)) * 1000000000
    )
    return osi_timestamp


def sensordata_timestamp_osi_to_list(osi_sensordata_trace: OSITrace) -> list[float]:
    """
    Extracts all timestamps from OSI SensorData trace.

    Returns list with float timestamps.
    """
    assert isinstance(osi_sensordata_trace, osi_sensordata_pb2.SensorData)
    osi_sensordata_trace.restart()
    timestamp_list = []
    for message in osi_sensordata_trace:
        timestamp_list.append(timestamp_osi_to_float(message.timestamp))
    return timestamp_list


def sensordata_last_measurement_time_osi_to_list(
    osi_sensordata_trace: OSITrace,
) -> list[float]:
    """
    Extracts all last_measurement_time timestamps from OSI SensorData trace.

    Returns list with float timestamps.
    """
    assert isinstance(osi_sensordata_trace, osi_sensordata_pb2.SensorData)
    osi_sensordata_trace.restart()
    timestamp_list = []
    for message in osi_sensordata_trace:
        timestamp_list.append(timestamp_osi_to_float(message.last_measurement_time))
    return timestamp_list


def trajectory_df_info(trajectory_df):
    print(trajectory_df)
    print("number of frames:    " + str(len(trajectory_df)))
    print(
        "start/end:           "
        + str(trajectory_df["timestamp"].iloc[0])
        + "/"
        + str(trajectory_df["timestamp"].iloc[-1])
    )
    print(
        "avg step size:       "
        + str(
            (trajectory_df["timestamp"].iloc[-1] - trajectory_df["timestamp"].iloc[0])
            / len(trajectory_df)
        )
    )
    print("-------------------------------------------------------")


def get_all_moving_object_ids(osi_trace: OSIChannelSpecification) -> list[int]:
    """
    Extracts all moving object ids from the input OSI SensorView or GroundTruth trace.
    """
    assert osi_trace.message_type in ("SensorView", "GroundTruth")
    moving_object_ids = []
    for message in OSIChannelReader.from_osi_channel_specification(osi_trace):
        osi_moving_objects = (
            message.global_ground_truth.moving_object
            if osi_trace.message_type == "SensorView"
            else message.moving_object
        )
        for mo in osi_moving_objects:
            if not mo.id.value in moving_object_ids:
                moving_object_ids.append(mo.id.value)
    return moving_object_ids


def get_trajectory_by_moving_object_id(
    osi_trace: OSIChannelSpecification,
    moving_object_id: str,
    start_time: float = None,
    end_time: float = None,
) -> pd.DataFrame:
    """
    Extracts trajectory of OSI MovingObject from the input OSI SensorView or GroundTruth trace in the optionally
    specified interval.

    Additionally preserves following information on the moving object in the data frame attrs metadata:
    * id
    * length
    * width
    * height
    * moving object type
    * vehicle type

    Returns pandas data frame containing timestamp, x, y, z, h, p, r.
    """
    assert osi_trace.message_type in ("SensorView", "GroundTruth")
    trajectory = {"timestamp": [], "x": [], "y": [], "z": [], "h": [], "p": [], "r": []}
    object_metadata = {}
    for message in OSIChannelReader.from_osi_channel_specification(osi_trace):
        osi_moving_objects = (
            message.global_ground_truth.moving_object
            if osi_trace.message_type == "SensorView"
            else message.moving_object
        )
        current_timestamp = timestamp_osi_to_float(message.timestamp)
        if start_time is not None and current_timestamp < start_time:
            continue
        if end_time is not None and current_timestamp > end_time:
            continue
        for mo in osi_moving_objects:
            if mo.id.value != moving_object_id:
                continue
            trajectory["timestamp"].append(current_timestamp)
            trajectory["x"].append(mo.base.position.x)
            trajectory["y"].append(mo.base.position.y)
            trajectory["z"].append(mo.base.position.z)
            trajectory["h"].append(mo.base.orientation.yaw)
            trajectory["p"].append(mo.base.orientation.pitch)
            trajectory["r"].append(mo.base.orientation.roll)
            if not object_metadata:
                object_metadata = {
                    "id": moving_object_id,
                    "length": mo.base.dimension.length,
                    "width": mo.base.dimension.width,
                    "height": mo.base.dimension.height,
                    "type": mo.type,
                    "vehicle_type": mo.vehicle_classification.type,
                }
    trajectory_df = pd.DataFrame(trajectory)
    if object_metadata:
        trajectory_df.attrs.update(object_metadata)
    return trajectory_df


def get_closest_trajectory(
    ref_trajectory: pd.DataFrame,
    tool_channel_spec: OSIChannelSpecification,
    start_time: float = None,
    end_time: float = None,
) -> pd.DataFrame:
    """
    Finds the tool trajectory that is closest to the reference trajectory based on the starting position.
    Args:
        ref_trajectory (pd.DataFrame): Reference trajectory DataFrame containing columns ['timestamp', 'x', 'y', 'z', 'h', 'p', 'r'].
        tool_channel_spec (OSIChannelSpecification): OSI channel specification for the tool trace.
        start_time (float, optional): Start time of the inclusive interval. Defaults to None.
        end_time (float, optional): End time of the inclusive interval. Defaults to None.
    Returns:
        pd.DataFrame: The trajectory DataFrame of the tool trace that is closest to the reference trajectory.
    """

    tool_moving_object_ids = get_all_moving_object_ids(tool_channel_spec)
    tool_trajectories = {
        obj_id: get_trajectory_by_moving_object_id(
            tool_channel_spec, obj_id, start_time, end_time
        )
        for obj_id in tool_moving_object_ids
    }

    tool_trajectory = None
    min_distance = None
    for obj_id, tool_trajectory in tool_trajectories.items():
        ref_start = ref_trajectory.iloc[0][["x", "y"]].values
        tool_start = tool_trajectory.iloc[0][["x", "y"]].values
        dx = ref_start[0] - tool_start[0]
        dy = ref_start[1] - tool_start[1]
        distance = math.hypot(dx, dy)
        if min_distance is None or distance < min_distance:
            min_distance = distance
            nearest_tool_trajectory = tool_trajectory
        tool_trajectory = nearest_tool_trajectory

    return tool_trajectory


def rotatePointZYX(x, y, z, yaw, pitch, roll):
    """Performs a rotation of the given coordinate based on given euler rotation angles.
    Rotation order:
    1. yaw (around z-axis)
    2. pitch (around y-axis)
    3. roll (around x-axis)

    Parameters:
    * x,y,z             input coordinate
    * yaw,pitch,roll    rotation angle

    Returns:
    * rx,ry,rz          rotated coordinate
    """
    cos_yaw = math.cos(yaw)
    cos_pitch = math.cos(pitch)
    cos_roll = math.cos(roll)
    sin_yaw = math.sin(yaw)
    sin_pitch = math.sin(pitch)
    sin_roll = math.sin(roll)

    # rotation order z-y-x
    rx = (
        (cos_yaw * cos_pitch) * x
        + (cos_yaw * sin_pitch * sin_roll - sin_yaw * cos_roll) * y
        + (cos_yaw * sin_pitch * cos_roll + sin_yaw * sin_roll) * z
    )
    ry = (
        (sin_yaw * cos_pitch) * x
        + (sin_yaw * sin_pitch * sin_roll + cos_yaw * cos_roll) * y
        + (sin_yaw * sin_pitch * cos_roll - cos_yaw * sin_roll) * z
    )
    rz = (-sin_pitch) * x + (cos_pitch * sin_roll) * y + (cos_pitch * cos_roll) * z

    return (rx, ry, rz)


def rotatePointXYZ(x, y, z, yaw, pitch, roll):
    """Performs a rotation of the given coordinate based on given euler rotation angles.
    Rotation order:
    1. roll (around x-axis)
    2. pitch (around y-axis)
    3. yaw (around z-axis)

    Parameters:
    * x,y,z             input coordinate
    * yaw,pitch,roll    rotation angle

    Returns:
    * rx,ry,rz          rotated coordinate
    """
    cos_yaw = math.cos(yaw)
    cos_pitch = math.cos(pitch)
    cos_roll = math.cos(roll)
    sin_yaw = math.sin(yaw)
    sin_pitch = math.sin(pitch)
    sin_roll = math.sin(roll)

    # rotation order x-y-z
    rx = (cos_pitch * cos_yaw) * x + (-cos_pitch * sin_yaw) * y + (sin_pitch) * z
    ry = (
        (sin_roll * sin_pitch * cos_yaw + cos_roll * sin_yaw) * x
        + (-sin_roll * sin_pitch * sin_yaw + cos_roll * cos_yaw) * y
        + (-sin_roll * cos_pitch) * z
    )
    rz = (
        (-cos_roll * sin_pitch * cos_yaw + sin_roll * sin_yaw) * x
        + (cos_roll * sin_pitch * sin_yaw + sin_roll * cos_yaw) * y
        + (cos_roll * cos_pitch) * z
    )

    return (rx, ry, rz)


def crop_trace(
    input_channel_spec: OSIChannelSpecification,
    output_channel_spec: OSIChannelSpecification,
    start_time: float = None,
    end_time: float = None,
) -> OSIChannelSpecification:
    """
    Crops the content of an input OSI trace based on the given inclusive interval and stores it
    at the given output path.

    Args:
        input_channel_spec (OSIChannelSpecification): OSI channel specification for the input OSI trace
        output_channel_spec (OSIChannelSpecification): OSI channel specification for the output OSI trace
        start_time (float, optional): Start time of the inclusive interval
        end_time (float, optional): End time of the inclusive interval
    Returns:
        Specification of the output OSI channel.
    """
    input_trace_reader = OSIChannelReader.from_osi_channel_specification(
        input_channel_spec
    )
    output_trace_writer = OSIChannelWriter.from_osi_channel_specification(
        output_channel_spec
    )
    with input_trace_reader as channel_reader, output_trace_writer as channel_writer:
        for message in channel_reader:
            message_time = timestamp_osi_to_float(message.timestamp)
            if (start_time is None or message_time >= start_time) and (
                end_time is None or message_time <= end_time
            ):
                channel_writer.write(message)
    return output_trace_writer.get_channel_specification()
