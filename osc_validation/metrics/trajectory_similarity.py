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

import similaritymeasures
from osi3trace.osi_trace import OSITrace

from osc_validation.utils.utils import get_all_moving_object_ids, get_trajectory_by_moving_object_id

def calculate_similarity(reference: Path, tool: Path):
    reference_trace = OSITrace(str(reference))
    tool_trace = OSITrace(str(tool))

    reference_moving_object_ids = get_all_moving_object_ids(reference_trace)
    tool_moving_object_ids = get_all_moving_object_ids(tool_trace)

    reference_trajectories = []
    tool_trajectories = []
    for i, id in enumerate(reference_moving_object_ids):
        reference_trajectories.append(get_trajectory_by_moving_object_id(reference_trace, id))
    for i, id in enumerate(tool_moving_object_ids):
        traj = get_trajectory_by_moving_object_id(tool_trace, id)
        tool_trajectories.append(traj)
        tool_trajectories[i] = tool_trajectories[i].iloc[6:].reset_index(drop=True)

    print(reference_trajectories)
    print("\n###################################################################\n")
    print(tool_trajectories)
    print("\n###################################################################\n")

    print(reference_trajectories[0].iloc[:, 1:3])
    print("\n###################################################################\n")
    print(tool_trajectories[0].iloc[:, 1:3])
    print("\n###################################################################\n")

    area = similaritymeasures.area_between_two_curves(reference_trajectories[0].iloc[:, 1:3].values, tool_trajectories[0].iloc[:, 1:3].values)
    cl = similaritymeasures.curve_length_measure(reference_trajectories[0].iloc[:, 1:3].values, tool_trajectories[0].iloc[:, 1:3].values)
    mae = similaritymeasures.mae(reference_trajectories[0].iloc[:, 1:3].values, tool_trajectories[0].iloc[:, 1:3].values)
    print(area, cl, mae)

    plt.figure()
    plt.plot(reference_trajectories[0]["x"], reference_trajectories[0]["y"], 'o-')
    plt.plot(tool_trajectories[0]["x"], tool_trajectories[0]["y"], 'o-')
    plt.show()


def create_argparser():
    parser = argparse.ArgumentParser(
        description="Compare OSI SensorView trace files using trajectory similarity metrics."
    )
    parser.add_argument("reference_sv", help="Path to the reference OSI SensorView trace file.")
    parser.add_argument("tool_sv", help="Path to the tool output OSI SensorView trace file.")
    return parser


def main():
    parser = create_argparser()
    args = parser.parse_args()
    path_reference = Path(args.reference_sv)
    path_tool = Path(args.tool_sv)
    calculate_similarity(path_reference, path_tool)


if __name__ == "__main__":
    main()
