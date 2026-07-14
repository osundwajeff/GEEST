# -*- coding: utf-8 -*-
"""S2S-backed Environmental Hazards raster datasource widget."""

import os

from qgis.PyQt.QtWidgets import QFileDialog

from geest.core.constants import DEFAULT_S2S_ENV_HAZARD_FIELDS

from .s2s_datasource_widget import S2SDataSourceWidget
from .s2s_ntl_raster_datasource_widget import S2SNTLRasterDataSourceWidget


class S2SEnvironmentalHazardsRasterDataSourceWidget(S2SNTLRasterDataSourceWidget):
    """Regional datasource widget that fetches hazard values from S2S."""

    # ------------------------------------------------------------------
    # Hook overrides — customise S2S behaviour for environmental hazards
    # ------------------------------------------------------------------

    def _get_s2s_filename(self) -> str:
        """Return hazard-specific output filename stem."""
        return f"s2s_environmental_hazards_{self._hazard_id()}"

    def _get_gate_label(self) -> str:
        """Return hazard-specific gate label."""
        return f"widget:hazard:{self._hazard_id()}"

    def _get_s2s_fields(self) -> list:
        """Return the hazard field to fetch from S2S."""
        return [self._hazard_field_from_attributes()]

    def _get_s2s_field_name(self) -> str:
        """Return a human-readable field name for UI messages."""
        return "environmental hazards"

    def _get_s2s_success_message(self) -> str:
        """Return the status text shown on successful download."""
        return "S2S environmental hazards downloaded"

    def _get_missing_field_error(self) -> str:
        """Return the error message when hazard field is not configured."""
        return f"No S2S environmental hazards field is configured for {self._hazard_id()}."

    def _validate_required_fields(self, fields: list) -> str:
        """Validate that the hazard field is configured."""
        if not fields or not fields[0]:
            return self._get_missing_field_error()
        return ""

    def _resolve_default_s2s_output_path(self, working_directory: str) -> str:
        """Return hazard-specific default S2S output path."""
        if not working_directory:
            return ""
        hazard_id = self._hazard_id()
        if not hazard_id:
            return ""
        return os.path.join(working_directory, "study_area", f"s2s_environmental_hazards_{hazard_id}.gpkg")

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def add_internal_widgets(self) -> None:
        """Build controls and configure hazard-specific S2S defaults."""
        super().add_internal_widgets()
        if hasattr(self, "s2s_vector_field_combo"):
            self.s2s_vector_field_combo.setLayer(None)
            self.s2s_vector_field_combo.setCurrentIndex(-1)
            self.s2s_vector_field_combo.setEnabled(False)
            self.s2s_vector_field_combo.setVisible(False)
        self.s2s_ntl_field = self._hazard_field_from_attributes()
        self.s2s_status_label.setToolTip(f"S2S field: {self.s2s_ntl_field}")
        self._select_existing_hazard_output_layer()

    def _update_vector_field_combo(self) -> None:
        """Disable manual field selection for S2S-specific hazards workflow."""
        if hasattr(self, "s2s_vector_field_combo"):
            self.s2s_vector_field_combo.setLayer(None)
            self.s2s_vector_field_combo.setCurrentIndex(-1)
            self.s2s_vector_field_combo.setEnabled(False)
            self.s2s_vector_field_combo.setVisible(False)

    # ------------------------------------------------------------------
    # Hazard-specific helpers
    # ------------------------------------------------------------------

    def _hazard_id(self) -> str:
        """Return the lowercased indicator id for this hazard."""
        return str(self.attributes.get("id", "")).lower()

    def _hazard_field_from_attributes(self) -> str:
        """Resolve S2S hazard field from indicator id or existing attribute."""
        existing = self.attributes.get("s2s_hazard_field", "")
        if existing:
            return str(existing)
        return DEFAULT_S2S_ENV_HAZARD_FIELDS.get(self._hazard_id(), "")

    def select_raster(self) -> None:
        """Select raster or vector file for environmental hazards input."""
        last_dir = self.settings.value("GeoE3/lastRasterDir", "")
        if not last_dir:
            last_dir = self.settings.value("GeoE3/lastShapefileDir", "")
        indicator_name = self.attributes.get("name") or "Environmental Hazards"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {indicator_name} Layer",
            last_dir,
            "Supported (*.vrt *.tif *.asc *.gpkg *.shp *.geojson *.json *.sqlite *.fgb *.parquet);;"
            "Raster (*.vrt *.tif *.asc);;"
            "Vector (*.gpkg *.shp *.geojson *.json *.sqlite *.fgb *.parquet);;"
            "All files (*)",
        )
        if not file_path:
            return

        self.raster_layer_combo.setVisible(False)
        self.raster_line_edit.setVisible(True)
        self.raster_line_edit.setText(file_path)
        parent_directory = os.path.dirname(file_path)
        self.settings.setValue("GeoE3/lastRasterDir", parent_directory)
        self.settings.setValue("GeoE3/lastShapefileDir", parent_directory)
        self.resizeEvent(None)
        self._update_vector_field_combo()

    def update_attributes(self):
        """Update attributes with hazard-specific S2S metadata."""
        super().update_attributes()
        self.attributes["s2s_hazard_field"] = self.s2s_ntl_field
        self.attributes["s2s_ntl_field"] = ""

    def _select_existing_hazard_output_layer(self) -> None:
        """Auto-select existing S2S hazard output when available."""
        if not self.s2s_output_path:
            self.s2s_output_path = self.attributes.get("s2s_output_path", "")
        if not self.s2s_output_path or not os.path.exists(self.s2s_output_path):
            return

        layer_name = os.path.splitext(os.path.basename(self.s2s_output_path))[0]
        output_layer = S2SDataSourceWidget._load_or_reuse_vector_layer(self.s2s_output_path, layer_name)
        if output_layer is None:
            self._set_status("S2S output invalid")
            return

        self.raster_line_edit.clear()
        self.raster_line_edit.setVisible(False)
        self.raster_layer_combo.setVisible(True)
        self.raster_layer_combo.setLayer(output_layer)
        self.s2s_controls.set_downloaded()
        self.update_attributes()
