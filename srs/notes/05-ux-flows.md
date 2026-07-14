Perfect! Now I have all the information I need. Let me create a comprehensive structured markdown report:

```markdown
# GeoE3 QGIS Plugin: User-Facing Flows & UX Documentation

## Executive Summary

This document defines the user-facing flows and UX interactions for the **Geospatial Enabling Environments for Employment (GeoE3)** QGIS plugin. The plugin enables spatial analysis of employment enabling environments through a structured multi-phase workflow: **PROJECT SETUP** → **CONFIGURATION** → **ANALYSIS** → **POST-ANALYSIS**.

The architecture uses a stacked panel pattern (`GeoE3Dock` with 10 panels) to guide users through distinct phases, with asynchronous task queues managing long-running operations. Each phase emphasizes progress feedback, error handling, and clear decision points.

---

## 1. PROJECT SETUP PHASE

### 1.1 Overview

The project setup phase guides users through creating a new GeoE3 project or opening an existing one. This phase consists of a sequence of panels that progressively gather project configuration parameters and trigger background study area processing.

### 1.2 Panel Flow (Sequential)

**Panel Navigation:**
`Intro Panel (0)` → `Credits Panel (1)` → `Setup Panel (2)` → `[Create/Open] Project Panel` → `[Optional: S2S/ORS/Road Network]` → `Tree Panel (8)`

**Entry Point:** Dock is opened in QGIS; user sees Intro Panel by default.

### 1.3 Detailed Panel Breakdown

#### 1.3.1 Intro Panel

**Purpose:** Welcome and orientation screen.

**Components:**
- Custom banner with GeoE3 logo/title
- Welcome heading
- Brief introduction text
- Next button → Credits Panel

**User Action:**
1. Read welcome message
2. Click "Next" to continue

---

#### 1.3.2 Credits Panel

**Purpose:** Attribution and credits screen.

**Components:**
- Credits content (organization, contributors)
- Previous button → Intro Panel
- Next button → Setup Panel

**User Action:**
1. Review credits
2. Click "Next" or "Previous"

---

#### 1.3.3 Setup Panel

**Purpose:** Choice between creating a new project or loading an existing one.

**Components:**
- "Create New Project" button
- "Open Existing Project" button
- Previous button → Credits Panel

**User Decision Points:**
1. **Create New Project** → Create Project Panel (4)
2. **Open Existing Project** → Open Project Panel (3)

---

#### 1.3.4 Open Project Panel

**Purpose:** Load and restore an existing GeoE3 project.

**Components:**
- Recent projects combo box (with ellided paths + full path data)
- Browse button (file dialog for manual selection)
- Open Project button

**Workflow:**
1. User selects from recent projects or browses to directory
2. System loads `model.json` from selected directory
3. Validates study area outputs exist:
   - `study_area/study_area.gpkg` with valid metadata tables
   - Feature count > 0 in `study_area_polygons` layer
4. If valid: automatically proceeds to Tree Panel (8)
5. If project incomplete: prompts user to regenerate study area
6. Emits `project_loaded` signal → dock opens QGIS project file if stored

**Key Signals:**
- `switch_to_next_tab` → Tree Panel
- `switch_to_previous_tab` → Setup Panel
- `set_working_directory(path)` → Tree Panel + Road Network Panel
- `project_loaded()` → Opens associated QGIS project if stored

**Fallback Logic:**
- If `model.json` and study area outputs are missing: user can retry or return to setup
- If `qgis_project_path` is stored in model: automatically opens that QGIS project

---

#### 1.3.5 Create Project Panel

**Purpose:** Configure new GeoE3 project and trigger study area generation.

**Sub-Components:**

##### 1.3.5a. Project Directory Selection
- **Widget:** File dialog (browse button)
- **Input:** User selects/creates working directory
- **Status Indicator:** Icon changes from ❌ (invalid) to ✓ (valid)
- **Validation:** Directory exists and is writable

##### 1.3.5b. Boundary Layer & Field Selection
- **Widget:** `QgsMapLayerProxyModel` (polygon layer filter)
- **Widget:** `QgsFieldProxyModel` (string field filter)
- **Inputs:**
  - Study area polygon layer from QGIS project
  - Field containing area names/IDs
- **Validation:** Layer must be valid, field must exist in layer schema
- **Action:** `layer_changed()` updates available fields and refreshes CRS checkbox

##### 1.3.5c. Analysis Scale Selection
- **Widget:** Radio buttons: **Regional** | **National** | **Local**
- **Default:** National
- **Behavior:**
  - **Regional:** Shows H3 resolution dropdown (0–15, default 6 "recommended")
    - Hides cell size spinbox
    - Validation: warns if H3 resolution will create <3 or >200,000 estimated cells
  - **National/Local:** Shows cell size spinbox (meters)
    - National: 1000 m default, 100 m steps
    - Local: 100 m default, 10 m steps
    - Hides H3 resolution dropdown
- **Signal:** `spatial_scale_changed(value)` updates UI

##### 1.3.5d. CRS Configuration
- **Checkbox:** "Use Boundary Layer CRS"
  - Enabled only if boundary layer CRS ≠ EPSG:4326
  - Checked: uses boundary layer CRS
  - Unchecked: auto-calculates UTM zone from layer extent
- **Display:** CRS label shows active CRS (e.g., "EPSG:32635")
- **Fallback:** If CRS unavailable from existing study area, calculates from UTM

##### 1.3.5e. Women Considerations
- **Widget:** Checkbox "Enable Women Considerations"
- **Default:** True (enabled)
- **Effect:** Propagated to model.json and affects factor enable/disable logic in Tree Panel

##### 1.3.5f. Progress Reporting

**When user clicks "Continue" (next_button):**

1. **Preflight Validation:**
   - Layer selected? ✓
   - Working directory selected? ✓
   - Field valid? ✓
   - (If regional) H3 cells within bounds? ✓
   - (If regional & H3 ≥ 9) Show warning: "High H3 Resolution can be very computationally expensive. Continue? [Yes/No]"

2. **Model Setup:**
   - If `model.json` missing: copy from `resources/model.json`
   - Update model.json:
     - `analysis_cell_size_m` = spinbox value
     - `analysis_scale` = "regional" | "national" | "local"
     - `analysis_h3_resolution` = H3 value (regional only)
     - `women_considerations_enabled` = checkbox state
     - `admin_boundary_layer_source` = layer file path

3. **StudyAreaProcessingTask Spawned:**
   - **Queue Manager:** Single-threaded `WorkflowQueueManager(pool_size=1)`
   - **Feedback Object:** `QgsFeedback` for subtask progress + cancellation
   - **Task Signals:**
     - `progressChanged(float)` → Main progress bar (0–100%)
     - `taskCompleted()` → Report generation
     - `taskTerminated()` → Error handling
     - `ghsl_download_failed(msg, processor)` → User prompt (continue without GHSL? Yes/No)

**StudyAreaProcessingTask Phase Steps:**

| Phase | Task | Progress | Notes |
|-------|------|----------|-------|
| 0 | **Bounding Boxes** | 0% (bouncing) | Compute feature bboxes; update QGIS map live |
| 1 | **GHSL Download** | 0–100% | Download/cache global GHSL settlement raster; user can continue without if failed |
| 2 | **Layer Pre-Creation** | ~10% | Initialize `study_area.gpkg` with metadata tables |
| 3 | **Per-Geometry Processing** | ~15–90% | For each study area feature: |
|    | — Chunking (if large) | | Split geometries if area exceeds threshold |
|    | — Grid Generation | | Regular square grid (national/local) OR H3 hexagon grid (regional) |
|    | — Clip Polygons | | Clip grid to feature boundary |
|    | — Raster Masks | | Generate GHSL mask for accessibility calculations |
|    | — VRT Generation | | Create virtual raster for seamless mosaic |
| 4 | **Model Column Addition** | ~95% | Add analysis grid layer to GeoPackage with default columns |
| 5 | **Report Generation** | ~100% | Generate PDF study area report (in background after task completes) |

**Live Feedback to User:**

```
Progress Bar (Main):     "Downloading GHSL data and building analysis grid..."  [████░░░░░]
Progress Bar (Child):    "Current area: 25%"  [██████░░░░]
Status Label:            "Processing study area. Bounding boxes will appear as each completes."
```

After initial GHSL phase (0% → bouncing → fixed %), if user doesn't see progress increment within 3 seconds, assumes task hung or locked file → shows error.

**Error Handling:**
- GHSL download fails → `ghsl_download_failed` signal → MessageBox: "GHSL Download Failed. Continue without GHSL data? [Yes/No]"
  - Yes: `processor.set_ghsl_user_response(continue_without=True)` → resuming task
  - No: Aborts task, shows "Aborted — GHSL download failed"
- Task terminates for other reason → `on_task_terminated()` → Enables widgets, shows error reason in progress bar

**Completion:**
- `on_task_completed()` → Report generation starts in background
- Child progress bar: "Generating study area report..."
- After report completes: `on_report_completed()` → Auto-advance to next panel (S2S or ORS, depending on `analysis_scale`)

**Output GeoPackage Structure:**
```
study_area/study_area.gpkg
├── gpkg_spatial_ref_sys       (metadata)
├── gpkg_contents               (metadata)
├── study_area_polygons         (input admin boundaries)
├── study_area_clip_polygons    (clipped boundaries)
├── study_area_grid             (analysis grid: squares or H3 hex)
├── study_area_bboxes           (feature bounding boxes)
├── study_area_creation_status  (processing status per geometry)
├── ghsl_settlements            (GHSL settlement layer, if downloaded)
├── chunks                      (chunking result for large geometries)
└── [analysis grid table]       (grid with default columns for model aggregation)
```

---

#### 1.3.6 S2S Panel (Space2Stats Prefetch)

**Visibility Condition:** Only shown if `analysis_scale == "regional"`

**Purpose:** Optional prefetching of remote Space2Stats datasets to reduce runtime during analysis.

**Components:**
- Checkbox: "Prefetch S2S datasets (NTL, Education, Hazards)"
- Description of datasets and prefetch strategy
- Progress bar (hidden initially)
- Processing info label (hidden initially)

**User Interaction:**
1. (Optional) Check box to enable prefetch
2. Click "Next" to proceed
   - If unchecked: skip prefetch, go to ORS Panel
   - If checked: start prefetch jobs in background
     - Multiple job chunks (default: 3000 hex IDs per chunk)
     - Retry logic (up to 4 attempts per chunk)
     - Inter-job delay (750 ms)
     - Show progress: "Prefetching S2S datasets... [██░░░░]"

**Signals:**
- `switch_to_next_tab` → ORS Panel
- `switch_to_previous_tab` → Create Project Panel

**Prefetch State Persistence:**
- Stored in `model.json`: `s2s_prefetch_enabled: true/false`

---

#### 1.3.7 ORS Panel (OpenRouteService Configuration)

**Purpose:** Configure optional OpenRouteService API for accessibility analysis.

**Components:**

##### Accessibility Mode Selection
- Radio button 1: "Use Free/OSM-based routing" (default)
- Radio button 2: "Use OpenRouteService (ORS) API"

##### ORS API Key Entry (Visible Only if ORS Radio Selected)
- Text field: ORS API key input
- Button: "Check Key" → Validate API key against ORS server
- Status icon: "Not configured" → "Valid" → shows ✓ or ❌

##### Link to ORS Sign-up
- Rich text label with clickable link: https://openrouteservice.org

**User Workflow:**
1. Select routing provider:
   - **Free/OSM:** Click "Next" immediately (enabled)
   - **ORS:** Enter key, click "Check Key"
     - If valid: Enable "Next" button → ORS Panel shows ✓ icon
     - If invalid: MessageBox "Invalid ORS API key"; Next remains disabled

2. Click "Next" → Road Network Panel

**Signals:**
- `switch_to_next_tab` → Road Network Panel (or conditionally jumps based on analysis flow)
- `switch_to_previous_tab` → S2S Panel (if regional) OR Create Project Panel (if national/local)

**Settings Stored:**
- `ors_key`: API key (encrypted or plain, stored in QSettings)
- `use_ors_for_accessibility`: bool

---

#### 1.3.8 Road Network Panel (Active Transport Preparation)

**Purpose:** Set up OpenStreetMap road network layers for accessibility analysis.

**Components:**

##### Reference Layer Display
- Shows study area boundary (read-only, for reference)
- CRS of boundary (read-only)

##### Network Layer Selection
- **Primary:** Road network layer combo (polygon or polyline)
- **Secondary:** Cycle path layer combo (optional)
- Layer must match CRS of study area

##### OSM Download Option
- Button: "Download from OSM"
  - Triggers background `OSMDownloaderTask` for study area extent
  - Shows progress bar: "Downloading OSM data... [██░░░░]"
  - Downloads roads/paths for study area, saves to GeoPackage or layer file
  - User can then select downloaded layer in combo

##### Validation & State
- Warning banner (if missing network layer): "Configure network layers before running analysis"
- "Configure" button in warning → Opens this panel from Tree Panel

**User Workflow:**
1. Option A: **Use Existing Layer**
   - Select from combo box
   - Validation: layer geometry type matches expected (polyline for roads)

2. Option B: **Download from OSM**
   - Click "Download from OSM"
   - Background task queued
   - Progress shown in progress bar
   - After completion, layer added to QGIS project
   - User selects in combo

3. Click "Next" → Tree Panel
   - Emits: `road_network_layer_path_changed(path)` → saved to model.json

**Signals:**
- `switch_to_next_tab` → Tree Panel
- `switch_to_previous_tab` → ORS Panel (or Create Project, depending on flow)
- `road_network_layer_path_changed` → Tree Panel stores in model

**Settings Stored:**
- `road_network_layer_path`: Full file path to network layer

---

### 1.4 PROJECT SETUP UML Activity Diagram

```
@startuml
start
:Dock opened;
:Show Intro Panel;
:User reads welcome;
:Click Next;
:Show Credits Panel;
:Click Next;
:Show Setup Panel;
if (User selects?) then (Create New)
  :Show Create Project Panel;
  :Select boundary layer;
  :Select area name field;
  :Choose analysis scale;
  if (Regional?) then (Yes)
    :Show H3 resolution dropdown;
    :User selects H3 resolution;
    :Validate H3 cell count;
  else (National/Local)
    :Show cell size spinbox;
    :User enters cell size (m);
  endif
  :Select working directory;
  :Select CRS strategy;
  :Check Women Considerations box;
  :Click Continue;
  :Copy model.json template;
  :Spawn StudyAreaProcessingTask;
  :Show progress bar (bouncing);
  :Process GHSL download;
  if (GHSL failed?) then (Yes)
    :Show user prompt: Continue without GHSL?;
    if (User chooses?) then (Yes)
      :Resume processing;
    else (No)
      :Abort task;
      :Show error message;
      stop
    endif
  endif
  :Process grids & masks;
  :Show live progress [15%...90%];
  :Live-update map with bboxes;
  :Task completes;
  :Generate study area report (background);
