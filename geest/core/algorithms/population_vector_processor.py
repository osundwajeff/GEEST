# -*- coding: utf-8 -*-
"""Population vector processor for Regional S2S demographics.

Joins S2S demographic data directly to the H3 study area grid, reclassifies
into three tercile classes, and rasterizes per study area. Outputs are written
to the same paths as ``PopulationRasterProcessingTask`` so downstream
processors (bivariate score, subnational aggregation) work unchanged.
"""

import os
import shutil
import traceback
from typing import List

from qgis.core import Qgis, QgsTask

from geest.core.algorithms import AreaIterator
from geest.core.grid_column_utils import (
    _ensure_column_exists,
    _execute_sql_with_retry,
    _open_gpkg_for_write,
    get_grid_column_values,
    rasterize_grid_column,
    write_joined_values_to_grid,
)
from geest.utilities import log_message, resources_path

POPULATION_RAW_COLUMN = "population_raw"
POPULATION_RECLASSIFIED_COLUMN = "population"


class PopulationVectorProcessingTask(QgsTask):
    """Process S2S vector demographics into a 3-class population raster.

    Pipeline:
        1. Join S2S demographic values to study_area_grid via hex_id -> h3_index.
        2. Compute global tercile breaks across all study areas.
        3. Reclassify grid column to 3 classes (Low=1, Medium=2, High=3).
        4. Rasterize per area to produce reclassified_{index}.tif.
        5. Build VRT and copy QML style.
    """

    def __init__(
        self,
        s2s_output_path: str,
        s2s_field: str,
        study_area_gpkg_path: str,
        working_directory: str,
        cell_size_m: float,
        force_clear: bool = False,
    ):
        """Initialize the population vector processor.

        Args:
            s2s_output_path: Path to the S2S demographics GeoPackage.
            s2s_field: S2S field name to use (e.g. "sum_pop_2024").
            study_area_gpkg_path: Path to the study area GeoPackage.
            working_directory: Parent working directory.
            cell_size_m: Target cell size in meters for rasterization.
            force_clear: If True, delete existing outputs before processing.
        """
        super().__init__("Population Vector Processor", QgsTask.CanCancel)
        self.s2s_output_path = s2s_output_path
        self.s2s_field = s2s_field
        self.study_area_gpkg_path = study_area_gpkg_path
        self.output_dir = os.path.join(working_directory, "population")
        self.cell_size_m = cell_size_m
        self.force_clear = force_clear
        self.reclassified_rasters: List[str] = []

        if self.force_clear and os.path.exists(self.output_dir):
            for file in os.listdir(self.output_dir):
                os.remove(os.path.join(self.output_dir, file))
        os.makedirs(self.output_dir, exist_ok=True)

        log_message("---------------------------------------------")
        log_message("Population vector processing task initialized")
        log_message("---------------------------------------------")
        log_message(f"S2S output path: {self.s2s_output_path}")
        log_message(f"S2S field: {self.s2s_field}")
        log_message(f"Study area GeoPackage: {self.study_area_gpkg_path}")
        log_message(f"Output directory: {self.output_dir}")
        log_message(f"Cell size: {self.cell_size_m}")
        log_message(f"Force clear: {self.force_clear}")
        log_message("---------------------------------------------")

    def run(self) -> bool:
        """Execute the population vector processing pipeline.

        Returns:
            True if the task completed successfully, False otherwise.
        """
        try:
            self._join_s2s_to_grid()
            self._reclassify_grid_column()
            self._rasterize_per_area()
            self._generate_vrt()
            return True
        except Exception as error:
            log_message(f"Population vector processing failed: {error}", level=Qgis.Critical)
            log_message(traceback.format_exc(), level=Qgis.Critical)
            return False

    def finished(self, result: bool) -> None:
        """Called when the task completes.

        Args:
            result: True if the task succeeded.
        """
        if result:
            log_message("Population vector processing completed successfully.")
        else:
            log_message("Population vector processing failed.")

    def _join_s2s_to_grid(self) -> None:
        """Join S2S demographic values to study_area_grid via hex_id -> h3_index."""
        source_layer = os.path.splitext(os.path.basename(self.s2s_output_path))[0]

        log_message(
            f"Joining S2S demographics to grid: {self.s2s_field} from {source_layer}",
            tag="GeoE3",
            level=Qgis.Info,
        )

        updated_count = write_joined_values_to_grid(
            gpkg_path=self.study_area_gpkg_path,
            column_name=POPULATION_RAW_COLUMN,
            source_gpkg=self.s2s_output_path,
            source_layer=source_layer,
            source_key_field="hex_id",
            target_key_field="h3_index",
            source_value_field=self.s2s_field,
        )

        if updated_count < 0:
            raise RuntimeError(
                f"Failed to join S2S demographics to grid. " f"Source: {self.s2s_output_path}, field: {self.s2s_field}"
            )

        log_message(
            f"Joined {updated_count} S2S demographic values to grid column '{POPULATION_RAW_COLUMN}'",
            tag="GeoE3",
            level=Qgis.Info,
        )

    def _reclassify_grid_column(self) -> None:
        """Reclassify the raw population column into 3 tercile classes.

        Class 1/2/3 values are written into the ``population`` column using a
        single SQL CASE update, derived from the global tercile boundaries. The
        raw S2S population counts in ``population_raw`` are left untouched so
        downstream processors (bivariate score, subnational aggregation) can
        always rely on the raw input being available.
        """
        values = get_grid_column_values(self.study_area_gpkg_path, POPULATION_RAW_COLUMN)
        if not values:
            raise RuntimeError("No population values found in grid after S2S join.")

        global_min = min(values)
        global_max = max(values)

        log_message(
            f"Population value range: min={global_min:.4f}, max={global_max:.4f}, n={len(values)}",
            tag="GeoE3",
            level=Qgis.Info,
        )

        if not _ensure_column_exists(self.study_area_gpkg_path, POPULATION_RECLASSIFIED_COLUMN):
            raise RuntimeError(f"Failed to create grid column '{POPULATION_RECLASSIFIED_COLUMN}'.")

        from geest.core.grid_column_utils import _quote_sql_identifier

        population_col = _quote_sql_identifier(POPULATION_RECLASSIFIED_COLUMN)
        raw_col = _quote_sql_identifier(POPULATION_RAW_COLUMN)

        if global_min == global_max:
            log_message(
                "All population values are identical; assigning all cells to class 1.",
                tag="GeoE3",
                level=Qgis.Warning,
            )
            self._execute_class_update(
                f"UPDATE study_area_grid SET {population_col} = 1 "
                f"WHERE {raw_col} IS NOT NULL"  # nosec B608 -- identifiers quoted, literal value
            )
            return

        range_third = (global_max - global_min) / 3.0
        break1 = global_min + range_third
        break2 = global_min + 2.0 * range_third

        log_message(
            f"Reclassifying population into 3 classes: "
            f"(−inf, {break1:.4f}]→1, ({break1:.4f}, {break2:.4f}]→2, ({break2:.4f}, +inf]→3",
            tag="GeoE3",
            level=Qgis.Info,
        )

        class_update_sql = (
            f"UPDATE study_area_grid SET {population_col} = CASE "  # nosec B608 -- identifiers quoted, numeric literals
            f"WHEN {raw_col} IS NULL THEN NULL "
            f"WHEN {raw_col} <= {break1:.10f} THEN 1 "
            f"WHEN {raw_col} <= {break2:.10f} THEN 2 "
            f"ELSE 3 "
            f"END "
            f"WHERE {raw_col} IS NOT NULL"
        )
        self._execute_class_update(class_update_sql)

        log_message(
            f"Reclassified {len(values)} grid cells into 3 population classes.",
            tag="GeoE3",
            level=Qgis.Info,
        )

    def _execute_class_update(self, sql: str) -> None:
        """Run a raw SQL UPDATE against the study area grid.

        Args:
            sql: The SQL UPDATE statement to execute.
        """
        ds = _open_gpkg_for_write(self.study_area_gpkg_path)
        if not ds:
            raise RuntimeError(f"Could not open GeoPackage: {self.study_area_gpkg_path}")

        try:
            _execute_sql_with_retry(ds, sql, dialect="SQLite")
        finally:
            ds = None

    def _rasterize_per_area(self) -> None:
        """Rasterize the reclassified population column per study area."""
        area_iterator = AreaIterator(self.study_area_gpkg_path)

        for index, (current_area, clip_area, current_bbox, progress, area_name) in enumerate(area_iterator):
            if self.isCanceled():
                return

            output_path = os.path.join(self.output_dir, f"reclassified_{index}.tif")

            if not self.force_clear and os.path.exists(output_path):
                log_message(f"Reusing existing reclassified raster: {output_path}")
                self.reclassified_rasters.append(output_path)
                continue

            rect = current_bbox.boundingBox()
            extent = (rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum())

            log_message(
                f"Rasterizing population column '{POPULATION_RECLASSIFIED_COLUMN}' "
                f"for area {area_name} (index={index})",
                tag="GeoE3",
                level=Qgis.Info,
            )

            success = rasterize_grid_column(
                gpkg_path=self.study_area_gpkg_path,
                column_name=POPULATION_RECLASSIFIED_COLUMN,
                output_raster_path=output_path,
                cell_size=self.cell_size_m,
                extent=extent,
                nodata=-9999.0,
                area_name=area_name,
            )

            if success:
                self.reclassified_rasters.append(output_path)
                log_message(f"Rasterized population for area {area_name}: {output_path}")
            else:
                log_message(
                    f"Failed to rasterize population for area {area_name}",
                    level=Qgis.Warning,
                )

    def _generate_vrt(self) -> None:
        """Build a VRT from all per-area reclassified rasters and copy QML style."""
        if not self.reclassified_rasters:
            log_message("No reclassified rasters to build VRT from.", level=Qgis.Warning)
            return

        from qgis import processing

        reclassified_vrt_path = os.path.join(self.output_dir, "reclassified_population.vrt")
        reclassified_qml_path = os.path.join(self.output_dir, "reclassified_population.qml")

        params = {
            "INPUT": self.reclassified_rasters,
            "RESOLUTION": 0,
            "SEPARATE": False,
            "OUTPUT": reclassified_vrt_path,
        }
        processing.run("gdal:buildvirtualraster", params)
        log_message(f"Generated VRT for reclassified population rasters: {reclassified_vrt_path}")

        source_qml = resources_path("resources", "qml", "population_3_classes.qml")
        if os.path.exists(source_qml):
            shutil.copyfile(source_qml, reclassified_qml_path)
            log_message(f"Copied QML style to {reclassified_qml_path}")
