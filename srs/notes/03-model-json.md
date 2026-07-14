Excellent! Now let me display the full documentation to the user:

---

# GeoE3 QGIS Plugin Model.json Architecture – Complete SRS Documentation

## 1. Overview

The GeoE3 model.json file defines a three-level hierarchical structure representing gender empowerment indicators analysis:

```
Analysis (root)
├── Dimensions (3 total)
│   ├── Contextual
│   ├── Accessibility
│   └── Place Characterization
│       ├── Factors (variable per dimension)
│       │   ├── Factor 1
│       │   ├── Factor 2
│       │   └── ...
│       │       ├── Indicators (1+ per factor)
│       │       ├── Indicator 1
│       │       ├── Indicator 2
│       │       └── ...
```

The shipped model (`geest/resources/model.json`) contains 880 lines with static definitions. Runtime copies in project folders diverge by accumulating execution state fields.

---

## 2. Full Hierarchy with Complete Attributes

### 2.1 Analysis Level (Root)

**JSON Path:** Top level of project `model.json`

| Attribute | Type | Meaning | Written By | Example |
|-----------|------|---------|------------|---------|
| `analysis_name` | string | User-friendly analysis title | Runtime (user input) | "Women's Economic Empowerment - StLucia" |
| `description` | string | Analysis purpose/notes | Runtime (user input) | "No Description" |
| `working_folder` | string | Path to project directory | Runtime (project creation) | "/path/to/GeestWorkingDirectory/StLucia" |
| `analysis_cell_size_m` | number | Grid resolution in meters | Runtime (user config) | 100 |
| `analysis_scale` | string | "local" \| "regional" \| "national" | Runtime (user config) | "local" |
| `road_network_layer_path` | string | QGIS layer source path for active transport | Runtime (user config) | "/path/road_network.shp\|layername=..." |
| `qgis_project_path` | string | Path to .qgz project file | Runtime (user config) | "/path/StLucia.qgz" |
| `guid` | string | UUID for analysis instance | Runtime (auto-generated) | "b2eb9ee8-a769-..." |
| `output_filename` | string | Base name for final output raster | Shipped default | "GeoE3_Score" |
| `result` | string | Execution status message | Runtime (workflow) | "analysis_aggregation Workflow Completed" |
| `result_file` | string | Path to final output file | Runtime (workflow) | "/path/GeoE3_Score_combined.vrt" |
| `execution_start_time` | string | ISO 8601 timestamp | Runtime (workflow) | "2026-04-20T01:22:28.761716" |
| `execution_end_time` | string | ISO 8601 timestamp | Runtime (workflow) | "2026-04-20T01:30:43.450981" |
| `error` | string \| null | Error message if failed | Runtime (workflow) | null or error text |
| `error_file` | string \| null | Path to error log | Runtime (workflow) | null |
| `mask_mode` | string | "None" \| masking strategy | Runtime (user config) | "None" |
| `buffer_distance_m` | number | Mask buffer radius | Runtime (user config) | 0.0 |
| `{aggregation,population,point_mask,polygon_mask,raster_mask}_*` | various | Mask layer references (5 prefixes) | Runtime (user config) | Layer metadata (source, crs, wkb_type, etc.) |
| `opportunities_mask_result*` | string | Opportunities masking output | Runtime (workflow) | "" or result path |
| `geoe3_by_opportunities_mask_result*` | string | Final score with opportunity mask | Runtime (workflow) | "" or result path |
| `geoe3_by_population*` | string | Population-weighted result | Runtime (workflow) | "" or result path |
| `geoe3_score_subnational_aggregation*` | string | Aggregated to admin boundaries | Runtime (workflow) | "" or result path |

---

### 2.2 Dimension Level

**JSON Path:** `dimensions[]`