else (Open Existing)
  :Show Open Project Panel;
  :Select from recent or browse;
  :Validate model.json & study area outputs;
  if (Outputs valid?) then (Yes)
    :Load project;
  else (No)
    :Prompt: Regenerate study area?;
    if (User chooses?) then (Yes)
      :Restart study area processing;
    else (No)
      :Return to setup;
      stop
    endif
  endif
endif
if (Regional analysis?) then (Yes)
  :Show S2S Prefetch Panel;
  if (User enables prefetch?) then (Yes)
    :Queue S2S download jobs;
  endif
  :Show ORS Setup Panel;
else (National/Local)
  :Show ORS Setup Panel;
endif
:Show Road Network Panel;
if (User needs OSM network?) then (Yes)
  :Trigger OSM downloader;
  :Wait for completion;
else (No)
  :Select existing road network;
endif
:Click Next;
:Show Tree Panel (Analysis Configuration);
stop
@enduml
```

---

## 2. CONFIGURATION PHASE

### 2.1 Overview

Once project setup completes, the user enters the **Configuration Phase**, where they customize analysis indicators, weights, and data sources via the **Tree Panel**. This phase is flexible: users can iteratively edit, preview, and save changes without running analysis.

### 2.2 Tree Panel

**Purpose:** Central interface for indicator/factor/dimension configuration, analysis execution, and result visualization.

**Layout:**

```
┌─────────────────────────────────────────┐
│  ⚠️  Warning (if network not configured) │
│      [Configure] [✕]                    │
├─────────────────────────────────────────┤
│  ▼ Analysis                             │
│    ▼ Contextual                         │
│      ▼ Population & Livelihoods         │
│        ○ Population Density             │
│        ○ Labor Force Size               │
│      ▼ Women Enabling (if enabled)      │
│        ○ Business Ownership Ratio       │
│    ▼ Geospatial                         │
│      ▼ Physical Infrastructure          │
│        ○ Road Density                   │
├─────────────────────────────────────────┤
│  [▶ Run all ▼] Run incomplete           │
│  [Project] [Help] [Overall: 0%][Task: 0%]
│  Status: "Starting..."                  │
└─────────────────────────────────────────┘
```

**Hierarchy:**
- **Analysis** (root, 1 item)
  - **Dimension** (e.g., Contextual, Geospatial, Social, Environmental)
    - **Factor** (e.g., Population & Livelihoods, Physical Infrastructure)
      - **Indicator** (e.g., Population Density, Road Density)
        - **Analysis Mode** (datasource type: vector layer, raster, OSM, S2S, etc.)
        - **Weighting** (factor contribution to parent dimension)

### 2.3 Tree Item Types & Properties

#### 2.3.1 Indicator (Leaf Node)

**Role:** `"indicator"`

**Attributes:**
- `id`: Unique identifier (e.g., "population_density")
- `indicator`: Display name (e.g., "Population Density")
- `analysis_mode`: Datasource widget type (see Section 2.5)
- `factor_weighting`: Weight 0–1 (default typically 1.0)
- `default_factor_weighting`: Fallback if user clears
- `osm_download_enabled`: Bool (if analysis_mode supports OSM)
- `status`: "Completed" | "Failed" | "Excluded from analysis" | (none)
- `result`: Path to output raster/grid layer (if completed)
- `result_file`: Same as result (alternative key)
- `error`: Error message text (if failed)
- `error_file`: Path to error log file (if failed)

**Status Icons (Column 1):**
- ✓ Green: Completed successfully
- ❌ Red: Failed (hover shows error)
- ⚠ Orange: Excluded (factor_weighting = 0 or analysis_mode = "Do Not Use")
- ▶ Throbber (animated .gif): Currently running

**User Actions (Right-click Context Menu):**
- "Run Item Workflow" (or "Rerun Item Workflow" if shift-held)
- "Edit Weights" → Opens parent factor's aggregation dialog
- "Clear Item" → Resets result/error state
- "Add to map" → Adds result raster to QGIS project
- "Add to map (Grid)" → Adds grid layer column to map
- "Disable" / "Enable" → Toggles by setting factor_weighting = 0
- "Show Attributes" → Modal dialog with JSON attributes

---

#### 2.3.2 Factor (Container)

**Role:** `"factor"`

**Attributes:**
- `id`: Unique identifier
- `name`: Display name (e.g., "Population & Livelihoods")
- `description`: Help text
- `dimension_weighting`: Weight 0–1 (contribution to parent dimension)
- `default_dimension_weighting`: Fallback
- `women_enabling`: 0 (always enabled) | 1 (women-specific, toggle with women considerations) | 2 (EPLEX, inverse toggle)
- `status`: Aggregated from child indicators (inherited)
- Contains 1+ child indicators

**Aggregation Behavior:**
- Factor result = weighted average or OWA of child indicator results
- Factor weight in dimension = sum of enabled child indicator weights (if weighting column visible)
- If all child indicators excluded → factor excluded

**User Actions (Right-click Context Menu):**
- "Edit Weights" → Opens Factor Aggregation Dialog (see Section 2.6)
- "Run Item Workflow"
- "Clear Item"
- "Add to map (Grid)"
- "Disable" / "Enable"

---

#### 2.3.3 Dimension (Container)

**Role:** `"dimension"`

**Attributes:**
- `id`: Identifier (e.g., "contextual", "geospatial")
- `name`: Display name (e.g., "Contextual")
- `description`: Help text
- `analysis_weighting`: Weight 0–1 (contribution to final GeoE3 score)
- `default_analysis_weighting`: Fallback
- `women_considerations_enabled`: Propagated from analysis item (for contextual logic)
- `eplex_score`: EPLEX aggregation value (contextual dimension only)
- Status: Aggregated from child factors
- Contains 1+ child factors

**Aggregation Behavior:**
- Dimension result = weighted average of child factor results
- Dimension weight in analysis = used by analysis aggregation dialog

**User Actions (Right-click Context Menu):**
- "Edit Weights" → Opens Dimension Aggregation Dialog
- "Run Item Workflow"
- "Clear Item"
- "Add to map (Grid)"
- "Disable" / "Enable"

---

#### 2.3.4 Analysis (Root)

**Role:** `"analysis"`

**Attributes:**
- `analysis_scale`: "regional" | "national" | "local"
- `analysis_cell_size_m`: Grid cell size in meters
- `analysis_h3_resolution`: H3 resolution (regional only)
- `women_considerations_enabled`: Bool
- `road_network_layer_path`: Path to network layer (optional)
- `qgis_project_path`: Path to associated QGIS project (optional)
- `population_layer_source`: Path to population raster (optional)
- `aggregation_polygon_layer_source`: Path to subnational boundary layer (optional)
- Status: Aggregated from all dimensions

**User Actions (Right-click Context Menu):**
- "Edit Weights and Settings" → Analysis Aggregation Dialog
- "Set Network Layers" → Opens Road Network Panel
- "Set ORS Options" → Opens ORS Panel
- "Run Item Workflow" → Runs entire analysis workflow (indicators → factors → dimensions → analysis)
- "Add to map (Raster)" → Adds GeoE3 score raster
- "Add to map (Grid)" → Adds GeoE3 score grid layer
- "Add GeoE3 by Population to Map"
- "Add Masked Scores to Map" (GHSL-masked)
- "Add Job Opportunities Mask to Map"
- "Add GHSL Settlements to Map"
- "Add Study Area to Map" → Adds all study area layers (grid, polygons, bboxes, etc.)
- "Animate results" → Cycles through dimension/factor results with time-lapse effect
- "Show Analysis Report" → Generates HTML/PDF report of results
- "Show Study Area Report" → Shows study area generation report
- "Clean Unused Layers from Project"
- "Open Working Directory"
- "Open Log File"

---

### 2.4 Datasource Widgets (Input Specification)

**Location:** `geest/gui/widgets/datasource_widgets/`

Datasource widgets allow users to specify the **source data** for each indicator. Each widget corresponds to an `analysis_mode` value in the indicator's attributes.

#### 2.4.1 Widget Types & Input Kinds

| Analysis Mode | Widget Class | Input Type(s) | Captured Fields |
|---|---|---|---|
| `vector_layer_and_field` | VectorAndFieldDataSourceWidget | Vector layer + attribute field | layer source, field name, buffer distance (optional) |
| `vector_layer` | VectorDataSourceWidget | Vector layer (point/polyline/polygon) | layer source, buffer/distance settings |
| `raster` | RasterDataSourceWidget | Raster layer | layer source, reclassification rules (optional) |
| `fixed_value` | FixedValueDataSourceWidget | Static scalar value | numeric value (0–1) |
| `csv` | CsvDataSourceWidget | CSV file | file path, key column (field), value column |
| `acled_csv` | AcledCsvDataSourceWidget | ACLED conflict dataset (CSV) | file path, event type filters |
| `s2s` | S2SDataSourceWidget | Space2Stats API (NTL, Education, Hazards) | dataset type (NTL, education, environmental), field mapping |
| `s2s_education` | S2SEducationDataSourceWidget | S2S Education data | urbanization field, enrollment field |
| `s2s_ntl` | S2SNtlRasterDataSourceWidget | S2S Night Time Lights raster | raster VRT path |
| `s2s_environmental_hazards` | S2SEnvironmentalHazardsRasterDataSourceWidget | S2S environmental hazards | hazard type (flood, earthquake, etc.) |
| `index_score` | IndexScoreConfigurationWidget | Pre-computed index raster | index raster source |
| `index_score_with_ghsl` | IndexScoreWithGhslConfigurationWidget | Index raster + GHSL mask | index raster, GHSL reference |
| `index_score_with_ookla` | IndexScoreWithOoklaConfigurationWidget | Ookla speed/coverage data | Ookla dataset path |
| `osm_transport` | OsmTransportConfigurationWidget | OSM road network + routing | ORS API key (if using ORS), study area geometry |
| `multi_buffer` | MultiBufferConfigurationWidget | Vector layer with multiple buffer distances | layer, distance list |
| `single_buffer` | SingleBufferConfigurationWidget | Vector layer with single buffer | layer, distance |
| `classified_polygon` | ClassifiedPolygonConfigurationWidget | Polygon layer with class field | layer, class field, class→value mapping |
| `safety_polygon` | SafetyPolygonConfigurationWidget | Safety polygon datasource | layer, safety metric field |
| `safety_raster` | SafetyRasterConfigurationWidget | Safety raster datasource | raster, safety score reclassification |
| `street_lights` | StreetLightsConfigurationWidget | Street light point layer | layer, light density calculation |
| `feature_per_cell` | FeaturePerCellConfigurationWidget | Count features per grid cell | vector layer, aggregation type |
| `contextual_index_score` | ContextualIndexScoreConfigurationWidget | Pre-computed contextual index | index raster |
| `eplex` | EplexConfigurationWidget | EPLEX women economic empowerment index | computation options |
| `dont_use` | DontUseConfigurationWidget | Disabled/unused indicator | (none) |

#### 2.4.2 Common Datasource Widget Features

Each widget inherits from `BaseDataSourceWidget`:

**Constructor Parameters:**
- `widget_key`: Analysis mode identifier
- `attributes`: Dict of indicator attributes (mutable reference)

**Methods:**
- `add_internal_widgets()`: Populate UI with layer combos, spinboxes, etc.
- `update_attributes()`: Read widget state and update attributes dict
- `data_changed.emit(dict)`: Signal when user modifies input

**Layout:** Horizontal `QHBoxLayout` (compact inline placement in Factor Aggregation Dialog table)

**Validation:**
- Layer validity (if vector/raster layer required)
- Field existence (if field-based input)
- Value ranges (e.g., buffer distance > 0)
- File existence (if CSV/raster path required)

---

#### 2.4.3 Datasource Widget Examples

**Example 1: Vector Layer + Field (e.g., Health Facilities)**

```
Inputs:
  - Combo: Select layer (from project layers)
  - Combo: Select field (attribute column)
  - Spinbox: Buffer distance (meters) [optional]

