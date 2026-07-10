#!/usr/bin/env bash

# Run the GEOE3 test suite inside the official QGIS docker images.
#
# Usage: scripts/run-docker-tests.sh [3|4|all]
#   3    QGIS 3.34 LTR   (qgis/qgis:release-3_34, Qt5/PyQt5)
#   4    QGIS 4.x master (qgis/qgis:latest,       Qt6/PyQt6)
#   all  Both (default)
#
# Exposed as nix run .#test-qgis3 / .#test-qgis4 / .#test-qgis
#
# This is the local counterpart of scripts/run-tests.sh (which drives the
# full docker-compose CI harness); it runs the suite directly in a
# throwaway container with the working tree mounted, so it is much faster
# for day-to-day use.

set -euo pipefail

VERSION="${1:-all}"
REPO_ROOT="${GEOE3_REPO:-$PWD}"

if [ ! -d "${REPO_ROOT}/geest" ] || [ ! -d "${REPO_ROOT}/test" ]; then
    echo "Error: run from the GEOE3 repository root (or set GEOE3_REPO)." >&2
    exit 2
fi

IMAGE_3="qgis/qgis:release-3_34"
IMAGE_4="qgis/qgis:latest"
# The ghsl tests mutate this file in the mounted checkout; restore it
# afterwards if it was clean before the run.
GHSL_GPKG="geest/resources/ghsl/ghs-mod-2023-tile-scheme.gpkg"

OVERALL=0

run_suite() {
    local image="$1"
    local label="$2"
    local gpkg_was_clean=0

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo " GEOE3 test suite on ${label} (${image})"
    echo "════════════════════════════════════════════════════════════"

    if git -C "${REPO_ROOT}" diff --quiet -- "${GHSL_GPKG}" 2>/dev/null; then
        gpkg_was_clean=1
    fi

    # QGIS python may segfault at interpreter teardown after a clean run
    # (notably 4.x master), so the container exit code is unreliable.
    # The runner prints a "GEOE3-SUITE: verdict=..." line we trust instead.
    # The timeout guards against xvfb-run occasionally wedging on shutdown.
    local suite_log
    suite_log="$(mktemp)"
    docker run --rm \
        -v "${REPO_ROOT}":/tests_directory \
        -w /tests_directory \
        -e GEOE3_TEST_DIR=/tests_directory/test \
        "${image}" \
        bash -c 'timeout 1800 xvfb-run -a python3 /tests_directory/scripts/docker_test_runner.py' \
        2>&1 | tee "${suite_log}" || true

    if [ "${gpkg_was_clean}" -eq 1 ] && ! git -C "${REPO_ROOT}" diff --quiet -- "${GHSL_GPKG}" 2>/dev/null; then
        echo "Restoring ${GHSL_GPKG} (mutated by ghsl tests)"
        git -C "${REPO_ROOT}" checkout -- "${GHSL_GPKG}"
    fi

    if grep -q "GEOE3-SUITE: verdict=PASS" "${suite_log}"; then
        echo "── ${label}: PASSED"
    else
        echo "── ${label}: FAILED"
        OVERALL=1
    fi
    rm -f "${suite_log}"
}

case "${VERSION}" in
    3)
        run_suite "${IMAGE_3}" "QGIS 3.34 LTR"
        ;;
    4)
        run_suite "${IMAGE_4}" "QGIS 4.x master"
        ;;
    all)
        run_suite "${IMAGE_3}" "QGIS 3.34 LTR"
        run_suite "${IMAGE_4}" "QGIS 4.x master"
        ;;
    *)
        echo "Usage: $0 [3|4|all]" >&2
        exit 2
        ;;
esac

exit "${OVERALL}"
