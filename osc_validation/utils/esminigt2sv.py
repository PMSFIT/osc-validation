"""Converts OSI GroundTruth trace file export from esmini into OSI SensorView
trace. Also adds some fields (version, moving object ids, host vehicle id, etc.)
that are missing in the esmini export."""

import argparse
from pathlib import Path

from osi3 import osi_version_pb2, osi_sensorview_pb2

from osi_utilities import ChannelSpecification, MessageType, open_channel, open_channel_writer


def gt2sv(
    gt_channel_spec: ChannelSpecification, sv_channel_spec: ChannelSpecification
) -> ChannelSpecification:
    with (
        open_channel(gt_channel_spec) as gt_reader,
        open_channel_writer(sv_channel_spec) as sv_writer,
    ):
        for gt_msg in gt_reader:
            gt_msg.version.CopyFrom(
                osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
                    osi_version_pb2.current_interface_version
                ]
            )
            sv_msg = osi_sensorview_pb2.SensorView()
            sv_msg.sensor_id.value = 10000
            sv_msg.mounting_position.position.x = 0
            sv_msg.mounting_position.position.y = 0
            sv_msg.mounting_position.position.z = 0
            sv_msg.timestamp.CopyFrom(gt_msg.timestamp)
            sv_msg.version.CopyFrom(
                osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
                    osi_version_pb2.current_interface_version
                ]
            )
            sv_msg.host_vehicle_id.CopyFrom(gt_msg.host_vehicle_id)
            sv_msg.global_ground_truth.CopyFrom(gt_msg)
            sv_writer.write_message(sv_msg)

    return sv_writer.get_channel_specification()


def create_argparser():
    parser = argparse.ArgumentParser(
        description="Wrap OSI GroundTruth in OSI SensorView."
    )
    parser.add_argument(
        "groundtruth", help="Path to the input OSI GroundTruth trace file."
    )
    parser.add_argument(
        "sensorview", help="Path to the output OSI SensorView trace file."
    )
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    path_groundtruth = Path(args.groundtruth)
    path_sensorview = Path(args.sensorview)
    gt_trace_spec = ChannelSpecification(
        path=path_groundtruth,
        message_type=MessageType.GROUND_TRUTH,
    )
    sv_trace_spec = ChannelSpecification(
        path=path_sensorview,
        message_type=MessageType.SENSOR_VIEW,
    )
    gt2sv(gt_trace_spec, sv_trace_spec)


if __name__ == "__main__":
    main()