Widget emits: data_changed({'layer_source': '/.../health_facilities.gpkg|layer=points',
                            'field_name': 'facility_type',
                            'buffer_distance_m': 500})
```

**Example 2: Raster Layer with Reclassification**

```
Inputs:
  - Combo: Select raster layer
  - Table: Define reclassification rules
    [Input Min] [Input Max] → [Output Value]

Widget emits: data_changed({'raster_source': '/.../population.tif',
                            'reclass_rules': [[0, 100, 0.0], [100, 500, 0.5], [500, 9999, 1.0]]})
```

**Example 3: Fixed Value (e.g., Placeholder)**

```
Input:
  - Spinbox: Value (0–1)

Widget emits: data_changed({'fixed_value': 0.75})
```

**Example 4: CSV Field Lookup (e.g., District Scores)**

```
Inputs:
  - File dialog: Select CSV file
  - Combo: Select column with grid cell IDs
  - Combo: Select column with values

Widget emits: data_changed({'csv_source': '/.../district_scores.csv',
                            'key_field': 'grid_id',
                            'value_field': 'score'})
```

**Example 5: Space2Stats NTL Raster**

```
Input:
  - (API handles download automatically to study area)
  - Raster path to VRT

Widget emits: data_changed({'s2s_source': '/.../s2s_ntl.vrt'})
```

---

### 2.5 Factor Aggregation Dialog

**Trigger:** User double-clicks a factor, or selects "Edit Weights" from context menu.

**Purpose:** Configure datasources, weights, and enable/disable status for all child indicators within a factor.

**Layout:**

```
┌──────────────────────────────────────────────────────────┐
│  [GeoE3 Banner]                                          │
├──────────────────────────────────────────────────────────┤
│  Contextual :: Population & Livelihoods                  │ (hierarchy label)
├──────────────────────────────────────────────────────────┤
│  "Assesses livelihood opportunities..."                  │ (factor description)
├──────────────────────────────────────────────────────────┤
│  [Configuration Widget] (toggles input type per indicator)
├──────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Input │ OSM Dl │ Indicator     │ Weight │ Use │ GUID  │
│  ├─────────────────────────────────────────────────────┤ │
│  │ [Combo]│[Btn]  │ Pop Density   │ 0.5  │[☑]  │ guid1 │
│  │ [Combo]│[Btn]  │ Jobs/1000     │ 0.5  │[☑]  │ guid2 │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  [Balance Weights] [Show GUIDs] [OK] [Cancel]            │
└──────────────────────────────────────────────────────────┘
```

**Table Columns:**

1. **Input** (Stretch)
   - Datasource widget for the indicator (see Section 2.4)
   - Allows user to change layer/field/raster/value on the fly
   - Emits `data_changed` → validates & refreshes configuration

2. **OSM Download** (Fixed 170px, conditionally visible)
   - Only shown if any indicator has `osm_download_enabled: 1`
   - Button: "Download OSM"
   - Triggers background `OSMDownloaderTask` for study area extent
   - Downloads relevant OSM features (e.g., amenities for health services)
   - User must manually merge point + polygon results into single point layer

3. **Indicator** (Stretch or Fixed 200px)
   - Read-only indicator name label

4. **Weight** (Fixed 100px, conditionally visible)
   - Only shown if 2+ indicators in factor
   - `QDoubleSpinBox(0.0–1.0, 4 decimals, step 0.01)`
   - Validation: sum of enabled indicator weights must = 1.0
   - "Reset" button restores default_factor_weighting

5. **Use** (Fixed 50px)
   - `QCheckBox` to enable/disable indicator
   - Affects factor_weighting and analysis inclusion
   - Unchecking → sets factor_weighting = 0, dims other cells
   - If analysis_mode = "Do Not Use", checkbox disabled

6. **GUID** (Hidden by default, toggleable)
   - Shows indicator's unique identifier
   - Useful for debugging; visible in verbose mode

**User Workflow:**

1. **Review Input Datasources:**
   - For each indicator, verify the Input widget is correctly configured
   - E.g., if indicator is "Population Density", Input should show a population raster

2. **Change Datasource (if needed):**
   - Click in Input cell → widget becomes active
   - User selects different layer, field, value, etc.
   - Widget emits `data_changed` → validates & refreshes configuration

3. **Enable/Disable Indicators:**
   - Check/uncheck "Use" checkbox for each indicator
   - Disabled indicators (unchecked or analysis_mode="Do Not Use") excluded from aggregation

4. **Set Weights (if 2+ indicators):**
   - Weight column only visible if weighting is necessary (2+ child indicators)
   - User manually enters weights, or:
   - Click "Balance Weights" button → Auto-calculates equal weights for enabled indicators
     - E.g., 2 enabled → each gets 0.5; 3 enabled → each gets 0.333

5. **Validation:**
   - **Green text:** Weights sum to 1.0 (valid) → OK button enabled
   - **Red text:** Weights do NOT sum to 1.0 (invalid) → OK button disabled
   - Special case: If ALL indicators disabled, sum = 0.0 (valid, means factor not used)

6. **Save:**
   - Click "OK" → Persists to model.json automatically
   - If any configuration changed (not just weights), clear indicator result/error state
   - Click "Cancel" → Reverts all unsaved changes

**Buttons:**
- "Balance Weights" (if weighting visible) → Auto-calculate equal weights
- "Show GUIDs" (if verbose mode) → Toggle GUID column visibility
- "OK" → Save and close
- "Cancel" → Revert and close

**OSM Disclaimer (if OSM Download column visible):**
```
⚠️ OSM Data Disclaimer:
The OSM downloader may return a mix of point and polygon geometries...
Polygon features should be converted to points (e.g., centroids) and merged...
```

---

### 2.6 Dimension & Analysis Aggregation Dialogs

**Similar structure to Factor Aggregation**, but operates on factors (not indicators).

**Dimension Aggregation Dialog:**
- Shows all child factors in dimension
- Allows user to set dimension_weighting for each factor
- "Balance Weights" button auto-calculates equal weights
- Same validation (sum = 1.0)

**Analysis Aggregation Dialog:**
- Shows all dimensions in analysis
- Allows user to set analysis_weighting for each dimension
- "Balance Weights" button
- Also includes:
  - Population layer selection (optional, for post-analysis products)
  - Aggregation polygon layer selection (optional, for subnational rollups)
  - OSM network validation (warning if not set)

---

### 2.7 CONFIGURATION PHASE UML Activity Diagram

```
@startuml
start
:Tree Panel loaded;
:Show indicator/factor/dimension tree;
loop Until user ready to analyze
  :User double-clicks item or right-clicks;
  if (Item type?) then (Indicator)
    :Open parent factor's aggregation dialog;
  else if (Factor)
    :Open Factor Aggregation Dialog;
    :Display all child indicators in table;
    loop User customizes indicators
      if (Change datasource?) then (Yes)
        :Click in Input cell;
        :Datasource widget becomes active;
        :User selects new layer/field/value;
        :Widget emits data_changed;
        :Dialog validates & updates configuration;
      endif
      if (Enable/disable indicator?) then (Yes)
        :Toggle "Use" checkbox;
        :Weight cell dims if unchecked;
        :Validation re-runs;
      endif
      if (Set weights manually?) then (Yes)
        :Edit weight spinbox;
        :Validate sum ≤ 1.0;
        :Toggle OK button state;
      endif
    endloop
    if (Auto-balance?) then (Yes)
      :Click "Balance Weights";
      :Calculate equal weights for enabled;
      :Update all weight spinboxes;
    endif
    :Click OK;
    :Save weights & datasources to model.json;
    :Clear indicator result state if config changed;
    :Close dialog;
  else if (Dimension)
    :Open Dimension Aggregation Dialog;
    :Show all child factors;
    :User sets dimension weights;
    :Click OK → Save;
  else if (Analysis)
    :Open Analysis Aggregation Dialog;
    :Show all dimensions;
    :User sets analysis weights;
    :Optional: Select population layer;
    :Optional: Select aggregation polygon layer;
    :Click OK → Save;
  endif
  if (Continue configuring?) then (Yes)
  else (No)
  endif