| Attribute | Type | Meaning | Written By | Example |
|-----------|------|---------|------------|---------|
| `id` | string | Unique identifier, lowercase_with_underscores | Shipped model | "contextual", "accessibility", "place_characterization" |
| `name` | string | Display name | Shipped model | "Contextual", "Accessibility", "Place Characterization" |
| `output_filename` | string | Raster output prefix | Shipped model | "Contextual_score", "Accessibility_score", "Place_score" |
| `description` | string | Explanation of the dimension | Shipped model | "The Contextual Dimension refers to laws and policies..." |
| `default_analysis_weighting` | number | Factory default contribution weight | Shipped model | 0.1, 0.45, 0.45 |
| `analysis_weighting` | number | Current contribution weight (mutable) | Runtime (user UI) | 0.1 (can be modified) |
| `factors` | array | Nested factors | Shipped + Runtime | Array of factor objects |
| `guid` | string | UUID for this dimension instance | Runtime (tree deserialization) | "6898d857-e692-4c5b-9a3b-..." |
| `analysis_mode` | string | Aggregation mode (dimensions always use aggregation) | Shipped default | "dimension_aggregation" (or "" in shipped) |
| `result` | string | Execution status | Runtime (workflow) | "dimension_aggregation Workflow Completed" or "Not Run" |
| `result_file` | string | Path to aggregated output | Runtime (workflow) | "/path/Contextual_score_combined.vrt" |
| `execution_start_time` | string | Workflow start timestamp | Runtime (workflow) | "2026-04-20T01:22:28..." |
| `execution_end_time` | string | Workflow end timestamp | Runtime (workflow) | "2026-04-20T01:30:43..." |

**Note:** Dimensions never have indicator data directly; they aggregate factors. The `analysis_weighting` at dimension level allows users to enable/disable entire dimensions (set to 0 = excluded).

---

### 2.3 Factor Level

**JSON Path:** `dimensions[].factors[]`

| Attribute | Type | Meaning | Written By | Example |
|-----------|------|---------|------------|---------|
| `id` | string | Unique identifier | Shipped model | "eplex", "workplace_discrimination", "women_s_travel_patterns" |
| `name` | string | Display name | Shipped model | "EPLEX Score", "Workplace Discrimination" |
| `output_filename` | string | Raster output prefix | Shipped model | "eplex_score", "workplace_discrimination" |
| `description` | string | Factor purpose/definition | Shipped model | "The Employment Protection Legislation Index..." |
| `women_enabling` | int | Women considerations flag (0=generic, 1=women-specific, 2=inverse/EPLEX) | Shipped model | 1, 0, or 2 |
| `default_dimension_weighting` | number | Factory default within-dimension weight | Shipped model | 1.0, 0.333333, 0.2 |
| `dimension_weighting` | number | Current within-dimension weight (mutable) | Runtime (user UI) | Can be 0.0 (excludes factor) |
| `indicators` | array | Nested indicators under this factor | Shipped + Runtime | Array of indicator objects |
| `guid` | string | UUID for this factor instance | Runtime (tree deserialization) | "618b209b-c706-4f2c-af13-..." |
| `analysis_mode` | string | Aggregation mode (factors use factor_aggregation) | Shipped default | "" (filled in at runtime) |
| `result` | string | Execution status | Runtime (workflow) | "factor_aggregation Workflow Completed" |
| `result_file` | string | Path to aggregated output | Runtime (workflow) | "/path/workplace_discrimination_combined.vrt" |
| `execution_start_time` | string | Workflow start timestamp | Runtime (workflow) | ISO 8601 string |
| `execution_end_time` | string | Workflow end timestamp | Runtime (workflow) | ISO 8601 string |

**Women Enabling Logic:**
- `women_enabling = 1`: Factor is shown when "Women Considerations" toggle is ON; hidden when OFF
- `women_enabling = 0`: Factor always shown (generic factors like education, active transport)
- `women_enabling = 2`: Factor shown when "Women Considerations" toggle is OFF (inverse, e.g., EPLEX replaces women-specific contextual factors)

---

### 2.4 Indicator Level

**JSON Path:** `dimensions[].factors[].indicators[]`

This is the most complex level with 30+ attributes defining data sources and processing workflows.

#### Core Identification Attributes

| Attribute | Type | Meaning | Written By | Example |
|-----------|------|---------|------------|---------|
| `indicator` | string | Display label for the indicator | Shipped model | "Employment Protection Legislation Index", "Location of kindergartens/childcare" |
| `id` | string | Unique identifier within factor | Shipped model | "eplex_score_indicator", "Kindergartens_Location" |
| `output_filename` | string | Raster output prefix | Shipped model | "EPLEX_output", "WTP_Kindergartens_output" |
| `description` | string | Detailed explanation | Shipped model (may be empty) | "EPLEX score representing employment protection..." or "" |

#### Weighting & Status Attributes

| Attribute | Type | Meaning | Written By | Example |
|-----------|------|---------|------------|---------|
| `default_factor_weighting` | number | Factory default contribution weight | Shipped model | 1.0, 0.2 |
| `factor_weighting` | number | Current contribution weight (mutable) | Runtime (user UI) | Can be 0.0 (disables indicator) |
| `guid` | string | UUID for this indicator instance | Runtime (tree deserialization) | "57ca6524-d9e5-4b25-9373-..." |

