import pytest
from lxml import etree
from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.features.sequencing import (
    TrajectorySequencingTransformRequest,
    TrajectorySequencingTransformSpec,
    apply_trajectory_sequencing_transform,
)
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.versioning import OscVersion, ScenarioContract


@pytest.mark.parametrize(
    "sequencing_level", ["event", "maneuver", "maneuver_group", "act", "story"]
)
@pytest.mark.parametrize(
    "version,policy,has_interpolation",
    [
        (OscVersion.V1_3_1, None, False),
        (OscVersion.V1_4_0, "standard_default", False),
        (OscVersion.V1_4_0, "custom", True),
        (OscVersion.V1_4_0, None, True),
    ],
)
def test_split_preserves_polyline_interpolation(
    tmp_path, sample_sensor_views, sequencing_level, version, policy, has_interpolation
):
    trace = ChannelSpecification(tmp_path / "input.osi", message_type="SensorView")
    with open_channel_writer(trace) as writer:
        for message in sample_sensor_views:
            vehicle = message.global_ground_truth.moving_object[0]
            vehicle.vehicle_classification.type = (
                vehicle.vehicle_classification.TYPE_MEDIUM_CAR
            )
            writer.write_message(message)
    source = osi2osc(
        trace,
        tmp_path / "source.xosc",
        contract=ScenarioContract(version),
        interpolation_policy=policy,
    )
    source_tree = etree.parse(str(source))
    source_polyline = source_tree.find(".//Event[@name='Ego_maneuver_event']//Polyline")
    source_vertices = source_polyline.findall("Vertex")

    result = apply_trajectory_sequencing_transform(
        TrajectorySequencingTransformRequest(
            source_xosc_path=source,
            output_xosc_path=tmp_path / "split.xosc",
            spec=TrajectorySequencingTransformSpec(
                entity_ref="Ego", segment_count=2, sequencing_level=sequencing_level
            ),
        )
    )

    tree = etree.parse(str(result.xosc_path))
    for index in range(2):
        polyline = tree.find(
            f".//Event[@name='Ego_maneuver_event_seq_{index + 1}']//Polyline"
        )
        assert polyline is not None
        assert [child.tag for child in polyline] == ["Vertex"] * 3 + (
            ["Interpolation"] if has_interpolation else []
        )
        if has_interpolation:
            assert etree.tostring(
                polyline.find("Interpolation"), with_tail=False
            ) == etree.tostring(source_polyline.find("Interpolation"), with_tail=False)
        vertices = polyline.findall("Vertex")
        assert [float(vertex.get("time")) for vertex in vertices] == pytest.approx(
            [0.0, 0.1, 0.2]
        )
        for vertex, original in zip(vertices, source_vertices[index * 2 :]):
            assert (
                vertex.find("Position/WorldPosition").attrib
                == original.find("Position/WorldPosition").attrib
            )