endloop
:User ready to run analysis;
stop
@enduml
```

---

## 3. ANALYSIS PHASE

### 3.1 Overview

The **Analysis Phase** executes indicator, factor, dimension, and analysis workflows in a structured queue, updating the tree with progress icons and results as each completes.

### 3.2 Running Analysis: User Actions

#### 3.2.1 Run All

**Trigger:** Click "▶ Run all" button or "Run all" menu item

**Behavior:**
1. Clears all results (indicators, factors, dimensions, analysis)
2. Counts total workflows to process (all indicators + factors + dimensions + analysis)
3. Sets `run_only_incomplete = False` (forces recomputation)
4. Queues all workflows in order: indicators → factors → dimensions → analysis
5. Shows progress bars and status label
6. Hides "Run all", "Project", "Help" buttons while running

**Output:**
```
Overall Progress: [████████░░] 18/20 (90%)
Task Progress:    [██░░░░░░░░] 20%
Status: "Processing Population Density..."
```

---

#### 3.2.2 Run Incomplete

**Trigger:** Click dropdown menu → "Run incomplete"

**Behavior:**
1. Counts only incomplete workflows (no prior result)
2. Sets `run_only_incomplete = True`
3. Queues only missing indicators + factors + dimensions + analysis
4. Faster than "Run all" (skips already-completed items)

---

#### 3.2.3 Run Item (With Shift for "Rerun")

**Trigger:** Right-click item → "Run Item Workflow" or "Rerun Item Workflow" (if shift-held)

**Behavior:**
1. Determines item type and required workflow stages:
   - Indicator → run ["indicators"]
   - Factor → run ["indicators", "factors"]
   - Dimension → run ["indicators", "factors", "dimensions"]
   - Analysis → run ["indicators", "factors", "dimensions", "analysis"]
2. Counts descendant items to process (only within scope of selected item)
3. Sets `run_only_incomplete`:
   - Normal click → True (skip already-completed children)
   - Shift-click → False (rerun all children)
4. Queues workflows in order
5. Shows progress bars for selected item's scope

---

### 3.3 Workflow Queue & Execution

**Queue Manager:** `WorkflowQueueManager(pool_size=None)` in TreePanel

- Pool size dynamically reads `concurrent_tasks` setting (default 1–4)
- Allows users to tune concurrency without restarting

**Execution Order (Sequential Stages):**

```
Stage 1: All indicators
  → After all complete, emit signal

