""" 
Process:
- extract trajectories from
    - 20240603T143803.535904Z_sv_pmsf_dronetracker_119_cutout_ESMINIEXPORT.osi (regenerate with corrected z-value)
    - 20240603T143803.535904Z_sv_370_3200_364_pmsf_dronetracker_119_cutout_resampled50ms.osi
    - export from osi3test OSC file playback
    - NOTE: All OSI traces should contain same frame rate (time step 0.05).
- use similaritymeasures to compare
    - for now only x-/y-coordinates

ORIGINAL
[357 rows x 7 columns]]
              x          y
0   -306.947559 -62.286357
1   -306.320860 -62.100572
2   -305.702312 -61.920447
3   -305.087506 -61.742930
4   -304.470932 -61.564183
..          ...        ...
359 -155.720896 -15.746643
360 -155.609734 -15.697055
361 -155.563616 -15.677388
362 -155.555590 -15.672761
363 -155.512163 -15.647916

[364 rows x 2 columns]

###################################################################

ESMINI EXPORT
              x          y
0   -306.947559 -62.286357
1   -306.320860 -62.100572
2   -305.702312 -61.920447
3   -305.087506 -61.742930
4   -304.470932 -61.564183
..          ...        ...
359 -155.720896 -15.746643
360 -155.609734 -15.697055
361 -155.563616 -15.677388
362 -155.555590 -15.672761
363 -155.512163 -15.647916

[364 rows x 2 columns]

###################################################################

OSI3TEST EXPORT
              x          y
0   -306.947559 -62.286357
1   -306.320860 -62.100572
2   -305.702312 -61.920447
3   -305.087506 -61.742930
4   -304.470932 -61.564183
..          ...        ...
359 -155.720896 -15.746643
360 -155.609734 -15.697055
361 -155.563616 -15.677388
362 -155.555590 -15.672761
363 -155.512163 -15.647916

"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

import pandas as pd
import similaritymeasures
from osi3trace.osi_trace import OSITrace

from osc_validation.utils.utils import (
    get_all_moving_object_ids,
    get_trajectory_by_moving_object_id,
)


def calculate_similarity(reference_trace: Path, tool_trace: Path, moving_object_id: int, plot=False):
    """
    Compares the trajectories of a specified moving object in two OSI SensorView traces and computes similarity measures.

    Preconditions:
        Reference and tool traces are OSI SensorView traces.
        Reference and tool traces have the same frame rate.
        Reference and tool traces are in the same time frame.
        Reference and tool traces contain the same number of frames.
        Reference and tool traces contain the same moving object ids identifying the same objects.

    Args:
        reference_trace (Path): Path to the reference OSI SensorView trace file.
        tool_trace (Path): Path to the tool-generated OSI SensorView trace file.
        moving_object_id (int): The ID of the moving object whose trajectory will be compared.
        plot (bool, optional): If True, plots the trajectories for visual comparison. Defaults to False.
    Returns:
        area (float): Area between the two trajectories' curves.
        cl (float): Curve length measure between the two trajectories.
        mae (float): Mean absolute error (MAE) between the two trajectories.
        report (str): Formatted string summarizing the similarity measures.
    Raises:
        KeyError: If the specified moving_object_id is not found in either trace.
    """

    reference_trace = OSITrace(str(reference_trace))
    tool_trace = OSITrace(str(tool_trace))

    reference_moving_object_ids = get_all_moving_object_ids(reference_trace)
    if moving_object_id not in reference_moving_object_ids:
        raise KeyError(f"Moving object ID {moving_object_id} not found in reference trace.")
    tool_moving_object_ids = get_all_moving_object_ids(tool_trace)
    if moving_object_id not in tool_moving_object_ids:
        raise KeyError(f"Moving object ID {moving_object_id} not found in tool trace.")

    reference_trajectories: dict[int, pd.DataFrame] = {}
    tool_trajectories: dict[int, pd.DataFrame] = {}
    for id in reference_moving_object_ids:
        reference_trajectories[id] = get_trajectory_by_moving_object_id(reference_trace, id)
    for id in tool_moving_object_ids:
        tool_trajectories[id] = get_trajectory_by_moving_object_id(tool_trace, id)

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

    if plot:
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
    path_tool = Path(args.tool_sv)
    calculate_similarity(path_reference, path_tool, args.plot)


if __name__ == "__main__":
    main()
