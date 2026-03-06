"""Rewrites the specified input channel as the specified output channel.

Examples:
    osi_format_converter input_sv.mcap SensorView output_sv.osi --input_topic SensorViewTopic
    osi_format_converter input_gt.osi GroundTruth output_gt.mcap --output_topic GroundTruthTopic

"""

import argparse
from pathlib import Path

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osi_utilities.converters.format_converter import convert_format


def convert(
    input_channel_spec: OSIChannelSpecification,
    output_channel_spec: OSIChannelSpecification,
) -> OSIChannelSpecification:
    result = convert_format(input_channel_spec, output_channel_spec)
    return OSIChannelSpecification(
        path=result.path,
        message_type=result.message_type,
        topic=result.topic,
        metadata=result.metadata,
    )


def create_argparser():
    parser = argparse.ArgumentParser(
        description="Rewrites the specified input file/channel as the specified output file/channel."
    )
    parser.add_argument("input", help="Path to the input trace file.")
    parser.add_argument("type", help="OSI message type of the input file.")
    parser.add_argument("output", help="Path to the output trace file.")
    parser.add_argument(
        "--input_topic", help="Topic name of input channel if multi-trace file."
    )
    parser.add_argument(
        "--output_topic", help="Topic name of output channel if multi-trace file."
    )
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    input_trace_spec = OSIChannelSpecification(
        path=Path(args.input), message_type=args.type
    )
    sensorview_trace_spec = OSIChannelSpecification(
        path=Path(args.output),
        message_type=args.type,
        topic=(args.output_topic if args.output_topic else None),
    )
    output_spec = convert(input_trace_spec, sensorview_trace_spec)
    print(f"Wrote {output_spec}")


if __name__ == "__main__":
    main()