Stage 2: All factors
  → After all complete, emit signal

Stage 3: All dimensions
  → After all complete, emit signal

Stage 4: Analysis aggregation (WEE score)
  → If successful:
     a) Calculate analysis insights (population score, opportunities mask, subnational aggregation)
     b) Auto-add result layer(s) to map
  → emit signal
```

**Constraints:**
- Factors cannot run until all child indicators complete (prevents race conditions)
- Dimensions cannot run until all child factors complete
- Analysis cannot run until all dimensions complete

---

### 3.4 Workflow Status & Visual Feedback

**Tree Item Status Icons (Column 1):**

| Icon | Status | Meaning |
|------|--------|---------|
| ✓ (green) | Completed | Workflow ran successfully; result stored |
| ❌ (red) | Failed | Workflow ran but error occurred; error file stored |
| ⚠️ (orange) | Excluded | Weighting = 0 or analysis_mode = "Do Not Use" |
| (throbber .gif animated) | Running | Workflow currently executing |
| (blank) | Pending | Not yet run; awaiting user input or queue slot |

**Progress Bars (Bottom of Tree Panel):**

- **Overall Progress:** `[████████░░] 18/20`
  - Total workflows completed / total to complete
  - Updated after each workflow finishes

- **Task Progress:** `[██░░░░░░░░] 20%`
  - Individual workflow progress (0–100%)
  - Updated in real-time if workflow emits progress updates

**Status Label:**
- Dynamic text: "Processing Population Density..." or "Building Accessibility Raster..."
- Truncated to 35 characters (full text shown on hover as tooltip)
- Clears when analysis completes

**Error Handling:**
- If workflow fails: status bar shows red; error icon added to tree item; error file saved to working directory
- Error message also pushed to dock-level message bar (top of dock) as persistent notification
- User can click item to see error details in tooltip or dialog

---

### 3.5 Workflow Job Types & Outputs

**Each indicator workflow:**
- Processes datasource (vector → raster, field lookup, S2S API call, etc.)
- Clips to study area grid extent
- Writes output raster to GeoPackage or VRT
- Stores result path in indicator.result_file attribute

**Each factor workflow:**
- Reads child indicator result rasters
- Performs weighted aggregation (average or OWA)
- Clips to study area grid
- Writes aggregated raster
- Stores result path in factor.result_file attribute

**Each dimension workflow:**
- Reads child factor result rasters
- Weighted aggregation
- Stores result path in dimension.result_file attribute

**Analysis workflow:**
- Reads all dimension result rasters
- Final weighted aggregation → GeoE3 score (0–1)
- Stores as raster + grid layer column
- Triggers post-processing:
  - **Population Score:** GeoE3 score × population density → opportunities grid
  - **Opportunities Mask:** User-specified job opportunity polygon layer → binary mask
  - **Masked Scores:** Apply mask to GeoE3 & population scores
  - **Subnational Aggregation:** Summarize scores by user-specified admin boundaries (optional)

---

### 3.6 Long-Running Background Tasks

**StudyAreaProcessingTask** (during project setup)
- Handled during project creation phase
- Shows bouncing progress bar while GHSL downloads; fixed progress % during grid processing

**IndicatorWorkflow, FactorWorkflow, DimensionWorkflow, AnalysisWorkflow** (during analysis)
- Queued in workflow manager
- Execute one-by-one (configurable concurrency)
- Emit progress updates every second (or less frequently for long tasks)
- Can be cancelled (user clicks "Cancel" button, if present)

**S2SDownloaderTask** (optional, regional projects only)
- Queues multiple download jobs if prefetch enabled
- Retry logic (4 attempts per chunk)
- Inter-job delay (750 ms) to avoid rate limiting

**OSMDownloaderTask** (optional, network layer setup)
- Downloads OpenStreetMap features for study area extent
- Shows progress bar during download
- Adds result layer to QGIS project

**AnalysisReportTask** (post-analysis, optional)
- Generates HTML/PDF report summarizing results
- Runs asynchronously after analysis completes
- User can view via "Show Analysis Report" context menu

---

### 3.7 Decision Points & Error Recovery

**During Run:**
1. **GHSL Download Failed (project setup phase):**
   - MessageBox: "Continue without GHSL data? [Yes/No]"
   - Yes → Resume with accessibility raster masks skipped
   - No → Abort project setup; return to Create Project Panel

2. **Workflow Execution Failed (analysis phase):**
   - Log error to error file
   - Update tree item status to ❌ (red)
   - Push error notification to dock message bar
   - Continue to next workflow in queue (don't halt entire analysis)

3. **User Cancels Analysis (if cancellation UI present):**
   - Stops queueing new jobs
   - Allows in-progress workflow to finish
   - Updates status label: "Cancelled by user"

---

### 3.8 ANALYSIS PHASE UML Activity Diagram

```
@startuml
start
:User clicks Run;
:Determine scope & workflow stages;
if (Run all?) then (Yes)
  :Set run_only_incomplete = False;
  :Clear all results;