#### Analysis Mode & Datasource Selection (Mutually Exclusive Flags)

The `use_*` flags and `analysis_mode` determine the workflow class and data input method. Only ONE `use_*` flag should be set to 1.

| Attribute | Type | Meaning | Workflow Class | Example |
|-----------|------|---------|----------------|---------|
| `use_index_score` | int | Fixed country-level index score (read from `index_score` field) | `DefaultIndexScoreWorkflow` | 1 for contextual indicators |
| `use_contextual_index_score` | int | WBL index (Workplace/Pay/Entrepreneurship scores) | `ContextualIndexScoreWorkflow` | 1 for workplace discrimination, regulatory frameworks |
| `use_eplex_score` | int | Employment Protection Legislation Index | `EPLEXWorkflow` | 1 for EPLEX indicator |
| `use_index_score_with_ookla` | int | Internet access index + Ookla broadband dataset | `IndexScoreWithOoklaWorkflow` | 1 for digital inclusion |
| `use_index_score_with_ghsl` | int | Education index + GHSL population data | `IndexScoreWithGHSLWorkflow` | 1 for education indicator |
| `use_multi_buffer_point` | int | Vector point layer + multiple concentric buffers | `MultiBufferDistances[Native\|ORS]Workflow` | 1 for kindergartens, schools, banks |
| `use_single_buffer_point` | int | Vector point layer + single buffer | `SinglePointBufferWorkflow` | 1 for FCV (conflict events), water/sanitation |
| `use_polygon_per_cell` | int | Vector polygon layer, one value per grid cell | `PolygonPerCellWorkflow` | 1 for education (GHSL), sometimes rasterized |
| `use_polyline_per_cell` | int | Vector line layer (roads) per grid cell | `PolylinePerCellWorkflow` | 0 (rarely used) |
| `use_osm_transport_polyline_per_cell` | int | OSM transport network (active transport) | `OsmTransportPolylinePerCellWorkflow` | 1 for active transport network |
| `use_point_per_cell` | int | Vector point layer, one value per grid cell | `PointPerCellWorkflow` | 0 (rarely used) |
| `use_csv_to_point_layer` | int | CSV data → point layer (ACLED conflict events) | `AcledImpactWorkflow` | 1 for FCV (ACLED data) |
| `use_classify_polygon_into_classes` | int | Vector polygon reclassified to class values | `ClassifiedPolygonWorkflow` | 1 for some specialized indicators |
| `use_classify_safety_polygon_into_classes` | int | Vector polygon for safety classification | `SafetyPolygonWorkflow` | 0 (for safety perception factor) |
| `use_nighttime_lights` | int | Nighttime satellite imagery | `SafetyRasterWorkflow` | 1 for street lights/safety |
| `use_environmental_hazards` | int | Raster hazard layers (fire, flood, landslide) | `RasterReclassificationWorkflow` | 1 for environmental hazards indicators |
| `use_street_lights` | int | Street lights (nighttime imagery) | `StreetLightsBufferWorkflow` | 1 for street lights safety perception |
| `analysis_mode` | string | **Set to the active `use_*` key** (e.g., "use_eplex_score") OR "Do Not Use" to disable | Runtime (user selects datasource) | "use_eplex_score", "use_multi_buffer_point", "Do Not Use" |

#### Buffer & Grid Configuration Attributes

| Attribute | Type | Meaning | Used By | Example |
|-----------|------|---------|---------|---------|
| `default_multi_buffer_distances` | string | Comma-separated buffer radii in meters | `MultiBufferDistances*Workflow` | "400, 800, 1200, 1500, 2000" |
| `default_single_buffer_distance` | int | Buffer radius in meters | `SinglePointBufferWorkflow` | 5000 (for FCV), 3000 (for water) |
| `default_pixel` | int | Grid cell size in meters (DEPRECATED: use analysis_cell_size_m) | Rarely used | 100 |

#### Runtime State & Datasource Configuration

These fields are populated at runtime when a user selects a datasource in the GUI.

