#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the GEOE3 test suite inside a qgis/qgis docker container.

Invoked by scripts/run-docker-tests.sh with the repository mounted at
/tests_directory. Initializes QgsApplication and the Processing framework
before discovery — running pytest/unittest directly against the mounted
checkout crashes without this.
"""
import sys
import unittest

sys.path.insert(0, "/usr/share/qgis/python/plugins")
sys.path.insert(0, "/tests_directory")
sys.path.insert(0, "/tests_directory/test")

from qgis.core import QgsApplication  # noqa: E402

QGIS_APP = QgsApplication([], False)
QGIS_APP.initQgis()

from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()


def prune_packaging_tests(suite):
    """Drop tests that require the packaged plugin layout.

    test_init expects metadata.txt at the repository root, which only
    exists after `python admin.py build --tests` assembles the plugin
    package (as CI does). In a raw checkout it always fails.
    """
    kept = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            kept.addTest(prune_packaging_tests(item))
        elif not item.id().startswith("test_init."):
            kept.addTest(item)
    return kept


loader = unittest.TestLoader()
suite = prune_packaging_tests(loader.discover("/tests_directory/test", pattern="test_*.py"))
print("NOTE: test_init skipped (requires packaged layout from `python admin.py build --tests`).")
result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
verdict = "PASS" if result.wasSuccessful() else "FAIL"
print(
    f"GEOE3-SUITE: verdict={verdict} run={result.testsRun} "
    f"failures={len(result.failures)} "
    f"errors={len(result.errors)} "
    f"skipped={len(result.skipped)}"
)
sys.stdout.flush()
sys.stderr.flush()
# QGIS python may segfault during interpreter teardown (notably on 4.x
# master), corrupting the exit code after a clean run. The shell wrapper
# therefore trusts the GEOE3-SUITE verdict line above, not this code.
sys.exit(0 if result.wasSuccessful() else 1)
