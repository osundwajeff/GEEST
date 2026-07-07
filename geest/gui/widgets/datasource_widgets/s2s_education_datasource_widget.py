# -*- coding: utf-8 -*-
"""S2S-backed Education datasource widget."""

import os

from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt.QtCore import QSettings

from geest.core.constants import DEFAULT_S2S_EDUCATION_URBANIZATION_FIELDS

from .s2s_datasource_widget import S2SDataSourceWidget


class S2SEducationDataSourceWidget(S2SDataSourceWidget):
    """Education-specific S2S datasource widget with fixed field configuration."""

    OUTPUT_FILENAME = "s2s_education"

    # ------------------------------------------------------------------
    # Hook overrides
    # ------------------------------------------------------------------

    def _get_s2s_filename(self) -> str:
        """Return education-specific output filename stem."""
        return self.OUTPUT_FILENAME

    def _get_gate_label(self) -> str:
        """Return education-specific gate label."""
        return "widget:education"

    def _get_s2s_fields(self) -> list:
        """Return the fixed list of Education S2S fields."""
        return list(DEFAULT_S2S_EDUCATION_URBANIZATION_FIELDS)

    def _get_s2s_field_name(self) -> str:
        """Return a human-readable field name for UI messages."""
        return "education proxy"

    def _get_s2s_success_message(self) -> str:
        """Return the status text shown on successful download."""
        return "S2S education data downloaded"

    def _resolve_default_s2s_output_path(self, working_directory: str) -> str:
        """Resolve the standard Education S2S output path."""
        if not working_directory:
            return ""
        return os.path.join(working_directory, "study_area", f"{self.OUTPUT_FILENAME}.gpkg")

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def add_internal_widgets(self) -> None:
        """Build controls and hide manual S2S fields input for Education."""
        super().add_internal_widgets()
        if hasattr(self, "layer_combo"):
            self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.PolygonLayer)
        default_fields_text = ",".join(DEFAULT_S2S_EDUCATION_URBANIZATION_FIELDS)
        self.s2s_fields_line_edit.setText(default_fields_text)
        self.s2s_fields_line_edit.setEnabled(False)
        self.s2s_fields_line_edit.setVisible(False)

        settings = QSettings()
        working_directory = settings.value("last_working_directory", "")
        self._load_best_available_s2s_output(working_directory)

    def _load_best_available_s2s_output(self, working_directory: str) -> None:
        """Load configured output path or fallback to default Education output path."""
        configured_path = str(self.s2s_output_path or "").strip()
        candidate_paths = []
        if configured_path:
            candidate_paths.append(configured_path)

        fallback_path = self._resolve_default_s2s_output_path(working_directory)
        if fallback_path and fallback_path not in candidate_paths:
            candidate_paths.append(fallback_path)

        for candidate in candidate_paths:
            if not candidate or not os.path.exists(candidate):
                continue

            layer_name = os.path.splitext(os.path.basename(candidate))[0]
            output_layer = self._load_or_reuse_vector_layer(candidate, layer_name)
            if output_layer is None:
                continue

            self.s2s_output_path = candidate
            self._switch_to_layer_mode(output_layer)
            self.s2s_controls.set_downloaded()
            self.update_attributes()
            return

    def update_attributes(self):
        """Persist fixed Education S2S fields and common metadata."""
        super().update_attributes()
        self.attributes["s2s_fields"] = list(DEFAULT_S2S_EDUCATION_URBANIZATION_FIELDS)
        self.attributes["s2s_fields_text"] = ",".join(DEFAULT_S2S_EDUCATION_URBANIZATION_FIELDS)