else (Run incomplete)
  :Set run_only_incomplete = True;
endif
:Count workflows to process;
:Show progress bars;
:Initialize workflow queue;
:Disable Run button, Project, Help buttons;
:status_label.setText("Starting...");
:overall_progress_bar.setValue(0);
:workflow_queue = ["indicators", "factors", "dimensions", "analysis"];
:run_next_workflow_queue();
|
:Dequeue first indicator;
:Set icon to throbber (animated);
:status_label.setText("Processing Population Density...");
:Spawn IndicatorWorkflow task;
while (Workflow running)
  :workflow_progress_bar.setValue(progress);
endwhile
:On workflow complete;
if (Success?) then (Yes)
  :Set icon to ✓ (green);
  :Store result path in item.result_file;
  :Auto-add result layer to map;
  :overall_progress_bar.increment();
else (Failed)
  :Set icon to ❌ (red);
  :Store error in item.error_file;
  :Push error notification to message bar;
  :overall_progress_bar.increment();
endif
:Dequeue next indicator;
if (More indicators?) then (Yes)
  :Repeat loop;
else (No, all indicators done)
endif
|
:Dequeue first factor;
:Repeat workflow execution;
:After all factors complete;
|
:Dequeue first dimension;
:Repeat workflow execution;
:After all dimensions complete;
|
:Dequeue analysis workflow;
:Spawn AnalysisWorkflow;
:Workflow computes GeoE3 score;
:On analysis complete;
:calculate_analysis_insights();
  note right
    - Population score
    - Opportunities mask
    - Masked scores
    - Subnational aggregation
  end note
:Auto-add analysis results to map;
|
:workflow_queue exhausted;
:overall_progress_bar.setValue(items_to_run);
:Show completion status;
:Re-enable Run all, Project, Help buttons;
:Hide progress bars (after 3s);
:status_label.setVisible(False);
stop
@enduml
```

---

## 4. SPECIAL PANELS & DIALOGS

### 4.1 Road Network Panel

**See Section 1.3.8 for full details.**

Key Features:
- Set primary road network layer + optional cycle paths
- Validate CRS matching
- Download OSM roads if needed
- Store path in model for accessibility calculations

---

### 4.2 S2S Prefetch Panel

**See Section 1.3.6 for full details.**

Key Features:
- Optional prefetch of remote Space2Stats datasets (regional projects only)
- Chunked downloads with retry logic
- Reduces runtime during indicator workflows

---

### 4.3 Settings / Options Dialog

**Trigger:** (Not directly in current UI; typically accessed via main QGIS plugin menu or dock settings button)

**Configurable Settings:**
- `ors_key`: OpenRouteService API key
- `use_ors_for_accessibility`: Bool (use ORS vs. free OSM routing)
- `concurrent_tasks`: Int (1–4, pool size for workflow queue manager)
- `verbose_mode`: Bool (show GUID columns, debug info)
- `geoe3_debug`: Env var (0/1, enables synchronous task execution for debugging)

**Storage:** QSettings (persistent across QGIS sessions)

---

### 4.4 Help Panel

**Trigger:** Click "Help" button in Tree Panel

**Content:**
- Link to GeoE3 User Guide (HTML/PDF)
- FAQ or troubleshooting tips
- Links to FAQs in Factor/Dimension dialogs

**Signals:**
- `switch_to_previous_tab` → Tree Panel

---

## 5. POST-ANALYSIS PHASE

### 5.1 Output Products

After analysis completes, users can add results to the map via context menu actions:

**GeoE3 Score Products:**
- **GeoE3 Score (Raster):** Full-resolution score raster
- **GeoE3 Score (Grid):** Score aggregated to grid cells (faster rendering)
- **GeoE3 by Population:** Score weighted by population density
- **GeoE3 Masked (GHSL):** Score masked by GHSL-defined settlement areas

**Aggregate Products (if subnational boundary layer provided):**
- **GeoE3 Score Aggregate:** Average GeoE3 score per admin unit
- **GeoE3 by Population Aggregate:** Population-weighted GeoE3 per admin unit
- **GeoE3 Score GHSL Masked Aggregate:** Masked aggregate per admin unit

**Opportunity Products:**
- **Job Opportunities Mask:** Binary layer showing user-specified job opportunity zones
- **Opportunities Masked GeoE3:** GeoE3 score × opportunities mask

**Study Area & Supporting Layers:**
- **Study Area Grid:** Analysis grid (squares or H3 hexagons)
- **Study Area Polygons:** Original input boundaries
- **GHSL Settlements:** Settlement areas (if downloaded)
- **Bounding Boxes:** Feature bounding boxes (for debugging)

### 5.2 Adding Results to Map

**Trigger:** Right-click Analysis item → Select output to add

**Actions:**
```
Add to map (Raster)          → Raster rendering at full resolution
Add to map (Grid)            → Simplified grid layer (faster)
Add GeoE3 by Population      → Population-weighted scores
Add Masked Scores            → GHSL-masked products
Add Job Opportunities Mask   → Opportunity zones
Add GHSL Settlements         → Settlement reference layer
Add Study Area to Map        → All study area layers (grid, polygons, etc.)
```

**Result:**
- Layers added to QGIS project under "GeoE3" group
- QML styling applied (predefined color ramps, symbology)
- Can be toggled/configured in QGIS legend

### 5.3 Report Generation

**Analysis Report:**
- **Trigger:** Right-click Analysis item → "Show Analysis Report"
- **Content:** Summary of analysis settings, factor weights, dimension results, final GeoE3 score
- **Format:** HTML/PDF (auto-generated from template)
- **Output:** Saved to `working_directory/analysis_report.pdf`
- **Action:** Opens in system default PDF viewer

**Study Area Report:**
- **Trigger:** Right-click Analysis item → "Show Study Area Report"
- **Content:** Study area creation summary, feature counts, grid statistics
- **Format:** PDF
- **Output:** Saved to `working_directory/study_area_report.pdf`
- **Auto-generate:** Automatically created after project setup completes

---

## 6. SEQUENCE DIAGRAMS

### 6.1 Project Setup Sequence

```
@startuml
User -> UI: Open dock\n"Intro Panel"
User -> UI: Click Next
UI -> UI: Switch to Credits Panel
User -> UI: Click Next
UI -> UI: Switch to Setup Panel
User -> UI: Click "Create Project"
UI -> UI: Switch to Create Project Panel
User -> UI: Select boundary layer, area field, analysis scale, directory
User -> UI: Click Continue
activate UI
UI -> Model: Copy default model.json
UI -> Task: Spawn StudyAreaProcessingTask
activate Task
Task -> GHSL: Download settlement raster
GHSL -> Task: GhslDataReady or GhslFailed
alt GHSL failed
  Task -> UI: ghsl_download_failed signal
  activate UI
  UI -> User: "Continue without GHSL? [Yes/No]"
  deactivate UI
  alt User clicks Yes
    Task -> Task: set_ghsl_user_response(continue_without=True)
  else User clicks No
    Task -> Task: Abort
    Task -> UI: taskTerminated signal
    deactivate Task
    UI -> User: Show error in progress bar
  end
