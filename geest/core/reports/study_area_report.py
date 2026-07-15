# -*- coding: utf-8 -*-
"""📦 Study Area Report module.

This module contains functionality for study area report.
"""

from qgis.core import QgsLayout, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import Qt

from geest.utilities import log_message, resources_path

from .base_report import CHARCOAL, CONTENT_W, CYAN, GREY, HEADER_H, MARGIN, MIST, NAVY, BaseReport

# Friendly page titles for the raw GeoPackage layer names.
LAYER_DISPLAY_NAMES = {
    "study_area_bbox": "Study Area Bounding Box",
    "study_area_bboxes": "Part Bounding Boxes",
    "study_area_polygons": "Study Area Polygons",
    "study_area_clip_polygons": "Clip Polygons",
    "chunks": "Processing Chunks",
    "study_area_creation_status": "Creation Timings",
    "ghsl_settlements": "GHSL Settlements",
}


class StudyAreaReport(BaseReport):
    """
    A class to generate a PDF report from a GeoPackage table of study area creation status data.

    The report computes summary statistics (based on the field "geom_total_duration_secs")
    and creates a QGIS layout (report) that is then exported to PDF.
    """

    def __init__(self, gpkg_path: str, report_name="Study Area Creation Report"):
        """
        Initialize the report.

        Parameters:
            layer_input (str): A file path to the GeoPackage (from which the
                layer "study_area_creation_status" and other layers will be loaded).
            report_name (str): The title to use for the report.

        Raises:
            ValueError: If the layer cannot be loaded from the given file path.
            TypeError: If layer_input is neither a string nor a QgsVectorLayer.
        """
        # Shares the analysis report cover (artwork + frosted title panel)
        # so the two reports form a matched set.
        template_path = resources_path("resources", "qpt", "analysis_summary_report_template.qpt")
        super().__init__(template_path, report_name)

        self.layers = None  # Will hold the loaded layers from the GeoPackage

        uri = f"{gpkg_path}|layername=study_area_creation_status"
        self.gpkg_path = gpkg_path
        layer = QgsVectorLayer(uri, "study_area_creation_status", "ogr")
        if not layer.isValid():
            raise ValueError("Failed to load layer from the given file path.")

        self.report_name = report_name
        self.load_layers_from_gpkg()
        self.page_descriptions = {}
        self.page_descriptions[
            "summary"
        ] = """
        How long each step of the study area preparation took, followed by the
        processed study area itself. Each internal data product used by the
        analysis is described on the pages that follow.
        """
        self.page_descriptions[
            "study_area_bbox"
        ] = """
        The study area bounding box (bbox) is the outer extent of the entire study area.
        The bounding box width and height is guaranteed to be a factor of the
        analysis dimension. All other data products are then aligned to this bbox.
        """
        self.page_descriptions[
            "study_area_bboxes"
        ] = """
        The study area bboxes are a set of smaller bounding boxes that surround each
        polygon in the study area. They are grid aligned such that the origin and
        furthest corners are guaranteed to be a factor of the analysis dimension
        apart.
        """
        self.page_descriptions[
            "study_area_polygons"
        ] = """
        The study area polygons are the single part form of all polygons in the
        study area. Any invalid geometries will have been discarded.
        """
        self.page_descriptions[
            "study_area_grid"
        ] = """
        The study area grid is a set of polygon squares that each have the
        x and y dimension of the analysis cell size. They are guaranteed to
        be aligned to the study area bbox and bboxes layers. The grid is used
        to create a version of the study_area_polygons that have been expanded
        out so that the edges align exactly to the grid.

        The grid is also used to perform certain types of spatial analysis such as
        the Active Transport layer analyses.
        """
        self.page_descriptions[
            "chunks"
        ] = """
        The chunks are the result of splitting the study area grid into smaller
        chunks that are used to process the study area more efficiently. Each chunk
        is labelled as to whether it is inside, on the edge of, or outside the
        geometry of a study area polygon. Grid cells in chunks that are 'inside' can be processed
        more efficiently as we can skip the intersection test with the study area polygons.
        """
        self.page_descriptions[
            "study_area_clip_polygons"
        ] = """
        The study area clip polygons are the original polygon areas but expanded so that the edges
        of the polygon exactly coincide with the edges of the grid. This will ensure that all analysis
        results are coherant with the grid."""
        self.page_descriptions[
            "study_area_creation_status"
        ] = """
        The study area creation status is a record of the time taken to process each part of the study area.
        """
        self.page_descriptions[
            "ghsl_settlements"
        ] = """
        The Global Human Settlement Layer is used to identify settled areas within the study region. Study area polygons are marked with whether they intersect GHSL settlement data, which is used in various analysis workflows.
        """
        self._cleanup_done = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup happens."""
        self.cleanup()
        return False  # Don't suppress exceptions

    def cleanup(self):
        """
        Explicitly clean up layers. Call this when done with the report,
        or use the context manager pattern.
        """
        if self._cleanup_done:
            return
        if self.layers:
            for layer_name, layer in self.layers.items():
                if layer and layer.isValid():
                    try:
                        QgsProject.instance().removeMapLayer(layer.id())
                        log_message(f"Layer '{layer_name}' removed from project.")
                    except Exception as e:
                        log_message(f"Could not remove layer '{layer_name}': {e}")
            self.layers = None
        self._cleanup_done = True

    def compute_ghsl_statistics(self):
        """
        Compute GHSL intersection statistics from the study_area_polygons layer.

        Returns:
            dict: A dictionary containing 'total', 'intersects', 'percentage', and 'has_ghsl'.
                  Returns None if GHSL data is not available.
        """
        uri = f"{self.gpkg_path}|layername=study_area_polygons"
        layer = QgsVectorLayer(uri, "study_area_polygons", "ogr")

        if not layer.isValid():
            return None

        # Check if intersects_ghsl field exists
        field_names = [field.name() for field in layer.fields()]
        if "intersects_ghsl" not in field_names:
            return None

        total_count = 0
        intersects_count = 0

        for feat in layer.getFeatures():
            total_count += 1
            intersects_ghsl = feat["intersects_ghsl"]
            if intersects_ghsl == 1:
                intersects_count += 1

        if total_count == 0:
            return None

        percentage = (intersects_count / total_count) * 100

        return {
            "total": total_count,
            "intersects": intersects_count,
            "percentage": percentage,
            "has_ghsl": True,
        }

    def compute_study_area_creation_statistics(self, field_name="geom_total_duration_secs"):
        """
        Compute statistical summary for a given field in the layer.

        Parameters:
            field_name (str): The attribute field on which to compute statistics.

        Returns:
            dict: A dictionary containing 'count', 'min', 'max', 'mean', 'sum', and 'std_dev'.
        """
        values = []
        uri = f"{self.gpkg_path}|layername=study_area_creation_status"
        layer = QgsVectorLayer(uri, "study_area_creation_status", "ogr")
        for feat in layer.getFeatures():
            val = feat[field_name]
            if val is not None:
                values.append(val)
        if not values:
            raise ValueError(f"No valid data found for field '{field_name}'.")

        count_val = len(values)
        sum_val = sum(values)
        min_val = min(values)
        max_val = max(values)
        mean_val = sum_val / count_val
        # Compute population standard deviation
        var = sum((x - mean_val) ** 2 for x in values) / count_val
        std_dev = var**0.5

        return {
            "count": count_val,
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "sum": sum_val,
            "std_dev": std_dev,
        }

    def add_ghsl_info_to_page(self, current_page, y: float = 214):
        """Add GHSL statistics and attribution as a styled panel.

        Parameters:
            current_page (int): The page number where the GHSL info should be added.
            y (float): Top of the panel in mm.
        """
        ghsl_stats = self.compute_ghsl_statistics()
        if not ghsl_stats:
            return
        panel_h = 42
        self._rect(MARGIN, y, CONTENT_W, panel_h, MIST, current_page)
        self._rect(MARGIN, y, 2.2, panel_h, CYAN, current_page)
        self._label(
            "Settlement coverage",
            MARGIN + 8,
            y + 4.5,
            CONTENT_W - 16,
            7,
            current_page,
            size=12,
            color=NAVY,
            bold=True,
        )
        self._label(
            f"<p>{ghsl_stats['intersects']} of {ghsl_stats['total']} study area parts "
            f"({ghsl_stats['percentage']:.1f}%) intersect GHSL settlement data.<br/>"  # noqa E231
            "Source: Copernicus / EC JRC — GHS-SMOD R2023A, licensed CC BY 4.0.</p>",
            MARGIN + 8,
            y + 13,
            CONTENT_W - 16,
            panel_h - 17,
            current_page,
            size=9.5,
            color=CHARCOAL,
            html=True,
        )

    def make_summary_page(self, current_page: int) -> int:
        """Add the summary page: creation statistics as stat cards over a map.

        Returns the next free page number.
        """
        self.make_page(
            title="Study Area Summary",
            description_key="summary",
            current_page=current_page,
            show_header_and_footer=True,
        )
        stats = self.compute_study_area_creation_statistics()
        cards = [
            (f"{stats['count']}", "Parts processed"),
            (f"{stats['sum']:.1f} s", "Total processing time"),  # noqa E231
            (f"{stats['mean']:.1f} s", "Average per part"),  # noqa E231
            (f"{stats['min']:.1f} s", "Fastest part"),  # noqa E231
            (f"{stats['max']:.1f} s", "Slowest part"),  # noqa E231
            (f"{stats['std_dev']:.1f} s", "Standard deviation"),  # noqa E231
        ]
        card_w = 56
        card_h = 24
        gap = (CONTENT_W - 3 * card_w) / 2
        top = HEADER_H + 26
        for i, (value, caption) in enumerate(cards):
            x = MARGIN + (i % 3) * (card_w + gap)
            y = top + (i // 3) * (card_h + 6)
            self._rect(x, y, card_w, card_h, MIST, current_page)
            self._rect(x, y, card_w, 1.4, CYAN, current_page)
            self._label(
                value,
                x,
                y + 4,
                card_w,
                10,
                current_page,
                size=15,
                color=NAVY,
                bold=True,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )
            self._label(
                caption,
                x,
                y + 15.5,
                card_w,
                6,
                current_page,
                size=8,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )
        polygons_layer = self.layers.get("study_area_polygons")
        if polygons_layer:
            self.make_map(
                layers=[polygons_layer],
                crs=polygons_layer.crs(),
                current_page=current_page,
                x=MARGIN,
                y=top + 2 * card_h + 14,
                map_width_mm=CONTENT_W,
                map_height_mm=160,
            )
        return current_page + 1

    def create_layout(self):
        """
        Create a QGIS layout (report) with a styled cover, credits, a summary
        page, and one page per internal data product.

        The layout is stored in the attribute self.layout.
        """
        project = QgsProject.instance()
        self.layout = QgsLayout(project)
        self.layout.initializeDefaults()
        self.load_template()
        self.style_cover_page()

        self.make_credits_page(current_page=1)
        current_page = self.make_summary_page(current_page=2)

        # One page per remaining layer. The grid is skipped (too many
        # features to render); the polygons layer is the summary page's map.
        layers_to_skip = {"study_area_grid", "study_area_polygons"}
        for layer_name, layer in self.layers.items():
            if layer_name in layers_to_skip:
                log_message(f"Skipping layer '{layer_name}' in report")
                continue
            title = LAYER_DISPLAY_NAMES.get(layer_name, layer_name.replace("_", " ").title())
            self.make_page(
                title=title,
                description_key=layer_name,
                current_page=current_page,
                show_header_and_footer=True,
            )
            if layer_name == "study_area_creation_status":
                self.make_text_table(
                    vector_layer=layer,
                    sort_column="geom_total_duration_secs",
                    current_page=current_page,
                )
            elif layer_name == "ghsl_settlements":
                self.make_map(
                    layers=[layer],
                    crs=layer.crs(),
                    current_page=current_page,
                    x=MARGIN,
                    y=64,
                    map_width_mm=CONTENT_W,
                    map_height_mm=140,
                )
                self.add_ghsl_info_to_page(current_page)
            else:
                self.make_map(
                    layers=[layer],
                    crs=layer.crs(),
                    current_page=current_page,
                    x=MARGIN,
                    y=64,
                    map_width_mm=CONTENT_W,
                    map_height_mm=195,
                )
            current_page += 1