| Attribute | Type | Meaning | Written By | Example |
|-----------|------|---------|------------|---------|
| `result` | string | Workflow execution status | Runtime (workflow) | "Workflow Completed", "Not Run", "Error: ..." |
| `result_file` | string | Path to output raster/layer | Runtime (workflow) | "/path/WTP_Kindergartens_output_combined.vrt" |
| `execution_start_time` | string | ISO 8601 start timestamp | Runtime (workflow) | "2026-04-20T01:22:28.761716" |
| `execution_end_time` | string | ISO 8601 end timestamp | Runtime (workflow) | "2026-04-20T01:22:30.474078" |
| `error` | string \| null | Error message if workflow failed | Runtime (workflow) | null or error text |
| `error_file` | string \| null | Path to error log file | Runtime (workflow) | null |
| `{use_mode}_layer_source` | string | QGIS layer source URI (if vector) | Runtime (user selection) | "file:///path/layer.gpkg\|layername=features" |
| `{use_mode}_shapefile` | string | Alternative: shapefile path | Runtime (user selection) | "/path/data.shp" |
| `{use_mode}_raster` | string | Raster file path (for raster workflows) | Runtime (user selection) | "/path/hazard.tif" |
| `{use_mode}_csv_file` | string | CSV file path (for ACLED workflow) | Runtime (user selection) | "/path/acled_data.csv" |
| `road_network_layer_path` | string | Active transport fallback path | Runtime (global config) | "/path/road_network.shp" |
| `ghsl_layer_path` | string | GHSL population raster path | Runtime (user selection) | "/path/ghsl_population.tif" |
| `osm_download_enabled` | int | Flag: auto-download OSM data (not currently used) | Shipped default | 1 or 0 |
| `index_score` | number | Fixed index value (for use_index_score workflows) | Runtime (WBL lookup or constant) | 0.0, 87.7, 78.3, 76.5 |
| `eplex_score` | number | EPLEX score value | Runtime (lookup) | 0.0 or computed value |
| `s2s_fields` | array | S2S (Sentinel-2 Settlement) fields for polygon classification | Shipped model (education) | ["ghs_11_pop", "ghs_12_pop", ...] |

---

## 3. Shipped Model Inventory

**Shipped model location:** `/home/timlinux/dev/python/GeoE3/geest/resources/model.json` (880 lines)

### 3.1 Dimensions

| ID | Name | Default Weight | Analysis Modes | Factors | Key Purpose |
|-----|------|-----------------|-----------------|---------|-------------|
| `contextual` | Contextual | 0.1 | dimension_aggregation | 4 | Laws, policies, financial frameworks |
| `accessibility` | Accessibility | 0.45 | dimension_aggregation | 5 | Access to essential services via proximity |
| `place_characterization` | Place Characterization | 0.45 | dimension_aggregation | 7 | Walkability, safety, hazards, infrastructure |

**Total factors:** 16
**Total indicators:** 35+

### 3.2 Contextual Dimension Factors & Indicators

**Factor: EPLEX Score** (women_enabling: 2)
- Employment Protection Legislation Index → use_eplex_score

**Factor: Workplace Discrimination** (women_enabling: 1)
- WBL 2024 Workplace Index Score → use_contextual_index_score (87.7 St Lucia)

**Factor: Regulatory Frameworks** (women_enabling: 1)
- Average WBL Pay Score and Parenthood Index → use_contextual_index_score (78.3 St Lucia)

**Factor: Financial Inclusion** (women_enabling: 1)
- WBL 2024 Entrepreneurship Index Score → use_contextual_index_score (76.5 St Lucia)

### 3.3 Accessibility Dimension Factors & Indicators

**Factor: Women's Travel Patterns** (women_enabling: 1, default_weight: 0.2)
- Kindergartens/childcare → use_multi_buffer_point (400, 800, 1200, 1500, 2000m)
- Primary schools → use_multi_buffer_point
- Groceries → use_multi_buffer_point
- Pharmacies → use_multi_buffer_point
- Green spaces → use_multi_buffer_point

**Factor: Access to Public Transport** (women_enabling: 0, default_weight: 0.2)
- Public transportation stops → use_multi_buffer_point (250, 500, 750, 1000, 1500m)

**Factor: Access to Health Facilities** (women_enabling: 1, default_weight: 0.2)
- Hospitals and clinics → use_multi_buffer_point (2000, 4000, 6000, 8000, 10000m)

**Factor: Access to Education and Training Facilities** (women_enabling: 0, default_weight: 0.2)
- Universities and technical schools → use_multi_buffer_point (2000, 4000, 6000, 8000, 10000m)

**Factor: Access to Financial Facilities** (women_enabling: 0, default_weight: 0.2)
- Banks and financial institutions → use_multi_buffer_point (500, 1000, 1500, 2000, 3000m)

