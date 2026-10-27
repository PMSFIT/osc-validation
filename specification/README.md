# OpenSCENARIO validation specification

The specification describes the behavior checked by the validation suite in the
same Git revision. It is a scoped validation contract, not a claim of full
OpenSCENARIO conformance or a list of everything the generators can emit.

- [Subset definition](subset.md): complete current scope and restrictions.
- [Coverage matrix](coverage.md): behavior, test identifiers, expectations, and limits.
- [Release index](releases.md): released definitions pinned to commits and maintenance rules.
- [Tool compatibility](tool_compatibility.md): historical implementation constraints and workarounds.

Read the subset and coverage matrix together. Only the documented combinations
are covered; including an XML type does not imply coverage of all its attributes
or combinations. Unit tests in `tests/` support the implementation but do not
expand the engine validation contract.

The current documents are a working definition until committed and released.
For reproducible validation, use the specification and tests from the same commit
and record that commit, the engine version, options, and test profile with results.
