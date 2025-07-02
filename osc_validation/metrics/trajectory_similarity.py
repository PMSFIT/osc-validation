import argparse
from pathlib import Path

import matplotlib.pyplot as plt

import pandas as pd
import similaritymeasures

from osc_validation.metrics.osimetric import OSIMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.utils import (
    get_all_moving_object_ids,
    get_trajectory_by_moving_object_id,
)


class TrajectorySimilarityMetric(OSIMetric):
    def __init__(self, name: str = "TrajectorySimilarity", plot=False):
        """
        Initializes the TrajectorySimilarityMetric with a name.

        Args:
            name (str): Name of the metric.
            plot (bool): Indicates whether plotting is enabled for this metric.
        """
        super().__init__(name)
        self.plot = plot

    def compute(self, reference_channel_spec: OSIChannelSpecification, tool_channel_spec: OSIChannelSpecification, moving_object_id: int):
        """
        Compares the 2d-trajectories of a specified moving object in two OSI SensorView traces and computes similarity measures.

        Preconditions:
            Reference and tool traces are OSI SensorView traces.
            Reference and tool traces have the same frame rate.
            Reference and tool traces are in the same time frame.
            Reference and tool traces contain the same number of frames.
            Reference and tool traces contain the same moving object ids identifying the same objects.

        Args:
            reference_channel_spec (OSIChannelSpecification): Specification of the reference OSI SensorView trace channel.
            tool_channel_spec (OSIChannelSpecification): Specification of the tool-generated OSI SensorView trace channel.
            moving_object_id (int): The ID of the moving object whose trajectory will be compared.
        Returns:
            area (float): Area between the two trajectories' curves.
            cl (float): Curve length measure between the two trajectories.
            mae (float): Mean absolute error (MAE) between the two trajectories.
            report (str): Formatted string summarizing the similarity measures.
        Raises:
            KeyError: If the specified moving_object_id is not found in either trace.
        """
        reference_channel_spec = OSIChannelReader.from_osi_channel_specification(reference_channel_spec)
        tool_channel_spec = OSIChannelReader.from_osi_channel_specification(tool_channel_spec)

        reference_moving_object_ids = get_all_moving_object_ids(reference_channel_spec)
        if moving_object_id not in reference_moving_object_ids:
            raise KeyError(f"Moving object ID {moving_object_id} not found in reference trace.")
        
        tool_moving_object_ids = get_all_moving_object_ids(tool_channel_spec)
        if moving_object_id not in tool_moving_object_ids:
            raise KeyError(f"Moving object ID {moving_object_id} not found in tool trace.")

        reference_trajectories: dict[int, pd.DataFrame] = {}
        tool_trajectories: dict[int, pd.DataFrame] = {}
        for id in reference_moving_object_ids:
            reference_trajectories[id] = get_trajectory_by_moving_object_id(reference_channel_spec, id)
        for id in tool_moving_object_ids:
            tool_trajectories[id] = get_trajectory_by_moving_object_id(tool_channel_spec, id)

        print("Reference Trajectories: ")
        print(reference_trajectories)
        print("\n###################################################################\n")
        print("Tool Trajectories: ")
        print(tool_trajectories)
        print("\n###################################################################\n")

        ref_trajectory = reference_trajectories[moving_object_id]
        tool_trajectory = tool_trajectories[moving_object_id]

        print(ref_trajectory.loc[:, ["x", "y"]])
        print("\n###################################################################\n")
        print(tool_trajectory.loc[:, ["x", "y"]])
        print("\n###################################################################\n")

        area = similaritymeasures.area_between_two_curves(
            ref_trajectory.loc[:, ["x", "y"]].values,
            tool_trajectory.loc[:, ["x", "y"]].values,
        )
        cl = similaritymeasures.curve_length_measure(
            ref_trajectory.loc[:, ["x", "y"]].values,
            tool_trajectory.loc[:, ["x", "y"]].values,
        )
        mae = similaritymeasures.mae(
            ref_trajectory.loc[:, ["x", "y"]].values,
            tool_trajectory.loc[:, ["x", "y"]].values,
        )

        report = (
            f"Similarity Measures:\n"
            f"Area between two curves:      {area}\n"
            f"Curve length measure:         {cl}\n"
            f"Mean absolute error (MAE):    {mae}\n"
        )

        if self.plot:
            plt.figure()
            plt.plot(ref_trajectory["x"], ref_trajectory["y"], "o-", label="Reference")
            plt.plot(tool_trajectory["x"], tool_trajectory["y"], "o-", label="Tool")
            plt.legend()
            plt.show()

        return area, cl, mae, report


def create_argparser():
    parser = argparse.ArgumentParser(
        description="Compare OSI SensorView trace files using trajectory similarity metrics."
    )
    parser.add_argument(
        "reference_sv", help="Path to the reference OSI SensorView trace file."
    )
    parser.add_argument(
        "tool_sv", help="Path to the tool output OSI SensorView trace file."
    )
    parser.add_argument(
        "moving_object_id", help="ID of the moving object's trajectories to be compared."
    )
    parser.add_argument(
        "-p",
        "--plot",
        action="store_true",
        help="Plot the reference and tool trajectories for visual comparison.",
    )
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    path_reference = Path(args.reference_sv)
    reference_reader = OSIChannelReader.from_osi_single_trace(path_reference, message_type="SensorView")
    path_tool = Path(args.tool_sv)
    tool_reader = OSIChannelReader.from_osi_single_trace(path_tool, message_type="SensorView")
    metric = TrajectorySimilarityMetric("TrajectorySimilarityMetric")
    metric.compute(reference_reader, tool_reader, args.moving_object_id, args.plot)


if __name__ == "__main__":
    main()
