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

import matplotlib.pyplot as plt

import similaritymeasures
from osi3trace.osi_trace import OSITrace

from utils import get_all_moving_object_ids, get_trajectory_by_moving_object_id

original = OSITrace("./example/20240603T143803.535904Z_sv_370_3200_364_pmsf_dronetracker_119_cutout_resampled50ms.osi")
esmini_export = OSITrace("./example/20240603T143803.535904Z_sv_pmsf_dronetracker_119_cutout_ESMINIEXPORT.osi")
osi3test_export = OSITrace("./example/20240603T143803.535904Z_sv_pmsf_dronetracker_119_cutout_OSI3TESTEXPORT.osi")

original_moving_object_ids = get_all_moving_object_ids(original)
esmini_moving_object_ids = get_all_moving_object_ids(esmini_export)
osi3test_moving_object_ids = get_all_moving_object_ids(osi3test_export)

original_trajectories = []
esmini_trajectories = []
osi3test_trajectories = []
for i, id in enumerate(original_moving_object_ids):
    original_trajectories.append(get_trajectory_by_moving_object_id(original, id))
for i, id in enumerate(esmini_moving_object_ids):
    traj = get_trajectory_by_moving_object_id(esmini_export, id)
    esmini_trajectories.append(traj)
    esmini_trajectories[i] = esmini_trajectories[i].iloc[6:].reset_index(drop=True)
for i, id in enumerate(osi3test_moving_object_ids):
    osi3test_trajectories.append(get_trajectory_by_moving_object_id(osi3test_export, id))
    osi3test_trajectories[i] = osi3test_trajectories[i].iloc[6:].reset_index(drop=True)

print(original_trajectories)
print("\n###################################################################\n")
print(esmini_trajectories)
print("\n###################################################################\n")
print(osi3test_trajectories)

print(original_trajectories[0].iloc[:, 1:3])
print("\n###################################################################\n")
print(esmini_trajectories[0].iloc[:, 1:3])
print("\n###################################################################\n")
print(osi3test_trajectories[0].iloc[:, 1:3])

area = similaritymeasures.area_between_two_curves(original_trajectories[0].iloc[:, 1:3].values, esmini_trajectories[0].iloc[:, 1:3].values)
cl = similaritymeasures.curve_length_measure(original_trajectories[0].iloc[:, 1:3].values, esmini_trajectories[0].iloc[:, 1:3].values)
mae = similaritymeasures.mae(original_trajectories[0].iloc[:, 1:3].values, esmini_trajectories[0].iloc[:, 1:3].values)
print(area, cl, mae)

plt.figure()
plt.plot(original_trajectories[0]["x"], original_trajectories[0]["y"], 'o-')
plt.plot(esmini_trajectories[0]["x"], esmini_trajectories[0]["y"], 'o-')
plt.plot(osi3test_trajectories[0]["x"], osi3test_trajectories[0]["y"], 'o-')
plt.show()
