# -*- coding: utf-8 -*-
"""Environmental Hazards raster datasource widget."""

from geest.core.constants import ENV_HAZARD_SOURCE_LABELS, ENV_HAZARD_SOURCE_URLS

from .raster_datasource_widget import RasterDataSourceWidget


class EnvironmentalHazardsRasterDataSourceWidget(RasterDataSourceWidget):
    """Datasource widget for environmental hazard layers at national/local scale.

    Behaves like the generic raster datasource widget but also exposes a link
    to the World Bank Data Catalog source dataset for the selected hazard.
    """

    def add_internal_widgets(self) -> None:
        """Build raster controls and append the source dataset link."""
        super().add_internal_widgets()
        hazard_id = self._hazard_id()
        self._add_source_link(
            ENV_HAZARD_SOURCE_URLS.get(hazard_id, ""),
            ENV_HAZARD_SOURCE_LABELS.get(hazard_id, ""),
        )

    def _hazard_id(self) -> str:
        """Return the lowercased indicator id for this hazard."""
        return str(self.attributes.get("id", "")).lower()
