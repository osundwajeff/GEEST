# -*- coding: utf-8 -*-
"""Guard against unscoped Qt enum accesses (removed in PyQt6 / QGIS 4).

Statically collects every ``QClass.Attr`` reference in the geest package and
verifies the attribute exists on the class in the running PyQt. On PyQt5 both
the unscoped and scoped forms exist, so this test only bites (as intended)
when the suite runs on the QGIS 4 / PyQt6 image — but the reference scan
itself keeps working on both.

When this test fails it prints the scoped replacement to use, e.g.::

    QDockWidget.DockWidgetClosable -> QDockWidget.DockWidgetFeature.DockWidgetClosable
"""

import enum
import re
import unittest
from pathlib import Path

from qgis.PyQt import QtCore, QtGui, QtNetwork, QtWidgets

MODULES = [QtWidgets, QtGui, QtCore, QtNetwork]
try:
    from qgis.PyQt import QtWebEngineWidgets

    MODULES.append(QtWebEngineWidgets)
except Exception:  # nosec B110 — webengine is optional in test images
    pass

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "geest"
PATTERN = re.compile(r"\b(Q[A-Za-z0-9]+)\.([A-Z][A-Za-z0-9_]*)\b")


def _find_class(name):
    for mod in MODULES:
        cls = getattr(mod, name, None)
        if cls is not None:
            return cls
    return None


def _scoped_replacement(cls, cls_name, attr):
    for type_name in dir(cls):
        candidate = getattr(cls, type_name, None)
        if isinstance(candidate, type) and issubclass(candidate, enum.Enum) and attr in candidate.__members__:
            return f"{cls_name}.{type_name}.{attr}"
    return None


STYLE_MEMBER_RE = re.compile(r"\.((?:PM|SP|SH|SE|CE|CC)_[A-Za-z0-9_]+)")
STYLE_SCOPED_RE = re.compile(
    r"QStyle\.(?:PixelMetric|StandardPixmap|StyleHint|SubElement|ControlElement|ComplexControl)"
    r"\.(?:PM|SP|SH|SE|CE|CC)_"
)
EVENT_MEMBER_RE = re.compile(r"\bevent\.[A-Z][A-Za-z0-9_]+")


class TestQtEnumCompliance(unittest.TestCase):
    def test_no_instance_enum_member_access(self):
        """Enum members must not be read off instances (removed in PyQt6).

        Covers the two patterns seen in the field: QStyle members like
        ``widget.style().PM_DefaultFrameWidth`` (use
        ``QStyle.PixelMetric.PM_...``) and event members like
        ``event.Resize`` (use ``QEvent.Type.Resize``).
        """
        offenders = []
        for path in PACKAGE_ROOT.rglob("*.py"):
            if "__pycache__" in str(path) or "extlibs" in str(path):
                continue
            for line_no, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                code = line.split("#")[0]
                for match in STYLE_MEMBER_RE.finditer(code):
                    # allowed only in the fully scoped QStyle.<EnumType>.<member> form
                    if not STYLE_SCOPED_RE.search(code[: match.end()]):
                        offenders.append(f"{path.name}:{line_no}: {match.group(0)}")
                for match in EVENT_MEMBER_RE.finditer(code):
                    offenders.append(f"{path.name}:{line_no}: {match.group(0)}")
        self.assertEqual(
            [],
            offenders,
            "Instance enum member access (breaks on PyQt6) — use the scoped enum type:\n" + "\n".join(offenders),
        )

    def test_all_qt_attribute_references_resolve(self):
        """Every QClass.Attr referenced in geest/ must exist in this PyQt."""
        references = {}
        for path in PACKAGE_ROOT.rglob("*.py"):
            if "__pycache__" in str(path) or "extlibs" in str(path):
                continue
            for line_no, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                code = line.split("#")[0]
                for match in PATTERN.finditer(code):
                    key = (match.group(1), match.group(2))
                    references.setdefault(key, []).append(f"{path.relative_to(PACKAGE_ROOT.parent)}:{line_no}")

        self.assertTrue(references, "reference scan found nothing — is the package path right?")

        problems = []
        for (cls_name, attr), locations in sorted(references.items()):
            cls = _find_class(cls_name)
            if cls is None or hasattr(cls, attr):
                continue
            scoped = _scoped_replacement(cls, cls_name, attr) or "??? (no owning enum found)"
            problems.append(f"{cls_name}.{attr} -> use {scoped}\n    " + "\n    ".join(locations))

        self.assertEqual(
            [],
            problems,
            "Unscoped/unknown Qt attribute references (break on PyQt6):\n" + "\n".join(problems),
        )


if __name__ == "__main__":
    unittest.main()
