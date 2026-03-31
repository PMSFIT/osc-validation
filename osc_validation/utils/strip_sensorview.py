"""Removes OSI SensorView overhead that may not be required for the validation
activity. The given boolean arguments can be used to specify which OSI content
should be removed."""

import argparse
from pathlib import Path

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter


def strip(sv_in: Path, sv_out: Path, args):
    input_channel_spec = OSIChannelSpecification(path=sv_in, message_type="SensorView")
    output_channel_spec = OSIChannelSpecification(
        path=sv_out, message_type="SensorView"
    )
    with (
        OSIChannelReader.from_osi_channel_specification(
            input_channel_spec
        ) as channel_reader,
        OSIChannelWriter.from_osi_channel_specification(
            output_channel_spec
        ) as channel_writer,
    ):
        for message in channel_reader:
            if args.lane_boundary:
                message.global_ground_truth.ClearField("lane_boundary")
            if args.reference_line:
                message.global_ground_truth.ClearField("reference_line")
            if args.logical_lane:
                message.global_ground_truth.ClearField("logical_lane")
            if args.logical_lane_boundary:
                message.global_ground_truth.ClearField("logical_lane_boundary")
            if args.lane:
                message.global_ground_truth.ClearField("lane")
            if args.environmental_conditions:
                message.global_ground_truth.ClearField("environmental_conditions")
            channel_writer.write(message)


def create_argparser():
    parser = argparse.ArgumentParser(description="Strip content from OSI SensorView.")
    parser.add_argument(
        "sensorview_in", help="Path to the input OSI SensorView trace file."
    )
    parser.add_argument(
        "sensorview_out", help="Path to the output OSI SensorView trace file."
    )
    parser.add_argument(
        "--lane_boundary",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Remove lane boundaries",
    )
    parser.add_argument(
        "--logical_lane",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Remove logical lanes",
    )
    parser.add_argument(
        "--logical_lane_boundary",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Remove logical lane boundaries",
    )
    parser.add_argument(
        "--lane",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Remove lanes",
    )
    parser.add_argument(
        "--reference_line",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Remove reference lines",
    )
    parser.add_argument(
        "--environmental_conditions",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Remove environmental conditions",
    )
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    path_sensorview_in = Path(args.sensorview_in)
    path_sensorview_out = Path(args.sensorview_out)
    strip(path_sensorview_in, path_sensorview_out, args)


if __name__ == "__main__":
    main()