### 3.4 Place Characterization Dimension Factors & Indicators

**Factor: Active Transport** (women_enabling: 0, default_weight: 0.142857...)
- Active Transport Network → use_osm_transport_polyline_per_cell

**Factor: Safety Perception** (women_enabling: 1)
- Street lights/Night time lights → use_nighttime_lights + use_street_lights

**Factor: FCV (Fragility, Conflict, Violence)** (women_enabling: 0)
- ACLED Violence Events → use_csv_to_point_layer (5000m buffer)

**Factor: Education** (women_enabling: 1, backward-compat rule)
- Labor force with university degrees → use_index_score + use_index_score_with_ghsl (GHSL fields)

**Factor: Digital Inclusion** (women_enabling: 0)
- Internet usage (% population) → use_index_score_with_ookla (Ookla dataset)

**Factor: Environmental Hazards** (women_enabling: 0)
- Fire → use_environmental_hazards
- Flood → use_environmental_hazards
- Landslide → use_environmental_hazards
- Tropical Cyclone → use_environmental_hazards
- Drought → use_environmental_hazards

**Factor: Water Sanitation** (women_enabling: 1)
- Facilities needing water/sanitation → use_single_buffer_point (3000m)

---

## 4. Runtime Model State vs. Shipped Resource

### 4.1 Shipped Model
- No runtime state, no GUIDs, all `analysis_mode` disabled
- Used for template and schema validation

### 4.2 Project Working Copy
- Fully enriched with execution results, datasources, GUIDs
- Written by tree panel + workflows after each user action

---

## 5. JSON Schema Validation

**Schema file:** `/home/timlinux/dev/python/GeoE3/geest/resources/schema.json` (201 lines)

**Generator:** `generate_schema.py` - infers type from data recursively

**Validator:** `JSONValidator` class - structural validation only; no semantic checks

**Limitation:** Does not enforce mutual exclusivity of `use_*` flags or that `analysis_mode` matches active flag

---

## 6. Model Generation Path

**Tool:** `generate_model.py` - converts ODS spreadsheet to model.json

**Input:** Spreadsheet columns (Dimension, Factor, Indicator, weightings, datasource flags)

**Process:**
1. Load ODS via pandas
2. Forward-fill hierarchical columns
3. Build dimension → factor → indicator tree
4. Initialize all indicators to `analysis_mode: "Do Not Use"`
5. Save as formatted JSON

**Status:** Static template; ODS source not currently maintained

---

## 7. GUI Read/Write Cycle

### Load
1. User opens project → loads model.json
2. JsonTreeModel deserializes JSON → creates JsonTreeItem tree
3. Tree view displays with name, status icon, weighting columns

### Interact
1. User selects datasource → widget populates {mode}_layer_source, {mode}_shapefile, etc.
2. Writes to in-memory item attributes
3. Tree updates status icons

### Save
1. TreePanel._save_json_to_disk() traverses tree
2. Collects all attributes from each item
3. Reconstructs dimensions → factors → indicators hierarchy
4. json.dump() to <working_folder>/model.json

---

## 8. Workflow Factory & Analysis Modes

**Factory:** `WorkflowFactory.create_workflow()` dispatches based on `analysis_mode` string

**17 Core Workflows:**
- `use_index_score` → DefaultIndexScoreWorkflow
- `use_contextual_index_score` → ContextualIndexScoreWorkflow
- `use_eplex_score` → EPLEXWorkflow
- `use_index_score_with_ookla` → IndexScoreWithOoklaWorkflow
- `use_index_score_with_ghsl` → IndexScoreWithGHSLWorkflow
- `use_multi_buffer_point` → MultiBufferDistancesNativeWorkflow or ORS variant
- `use_single_buffer_point` → SinglePointBufferWorkflow
- `use_point_per_cell` → PointPerCellWorkflow
- `use_polyline_per_cell` → PolylinePerCellWorkflow
- `use_osm_transport_polyline_per_cell` → OsmTransportPolylinePerCellWorkflow
- `use_polygon_per_cell` → PolygonPerCellWorkflow
- `use_classify_polygon_into_classes` → ClassifiedPolygonWorkflow
- `use_classify_safety_polygon_into_classes` → SafetyPolygonWorkflow
- `use_csv_to_point_layer` → AcledImpactWorkflow
- `use_nighttime_lights` → SafetyRasterWorkflow
- `use_environmental_hazards` → RasterReclassificationWorkflow
- `use_street_lights` → StreetLightsBufferWorkflow

