from pathlib import Path
import math
import struct

import pandas as pd

from osi3 import osi_common_pb2, osi_sensordata_pb2, osi_sensorview_pb2
from osi3trace.osi_trace import OSITrace

from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSITraceWriter


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


def get_all_moving_object_ids(osi_trace: OSIChannelReader) -> list[int]:
    """
    Extracts all moving object ids in the osi trace.
    """
    moving_object_ids = []
    for message in osi_trace:
        for mo in message.global_ground_truth.moving_object:
            if not mo.id.value in moving_object_ids:
                moving_object_ids.append(mo.id.value)
    return moving_object_ids


def get_trajectory_by_moving_object_id(
    osi_trace: OSIChannelReader, moving_object_id: str
) -> pd.DataFrame:
    """
    Extracts trajectory of OSI MovingObject from OSI SensorView.
    Additionally preserves following information on the moving object in the data frame metadata:
    * id
    * length
    * width
    * height
    * moving object type
    * vehicle type

    Returns pandas data frame containing timestamp, x, y, z, h, p, r.
    """
    trajectory = {"timestamp": [], "x": [], "y": [], "z": [], "h": [], "p": [], "r": []}
    for message in osi_trace:
        for mo in message.global_ground_truth.moving_object:
            if mo.id.value == moving_object_id:
                trajectory["timestamp"].append(
                    timestamp_osi_to_float(message.timestamp)
                )
                trajectory["x"].append(mo.base.position.x)
                trajectory["y"].append(mo.base.position.y)
                trajectory["z"].append(mo.base.position.z)
                trajectory["h"].append(mo.base.orientation.yaw)
                trajectory["p"].append(mo.base.orientation.pitch)
                trajectory["r"].append(mo.base.orientation.roll)
    trajectory_df = pd.DataFrame(trajectory)
    trajectory_df.id = moving_object_id
    trajectory_df.length = mo.base.dimension.length
    trajectory_df.width = mo.base.dimension.width
    trajectory_df.height = mo.base.dimension.height
    trajectory_df.type = mo.type
    trajectory_df.vehicle_type = mo.vehicle_classification.type
    return trajectory_df


def rotatePointZYX(x,y,z,yaw,pitch,roll):
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
    rx = (cos_yaw*cos_pitch) * x + (cos_yaw*sin_pitch*sin_roll - sin_yaw*cos_roll) * y + (cos_yaw*sin_pitch*cos_roll + sin_yaw*sin_roll) * z
    ry = (sin_yaw*cos_pitch) * x + (sin_yaw*sin_pitch*sin_roll + cos_yaw*cos_roll) * y + (sin_yaw*sin_pitch*cos_roll - cos_yaw*sin_roll) * z
    rz = (-sin_pitch)        * x + (cos_pitch*sin_roll)                            * y + (cos_pitch*cos_roll)                            * z

    return (rx,ry,rz)


def rotatePointXYZ(x,y,z,yaw,pitch,roll):
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
    rx = (cos_pitch*cos_yaw)                              * x + (-cos_pitch*sin_yaw)                             * y + (sin_pitch)           * z
    ry = (sin_roll*sin_pitch*cos_yaw + cos_roll*sin_yaw)  * x + (-sin_roll*sin_pitch*sin_yaw + cos_roll*cos_yaw) * y + (-sin_roll*cos_pitch) * z
    rz = (-cos_roll*sin_pitch*cos_yaw + sin_roll*sin_yaw) * x + (cos_roll*sin_pitch*sin_yaw + sin_roll*cos_yaw)  * y + (cos_roll*cos_pitch)  * z

    return (rx,ry,rz)


def crop_trace(input_trace: OSIChannelReader, output_trace_path: Path, start_time: float = None, end_time: float = None) -> Path:
    """
    Crops the content of an input OSI trace based on the given inclusive interval and stores it
    at the given output path.

    Args:
        input (OSIChannelReader): OSI channel reader for the input OSI trace
        output (Path): Path to the output OSI trace
        start_time (float, optional): Start time of the inclusive interval
        end_time (float, optional): End time of the inclusive interval
    Returns:
        Path to the output OSI trace
    """
    with input_trace as reader, OSITraceWriter(output_trace_path, input_trace.get_file_metadata()) as writer:
        writer.add_osi_channel(osi_sensorview_pb2.SensorView, input_trace.get_topic_name(), input_trace.get_channel_metadata())
        for message in reader:
            message_time = timestamp_osi_to_float(message.timestamp)
            if (start_time is None or message_time >= start_time) and (end_time is None or message_time <= end_time):
                writer.write(message, reader.get_topic_name())
    return output_trace_path
