from pathlib import Path
import similaritymeasures

from osc_validation.metrics.osimetric import OSIMetric
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from osi_utilities import ChannelSpecification
from osc_validation.utils.utils import (
    get_trajectory_by_moving_object_id,
    get_closest_trajectory,
)


class TrajectoryAlignmentSimilarityMetric(OSIMetric):
    """
    Trajectory similarity metric with optional frame-lag alignment scan.

    If `lag_scan_max_frames == 0`, this behaves like plain trajectory similarity
    (no lag scan, effectively zero-lag comparison).

    If `lag_scan_max_frames > 0`, the metric evaluates all integer frame lags in
    `[-lag_scan_max_frames, +lag_scan_max_frames]`, selects the lag with the
    smallest MAE, and then reports area/curve-length/MAE for that best-aligned
    overlap window.

    Practical interpretation:
    - Setting `lag_scan_max_frames = N` means "accept up to +/-N frames temporal
      offset when evaluating similarity."
    - Threshold checks should be applied to the returned metrics, which are from
      the best lag found in that interval (not necessarily lag 0).
    """
    def __init__(
        self,
        trajectory_metric: TrajectorySimilarityMetric = None,
        name: str = "TrajectoryAlignmentSimilarity",
    ):
        super().__init__(name)
        self.trajectory_metric = trajectory_metric or TrajectorySimilarityMetric()

    @staticmethod
    def _align_xy_with_lag_scan(ref_xy, tool_xy, max_frames: int):
        """
        Align two XY trajectories by scanning integer frame lags and selecting
        the lag with minimal MAE.

        Returns:
        - aligned reference XY
        - aligned tool XY
        - selected lag in frames
        """
        best_lag = 0
        best_mae = None
        best_ref_xy = ref_xy
        best_tool_xy = tool_xy

        for lag in range(-max_frames, max_frames + 1):
            if lag > 0:
                ref_slice = ref_xy[lag:]
                tool_slice = tool_xy[:-lag]
            elif lag < 0:
                ref_slice = ref_xy[:lag]
                tool_slice = tool_xy[-lag:]
            else:
                ref_slice = ref_xy
                tool_slice = tool_xy

            if len(ref_slice) < 2 or len(tool_slice) < 2:
                continue

            current_mae = similaritymeasures.mae(ref_slice, tool_slice)
            if best_mae is None or current_mae < best_mae:
                best_mae = current_mae
                best_lag = lag
                best_ref_xy = ref_slice
                best_tool_xy = tool_slice

        return best_ref_xy, best_tool_xy, best_lag

    def compute(
        self,
        reference_channel_spec: ChannelSpecification,
        tool_channel_spec: ChannelSpecification,
        moving_object_id: int,
        start_time: float = None,
        end_time: float = None,
        result_file: Path = None,
        time_tolerance: float = 0.0,
        lag_scan_max_frames: int = 0,
    ) -> tuple[float, float, float, int]:
        """
        Compute trajectory similarity for `moving_object_id`.

        Parameters:
        - `lag_scan_max_frames`: maximum absolute frame shift to evaluate.
          - `0`: no lag scan (zero-lag comparison via `TrajectorySimilarityMetric`).
          - `N > 0`: scan lags in `[-N, ..., 0, ..., +N]` and select the lag with
            minimal MAE.

        Returns:
        - `(area, cl, mae, best_lag_frames)` for the selected alignment.
        """
        if lag_scan_max_frames < 0:
            raise ValueError("lag_scan_max_frames must be >= 0.")

        if lag_scan_max_frames == 0:
            area, cl, mae = self.trajectory_metric.compute(
                reference_channel_spec=reference_channel_spec,
                tool_channel_spec=tool_channel_spec,
                moving_object_id=moving_object_id,
                start_time=start_time,
                end_time=end_time,
                result_file=result_file,
                time_tolerance=time_tolerance,
            )
            self.best_lag_frames = 0
            return area, cl, mae, self.best_lag_frames

        adj_start_time = (
            start_time - time_tolerance if start_time is not None else None
        )
        adj_end_time = end_time + time_tolerance if end_time is not None else None

        ref_trajectory = get_trajectory_by_moving_object_id(
            reference_channel_spec,
            moving_object_id,
            adj_start_time,
            adj_end_time,
        )
        if ref_trajectory is None or len(ref_trajectory) < 2:
            raise ValueError("Reference trajectory must contain at least 2 points.")

        tool_trajectory = get_closest_trajectory(
            ref_trajectory,
            tool_channel_spec,
            adj_start_time,
            adj_end_time,
        )
        if tool_trajectory is None or len(tool_trajectory) < 2:
            raise ValueError("Tool trajectory must contain at least 2 points.")

        if len(ref_trajectory) != len(tool_trajectory):
            raise ValueError(
                "Reference and tool trajectories must have the same number of points for lag scan."
            )

        ref_xy = ref_trajectory.loc[:, ["x", "y"]].values
        tool_xy = tool_trajectory.loc[:, ["x", "y"]].values
        best_ref_xy, best_tool_xy, best_lag = self._align_xy_with_lag_scan(
            ref_xy=ref_xy,
            tool_xy=tool_xy,
            max_frames=lag_scan_max_frames,
        )

        area = similaritymeasures.area_between_two_curves(best_ref_xy, best_tool_xy)
        cl = similaritymeasures.curve_length_measure(best_ref_xy, best_tool_xy)
        mae = similaritymeasures.mae(best_ref_xy, best_tool_xy)

        if result_file:
            with open(result_file, "w") as f:
                f.write(
                    "Report for Trajectory Alignment Similarity Metric\n"
                    f"Best lag (frames): {best_lag}\n"
                    f"Area between two curves:      {area}\n"
                    f"Curve length measure:         {cl}\n"
                    f"Mean absolute error (MAE):    {mae}\n"
                )

        return area, cl, mae, best_lag