**3 Aggregation Workflows:**
- `factor_aggregation` → FactorAggregationWorkflow
- `dimension_aggregation` → DimensionAggregationWorkflow
- `analysis_aggregation` → AnalysisAggregationWorkflow

---

## 9. Women's Considerations & Enabling Flags

**Function:** `resolve_women_enabling_for_factor(factor_id, women_enabling)` applies backward-compat rule

**Rule:** If factor_id=="education" and women_enabling==0 → treat as 1

**Logic in Tree Panel:**
```
if women_enabling == 1:
    factor.enabled = women_considerations_toggle_state
elif women_enabling == 2:
    factor.enabled = NOT women_considerations_toggle_state  (inverse for EPLEX)
else:  # women_enabling == 0
    factor.enabled = True  (always visible)
```

**Effect:** Women-specific factors toggle visibility; contextual factors auto-swap EPLEX ↔ women-factors

---

## 10. How to Extend the Model

### 10.1 Add Indicator to Existing Factor
1. Edit model.json: add indicator object with all 30+ fields
2. Set one `use_*` flag to 1; rest to 0
3. Set `analysis_mode` to "Do Not Use" initially
4. Regenerate schema: `python -m geest.core.generate_schema`
5. Update ODS template if using spreadsheet
6. No workflow changes if reusing existing workflow (e.g., multi-buffer)

### 10.2 Add Factor to Dimension
1. Add factor object with id, name, description, women_enabling, weightings, indicators array
2. Regenerate schema
3. No code changes (factor aggregation is generic)

### 10.3 Add Dimension
1. Add dimension object with id, name, output_filename, description, default_analysis_weighting, factors array
2. Adjust other dimension weights to sum to 1.0
3. Regenerate schema
4. No code changes (dimension aggregation is generic)

### 10.4 Add New Workflow (requires Python code)
1. Create workflow class in `geest/core/workflows/`
2. Register in `WorkflowFactory.create_workflow()` with new `analysis_mode` string
3. Add model flag `use_new_workflow: 1` to indicators
4. Create datasource widget if custom UI needed
5. Register widget in `DataSourceWidgetFactory`
6. Add to schema

---

## 11. Versioning & Migration

**Current State:** No explicit versioning; shipped model is static

**Backward Compatibility:** Preserved by treating missing fields as defaults + special cases (Education rule)

**Recommended Strategy (future):**
- Add `model_version: "2.0.0"` field at top level
- Implement migration registry: `MIGRATIONS = {"1.0": lambda model: {...}}`
- Apply intermediate migrations when loading old project files

---

## 12. Project Lifecycle

### Phase 1: Creation
- User creates project → copies shipped model → sets analysis name, cell size, scale

### Phase 2: Configuration
- User selects datasource for each indicator → populates analysis_mode, layer sources, buffers
- Tree marks "Configured, not run"

### Phase 3: Execution
- User runs → WorkflowFactory creates workflows → outputs rasters + updates result_file, timestamps
- Auto-saves model.json

### Phase 4: Aggregation
- Workflows compute factor sums, dimension sums, final GeoE3_Score

### Phase 5: Export
- User exports rasters + PDF report
- Model saved for re-running

---

## 13. Key Developer Takeaways

| Aspect | Key Info |
|--------|----------|
| **Shipped Model** | `/geest/resources/model.json` (880 lines, 3 dims, 16 factors, 35+ indicators) |
| **Project Model** | `<working_dir>/model.json` (includes runtime state + GUIDs) |
| **Hierarchy** | Analysis → Dimensions (3) → Factors (16) → Indicators (35+) |
| **Uniqueness** | `id` (immutable string), `guid` (runtime UUID) per item |
| **Weighting** | Cascading: analysis_weighting × dimension_weighting × factor_weighting |
| **Analysis Modes** | 17 datasource workflows + 3 aggregation workflows |
| **Women Enabling** | Factor-level: 0=generic, 1=women-specific (toggle), 2=EPLEX (inverse) |
| **Datasources** | Mutually exclusive `use_*` flags; only one active per indicator |
| **Runtime Config** | Layer sources, buffers, CSV paths populated at runtime |
| **Execution State** | result, result_file, error, timestamps auto-populated |
| **Serialization** | JsonTreeItem attributes dict ↔ JSON (no ORM) |
| **Validation** | Structural only; no semantic checks |
| **Extension** | JSON edits + schema regen for indicators/factors/dimensions; Python code for new workflows |
