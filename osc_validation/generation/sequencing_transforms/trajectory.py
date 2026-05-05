from copy import deepcopy
from pathlib import Path

from lxml import etree

from .models import (
    TrajectorySequencingTransformRequest,
    TrajectorySequencingTransformResult,
    TrajectorySequencingTransformSpec,
)


def apply_trajectory_sequencing_transform(
    request: TrajectorySequencingTransformRequest,
) -> TrajectorySequencingTransformResult:
    output_path = split_entity_trajectory(
        source_xosc_path=request.source_xosc_path,
        output_xosc_path=request.output_xosc_path,
        spec=request.spec,
    )
    return TrajectorySequencingTransformResult(xosc_path=output_path)


def split_entity_trajectory(
    source_xosc_path: Path,
    output_xosc_path: Path,
    spec: TrajectorySequencingTransformSpec,
) -> Path:
    if spec.segment_count < 2:
        raise ValueError("segment_count must be >= 2.")

    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()
    event = _find_entity_event(root, spec.entity_ref)
    action = _find_single_trajectory_action(event, spec.entity_ref)
    vertices = _find_vertices(action, spec.entity_ref)
    vertex_segments = _split_vertices(vertices, spec.segment_count)

    if spec.sequencing_level == "event":
        _replace_event_with_split_events(event, action, vertex_segments)
    elif spec.sequencing_level == "maneuver":
        _replace_maneuver_with_split_maneuvers(event, action, vertex_segments)
    elif spec.sequencing_level == "maneuver_group":
        _replace_maneuver_group_with_split_groups(event, action, vertex_segments)
    elif spec.sequencing_level == "act":
        _replace_act_with_split_acts(event, action, vertex_segments)
    elif spec.sequencing_level == "story":
        _replace_act_with_split_stories(event, action, vertex_segments)
    else:
        raise ValueError(f"Unsupported sequencing_level '{spec.sequencing_level}'.")

    tree.write(
        str(output_xosc_path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )
    return output_xosc_path


def _find_entity_event(root, entity_ref: str):
    event = root.find(f".//Event[@name='{entity_ref}_maneuver_event']")
    if event is None:
        raise RuntimeError(
            f"Could not find generated event for entityRef='{entity_ref}'."
        )
    return event


def _find_single_trajectory_action(event, entity_ref: str):
    actions = event.findall("Action")
    trajectory_actions = [
        action
        for action in actions
        if action.find(".//FollowTrajectoryAction") is not None
    ]
    if len(trajectory_actions) != 1:
        raise RuntimeError(
            f"Expected exactly one FollowTrajectoryAction for entityRef='{entity_ref}', "
            f"found {len(trajectory_actions)}."
        )
    return trajectory_actions[0]


def _find_vertices(action, entity_ref: str):
    vertices = action.findall(".//TrajectoryRef/Trajectory/Shape/Polyline/Vertex")
    if len(vertices) < 2:
        raise RuntimeError(
            f"Expected at least two trajectory vertices for entityRef='{entity_ref}'."
        )
    return vertices


def _split_vertices(vertices, segment_count: int):
    if segment_count >= len(vertices):
        raise ValueError("segment_count must be smaller than the number of vertices.")

    split_indices = [
        round(index * (len(vertices) - 1) / segment_count)
        for index in range(segment_count + 1)
    ]
    segments = []
    for start, stop in zip(split_indices[:-1], split_indices[1:]):
        segment = [deepcopy(vertex) for vertex in vertices[start : stop + 1]]
        _normalize_segment_vertex_times(segment)
        segments.append(segment)
    return segments


def _normalize_segment_vertex_times(vertices):
    segment_start_time = float(vertices[0].get("time"))
    for vertex in vertices:
        normalized_time = float(vertex.get("time")) - segment_start_time
        vertex.set("time", str(normalized_time))


def _replace_event_with_split_events(event, action, vertex_segments):
    maneuver = event.getparent()
    event_index = maneuver.index(event)
    maneuver.remove(event)

    previous_event_name = None
    for index, segment in enumerate(vertex_segments):
        split_event = _build_event(event, action, segment, index, previous_event_name)
        maneuver.insert(event_index + index, split_event)
        previous_event_name = split_event.get("name")


def _replace_maneuver_with_split_maneuvers(event, action, vertex_segments):
    maneuver = event.getparent()
    maneuver_group = maneuver.getparent()
    maneuver_index = maneuver_group.index(maneuver)
    maneuver_group.remove(maneuver)

    previous_maneuver_name = None
    for index, segment in enumerate(vertex_segments):
        split_maneuver = deepcopy(maneuver)
        split_maneuver.set("name", f"{maneuver.get('name')}_seq_{index + 1}")
        _clear_children(split_maneuver)
        split_event = _build_event(event, action, segment, index)
        if previous_maneuver_name is not None:
            _append_storyboard_element_start_trigger(
                split_event,
                condition_name=f"{split_event.get('name')}_start",
                storyboard_element_type="maneuver",
                storyboard_element_ref=previous_maneuver_name,
            )
        split_maneuver.append(split_event)
        maneuver_group.insert(maneuver_index + index, split_maneuver)
        previous_maneuver_name = split_maneuver.get("name")


def _replace_maneuver_group_with_split_groups(event, action, vertex_segments):
    maneuver = event.getparent()
    maneuver_group = maneuver.getparent()
    act = maneuver_group.getparent()
    group_index = act.index(maneuver_group)
    act.remove(maneuver_group)

    previous_group_name = None
    for index, segment in enumerate(vertex_segments):
        split_group = deepcopy(maneuver_group)
        split_group.set("name", f"{maneuver_group.get('name')}_seq_{index + 1}")
        actors = deepcopy(maneuver_group.find("Actors"))
        _clear_children(split_group)
        split_group.append(actors)
        split_maneuver = deepcopy(maneuver)
        split_maneuver.set("name", f"{maneuver.get('name')}_seq_{index + 1}")
        _clear_children(split_maneuver)
        split_event = _build_event(event, action, segment, index)
        if previous_group_name is not None:
            _append_storyboard_element_start_trigger(
                split_event,
                condition_name=f"{split_event.get('name')}_start",
                storyboard_element_type="maneuverGroup",
                storyboard_element_ref=previous_group_name,
            )
        split_maneuver.append(split_event)
        split_group.append(split_maneuver)
        act.insert(group_index + index, split_group)
        previous_group_name = split_group.get("name")


def _replace_act_with_split_acts(event, action, vertex_segments):
    maneuver = event.getparent()
    maneuver_group = maneuver.getparent()
    act = maneuver_group.getparent()
    story = act.getparent()
    act_index = story.index(act)
    story.remove(act)

    previous_act_name = None
    for index, segment in enumerate(vertex_segments):
        split_act, _ = _build_act_segment(
            act, maneuver_group, maneuver, event, action, segment, index
        )
        if previous_act_name is not None:
            _append_storyboard_element_start_trigger(
                split_act,
                condition_name=f"{split_act.get('name')}_start",
                storyboard_element_type="act",
                storyboard_element_ref=previous_act_name,
            )
        story.insert(act_index + index, split_act)
        previous_act_name = split_act.get("name")


def _replace_act_with_split_stories(event, action, vertex_segments):
    maneuver = event.getparent()
    maneuver_group = maneuver.getparent()
    act = maneuver_group.getparent()
    story = act.getparent()
    storyboard = story.getparent()
    story_index = storyboard.index(story)
    storyboard.remove(story)

    previous_story_name = None
    for index, segment in enumerate(vertex_segments):
        split_story = etree.Element(
            "Story", name=f"{story.get('name')}_seq_{index + 1}"
        )
        split_act, _ = _build_act_segment(
            act, maneuver_group, maneuver, event, action, segment, index
        )
        if previous_story_name is not None:
            _append_storyboard_element_start_trigger(
                split_act,
                condition_name=f"{split_act.get('name')}_start",
                storyboard_element_type="story",
                storyboard_element_ref=previous_story_name,
            )
        split_story.append(split_act)
        storyboard.insert(story_index + index, split_story)
        previous_story_name = split_story.get("name")


def _build_act_segment(act, maneuver_group, maneuver, event, action, segment, index):
    split_act = etree.Element("Act", name=f"{act.get('name')}_seq_{index + 1}")
    split_group = deepcopy(maneuver_group)
    split_group.set("name", f"{maneuver_group.get('name')}_seq_{index + 1}")
    actors = deepcopy(maneuver_group.find("Actors"))
    _clear_children(split_group)
    split_group.append(actors)
    split_maneuver = deepcopy(maneuver)
    split_maneuver.set("name", f"{maneuver.get('name')}_seq_{index + 1}")
    _clear_children(split_maneuver)
    split_event = _build_event(event, action, segment, index)
    split_maneuver.append(split_event)
    split_group.append(split_maneuver)
    split_act.append(split_group)
    return split_act, split_event


def _build_event(event, action, segment, index, previous_event_name=None):
    split_event = deepcopy(event)
    split_event.set("name", f"{event.get('name')}_seq_{index + 1}")
    _clear_children(split_event)
    split_action = _build_action(action, segment, index)
    split_event.append(split_action)
    if previous_event_name is not None:
        _append_storyboard_element_start_trigger(
            split_event,
            condition_name=f"{split_event.get('name')}_start",
            storyboard_element_type="event",
            storyboard_element_ref=previous_event_name,
        )
    return split_event


def _build_action(action, segment, index):
    split_action = deepcopy(action)
    split_action.set("name", f"{action.get('name')}_seq_{index + 1}")
    trajectory = split_action.find(".//TrajectoryRef/Trajectory")
    trajectory.set("name", f"{trajectory.get('name')}_seq_{index + 1}")
    polyline = split_action.find(".//TrajectoryRef/Trajectory/Shape/Polyline")
    _clear_children(polyline)
    for vertex in segment:
        polyline.append(vertex)
    return split_action


def _append_storyboard_element_start_trigger(
    element,
    condition_name: str,
    storyboard_element_type: str,
    storyboard_element_ref: str,
):
    existing_start = element.find("StartTrigger")
    if existing_start is not None:
        element.remove(existing_start)

    start_trigger = etree.SubElement(element, "StartTrigger")
    condition_group = etree.SubElement(start_trigger, "ConditionGroup")
    condition = etree.SubElement(
        condition_group,
        "Condition",
        name=condition_name,
        delay="0",
        conditionEdge="rising",
    )
    by_value = etree.SubElement(condition, "ByValueCondition")
    etree.SubElement(
        by_value,
        "StoryboardElementStateCondition",
        storyboardElementType=storyboard_element_type,
        storyboardElementRef=storyboard_element_ref,
        state="completeState",
    )


def _clear_children(element):
    for child in list(element):
        element.remove(child)
