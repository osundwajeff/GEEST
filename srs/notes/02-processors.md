Now I have sufficient information to create a comprehensive report. Let me compile all this knowledge into a detailed markdown SRS document.

Based on my thorough reverse-engineering of the GeoE3 QGIS plugin codebase, here is the complete structured markdown report:

---

# GeoE3 QGIS Plugin - Software Requirements Specification (SRS)
## Workflows and Processor Types Documentation

---

## Table of Contents
1. [Workflow Factory Selection Logic](#workflow-factory-selection-logic)
2. [Workflow Base Class](#workflow-base-class)
3. [Indicator Workflows](#indicator-workflows)
4. [Per-Cell Counting Workflows](#per-cell-counting-workflows)
5. [Accessibility/Buffer Workflows](#accessibilitybuffer-workflows)
6. [Special Analysis Workflows](#special-analysis-workflows)
7. [Raster Processing Workflows](#raster-processing-workflows)
8. [Safety/Classification Workflows](#safetyclassification-workflows)
9. [Aggregation Workflows](#aggregation-workflows)
10. [Standalone Processors](#standalone-processors)
11. [Aggregation Pyramid](#aggregation-pyramid)

---

## Workflow Factory Selection Logic

**File:** `/geest/core/workflow_factory.py`

The `WorkflowFactory.create_workflow()` method routes to concrete workflow classes based on the `analysis_mode` attribute from a JsonTreeItem and optional `analysis_scale` parameter (local/national/regional).

### Selection Conditions

| analysis_mode | Workflow Class | Conditions | Purpose |
|---|---|---|---|
| `use_index_score` | DefaultIndexScoreWorkflow | None | Uniform score across clip area |
| `use_contextual_index_score` | ContextualIndexScoreWorkflow | None | Contextual dimension scoring |
| `use_eplex_score` | EPLEXWorkflow | None | Employment Protection Legislation Index |
| `use_index_score_with_ookla` | IndexScoreWithOoklaWorkflow | None | Index score masked to Ookla connectivity |
| `use_index_score_with_ghsl` | IndexScoreWithGHSLWorkflow | None | Index score masked to GHSL settlements |
| `use_multi_buffer_point` | MultiBufferDistancesNativeWorkflow or MultiBufferDistancesORSWorkflow | `use_ors_for_accessibility` setting (default: False) | Multiple concentric isochrones or ORS routing |
| `use_single_buffer_point` | SinglePointBufferWorkflow | None | Single buffer around points |
| `use_point_per_cell` | PointPerCellWorkflow | None | Count point features per grid cell |
| `use_polyline_per_cell` | PolylinePerCellWorkflow | None | Count line features per grid cell |
| `use_osm_transport_polyline_per_cell` | OsmTransportPolylinePerCellWorkflow | None | OSM road network transport scoring per cell |
| `use_polygon_per_cell` | PolygonPerCellWorkflow | Special: S2S education proxy when `analysis_scale=="regional"` and `layer_id=="education"` and `s2s_output_path` set | Count/score polygon features per cell |
| `factor_aggregation` | FactorAggregationWorkflow | None | Aggregate indicators within a factor |
| `dimension_aggregation` | DimensionAggregationWorkflow | None | Aggregate factors within a dimension |
| `analysis_aggregation` | AnalysisAggregationWorkflow | None | Aggregate dimensions to produce GeoE3 Score |
| `use_csv_to_point_layer` | AcledImpactWorkflow | None | ACLED conflict data point buffering |
| `use_classify_polygon_into_classes` | ClassifiedPolygonWorkflow | None | Classify polygons into discrete classes |
| `use_classify_safety_polygon_into_classes` | SafetyPolygonWorkflow | None | Safety perception polygon classification |
| `use_nighttime_lights` | SafetyRasterWorkflow | Optional S2S field `s2s_ntl_field` for regional scale | Nighttime lights raster masking/reclassification |
| `use_environmental_hazards` | RasterReclassificationWorkflow | Optional S2S hazard field for regional scale | Environmental hazard raster reclassification (fire, flood, landslide, cyclone) |
| `use_street_lights` | StreetLightsBufferWorkflow | None | Street light proximity analysis |
| `Do Not Use` | DontUseWorkflow | None | Disabled/placeholder workflow |

---

## Workflow Base Class

**File:** `/geest/core/workflows/workflow_base.py`

All concrete workflows inherit from `WorkflowBase(QObject)`, establishing common patterns:

### Initialization
- **Parameters:** `item` (JsonTreeItem), `cell_size_m` (float), `analysis_scale` (local/national/regional), `feedback` (QgsFeedback), `context` (QgsProcessingContext), `working_directory` (str)
- **Loads Study Area Resources:**
  - `study_area.gpkg` layers: study_area_bbox, study_area_bboxes, study_area_polygons, study_area_clip_polygons, study_area_grid
  - Target CRS resolution from GeoPackage (with fallback to gpkg metadata tables via OGR SQL)
  - GHSL settlements layer (auto-downloaded if missing for certain workflows)

### Common Attributes
- **layer_id:** Generated from item ID with prefixes: `dim_*` for dimensions, `fac_*` for factors, raw ID for indicators
- **target_crs:** QgsCoordinateReferenceSystem resolved from study_area_gpkg
- **result_file_key, result_key:** Output attribute keys ("result_file", "result")
- **aggregation:** Boolean flag (True only for aggregation workflows)
- **use_grid_first:** Boolean flag enabling direct grid column writing (default varies by workflow)
- **Grid Column Prefix:** Layer ID becomes column name for grid updates

### Abstract Methods (must implement)
- `_process_features_for_area(current_area, clip_area, current_bbox, area_features, index, area_name)` → str (raster path)
- `_process_raster_for_area(current_area, clip_area, current_bbox, area_raster, index, area_name)` → Optional[str]
- `_process_aggregate_for_area(current_area, clip_area, current_bbox, index, area_name)` → Optional[str]

### Common Methods
- **updateProgress(float):** Emit progressChanged signal
- **updateStatus(str):** Emit statusChanged signal
- **ensure_ghsl_data():** Check/download GHSL settlements layer
- **_rasterize(layer, bbox, index, value_field, default_value):** Rasterize vector layer using gdal:rasterize with configured cell size
- **_study_area_bbox():** Get study area extent in target CRS
- **_study_area_bbox_4326():** Get study area extent in EPSG:4326

---

## Indicator Workflows

### 1. DefaultIndexScoreWorkflow

**File:** `/geest/core/workflows/index_score_workflow.py`

**Selection:** `analysis_mode == "use_index_score"`

**Purpose:** Assign uniform enablement score (0-5 Likert scale) to all cells in study area.

**Inputs:**
- **Item Attributes:** `index_score` (0-100, rescaled to 0-5 Likert)
- **Grid Layer:** study_area_grid from GeoPackage
- **No feature layer required**

**Algorithm (Grid-First Mode, Default):**
1. Retrieve index_score from item attributes and rescale: `(score / 100) * 5`
2. Call `write_uniform_value_to_grid(gpkg_path, column_name=layer_id, value=rescaled_score, area_name)`
   - Updates all study_area_grid cells in named area to uniform score
3. Call `rasterize_grid_column(gpkg_path, column_name=layer_id, output_raster_path, cell_size, extent, nodata=-9999, area_name)`
   - Creates GeoTIFF raster from grid column values
   - Output: `{layer_id}_{index}.tif`

**Outputs:**
- **Raster File:** `workflow_directory/{layer_id}_{index}.tif` (GeoTIFF, 32-bit float, cell_size_m resolution)
- **Grid Column:** study_area_grid.`{layer_id}` populated with rescaled score
- **Item Attributes:** result_file, result status

**QGIS/GDAL Algorithms Used:**
- gdal:rasterize (via rasterize_grid_column)
- OGR SQL UPDATE (via write_uniform_value_to_grid)

**Legacy (Raster-First) Mode:**
1. Create scored boundary layer (Polygon shapefile with score field)
2. Rasterize using gdal:rasterize

---

### 2. ContextualIndexScoreWorkflow

**File:** `/geest/core/workflows/contextual_index_score_workflow.py`

**Selection:** `analysis_mode == "use_contextual_index_score"`

**Purpose:** Score contextual dimensions (e.g., gender dimensions) using predefined score mapping.

**Inputs:**
- **Item Attributes:** `index_score` (0-100)
- **Score Mapping Table:** contextual_index_score_mappings.py defines thresholds → output scores

**Algorithm (Grid-First):**
1. Retrieve index_score and find highest threshold ≤ score in mapping table
2. Use mapped score instead of linear rescaling
3. Write uniform value to grid with mapped score
4. Rasterize grid column to output raster

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (GeoTIFF, contextually mapped values)
- Grid column: study_area_grid.`{layer_id}`

---

### 3. EPLEXWorkflow

**File:** `/geest/core/workflows/eplex_workflow.py`

**Selection:** `analysis_mode == "use_eplex_score"`

**Purpose:** Create uniform raster filled with Employment Protection Legislation Index score (alternative to gender-based scoring when disabled).

**Inputs:**
- **Item Attributes:** `eplex_score` (float, 0-1 normalized or 0-5 Likert)

**Algorithm:**
1. Convert raw score to Likert 0-5 scale
   - If 0 ≤ raw ≤ 1: multiply by 5
   - If 1 < raw ≤ 5: use as-is (already Likert)
   - Otherwise: clamp to [0, 5]
2. Create in-memory Polygon layer with single feature (clip_area) and EPLEX value
3. Rasterize to GeoTIFF

**Outputs:**
- Raster: `{layer_id}_{index}.tif`
- Single uniform value across study area

---

### 4. IndexScoreWithGHSLWorkflow

**File:** `/geest/core/workflows/index_score_with_ghsl_workflow.py`

**Selection:** `analysis_mode == "use_index_score_with_ghsl"`

**Purpose:** Apply index score only to grid cells that intersect GHSL (Global Human Settlements Layer) settlement polygons; remaining cells stay NULL (masked).

**Inputs:**
- **Item Attributes:** `index_score` (0-100, rescaled to Likert)
- **GHSL Layer:** study_area_grid `ghsl_settlements` layer (auto-downloaded if missing)

**Algorithm (Grid-First, Required):**
1. Ensure GHSL settlements data is available (download from GHS-SMOD if needed)
2. Clear target grid column
3. Spatial join: `write_spatial_join_to_grid()`
   - For each grid cell, check if it intersects any GHSL settlement polygon
   - If yes: set grid cell to rescaled index_score
   - If no: leave NULL
4. Post-process: set all remaining NULL cells to 0 (indicating non-settlement = no enablement)
5. Rasterize grid column

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (masked to settlements; 0 outside settlements, score inside)
- Grid column: study_area_grid.`{layer_id}` with spatial-join result

**Special Handling:**
- Auto-downloads GHSL data if not in GeoPackage
- GHSLDownloader and GHSLProcessor used for tile retrieval and processing

---

### 5. IndexScoreWithOoklaWorkflow

**File:** `/geest/core/workflows/index_score_with_ookla_workflow.py`

**Selection:** `analysis_mode == "use_index_score_with_ookla"`

**Purpose:** Apply index score only to grid cells with Ookla broadband/mobile connectivity data.

**Inputs:**
- **Item Attributes:** `index_score`, connectivity threshold
- **Ookla Layer:** Downloaded or provided connectivity grid

**Algorithm:**
- Similar to GHSL workflow but uses Ookla connectivity hexagons
- Spatial join identifies cells with connectivity
- Rescaled index score applied to connected cells

**Outputs:**
- Raster: connectivity-masked index score

---

## Per-Cell Counting Workflows

These workflows count features (points/lines/polygons) per grid cell and optionally apply scoring functions.

### 6. PointPerCellWorkflow

**File:** `/geest/core/workflows/point_per_cell_workflow.py`

**Selection:** `analysis_mode == "use_point_per_cell"`

**Purpose:** Count point features intersecting each grid cell, optionally apply scoring function.

**Inputs:**
- **Item Attributes:**
  - `point_per_cell_shapefile` or `point_per_cell_layer_source` (point layer path)
  - Optional scoring/weighting configuration
- **Area Features:** Point vector layer filtered to study area

**Algorithm (Grid-First, Default):**
1. Clear grid column once at workflow start
2. For each area:
   - Call `count_features_per_grid_cell(gpkg_path, column_name, features_layer, feedback)`
     - Iterates area_features, finds intersecting grid cells
     - Increments count in grid column for each intersecting cell
3. Rasterize grid column with cell counts

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (count values 0-N per cell)
- Grid column: study_area_grid.`{layer_id}` with feature counts

**QGIS/GDAL Algorithms:**
- features_per_cell_processor.select_grid_cells_and_count_features()
- OGR SQL spatial join for count aggregation

**Legacy (Raster-First):**
1. select_grid_cells_and_count_features() → temporary grid with counts
2. assign_values_to_grid() → reclassify to 0-5 scale
3. Rasterize with rasterize value field

---

### 7. PolylinePerCellWorkflow

**File:** `/geest/core/workflows/polyline_per_cell_workflow.py`

**Selection:** `analysis_mode == "use_polyline_per_cell"`

**Purpose:** Count line features intersecting each grid cell.

**Inputs:**
- **Item Attributes:** `polyline_per_cell_shapefile` or `polyline_per_cell_layer_source`
- **Area Features:** Line vector layer

**Algorithm:**
- Identical to PointPerCellWorkflow
- `count_features_per_grid_cell()` works with line geometries
- Uses prepared geometry intersection tests (optimization for lines)

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (line counts per cell)
- Grid column: feature counts

---

### 8. PolygonPerCellWorkflow

**File:** `/geest/core/workflows/polygon_per_cell_workflow.py`

**Selection:** `analysis_mode == "use_polygon_per_cell"`

**Purpose:** Count polygon features intersecting each grid cell; supports S2S education proxy for regional scale.

**Inputs:**
- **Item Attributes:**
  - `polygon_per_cell_shapefile` or `polygon_per_cell_layer_source`
  - For education proxy: `s2s_output_path`, `s2s_fields` (S2S GeoPackage path and field list)
- **Area Features:** Polygon vector layer or S2S grid layer

**Special Case: S2S Education Proxy (Regional Scale)**

**Trigger Condition:**
```
analysis_scale == "regional"
  AND layer_id == "education"
  AND s2s_output_path is set
  AND s2s_fields is configured
```

**Algorithm:**
1. For each area, join S2S urbanization fields to study_area_grid:
   - ghs_11_pop (sparse rural), ghs_12_pop (very sparse rural), ghs_13_pop (sparse rural)
   - ghs_22_pop (low urban), ghs_23_pop (medium urban), ghs_30_pop (high urban)
   - ghs_total_pop (total population)
2. Compute urban share ratio:
   ```
   urban_share = (ghs_22_pop + ghs_23_pop + ghs_30_pop) / ghs_total_pop
   ```
3. Classify to Likert 1-5 using thresholds [0.2, 0.4, 0.6, 0.8]:
   - < 0.2: score 1
   - 0.2-0.4: score 2
   - 0.4-0.6: score 3
   - 0.6-0.8: score 4
   - ≥ 0.8: score 5
4. Rasterize result

**Normal Algorithm:**
- Count polygon features per grid cell
- Optional per-cell scoring function

**Outputs:**
- Raster: `{layer_id}_{index}.tif`
- Grid column: polygon counts or education proxy Likert scores

---

### 9. OsmTransportPolylinePerCellWorkflow

**File:** `/geest/core/workflows/osm_transport_polyline_per_cell_workflow.py`

**Selection:** `analysis_mode == "use_osm_transport_polyline_per_cell"`

**Purpose:** Score grid cells based on active transport (cycling + walking) network coverage using OSM data.

**Inputs:**
- **Item Attributes:**
  - `osm_transport_polyline_per_cell_shapefile` or `osm_transport_polyline_per_cell_layer_source` or `road_network_layer_path`
  - Optional analysis_scale-specific scoring config from mappings
- **Area Features:** Road/path line layer (OSM highway/cycleway)

**Algorithm:**
1. Call `select_grid_cells_and_assign_transport_score()`
   - Iterates grid cells
   - Finds intersecting road/cycleway features
   - Assigns score based on transport mode:
     - Highway types (trunk, primary, secondary, tertiary, unclassified, residential, living_street, pedestrian) → Likert scores
     - Cycleway types → higher scores for dedicated cycling infrastructure
     - Best-score logic: if cell has both highway and cycleway, use max score
   - Regional scale may use percent-intersection thresholds
2. Rasterize scored grid

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (transport quality scores)
- Grid layer: grid with assigned transport scores

**Grid Column Behavior:**
- Currently uses legacy raster-first approach (direct rasterization)
- May transition to grid-first in future

---

## Accessibility/Buffer Workflows

### 10. SinglePointBufferWorkflow

**File:** `/geest/core/workflows/single_point_buffer_workflow.py`

**Selection:** `analysis_mode == "use_single_buffer_point"`

**Purpose:** Create single Euclidean buffer around point features; score grid cells by containment.

**Inputs:**
- **Item Attributes:**
  - `single_buffer_point_shapefile` or `single_buffer_point_layer_source`
  - `single_buffer_point_layer_distance` or `default_single_buffer_distance` (buffer radius in meters)
  - Optional mapping-based configuration
- **Area Features:** Point vector layer

**Algorithm (Grid-First, Default):**
1. Clear grid column once
2. For each area:
   - Call `write_buffer_values_to_grid(gpkg_path, column_name, features_layer, buffer_distance_m, area_name)`
     - For each point feature, create buffer of specified radius
     - Spatial join: find all grid cells within any buffer
     - Set grid cell value = 5 (inside buffer, high accessibility)
     - Cells outside remain NULL (0 accessibility)
3. Rasterize grid column

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (binary: 5 inside buffer, 0 outside)
- Grid column: buffer presence indicator

**Legacy (Raster-First):**
1. Buffer points using gdal:buffer or processing:buffer
2. Rasterize buffered polygons with fixed value

---

### 11. MultiBufferDistancesNativeWorkflow

**File:** `/geest/core/workflows/multi_buffer_distances_native_workflow.py`

**Selection:** `analysis_mode == "use_multi_buffer_point"` + `use_ors_for_accessibility == False` (default)

**Purpose:** Create concentric isochrones (distance-based service areas) around points using road network; score grid cells by closest distance band.

**Inputs:**
- **Item Attributes:**
  - `multi_buffer_point_shapefile` or `multi_buffer_point_layer_source` (point layer)
  - `multi_buffer_travel_distances` (comma-separated list of distance thresholds in meters, up to 5)
  - `multi_buffer_travel_mode` ("Walking" → distance-based, "Driving" → time-based)
  - `road_network_layer_path` (network graph for routing)
  - Optional mapping_id/factor_id for config lookup
- **Analysis Scale:** national/local (uses network analysis); regional (may use simple buffer)
- **Area Features:** Point layer for routing origins

**Algorithm (Complex):**
1. Validate/parse distances: [d1, d2, d3, d4, d5] (maximum 5 distances, e.g., [500, 1000, 1500, 2000, 2500])
2. Load road network layer (linear features)
3. For each area:
   a. Create isochrones using QGIS native:serviceareafromlayer
      - Input: road_network_layer, point_layer (area_features)
      - Distances: [d1, d2, d3, d4, d5]
      - Strategy: 0 (shortest distance) or 1 (fastest time)
      - Tolerance: network topology tolerance 50m
   b. Generate concave hull polygons from service area points
      - Alpha parameter 0.3 for concavity
      - Results: nested polygons representing distance bands
   c. Score grid cells by outermost distance band reached:
      - Inside d1 → score 5
      - d1 to d2 → score 4
      - d2 to d3 → score 3
      - d3 to d4 → score 2
      - d4 to d5 → score 1
      - Outside d5 → score 0
   d. Call `write_buffer_values_to_grid()` with scored isochrones
4. Rasterize grid column

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (nested distance bands scored 0-5)
- Grid column: distance-based accessibility scores
- Intermediate: isochrone polygons (GeoPackage)

**QGIS Algorithms:**
- native:serviceareafromlayer (batch isochrone generation)
- native:concavehull (isochrone boundary refinement)

**Special Handling:**
- Validates road network layer validity and connectivity
- Handles points with no network access (marked with warning)
- ORS routing (alternative) uses ORS API instead of local network

---

### 12. MultiBufferDistancesORSWorkflow

**File:** `/geest/core/workflows/multi_buffer_distances_ors_workflow.py`

**Selection:** `analysis_mode == "use_multi_buffer_point"` + `use_ors_for_accessibility == True` (setting)

**Purpose:** Create isochrones using OpenRouteService (ORS) cloud API instead of local network.

**Inputs:**
- Same as MultiBufferDistancesNativeWorkflow
- **ORS API Key:** from settings (geest.ors_api_key)
- **Travel Mode:** car (driving), foot (walking), bicycle (cycling)

**Algorithm:**
1. Validate ORS API key from settings
2. For each area point:
   - Call ORS isochrones API with distance values
   - Returns GeoJSON polygons representing distance bands
   - Score polygons as per native workflow
3. Merge all point isochrones for the area
4. Score grid cells
5. Rasterize

**Outputs:**
- Raster: distance-based scores from ORS API
- Grid column: ORS-derived accessibility

---

## Special Analysis Workflows

### 13. AcledImpactWorkflow

**File:** `/geest/core/workflows/acled_impact_workflow.py`

**Selection:** `analysis_mode == "use_csv_to_point_layer"`

**Purpose:** Process ACLED (Armed Conflict Location & Event Data) CSV of conflict events; create point layer with temporal/event-type scoring and buffer-based impact zones.

**Inputs:**
- **Item Attributes:**
  - `use_csv_to_point_layer_csv_file` (path to ACLED CSV export)
  - Mapping configuration from ACLED mappings: `event_scores`, `buffer_distances` (per event type)
- **CSV Fields:** latitude, longitude, event_id_cnty, event_date, event_type, year, data_source, iso, event_id_no_cnty, fatalities, time_precision, event_code, iso_code, admin1, geo_precision, source_scale, notes, url, year, time_precision, timestamp

**Algorithm:**
1. Load CSV file as GeoPackage-backed point layer
2. Parse coordinates (lat/lon) to Point geometries in target CRS
3. For each event, assign score based on:
   - Event type (from ACLED mapping: riots, protests, violence, etc.) → score 0-5
   - Temporal decay (older events = lower impact)
4. For each area:
   - Filter events to area features
   - Create buffer around each event (distance from mapping, e.g., 500m-2km)
   - Spatial join: find grid cells within any buffer
   - Aggregate scores: max score within buffer for each cell
5. Rasterize scored grid

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (conflict impact scores)
- Grid column: conflict intensity
- Point layer: ACLED events with scores (GeoPackage)

**Mapping:** ACLED mappings define event_scores and buffer_distances per event type

---

## Raster Processing Workflows

### 14. RasterReclassificationWorkflow

**File:** `/geest/core/workflows/raster_reclassification_workflow.py`

**Selection:** `analysis_mode == "use_environmental_hazards"`

**Purpose:** Reclassify environmental hazard raster values (fire risk, flood probability, landslide susceptibility, cyclone exposure) into Likert 0-5 scores; optional S2S regional grid path.

**Inputs:**
- **Item Attributes:**
  - `environmental_hazards_raster` or `environmental_hazards_layer_source` (raster path)
  - Hazard type: fire, flood, landslide, cyclone (determines reclassification rules)
  - Regional-only: `s2s_output_path` and `s2s_hazard_field`
- **Raster Layer:** Environmental hazard GeoTIFF or VRT

**Reclassification Rules (Hazard-Specific):**

**Fire:**
```
Value Range → Score
-∞ to 0    → 5.0 (not in fire zone)
0 to 1     → 4.0
1 to 2     → 3.0
2 to 5     → 2.0
5 to 8     → 1.0
8 to ∞     → 0 (severe fire risk)
```

**Flood:**
```
Value Range (days) → Score
-1 to 0           → 5.0 (not flood zone)
0 to 180          → 4.0
180 to 360        → 3.0
360 to 540        → 2.0
540 to 720        → 1.0
720 to 900        → 0
```

**Landslide:**
```
Value (susceptibility class) → Score
0                           → 5.0
1                           → 4.0
2                           → 3.0
3                           → 2.0
4                           → 1.0
5                           → 0
```

**Cyclone:**
```
Value Range (return period years) → Score
-1 to 0   → 5.0
0 to 25   → 4.0
25 to 50  → 3.0
50 to 75  → 2.0
75 to ∞   → 1.0
```

**Regional S2S Path (Alternative):**
- If `analysis_scale == "regional"` and S2S output configured:
  - Join S2S grid `s2s_hazard_field` to study_area_grid
  - Apply reclassification rules to joined field
  - Write to grid column
  - Rasterize

**Algorithm (Raster Path):**
1. Load hazard raster
2. For each area:
   - Clip raster to area bbox using gdal:cliprasterbymasklayer
   - Apply reclassification using gdal:rasterreclassify with rule table
   - Mask output to study area (nodata = -9999 outside area)
3. Combine area rasters into VRT
4. Optional: write raster values to grid column

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (reclassified scores 0-5)
- Grid column: rasterized reclassified values (if grid-first enabled)

**QGIS Algorithms:**
- gdal:cliprasterbymasklayer
- gdal:rasterreclassify
- gdal:buildvirtualraster

---

### 15. SafetyRasterWorkflow

**File:** `/geest/core/workflows/safety_raster_workflow.py`

**Selection:** `analysis_mode == "use_nighttime_lights"`

**Purpose:** Process nighttime lights (NTL) raster; apply reclassification to score safety based on illumination; optional S2S regional path.

**Inputs:**
- **Item Attributes:**
  - Nighttime lights GeoTIFF/VRT (luminance or radiance values)
  - Regional-only: `s2s_ntl_field` (S2S GeoPackage field with NTL values)
- **Raster Layer:** NTL raster (typically NOAA VIIRS or similar)

**Reclassification Logic:**
- Lower light values → unsafe (score 0)
- Higher light values → safer (score 5)
- Specific thresholds configured per analysis_scale

**Algorithm:**
- Similar to RasterReclassificationWorkflow
- Reclassify NTL pixel values to safety scores
- Mask to study area
- Optional grid column writing

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (safety scores 0-5 from illumination)

---

## Safety/Classification Workflows

### 16. SafetyPolygonWorkflow

**File:** `/geest/core/workflows/safety_polygon_workflow.py`

**Selection:** `analysis_mode == "use_classify_safety_polygon_into_classes"`

**Purpose:** Classify polygon features (e.g., wards, neighborhoods) by perceived safety attribute into Likert scores; rasterize.

**Inputs:**
- **Item Attributes:**
  - `classify_safety_polygon_into_classes_shapefile` or `classify_safety_polygon_into_classes_layer_source`
  - `classify_safety_polygon_into_classes_selected_field` (polygon attribute to classify)
  - `classify_safety_polygon_into_classes_unique_values` (dict mapping field values → safety scores 0-100)
- **Area Features:** Polygon layer with safety perception/classification attribute

**Algorithm:**
1. For each area:
   a. Filter polygons to area
   b. Add "value" field if not present
   c. Iterate features:
      - Read selected_field value
      - Look up score in safety_mapping_table
      - Scale score 0-100 to 0-5 Likert
      - Write to "value" field
   d. Rasterize value field
2. Output raster with classified safety scores

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (scaled safety scores)

---

### 17. ClassifiedPolygonWorkflow

**File:** `/geest/core/workflows/classified_polygon_workflow.py`

**Selection:** `analysis_mode == "use_classify_polygon_into_classes"`

**Purpose:** Generic polygon classification into Likert scores based on polygon attribute.

**Inputs:**
- **Item Attributes:**
  - `classify_polygon_into_classes_shapefile` or `classify_polygon_into_classes_layer_source`
  - `classify_polygon_into_classes_selected_field` (attribute to map)
  - Classification mapping table (attribute value → score)
- **Area Features:** Polygon layer

**Algorithm:**
1. Similar to SafetyPolygonWorkflow
2. Assign scores per classification field value
3. Rasterize with value field

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (classified scores)
- Grid column: classification scores (grid-first mode)

---

### 18. StreetLightsBufferWorkflow

**File:** `/geest/core/workflows/street_lights_buffer_workflow.py`

**Selection:** `analysis_mode == "use_street_lights"`

**Purpose:** Buffer street light points; score grid cells by proximity/containment in street light buffer.

**Inputs:**
- **Item Attributes:**
  - Street lights point layer (OSM or custom)
  - Buffer distance (radius for street light illumination)
- **Area Features:** Point layer of street lights

**Algorithm:**
1. Similar to SinglePointBufferWorkflow
2. Buffer points by specified distance
3. Spatial join to grid cells within buffer
4. Score based on coverage density or binary containment

**Outputs:**
- Raster: `{layer_id}_{index}.tif` (street light proximity scores)

---

## Aggregation Workflows

All aggregation workflows inherit from `AggregationWorkflowBase` and implement grid-first weighted aggregation.

### 19. FactorAggregationWorkflow

**File:** `/geest/core/workflows/factor_aggregation_workflow.py`

**Selection:** `analysis_mode == "factor_aggregation"`

**Purpose:** Aggregate (weighted average) all indicator rasters within a Factor to produce a single Factor raster.

**Inputs:**
- **Item:** Factor JsonTreeItem
- **Guids:** List of indicator child GUIDs via `item.getFactorIndicatorGuids()`
- **Weights:** `factor_weighting` attribute per indicator (sum to 1.0)
- **Input Rasters:** All completed indicator raster files

**Algorithm (Grid-First, Default):**
1. Clear target grid column (factor_{id})
2. For each area:
   a. Retrieve completed indicator rasters via GUIDs
   b. Load each raster and validate
   c. Call `write_aggregation_to_grid()`
      - For each grid cell, read indicator values
      - Compute weighted sum: Σ(weight_i × indicator_i value)
      - Write result to factor grid column
   d. Rasterize factor column
3. Combine area rasters into VRT

**Legacy (Raster-First, Alternative):**
1. Use QgsRasterCalculator with weighted sum expression
2. Output aggregated raster per area

**Outputs:**
- Raster: `{factor_id}_aggregated_{index}.tif` (0-5 Likert weighted aggregate)
- Grid column: factor_{factor_id} with aggregated values
- VRT: Combined raster for visualization

**Status Checks:**
- Verify each indicator is Completed successfully
- Skip indicators set to "Do Not Use" or "Excluded from analysis"
- Fail if any required indicator not ready

---

### 20. DimensionAggregationWorkflow

**File:** `/geest/core/workflows/dimension_aggregation_workflow.py`

**Selection:** `analysis_mode == "dimension_aggregation"`

**Purpose:** Aggregate (weighted average) all Factor rasters within a Dimension to produce a single Dimension raster.

**Inputs:**
- **Item:** Dimension JsonTreeItem
- **Guids:** List of factor child GUIDs via `item.getDimensionFactorGuids()`
- **Weights:** `dimension_weighting` attribute per factor
- **Input Rasters:** All completed factor rasters

**Algorithm:**
- Identical to FactorAggregationWorkflow
- Weight key: `dimension_weighting`
- Output column: dim_{dimension_id}

**Outputs:**
- Raster: `{dimension_id}_aggregated_{index}.tif`
- Grid column: dim_{dimension_id}

---

### 21. AnalysisAggregationWorkflow

**File:** `/geest/core/workflows/analysis_aggregation_workflow.py`

**Selection:** `analysis_mode == "analysis_aggregation"`

**Purpose:** Aggregate (weighted average) all Dimension rasters to produce final **GeoE3 Score** (0-5 Likert enablement index).

**Inputs:**
- **Item:** Analysis (root) JsonTreeItem
- **Guids:** List of dimension child GUIDs via `item.getAnalysisDimensionGuids()`
- **Weights:** `analysis_weighting` attribute per dimension
- **Input Rasters:** All completed dimension rasters

**Algorithm:**
1. Get analysis_name from item attribute → layer_id = "geoe3"
2. Output to special directory: `working_directory/geoe3_score/`
3. For each area:
   a. Load dimension rasters
   b. Weighted sum: Σ(analysis_weight_i × dimension_i value)
   c. Write to study_area_grid.geoe3 column
   d. Rasterize

**Outputs:**
- **Raster:** `geoe3_score/geoe3_aggregated_{index}.tif` (final GeoE3 Score 0-5)
- **Grid Column:** study_area_grid.geoe3
- **VRT:** `geoe3_score/geoe3_score.vrt` (combined visualization)

**Post-Processing:**
- This output feeds into WEE (Women Economic Empowerment) score calculation
- Population raster processor creates geoe3_by_population_score as secondary product

---

## Standalone Processors

Processors are QgsTask subclasses that run asynchronously. Unlike workflows, they are not selected by analysis_mode but invoked via tree_panel or analysis orchestration logic.

### 22. PopulationRasterProcessingTask

**File:** `/geest/core/algorithms/population_processor.py`

**Purpose:** Process population raster (e.g., WorldPop); clip to study areas; reclassify into 3 population density classes.

**Inputs:**
- **population_raster_path:** Source raster (typically WorldPop GeoTIFF)
- **study_area_gpkg_path:** Study area masks
- **cell_size_m:** Target resolution

**Algorithm:**
1. For each area:
   a. Clip population raster to area bbox using gdal:cliprasterbymasklayer
   b. Resample to cell_size using gdalwarp -r sum
   c. Reclassify into 3 classes:
      - Low: values 0 to percentile(33) → class 1 (yellow #FFFF00)
      - Medium: percentile(33) to percentile(67) → class 2 (orange #FFA500)
      - High: percentile(67) to max → class 3 (dark red #800000)
2. Combine area rasters into VRT
3. Output directory: `working_directory/population/`

**Outputs:**
- Rasters: `population/clipped_phase1_{index}.tif`, `population/resampled_{index}.tif`, `population/reclassified_{index}.tif`
- VRT: `population/population.vrt`

**Methods:**
- clip_population_rasters(): gdal:cliprasterbymasklayer
- resample_population_rasters(): gdalwarp (via subprocess for -r sum)
- reclassify_resampled_rasters(): gdal:rasterreclassify
- generate_vrts(): gdal:buildvirtualraster

---

### 23. WEEByPopulationScoreProcessingTask

**File:** `/geest/core/algorithms/wee_by_population_score_processor.py`

**Purpose:** Create bivariate **GeoE3 × Population Score** by combining GeoE3 Score (5 Likert levels) × Population (3 classes) → 15-class output using raster algebra.

**Inputs:**
- **geoe3_raster:** GeoE3 Score (output from AnalysisAggregationWorkflow)
- **population_raster:** Reclassified population (output from PopulationRasterProcessingTask)

**Algorithm:**
1. For each area:
   a. Load aligned GeoE3 and population rasters
   b. Apply formula: `((A - 1) * 3) + B`
      - A = GeoE3 Score (1-5)
      - B = Population class (1-3)
      - Result: 15 discrete classes (1-15)
   c. Save bivariate raster
   d. Write raster values to grid_column "geoe3_by_population"
2. Combine into VRT with QML styling

**Output Classes:**
```
Score   Enablement             Population Class
1-3     Very Low (red)         Low/Medium/High
4-6     Low (orange)           Low/Medium/High
7-9     Moderate (yellow)      Low/Medium/High
10-12   Enabling (green)       Low/Medium/High
13-15   Highly Enabling (blue) Low/Medium/High
```

**Outputs:**
- Rasters: `geoe3_by_population_score/geoe3_by_population_score_{index}.tif`
- Grid column: study_area_grid.geoe3_by_population
- VRT: `geoe3_by_population_score/geoe3_by_population_score.vrt`
- QML: `geoe3_by_population_score.qml` (bivariate color scheme)

---

### 24. OpportunitiesMaskProcessor

**File:** `/geest/core/algorithms/opportunities_mask_processor.py`

**Purpose:** Create binary opportunity mask raster (1 = opportunity zone, 0 = outside).

**Inputs:**
- **Item Attributes:**
  - `mask_mode`: "point", "polygon", "raster", or "ghsl"
  - For points: `buffer_distance_m` (radius)
  - For point/polygon: layer source path
  - For raster: raster path
  - For GHSL: auto-downloaded settlements
- **Analysis Scale:** local/national/regional

**Algorithm:**

**Point Mode:**
1. Load point layer (opportunities locations)
2. Buffer by distance_m
3. Rasterize buffered zones to binary (1 inside buffer, 0 outside)

**Polygon Mode:**
1. Load polygon layer
2. Rasterize to binary (1 inside, 0 outside)

**Raster Mode:**
1. Load raster
2. Reclassify: non-null → 1, null → 0

**GHSL Mode:**
1. Load GHSL settlements layer (auto-downloaded if needed)
2. Rasterize to binary

**Outputs:**
- Rasters: `opportunity_masks/opportunities_{mask_mode}_mask_{index}.tif`
- VRT: `opportunity_masks/opportunities_mask.vrt`
- Used by GeoE3 Score → GeoE3 × Opportunities Score (post-processing)

---

### 25. SubnationalAggregationProcessor

**File:** `/geest/core/algorithms/subnational_aggregation_processor.py`

**Purpose:** Aggregate GeoE3 and derivative scores to subnational admin boundaries (country, province, district).

**Inputs:**
- **GeoE3 Score raster**
- **Admin boundary layer** (polygons with administrative hierarchy)
- **Optional:** population weighting, gender weighting

**Algorithm:**
1. For each admin boundary:
   a. Mask GeoE3 raster to admin polygon
   b. Compute zonal statistics: mean, weighted average
   c. Write result to admin boundary attribute table
2. Output boundary shapefile/GeoPackage with aggregated scores

**Outputs:**
- Admin layer with aggregated indicator/factor/dimension/analysis scores
- Summary statistics table

---

### 26. FeaturesPerCellProcessor (Standalone)

**File:** `/geest/core/algorithms/features_per_cell_processor.py`

**Purpose:** Count/classify features per grid cell (used by per-cell workflows and standalone analysis).

**Key Functions:**
- `select_grid_cells_and_count_features(grid_layer, features_layer, output_path)` → grid with counts
- `select_grid_cells_and_assign_transport_score(osm_type, grid_layer, features_layer, output_path)` → grid with transport scores
- `assign_values_to_grid(grid_layer, feedback)` → rescale counts to 0-5
- Uses prepared geometry optimization for intersection testing
- Batch writes for performance (10K features per batch)

**Outputs:**
- GeoPackage grid with counts/scores

---

### 27. NativeNetworkAnalysisProcessingTask

**File:** `/geest/core/algorithms/native_network_analysis_processor.py`

**Purpose:** Batch isochrone generation using QGIS native routing algorithms.

**Inputs:**
- **point_layer:** Origin points
- **distances:** List of distance values (meters)
- **road_network_path:** Network edges
- **output_gpkg_path:** Output file

**Algorithm:**
1. For each distance:
   a. native:serviceareafromlayer all points → service areas
   b. native:concavehull → concave hull polygons (α=0.3)
   c. Append to output GeoPackage
2. Spatial index output for fast queries

**Outputs:**
- GeoPackage with nested isochrone polygons

**Configuration:**
- POINT_TOLERANCE: 50m
- NETWORK_TOLERANCE: 50m
- STRATEGY: 0 (shortest distance)
- CONCAVE_HULL_ALPHA: 0.3

---

### 28. GHSLDownloader & GHSLProcessor

**Files:**
- `/geest/core/algorithms/ghsl_downloader.py`
- `/geest/core/algorithms/ghsl_processor.py`

**Purpose:** Download, process, and integrate Global Human Settlements Layer (GHSL) data.

**Inputs:**
- Study area extent in EPSG:4326
- Output directory

**Algorithm (GHSLDownloader):**
1. Query GHSL tile index for intersecting tiles
2. Download tiles for each intersection
3. Extract raster files

**Algorithm (GHSLProcessor):**
1. Reclassify rasters (settlement class 1-3)
2. Polygonize (raster → vector settlements)
3. Combine polygons into parquet file
4. Import to GeoPackage via gdal:vectortranslate

**Outputs:**
- study_area_gpkg: ghsl_settlements layer (settlement polygons)
- study_area/ghsl_settlements_layer.parquet (intermediate)

---

## Aggregation Pyramid

The GeoE3 analysis follows a hierarchical aggregation structure with weighted averaging at each level.

```
Indicator Layer (analysis_mode specific workflow)
    ↓ (weighted average by factor_weighting)
Factor Layer (FactorAggregationWorkflow)
    ↓ (weighted average by dimension_weighting)
Dimension Layer (DimensionAggregationWorkflow)
    ↓ (weighted average by analysis_weighting)
GeoE3 Score (AnalysisAggregationWorkflow) → study_area_grid.geoe3
    ↓ (raster algebra with population)
GeoE3 × Population Score (WEEByPopulationScoreProcessingTask) → geoe3_by_population
    ↓ (optional masking)
GeoE3 × Population × Opportunities Score → masked output
```

### Weight Sources (from model.json)

- **indicator_weighting:** Per-indicator weight within factor
- **factor_weighting:** Per-factor weight within dimension
- **dimension_weighting:** Per-dimension weight within analysis
- **analysis_weighting:** Per-analysis weight (for multi-analysis setups)

All weights are normalized to sum to 1.0 per aggregation level.

### Grid-First Aggregation Flow

1. **Indicator Workflows:** Write scores directly to study_area_grid.`{layer_id}` columns
2. **FactorAggregationWorkflow:**
   - Read all indicator columns for factor
   - Compute: grid_cell.factor = Σ(weight_i × grid_cell.indicator_i)
   - Write to study_area_grid.fac_`{factor_id}`
3. **DimensionAggregationWorkflow:**
   - Read all factor columns
   - Compute: grid_cell.dimension = Σ(weight_j × grid_cell.factor_j)
   - Write to study_area_grid.dim_`{dimension_id}`
4. **AnalysisAggregationWorkflow:**
   - Read all dimension columns
   - Compute: grid_cell.geoe3 = Σ(weight_k × grid_cell.dimension_k)
   - Write to study_area_grid.geoe3
5. **Rasterization:** Each aggregation workflow rasterizes its grid column for VRT output

### Post-Aggregation Products

- **WEE Score:** Bivariate GeoE3 × Population
- **Job Opportunities Mask:** Binary mask layer
- **Subnational Aggregation:** Admin-level rollup

---

## Common Grid Column Utilities

**File:** `/geest/core/grid_column_utils.py`

All workflows interact with study_area_grid via these functions:

- `clear_grid_column(gpkg, column_name)` → Clear column to NULL
- `write_uniform_value_to_grid(gpkg, column_name, value, area_name)` → Set uniform value
- `count_features_per_grid_cell(gpkg, column_name, features_layer)` → Spatial join count
- `write_buffer_values_to_grid(gpkg, column_name, features_layer, buffer_distance, area_name)` → Buffer scoring
- `write_spatial_join_to_grid(gpkg, column_name, features_gpkg, features_layer, score_expr, area_name)` → Spatial join with score function
- `write_joined_values_to_grid(gpkg, column_name, source_gpkg, source_layer, key_fields, source_field, area_name)` → Attribute join
- `write_raster_values_to_grid(gpkg, raster_path, column_name, area_name)` → Sample raster to grid
- `write_aggregation_to_grid(gpkg, column_name, source_rasters, weights, area_name)` → Weighted sum from rasters
- `reclassify_grid_column_with_table(gpkg, column_name, reclassification_table, area_name)` → Apply rule table
- `rasterize_grid_column(gpkg, column_name, output_raster_path, cell_size, extent, nodata, area_name)` → Grid → GeoTIFF

All grid operations use OGR SQL for performance (100M+ cell updates).

---

## Workflow Base Output Conventions

All workflows produce standardized outputs:

- **Raster File Name:** `{layer_id}_{index}.tif` per area
- **Raster Format:** GeoTIFF, 32-bit float (GDAL data type 5), cell_size_m resolution, nodata=-9999
- **Grid Column:** study_area_grid.`{layer_id}` (or dim_*, fac_* prefix for aggregation)
- **Item Attributes Updated:**
  - `result_file`: Path to final VRT or primary raster
  - `result`: Status message ("Workflow completed successfully", "Failed", etc.)
  - `error`: Error message if failed
  - `execution_start_time`, `execution_end_time`: Timestamps
- **Status:** Workflow sets item.setStatus("Completed successfully") on success

---

End of SRS
