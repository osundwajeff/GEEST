# -*- coding: utf-8 -*-
"""Guard against ``return <value>`` inside workflow ``__init__`` methods.

Returning a value from ``__init__`` raises ``TypeError: __init__() should
return None`` the moment the branch is hit (seen in the field as a crash
when running an unconfigured indicator). Misconfiguration must raise
``WorkflowNotConfiguredError`` instead, which the queue manager converts
into a skipped job and a user-facing message.

Pure AST analysis — no QGIS required — so this runs on every image.
"""

import ast
import unittest
from pathlib import Path

# Derive the location from the imported package when possible (correct in
# every layout); fall back to path heuristics so this test also runs on a
# bare python without QGIS installed.
try:
    import geest.core.workflows

    WORKFLOWS_DIR = Path(geest.core.workflows.__file__).resolve().parent
except ImportError:
    _parent = Path(__file__).resolve().parent.parent
    _root = _parent / "geest" if (_parent / "geest" / "core").exists() else _parent
    WORKFLOWS_DIR = _root / "core" / "workflows"


def _value_returns_in_init(tree):
    """Yield (class_name, line) for every value-return in an __init__ body."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for method in node.body:
            if not (isinstance(method, ast.FunctionDef) and method.name == "__init__"):
                continue
            stack = list(method.body)
            while stack:
                stmt = stack.pop()
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    continue  # nested callables may return whatever they like
                if isinstance(stmt, ast.Return) and stmt.value is not None:
                    yield node.name, stmt.lineno
                stack.extend(ast.iter_child_nodes(stmt))


class TestWorkflowInitHygiene(unittest.TestCase):
    def test_no_value_returns_in_workflow_inits(self):
        offenders = []
        checked = 0
        for path in sorted(WORKFLOWS_DIR.glob("*.py")):
            checked += 1
            tree = ast.parse(path.read_text(), filename=str(path))
            for class_name, line in _value_returns_in_init(tree):
                offenders.append(f"{path.name}:{line} ({class_name}.__init__)")
        self.assertGreater(checked, 10, "workflow directory scan looks wrong")
        self.assertEqual(
            [],
            offenders,
            "__init__ must not return a value — raise WorkflowNotConfiguredError instead:\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
