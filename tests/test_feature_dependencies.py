"""Keep feature reference behavior independent of other feature packages."""

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest


@pytest.mark.parametrize("package_name", ["features", "reference"])
def test_feature_imports_stay_within_owner_or_shared(package_name):
    root = Path(__file__).resolve().parents[1] / "osc_validation" / package_name
    prefix = "osc_validation.features."
    violations = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if package_name == "features" and len(relative.parts) < 2:
            continue
        owner = relative.parts[0] if package_name == "features" else "shared"
        package = ".".join(["osc_validation", package_name, *relative.parts[:-1]])
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    module = resolve_name("." * node.level + module, package)
                # Include names to catch `from osc_validation.features import foo`.
                imports = [module] + [module + "." + alias.name for alias in node.names]
            else:
                continue
            for module in imports:
                if module.startswith(prefix):
                    dependency = module[len(prefix) :].split(".")[0]
                    if dependency not in {owner, "shared"}:
                        violations.append(f"{relative}:{node.lineno}: {module}")
    assert not violations, "Cross-feature imports:\n" + "\n".join(violations)
