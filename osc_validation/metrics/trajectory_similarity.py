import argparse
import logging
import math
from pathlib import Path

import numpy

import matplotlib.pyplot as plt

import pandas as pd
import similaritymeasures

from osc_validation.metrics.osimetric import OSIMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.utils import (
    get_all_moving_object_ids,
    get_closest_trajectory,
    get_trajectory_by_moving_object_id,
)


class TrajectorySimilarityMetric(OSIMetric):
    def __init__(self, name: str = "TrajectorySimilarity", plot_path: Path = None):
        """
        Initializes the TrajectorySimilarityMetric with a name.

        Args:
            name (str): Name of the metric.
            plot_path (Path, optional): Path to save the plot for this metric.
                If None, the plot will not be saved.
        """
        super().__init__(name)
        self.plot_path = plot_path

    def compute(
            self,
            reference_channel_spec: OSIChannelSpecification,
            tool_channel_spec: OSIChannelSpecification,
            moving_object_id: int,
            start_time: float = None,
            end_time: float = None,
            result_file: Path = None,
        ):
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
            moving_object_id (int): The ID of the moving object in the reference trace whose trajectory will be compared with the corresponding moving object's trajectory in the tool trace.
            start_time (float, optional): Start time in seconds for the trajectory comparison. Defaults to None, in which case the complete trajectory is considered.
            end_time (float, optional): End time in seconds for the trajectory comparison. Defaults to None, in which case the complete trajectory is considered.
            result_file (Path, optional): Path to save the similarity report. If None, the report is logged to info level.
        Returns:
            area (float): Area between the two trajectories' curves.
            cl (float): Curve length measure between the two trajectories.
            mae (float): Mean absolute error (MAE) between the two trajectories.
            report (str): Formatted string summarizing the similarity measures.
        Raises:
            KeyError: If the specified moving_object_id is not found in either trace.
        """
        pd.set_option("display.precision", 15)

        report = f"Report for Trajectory Similarity Metric '{self.name}':\n"

        reference_moving_object_ids = get_all_moving_object_ids(reference_channel_spec)
        if moving_object_id not in reference_moving_object_ids:
            raise KeyError(f"Moving object ID {moving_object_id} not found in reference trace.")
        
        ref_trajectory = get_trajectory_by_moving_object_id(reference_channel_spec, moving_object_id, start_time, end_time)
        tool_trajectory = get_closest_trajectory(ref_trajectory, tool_channel_spec, start_time, end_time) # matching trajectories based on starting position proximity
        logging.info(f"Comparing tool trace trajectory of moving object ID '{tool_trajectory.attrs["id"]}' to reference trace trajectory of moving object ID '{moving_object_id}'.")

        if len(ref_trajectory) < 2 or len(tool_trajectory) < 2:
            raise ValueError("Trajectories must contain at least 2 points for comparison.")
        
        if len(ref_trajectory) != len(tool_trajectory):
            raise ValueError("Reference and tool trajectories must have the same number of points.")

        report += f"Reference trajectory for moving object ID {moving_object_id}:\n"
        report += ref_trajectory.loc[:, ["timestamp", "x", "y"]].to_string(index=False)
        report += "\n###################################################################\n"
        report += f"Tool trajectory for moving object ID {moving_object_id}:\n"
        report += tool_trajectory.loc[:, ["timestamp", "x", "y"]].to_string(index=False)
        report += "\n###################################################################\n"

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

        report += (
            f"Similarity Measures:\n"
            f"Area between two curves:      {area}\n"
            f"Curve length measure:         {cl}\n"
            f"Mean absolute error (MAE):    {mae}\n"
        )

        if result_file:
            logging.info(f"Writing results to {result_file}")
            with open(result_file, "w") as f:
                f.write(report)
        else:
            logging.info(report)

        if self.plot_path:
            plot_path = self.plot_path / f"trajectory_similarity_{moving_object_id}.png"
            plt.figure(figsize=(25.6, 14.4))
            plt.plot(ref_trajectory["x"], ref_trajectory["y"], "o-", label="Reference", markersize=3)
            plt.plot(tool_trajectory["x"], tool_trajectory["y"], "o-", label="Tool", markersize=3)
            plt.legend()
            plt.savefig(plot_path, dpi=100)
            plt.close()
            logging.info(f"Plot saved to {plot_path}")

        return area, cl, mae


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
    parser.add_argument("--start-time", type=float, help="Start time for trajectory comparison in seconds (float)")
    parser.add_argument("--end-time", type=float, help="End time for trajectory comparison in seconds (float)")
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    path_reference = Path(args.reference_sv)
    reference_reader = OSIChannelReader.from_osi_single_trace(path_reference, message_type="SensorView")
    path_tool = Path(args.tool_sv)
    tool_reader = OSIChannelReader.from_osi_single_trace(path_tool, message_type="SensorView")
    metric = TrajectorySimilarityMetric("TrajectorySimilarityMetric")
    _, _, _ = metric.compute(
        reference_channel_spec=reference_reader,
        tool_channel_spec=tool_reader,
        moving_object_id=args.moving_object_id,
        plot=args.plot,
        start_time=args.start_time,
        end_time=args.end_time
    )


if __name__ == "__main__":
    main()
