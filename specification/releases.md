# Specification releases and revision binding

The authoritative subset for a run is committed alongside its tests at the
**same full Git commit SHA**. Package version alone cannot identify development
or modified checkouts. Tags name releases; commit links pin actual contents.

| Suite revision | Full commit SHA | Documents or source snapshot |
| --- | --- | --- |
| Working checkout (unreleased reorganization) | Record the commit containing these changes once committed | [Subset](subset.md), [coverage](coverage.md) |
| `v0.2.0` | `48029fb84dbd80d9ed9f707fda90db973759151e` | [Release source](https://github.com/PMSFIT/osc-validation/tree/48029fb84dbd80d9ed9f707fda90db973759151e) |
| `v0.1.0` | `a73c96b8ea3a494f5326ab07661f41bad327ee24` | [Release source](https://github.com/PMSFIT/osc-validation/tree/a73c96b8ea3a494f5326ab07661f41bad327ee24) |

Release source links identify immutable snapshots, without claiming today's
specification structure or 28-case inventory existed then.

The comparison baseline for this reorganization is commit
`eb202f819cfb6c0cd6ec4e91f38929befebe0ec1`. That identifies the inspected source,
not a commit containing these new documents.

## Release maintenance

1. Update subset and matrix alongside test/assertion changes that affect scope.
   Review generated settings and actual assertions, not only test names.
2. Collect the suite; check all engine test functions, parameter counts, links,
   and version expectations against the matrix.
3. Commit code and specification together and tag that commit. Do not move
   release tags or rewrite historical released definitions.
4. Publish permanent subset/matrix links at the resolved SHA. Add the tag/SHA to
   this index afterward or in release metadata; a commit cannot embed its own SHA.
5. Keep suite version/SHA, engine version, command/options, profile, and artifacts
   with reports. Mark dirty checkouts as modified and preserve their diff when
   reproducibility is needed.

Git preserves snapshots; per-release directory copies are unnecessary. Release
notes should identify scope additions and corrected expectations. This document
defines reporting requirements; it does not claim the report generator already
automates all this metadata. A subset pass does not imply full conformance.
