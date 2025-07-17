""" Converts OSI GroundTruth trace file export from esmini into OSI SensorView
trace. Also adds some fields (version, moving object ids, host vehicle id, etc.)
that are missing in the esmini export. """

import struct
import argparse
from pathlib import Path

from osi3 import osi_version_pb2, osi_sensorview_pb2

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter

def gt2sv(gt_channel_spec: OSIChannelSpecification, sv_channel_spec: OSIChannelSpecification) -> OSIChannelSpecification:
    writer = OSIChannelWriter.from_osi_channel_specification(sv_channel_spec)
    with OSIChannelReader.from_osi_channel_specification(gt_channel_spec) as gt_reader:
        with writer as sv_writer:
            for gt_msg in gt_reader:
                gt_msg.version.CopyFrom(
                    osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
                        osi_version_pb2.current_interface_version
                    ]
                )
                # Workaround for Esmini: Esmini OSI export does not contain a
                # host vehicle id, so we set it to 0. The reference
                # implementation (osi2osc) intentionally writes the ego vehicle
                # as first scenario object which results in id 0 for the esmini
                # export based on rising enumeration starting from 0.
                gt_msg.host_vehicle_id.value = 0
                sv_msg = osi_sensorview_pb2.SensorView()
                sv_msg.timestamp.CopyFrom(gt_msg.timestamp)
                sv_msg.version.CopyFrom(
                    osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
                        osi_version_pb2.current_interface_version
                    ]
                )
                sv_msg.host_vehicle_id.CopyFrom(gt_msg.host_vehicle_id)
                sv_msg.global_ground_truth.CopyFrom(gt_msg)
                sv_writer.write(sv_msg)

    return writer.get_channel_specification()


def create_argparser():
    parser = argparse.ArgumentParser(
        description="Wrap OSI GroundTruth in OSI SensorView."
    )
    parser.add_argument("groundtruth", help="Path to the input OSI GroundTruth trace file.")
    parser.add_argument("sensorview", help="Path to the output OSI SensorView trace file.")
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    path_groundtruth = Path(args.groundtruth)
    path_sensorview = Path(args.sensorview)
    gt_trace_spec = OSIChannelSpecification(
        path=path_groundtruth,
        message_type="GroundTruth",
    )
    sv_trace_spec = OSIChannelSpecification(
        path=path_sensorview,
        message_type="SensorView",
    )
    gt2sv(gt_trace_spec, sv_trace_spec)


if __name__ == "__main__":
    main()