end
Task -> DB: Create study_area.gpkg (metadata tables)
Task -> Grid: Generate grid (regular or H3)
note right of Task: Show progress 0-100%\nUpdate map live with bboxes
Task -> Raster: Create masks (GHSL, VRT)
Task -> DB: Write grids to GeoPackage
Task -> UI: progressChanged(100)
Task -> UI: taskCompleted signal
deactivate Task
UI -> Report: Spawn StudyAreaReportTask
activate Report
Report -> Report: Generate PDF report
Report -> UI: taskCompleted signal
deactivate Report
UI -> UI: show "Report complete"
UI -> User: Auto-advance to S2S/ORS/RoadNetwork Panel
```

---

### 6.2 Analysis Workflow Sequence

```
@startuml
User -> Tree: Right-click indicator\n"Run Item Workflow"
Tree -> Queue: run_item(indicator, shift=False)
Tree -> Tree: Count descendant indicators to process
Tree -> UI: Show progress bars
activate Queue
loop For each indicator in scope
  Queue -> Workflow: Dequeue indicator workflow
  activate Workflow
  Workflow -> Datasource: Resolve datasource (vector/raster/S2S/OSM)
  alt Datasource type
    Workflow -> Vector: Load vector layer
    Workflow -> Raster: Rasterize to grid
  else
    Workflow -> Raster: Load raster
    Workflow -> Raster: Reproject/resample to grid CRS
  else
    Workflow -> S2S: Query S2S API
    Workflow -> Raster: Retrieve raster from cache
  end
  Workflow -> Grid: Aggregate to grid cells
  Workflow -> DB: Write output raster to GeoPackage
  Workflow -> Tree: on_workflow_completed signal
  deactivate Workflow
  Tree -> Tree: Update icon: ✓ (green)
  Tree -> Tree: overall_progress_bar.increment()
  Tree -> Map: add_to_map(indicator) auto-add result
end
deactivate Queue
alt User ran single indicator
  Tree -> Tree: Dequeue factor (parent)
  activate Queue
  Queue -> Workflow: Factor aggregation workflow
  Workflow -> Raster: Read child indicator rasters
  Workflow -> Raster: Weighted aggregation (average/OWA)
  Workflow -> DB: Write factor result raster
  Workflow -> Tree: on_workflow_completed signal
  deactivate Workflow
  Tree -> Tree: Update factor icon: ✓
  Tree -> Map: add_to_map(factor)
else User ran factor
  Tree -> Tree: Dequeue all factor workflows
  note right of Tree: Factors execute sequentially\nor in parallel (depends on concurrency setting)
end
alt
  Tree -> Tree: Dequeue dimension workflows
  Tree -> Tree: Dequeue analysis workflow
  activate Queue
  Queue -> Workflow: AnalysisAggregationWorkflow
  Workflow -> Raster: Read dimension rasters
  Workflow -> Raster: Final aggregation → GeoE3 score
  Workflow -> DB: Write GeoE3 raster
  Workflow -> Tree: on_workflow_completed signal
  deactivate Workflow
  Tree -> Insights: calculate_analysis_insights(analysis_item)
  activate Insights
  Insights -> Population: PopulationRasterProcessingTask
  Insights -> Population: Compute GeoE3 × population scores
  Insights -> Opportunities: OpportunitiesMaskProcessor
  Insights -> Opportunities: Apply job opportunity mask
  Insights -> Subnational: SubnationalAggregationProcessingTask
  Insights -> DB: Write all aggregate layers
  deactivate Insights
  Tree -> Map: add_to_map(analysis) auto-add all products
  Tree -> Tree: analysis_item.status = Completed
end
Tree -> UI: overall_progress_bar.setValue(max)
Tree -> UI: Hide progress bars after delay
Tree -> User: Analysis complete!
```

---

## 7. ERROR HANDLING & USER FEEDBACK

### 7.1 Error Surfacing Mechanisms

| Error Type | Feedback Method | Location | Duration |
|---|---|---|---|
| GHSL download failure (setup phase) | Modal MessageBox | Center screen | User dismisses |
| Study area processing error | Progress bar text + error.txt file | Bottom of Create Project Panel | Until panel reset |
| Workflow execution error | Tree item ❌ icon + error.txt file | Tree Panel column 1 + working_directory | Persistent (can be viewed via right-click) |
| ORS API key invalid | Modal MessageBox | Center screen | User dismisses |
| Invalid user input (weights don't sum to 1.0) | Spinbox text color → red | Factor Aggregation Dialog | Until fixed |
| Missing network layer | Inline warning banner | Top of Tree Panel | Until configured or dismissed |
| File not found (layer, raster, CSV) | Workflow error → tree item ❌ + error notification | Dock message bar + tree | Persistent |

### 7.2 Hover Tooltips & Extended Info

- **Tree Item Icons:** Hover shows full error message if ❌
- **Status Label:** Hover shows full status text (truncated to 35 chars in label)
- **Progress Bars:** Hover shows detailed message (if available)
- **GUID Column:** Hover shows full indicator attributes (JSON dict)

### 7.3 Log File Access

- **Trigger:** Right-click Analysis item → "Open Log File"
- **File Location:** QGIS application log (typically `~/.qgis*/QGIS/QGIS3.log`)
- **Action:** Opens in default text editor
- **Content:** All GeoE3 plugin log messages (prefixed with "GeoE3" tag)

---

## 8. SHIFT-CLICK BEHAVIORS

### 8.1 Shift-Click in Tree Context Menu

**Normal Click:** "Run Item Workflow"
- Runs item + children (incomplete only, i.e., `run_only_incomplete=True`)
- Skips already-completed workflows

**Shift-Click:** "Rerun Item Workflow"
- Runs item + children (all, i.e., `run_only_incomplete=False`)
- Forces recomputation of all, even if already completed
- Useful if user changes datasource and wants to reprocess

**Implementation:**
```python
def run_item(self, item, shift_pressed):
    if shift_pressed:
        self.run_only_incomplete = False  # Force rerun
    else:
        self.run_only_incomplete = True   # Skip completed
    # ... queue workflows
