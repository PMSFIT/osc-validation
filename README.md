# osc-validation

## Example execution

1. Convert original (resampled) OSI trace to OpenSCENARIO file
   ```
   python .\osi2osc.py .\example\20240603T143803.535904Z_sv_370_3200_364_pmsf_dronetracker_119_cutout_resampled50ms.osi 20240603T143803.535904Z_osc_pmsf_dronetracker_119_cutout.xosc
   ```

2. Run arbitrary OpenSCENARIO player and export OSI trace
   - Run OpenSCENARIO file in Esmini and export OSI GroundTruth trace file

     Note: Run with same frame rate as original resampled OSI trace (e.g. 20 fps / 0.05 step size)

     ```
     "../../bin/esmini" --window 60 60 1024 576 --osc 20240603T143803.535904Z_osc_pmsf_dronetracker_119_cutout.xosc --osi_file --pause --ground_plane --fixed_timestep 0.05
     ```

   - OpenSCENARIO file could also be run with any other OpenSCENARIO engine, like PMSF OSI3Test, to export OSI trace.

3. Convert Esmini OSI GroundTruth trace into OSI SensorView 
   ```
   python .\esminigt2sv.py .\example\20240603T143803.535904Z_gt_370_3200_370_pmsf_dronetracker_119_cutout_ESMINIEXPORT.osi .\example\20240603T143803.535904Z_sv_370_3200_370_pmsf_dronetracker_119_cutout_ESMINIEXPORT.osi
   ```

4. Extract trajectories from OSI trace and analyze
   ```
   python .\trajectory_similarity.py
   ```

5. Optionally run any OSI trace with OSI3Test Viewer
   ```
   python osi3test_run_osi.py
   ```
