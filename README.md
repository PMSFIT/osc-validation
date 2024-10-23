# osc-validation

This repository provides a validation suite for ASAM OpenSCENARIO XML engines based on comparing their OSI ground_truth/sensor_view output to known good references.

The validation is based on a [subset definition](specification/osc_subset_definition.md) that restricts the covered constructs of OpenSCENARIO XML to a minimal, unambiguous, validatable, but useful subset.
It derives from this subset a validation suite of representative test cases and metrics that can then be used to check an implementation for correct OSI ground truth generation for those cases.

## Example execution

1. Convert original (resampled) OSI trace to OpenSCENARIO file

   ```bash
   python osi2osc.py example/20240603T143803.535904Z_sv_370_3200_364_pmsf_dronetracker_119_cutout_resampled50ms.osi 20240603T143803.535904Z_osc_pmsf_dronetracker_119_cutout.xosc
   ```

2. Run arbitrary OpenSCENARIO player and export OSI trace
   - Run OpenSCENARIO file in Esmini and export OSI GroundTruth trace file

     Note: Run with same frame rate as original resampled OSI trace (e.g. 20 fps / 0.05 step size)

     ```bash
     esmini --window 60 60 1024 576 --osc 20240603T143803.535904Z_osc_pmsf_dronetracker_119_cutout.xosc --osi_file --ground_plane --fixed_timestep 0.05
     ```

   - OpenSCENARIO file could also be run with any other OpenSCENARIO engine, like PMSF OSI3Test, to export OSI trace.

3. Convert Esmini OSI GroundTruth trace into OSI SensorView

   ```bash
   python esminigt2sv.py ground_truth.osi example/20240603T143803.535904Z_sv_370_3200_370_pmsf_dronetracker_119_cutout_ESMINIEXPORT.osi
   ```

4. Extract trajectories from OSI trace and analyze

   ```bash
   python trajectory_similarity.py
   ```

5. Optionally run any OSI trace with OSI3Test Viewer

   ```bash
   python osi3test_run_osi.py
   ```