```

---

## 9. VALIDATION & CONSTRAINTS

### 9.1 Preflight Checks Before Analysis

**Before running any workflow:**

1. ✓ Working directory is set and valid
2. ✓ Study area GeoPackage exists with valid metadata
3. ✓ All indicators have valid datasources configured
4. ✓ All factor weights (if visible) sum to 1.0
5. ✓ (If using ORS) ORS API key is valid (already tested in ORS Panel)
6. ✓ (If network required) Road network layer is configured

**Warnings (non-blocking):**
- If network layer not set but connectivity indicators exist → Show warning banner in Tree Panel

**Errors (blocking):**
- If study area outputs missing → Cannot proceed; prompt user to regenerate
- If datasource layer/field invalid → Workflow skipped; error logged

### 9.2 Weight Validation

**Factor Dialog:**
- Sum of enabled indicator weights must = 1.0 (±0.001 tolerance for floating-point)
- All disabled → sum = 0.0 (valid, factor not used)
- OK button enabled only if valid

**Dimension Dialog:**
- Sum of enabled factor weights must = 1.0
- Same logic as factor

**Analysis Dialog:**
- Sum of enabled dimension weights must = 1.0

---

## 10. KEY SIGNALS & CONNECTIONS

### 10.1 Dock-Level Signals

| Signal | Emitter | Receiver | Purpose |
|--------|---------|----------|---------|
| `switch_to_next_tab` | All panels | Dock stacked widget | Navigate to next panel |
| `switch_to_previous_tab` | All panels | Dock stacked widget | Navigate to previous panel |
| `working_directory_changed(path)` | Create Project, Open Project | Tree Panel, S2S Panel | Update working directory |
| `project_loaded()` | Open Project | Dock | Auto-open associated QGIS project |
| `switch_to_network_tab` | Tree Panel | Dock | Jump to Road Network Panel |
| `switch_to_ors_tab` | Tree Panel | Dock | Jump to ORS Panel |
| `switch_to_setup_tab` | Tree Panel | Dock | Return to Setup Panel (Project selection) |

### 10.2 Tree Panel Signals

| Signal | Emitter | Receiver | Purpose |
|---|---|---|---|
| `switch_to_next_tab` | Tree Panel | Dock | Advance to Help Panel |
| `switch_to_setup_tab` | Tree Panel | Dock | Return to Setup Panel |
| `switch_to_network_tab` | Tree Panel | Dock | Open Road Network Panel |
| `switch_to_ors_tab` | Tree Panel | Dock | Open ORS Panel |
| `progressChanged(float)` | Workflow task | Tree Panel | Update task progress bar |
| `taskCompleted()` | Workflow task | Tree Panel | Workflow finished successfully |
| `taskTerminated()` | Workflow task | Tree Panel | Workflow failed or cancelled |
| `processing_completed()` | Workflow queue | Tree Panel | All queued workflows done |
| `processing_error(msg)` | Workflow queue | Tree Panel | Workflow error notification |

### 10.3 Dialog Signals

| Signal | Emitter | Receiver | Purpose |
|---|---|---|---|
| `data_changed(dict)` | Datasource widget | Factor Aggregation Dialog | Refresh configuration after input changed |
| `selection_changed()` | Configuration widget | Factor Aggregation Dialog | Update table after analysis mode changed |
| `valueChanged(float)` | Weight spinbox | Dialog | Validate weights |

---

## 11. STATE PERSISTENCE

### 11.1 Model.json Structure

```json
{
  "analysis_scale": "national",
  "analysis_cell_size_m": 1000,
  "analysis_h3_resolution": 6,
  "women_considerations_enabled": true,
  "admin_boundary_layer_source": "/.../boundaries.gpkg|layer=admin",
  "road_network_layer_path": "/.../roads.gpkg|layer=network",
  "qgis_project_path": "/.../project.qgis",
  "ors_key": "xxxxx",
  "s2s_prefetch_enabled": true,
  "dimensions": [
    {
      "id": "contextual",
      "name": "Contextual",
      "analysis_weighting": 0.333,
      "women_considerations_enabled": true,
      "factors": [
        {
          "id": "population",
          "name": "Population & Livelihoods",
          "dimension_weighting": 0.5,
          "women_enabling": 0,
          "indicators": [
            {
              "id": "population_density",
              "indicator": "Population Density",
              "analysis_mode": "raster",
              "factor_weighting": 1.0,
              "default_factor_weighting": 1.0,
              "raster_source": "/.../pop.tif",
              "status": "Completed",
              "result": "/.../results/pop.vrt",
              "execution_start_time": "2025-07-13 10:30:00",
              "execution_end_time": "2025-07-13 10:35:00"
            }
          ]
        }
      ]
    }
  ]
}
```

**Persistence:**
- Saved to disk after every tree edit (double-click, right-click "Edit Weights")
- Automatically saved after workflow completion
- User can reload from disk via "Open Project" panel

---

## 12. SUMMARY: USER DECISION POINTS

**Critical decision points during GeoE3 workflow:**

1. **Entry:** Create new project OR open existing?
2. **Project Setup:** Analysis scale (Regional/National/Local)? → H3 resolution or cell size?
3. **CRS Selection:** Use boundary layer CRS or auto-calculate UTM?
4. **Women Considerations:** Enable women-specific factors?
5. **S2S Prefetch (Regional only):** Prefetch remote datasets?
6. **Accessibility Provider:** Use free OSM routing or ORS API?
7. **ORS Configuration:** Provide valid ORS API key?
8. **Road Network:** Select/download road network layer for accessibility?
9. **Configuration:** For each factor, select datasources, set weights, enable/disable indicators?
10. **Analysis Execution:** Run all workflows? Run incomplete only? Run single item (normal or shift-rerun)?
11. **Post-Analysis:** Which output products to add to map? Generate reports?

---

## 13. APPENDIX: UI COMPONENTS & WIDGETS

### 13.1 Core Widgets

- `GeoE3Dock`: Main QDockWidget container (stacked panels)
- `IntroPanel`, `CreditsPanel`, `SetupPanel`, `CreateProjectPanel`, `OpenProjectPanel`, `S2SPanel`, `OrsPanel`, `RoadNetworkPanel`, `TreePanel`, `HelpPanel`: Sequential workflow panels
- `JsonTreeView`, `JsonTreeModel`: Hierarchical indicator/factor/dimension tree
- `FactorAggregationDialog`, `DimensionAggregationDialog`, `AnalysisAggregationDialog`: Configuration dialogs
- `DataSourceWidgetFactory`: Creates appropriate widget per analysis_mode
- `Datasource*Widget`: 15+ specialized input widgets
- `WorkflowQueueManager`: Manages async task queuing & execution
- `StudyAreaProcessingTask`, `*WorkflowTask`, `S2SDownloaderTask`, `OSMDownloaderTask`: Background tasks

### 13.2 Key QSettings Keys

```
last_working_directory      → str (path to most recent project)
recent_projects             → list[str] (recent project directories)
ors_key                    → str (OpenRouteService API key)
use_ors_for_accessibility  → bool (0/1)
concurrent_tasks           → int (1–4, workflow pool size)
verbose_mode               → int (0/1)
FactorAggregationDialog/geometry_v2  → QByteArray (dialog size/position)
```

---

## 14. CONCLUSION

The GeoE3 QGIS plugin orchestrates a complex, multi-phase spatial analysis workflow through a carefully designed UX that emphasizes:

- **Progressive Disclosure:** Information revealed in logical sequence (setup → config → analysis)
- **Clear Feedback:** Status icons, progress bars, and error messages at every step
- **Flexibility:** Run all, run incomplete, or run specific items (with shift-rerun option)
- **Asynchronous Execution:** Long-running tasks don't freeze UI; queue manager handles concurrency
- **State Persistence:** model.json stores all configuration and results; easy project reload
- **Accessibility:** Support for multiple routing providers (free OSM or paid ORS), optional women-specific factors, configurable grid types (squares or H3 hexagons)

The documented flows, diagrams, and decision points provide a comprehensive reference for understanding user interactions and troubleshooting issues in production deployments.
```
