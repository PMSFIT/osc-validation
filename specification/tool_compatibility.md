# Tool compatibility notes

Engine setup constraints are separate from the [subset](subset.md). A workaround
is not a standard requirement. External [test profiles](../README.md#test-profiles)
can declare expected failures for an engine version.

## Historical engine observations

These notes have not been reverified against current engine releases:

- esmini needed init `TeleportAction` entries to spawn objects.
- GTGen needed an `Ego` or `Host` name and OpenDRIVE road network; off-road
  placement could terminate execution.
- GTGen needed empty vehicle `Properties`; the original note records a fix in 9.0.0.
- GTGen did not support story-completion storyboard termination; simulation-time
  stopping was used instead.

Current cases use explicit on-road init poses and near-start policies where
needed. If a workaround changes tested behavior, document it in the case and
matrix.
