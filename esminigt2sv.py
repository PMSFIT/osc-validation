""" Converts OSI GroundTruth trace file export from esmini into OSI SensorView
trace. Also adds some fields (version, moving object ids, host vehicle id, etc.)
that are missing in the esmini export. """

import struct
import argparse

from osi3 import osi_version_pb2, osi_groundtruth_pb2, osi_sensorview_pb2
from osi3trace.osi_trace import OSITrace


def cli():
    parser = argparse.ArgumentParser(
        description="Wrap OSI GroundTruth in OSI SensorView.",
        prog="osigt2sv",
    )
    parser.add_argument("groundtruth", help="Path to the input OSI GroundTruth trace file.")
    parser.add_argument("sensorview", help="Path to the output OSI SensorView trace file.")
    return parser.parse_args()


args = cli()

trace = OSITrace(args.groundtruth, "GroundTruth")

sv_output_file = open(args.sensorview, "ab")
for i, gt_msg in enumerate(trace):
    # fix gt stuff
    gt_msg.version.CopyFrom(
        osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
            osi_version_pb2.current_interface_version
        ]
    )
    gt_msg.host_vehicle_id.value = 1
    id = 1
    for mo in gt_msg.moving_object:
        mo.id.value = id
        id = id+1
    # create sv wrapper
    sv_msg = osi_sensorview_pb2.SensorView()
    sv_msg.timestamp.CopyFrom(gt_msg.timestamp)
    sv_msg.version.CopyFrom(
        osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
            osi_version_pb2.current_interface_version
        ]
    )
    sv_msg.host_vehicle_id.CopyFrom(gt_msg.host_vehicle_id)
    # serialize and write to file
    sv_msg.global_ground_truth.CopyFrom(gt_msg)
    bytes_buffer = sv_msg.SerializeToString()
    sv_output_file.write(struct.pack("<L", len(bytes_buffer)))
    sv_output_file.write(bytes_buffer)
