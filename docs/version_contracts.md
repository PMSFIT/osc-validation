# OpenSCENARIO XML version contracts

Each validation case explicitly declares the OpenSCENARIO XML releases for
which its input and expected behavior apply. The supported release identifiers
are `1.3.0`, `1.3.1`, and `1.4.0`. The generated XOSC header contains only
`revMajor` and `revMinor`, so it cannot distinguish patch releases. Patch-level
selection is tracked in the test contract, test ID, and reports. The header
check validates the major and minor components only.

## Running cases

`osc-validate` and direct pytest runs default to version `1.4.0`. Select a version
with `--osc-version 1.3.1`; repeat the option to run a matrix. Each applicable
test is collected once per selected version with an `osc-1.3.1` or `osc-1.4.0`
parameter in its ID. Cases that do not declare the selected release are
deselected. HTML reports and JUnit properties include the contract and whether
the expectation is conformance or exploratory.

```bash
pytest osc_validation/validation --collect-only --osc-version 1.3.1 --osc-version 1.4.0
osc-validate --tool ESMini --osc-version 1.3.1 --include-exploratory
```

Exploratory tests are excluded by default. When explicitly included, their
failures affect the run's exit status just like other tests. Run them separately
when a conformance-only result is needed.

## Writing a case

Use a single explicit marker on each test. List multiple releases only after
reviewing the scenario and its expectations against each release. The collector
rejects missing, empty, duplicate, conflicting, or unknown declarations.

```python
@pytest.mark.osc_versions("1.3.0", "1.3.1", "1.4.0")
def test_init_action(scenario_contract, ...):
    result = build_init_speed_action_case(
        InitActionCaseSpec(..., contract=scenario_contract)
    )
    ...
```

The `osc_version` fixture is also available for cases with version-specific
expectations. Pass `scenario_contract` when generating XOSC. Generators must
validate the availability of version-specific constructs; a contract alone does
not validate XML against a schema. The `generate_tool_trace` fixture checks the
XOSC header against the selected contract before invoking the engine.

When versions define different behavior, either use the `osc_version` fixture
to select explicit expectations or write separate tests. Mark non-normative
behavior with `@pytest.mark.exploratory`. Add a new release to `OscVersion`
only when the suite is ready to recognize it, and explicitly review each case
before adding that release to its marker. There is no implicit future-version
matching.

## Profiles

Profile rules can target a function, a parameter pattern, or a versioned test
ID. A function-level rule applies to every version. For example, a bare
exception pattern `*osc-1.4.0*` exempts only 1.4.0 instances. Existing patterns
without a version still match the original parameter IDs after the version
component is removed. Older two-component version patterns match all patch
releases of that major/minor version. Inspect `--collect-only` output for the
full IDs before writing version-specific patterns.

