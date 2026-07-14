Now let me create a final comprehensive report based on all the information gathered:

# GeoE3 QGIS Plugin - System Requirements Specification (SRS)

## Executive Summary

The GeoE3 (Women's Economic Empowerment) QGIS plugin is a comprehensive geospatial analysis framework for assessing women's economic opportunities and development enablement. The system produces multi-dimensional spatial datasets organized in a hierarchical model structure (Dimensions → Factors → Indicators), storing analysis results in a central GeoPackage database with a vector grid layer foundation, while generating raster products for visualization and aggregation.

---

## 1. study_area.gpkg Schema and Structure

The study area GeoPackage (`/study_area/study_area.gpkg`) serves as the central database for all geometric data and grid-based attribute scores. It contains 8 primary feature tables plus spatial indexing infrastructure.

### 1.1 Core Geometry Tables

#### **study_area_bbox**
- **Purpose**: Bounding box of the entire analysis area
- **Geometry**: POLYGON (single-part, boundary rectangle)
- **CRS**: EPSG:32735 (WGS 84 / UTM zone 35S) or dynamically selected UTM zone based on study area centroid
- **Schema**:
  - `fid` (INTEGER, PRIMARY KEY AUTOINCREMENT)
  - `geom` (POLYGON)
  - `area_name` (TEXT)
- **Spatial Index**: Automatic R-tree (`rtree_study_area_bbox_geom`)
- **Write Source**: `study_area_processing_task.py` - created during study area initialization
- **Triggers**: Feature count tracking, R-tree maintenance (insert, update, delete)

#### **study_area_bboxes**
- **Purpose**: Per-area bounding boxes (used when multiple study areas exist)
- **Geometry**: POLYGON
- **CRS**: EPSG:32735 (or auto-selected UTM)
- **Schema**: Identical to `study_area_bbox`
- **Spatial Index**: R-tree (`rtree_study_area_bboxes_geom`)
- **Write Source**: `study_area_processing_task.py`
- **Note**: Supports multi-area analyses; tracks individual area bounding boxes for optimization

#### **study_area_polygons**
- **Purpose**: Study area boundaries with metadata
- **Geometry**: POLYGON (clipped to input boundary)
- **CRS**: EPSG:32735 (or auto-selected UTM)
- **Schema**:
  - `fid` (INTEGER, PRIMARY KEY AUTOINCREMENT)
  - `geom` (POLYGON)
  - `area_name` (TEXT) - e.g., "DemocraticRepublicOfCongo"
  - `intersects_ghsl` (MEDIUMINT) - flag (0/1) whether GHSL settlements data exists for this area
  - `geom_area` (REAL) - computed polygon area in square map units
- **Spatial Index**: R-tree (`rtree_study_area_polygons_geom`)
- **Write Source**: `study_area_processing_task.py`
- **Purpose of intersects_ghsl**: Optimization flag to skip GHSL processing for areas with no settlement data

#### **study_area_clip_polygons**
- **Purpose**: Clipped geometry for masking raster outputs; may differ from study_area_polygons due to data availability
- **Geometry**: POLYGON
- **CRS**: EPSG:32735 (or auto-selected UTM)
- **Schema**: Same as `study_area_polygons` (no `intersects_ghsl` or `geom_area`)
  - `fid`, `geom`, `area_name`
- **Spatial Index**: R-tree (`rtree_study_area_clip_polygons_geom`)
- **Write Source**: `study_area_processing_task.py`
- **Relationship to study_area_polygons**: May be smaller (masked to data availability)

### 1.2 Grid Layer (Primary Analysis Vector Dataset)

#### **study_area_grid**
- **Purpose**: Regular or irregular grid cells forming the foundation for all indicator/factor/dimension analysis
- **Geometry**: POLYGON (grid cells, typically square with configurable cell size)
- **CRS**: EPSG:32735 (or auto-selected UTM)
- **Cell Size**: Configurable in model.json (`analysis_cell_size_m`), typically 1000m
- **Grid Generation**: Uses `GridFromBboxTask` with numpy-accelerated coordinate generation and intersection testing
  - Cells are clipped to study area boundaries
  - Two-phase generation: fast pass if entire chunk inside boundary, precise intersection if partial
- **Write Source**: `study_area_processing_task.py` → `GridFromBboxTask` / `GridFromBboxH3Task`

#### **study_area_grid Column Schema**

The grid layer has **54 columns** organized as follows:

**Geometry & Administrative (3 columns)**:
- `fid` (INTEGER, PRIMARY KEY AUTOINCREMENT)
- `geom` (POLYGON)
- `grid_id` (MEDIUMINT) - unique grid cell identifier
- `area_name` (TEXT) - study area identifier

**Indicator Columns (18 columns)** - individual scores from OSM/SDI sources:
- `eplex_score_indicator` (REAL) - Employment Protection Legislation Index
- `workplace_index` (REAL) - Workplace discrimination index
- `pay_parenthood_index` (REAL) - Regulatory framework for pay & parenthood
- `entrepreneurship_index` (REAL) - Financial inclusion indicator
- `kindergartens_location` (REAL) - Score 0-5 for access to kindergartens
- `primary_school_location` (REAL) - Score 0-5 for access to primary schools
- `groceries_location` (REAL) - Score 0-5 for access to grocery shops
- `pharmacies_location` (REAL) - Score 0-5 for access to pharmacies
- `green_space_location` (REAL) - Score 0-5 for access to green spaces
- `public_transport_location` (REAL) - Score 0-5 for access to public transport
- `hospital_location` (REAL) - Score 0-5 for access to health facilities
- `universities_location` (REAL) - Score 0-5 for access to universities
- `banks_location` (REAL) - Score 0-5 for access to financial facilities
- `active_transport_network` (REAL) - Score 0-5 for active transport accessibility
- `street_lights` (REAL) - Score 0-5 indicating street lighting availability
- `fcv` (REAL) - Fragility/Conflict/Violence indicator
- `education` (REAL) - Education access/quality indicator
- `digital_inclusion` (REAL) - Digital infrastructure access (Ookla data)

**Factor Columns (19 columns)** - aggregated scores per dimension factor, prefixed `fac_`:
- `fac_eplex` (REAL)
- `fac_workplace_discrimination` (REAL)
- `fac_regulatory_frameworks` (REAL)
- `fac_financial_inclusion` (REAL)
- `fac_women_s_travel_patterns` (REAL)
- `fac_access_to_public_transport` (REAL)
- `fac_access_to_health_facilities` (REAL)
- `fac_access_to_education_and_training_facilities` (REAL)
- `fac_access_to_financial_facilities` (REAL)
- `fac_active_transport` (REAL)
- `fac_safety_perception` (REAL)
- `fac_fcv` (REAL)
- `fac_education` (REAL)
- `fac_digital_inclusion` (REAL)
- `fac_environmental_hazards` (REAL)
- `fac_water_sanitation` (REAL)
- Plus 3 additional factor columns for specialized aggregations

**Dimension Columns (3 columns)** - top-level dimension scores, prefixed `dim_`:
- `dim_contextual` (REAL) - Contextual dimension score (economic policy, safety, education)
- `dim_accessibility` (REAL) - Accessibility dimension score (location-based services)
- `dim_place_characterization` (REAL) - Place characterization dimension score (hazards, water, digital)

**Aggregate Analysis Columns (8 columns)** - final WEE products:
- `geoe3` (REAL) - GeoE3 Score (0-5 scale), aggregate across all three dimensions
- `geoe3_by_population` (REAL) - GeoE3 × Population Score (1-15 bivariate classification)
  - Combines GeoE3 (5 classes) with population density (3 classes): (A-1)×3 + B
- `geoe3_masked` (REAL) - GeoE3 score masked by GHSL settlements (only in populated areas)
- `geoe3_by_population_masked` (REAL) - GeoE3×Population masked by opportunities/GHSL
- `opportunities_mask` (REAL) - Binary mask (0/1) indicating job opportunity zones
- `contextual_score` (REAL) - Raw contextual dimension score (before final aggregation)
- `accessibility_score` (REAL) - Raw accessibility dimension score
- `place_characterization_score` (REAL) - Raw place characterization dimension score

**Column Management**:
- Columns are created by `add_model_columns_to_grid()` during study area initialization
- **Lazy column creation**: Individual workflow tasks create columns on-demand using `_ensure_column_exists()` to handle Windows file locking
- Column names sanitized via `_sanitize_column_name()`: spaces/hyphens → underscores, max 63 characters
- All columns are REAL (Float32) type for vector storage; rasterized separately for raster products

### 1.3 Metadata & Status Tables

#### **study_area_creation_status**
- **Purpose**: Track study area processing steps and timing
- **Geometry**: None (attribute-only table)
- **Schema**:
  - `fid` (INTEGER, PRIMARY KEY AUTOINCREMENT)
  - `area_name` (TEXT)
  - `timestamp_start` (DATETIME) - processing start time
  - `timestamp_end` (DATETIME) - processing end time
  - `geometry_processed` (MEDIUMINT) - flag (0/1) whether geometry layer created
  - `clip_geometry_processed` (MEDIUMINT) - flag (0/1) whether clip geometry layer created
  - `grid_processed` (MEDIUMINT) - flag (0/1) whether grid created
  - `mask_processed` (MEDIUMINT) - flag (0/1) whether mask layer created
  - `grid_creation_duration_secs` (REAL) - time to create grid
  - `clip_geom_creation_duration_secs` (REAL) - time to create clip geometry
  - `geom_total_duration_secs` (REAL) - total geometry processing time
- **Write Source**: `study_area_processing_task.py`
- **Purpose**: Workflow state management and performance monitoring

### 1.4 Settlement & Auxiliary Data Tables

#### **chunks**
- **Purpose**: Grid spatial chunking metadata for parallel processing optimization
- **Geometry**: POLYGON (rectangular processing chunks)
- **CRS**: EPSG:32735 (or auto-selected UTM)
- **Schema**:
  - `fid` (INTEGER, PRIMARY KEY AUTOINCREMENT)
  - `geom` (POLYGON) - chunk boundary rectangle
  - `index` (MEDIUMINT) - chunk sequence number (0, 1, 2, ...)
  - `type` (TEXT) - chunk type classification (e.g., "interior", "boundary")
- **Spatial Index**: R-tree (`rtree_chunks_geom`)
- **Write Source**: `GridChunkerTask`
- **Purpose**: Parallelizable grid generation; chunks are processed independently then merged

#### **ghsl_settlements**
- **Purpose**: GHSL (Global Human Settlement Layer) settlement polygons for population-based masking
- **Geometry**: MULTIPOLYGON (polygons from GHSL rasterization)
- **CRS**: EPSG:32735 (or auto-selected UTM)
- **Schema**:
  - `fid` (INTEGER, PRIMARY KEY AUTOINCREMENT)
  - `geometry` (MULTIPOLYGON)
  - `pixel_value` (MEDIUMINT) - GHSL classification value (settlement density indicator)
- **Spatial Index**: R-tree (`rtree_ghsl_settlements_geometry`)
- **Write Source**: `GHSLProcessor` in `study_area_processing_task.py`
- **Purpose**: Mask analysis outputs to populated areas; enables masked WEE scores

### 1.5 Spatial Reference & CRS Conventions

**Automatic UTM Zone Selection**:
- Study area centroid longitude is used to calculate appropriate UTM zone
- Formula: `zone = int((centroid_lon + 180) / 6) + 1`
- Example: DRC uses EPSG:32735 (UTM Zone 35S)
- All vector and raster outputs use same CRS for consistency

**SRS Management**:
- Stored in `gpkg_spatial_ref_sys` table (auto-managed by QGIS OGR provider)
- Referenced by `gpkg_geometry_columns` for each table
- CRS EPSG codes preserved in GeoTIFF and VRT sidecar metadata

### 1.6 Spatial Index & Trigger Infrastructure

**R-tree Spatial Indexes**:
- Automatic spatial indexing on all geometry columns
- Tables created and maintained automatically by QGIS OGR provider:
  - `rtree_study_area_bbox_geom`, `rtree_study_area_bboxes_geom`, etc.
  - Composed of `_node`, `_parent`, `_rowid` subtables per table
- Enables rapid bounding box and spatial filter queries

**SQLite Triggers**:
- **Feature count tracking**: Auto-update `gpkg_ogr_contents.feature_count` on insert/delete
- **R-tree maintenance**: Automatic insert/update/delete on geometry changes
- **Transaction safety**: WAL (Write-Ahead Logging) mode with PRAGMA `busy_timeout=10000ms`

**Write Safety Pragmas** (applied in `grid_column_utils.py`):
```sql
PRAGMA busy_timeout=10000;        -- 10 second timeout for lock contention
PRAGMA journal_mode=WAL;           -- Write-Ahead Logging for concurrent reads
PRAGMA synchronous=NORMAL;         -- Balance durability/speed
PRAGMA wal_checkpoint(TRUNCATE);   -- Force WAL flush before close
```

---

## 2. Working Directory Filesystem Layout

The GeoE3 working directory follows a hierarchical structure reflecting the model's Dimensions → Factors → Indicators hierarchy. All paths are relative to `working_folder` defined in `model.json`.

### 2.1 Top-Level Structure

```
<working_folder>/
├── model.json                              # Master model definition & state tracking
├── error.txt (optional)                   # Workflow error logs if processing failed
├── osm_download_error.txt (optional)      # OSM Downloader errors (quota exceeded, etc.)
├── study_area_report.pdf                  # Final study area summary report
├── study_area_report.qpt                  # QGIS Print Template (.qpt) for report generation
│
├── study_area/                            # Geometry & input data layer folder
│   ├── study_area.gpkg                    # Core GeoPackage (primary database)
│   ├── study_area.gpkg.corrupt-YYYYMMDD.bak  # Auto-backup if corruption detected
│   ├── combined_mask.vrt                  # VRT merging all area clip masks
│   ├── cod.tif                            # Country boundary raster (e.g., 2.4 KB)
│   ├── boundaries.shp/dbf/shx             # Original study area boundary shapefile
│   ├── boundaries_dissolved.gpkg          # Dissolved boundary (single polygon)
│   ├── active_transport_network.gpkg      # Road network for isochrone routing
│   ├── active_transport_network.xml       # 175 MB XML metadata/styling
│   ├── ookla_*.gpkg                       # Ookla mobile/fixed broadband coverage layers:
│   │   ├── ookla_mobile.gpkg              # Mobile network coverage
│   │   ├── ookla_fixed.gpkg               # Fixed broadband coverage
│   │   └── ookla_combined.gpkg            # Combined indicator
│   └── osm_*.gpkg                         # OpenStreetMap vector data:
│       ├── osm_education.gpkg, osm_education.xml
│       ├── osm_financial.gpkg, osm_financial.xml
│       ├── osm_grocery.gpkg, osm_grocery.xml
│       ├── osm_green_space.gpkg, osm_green_space.xml  (8.8 MB XML)
│       ├── osm_health_facility.gpkg, osm_health_facility.xml
│       ├── osm_kindergarten.gpkg, osm_kindergarten.xml
│       ├── osm_pharmacy.gpkg, osm_pharmacy.xml
│       ├── osm_public_transport.gpkg, osm_public_transport.xml
│       └── osm_water_point.gpkg, osm_water_point.xml
│
├── contextual/                            # Contextual Dimension (policies, economic factors)
│   ├── Contextual_score_combined.vrt      # VRT of all factor outputs
│   ├── Contextual_score_combined.qml      # Master dimension style
│   ├── dim_contextual_masked_0.tif        # Final masked dimension raster
│   ├── dim_contextual_aggregated_0.tif.aux.xml  # GDAL metadata sidecar
│   │
│   ├── eplex/                             # EPLEX Employment Protection Legislation
│   ├── workplace_discrimination/          # Workplace Discrimination Factor
│   │   ├── fac_workplace_discrimination_masked_0.tif
│   │   ├── fac_workplace_discrimination_aggregated_0.tif.aux.xml
│   │   ├── workplace_discrimination_combined.vrt
│   │   ├── workplace_discrimination_combined.qml
│   │   └── workplace_index/               # Indicator subfolder
│   │       ├── WD_output_combined.vrt
│   │       ├── WD_output_combined.qml
│   │       ├── workplace_index_0.tif.aux.xml
│   │       └── workplace_index_masked_0.tif
│   ├── regulatory_frameworks/             # Pay, Parenthood, Legislative Frameworks
│   │   ├── fac_regulatory_frameworks_masked_0.tif
│   │   ├── regulatory_frameworks_combined.vrt/qml
│   │   └── pay_parenthood_index/
│   └── financial_inclusion/               # Financial Inclusion Factor
│       ├── fac_financial_inclusion_masked_0.tif
│       ├── financial_inclusion_combined.vrt/qml
│       └── entrepreneurship_index/
│           ├── FIN_output_combined.vrt/qml
│           ├── entrepreneurship_index_masked_0.tif
│           └── entrepreneurship_index_0.tif.aux.xml
│
├── accessibility/                         # Accessibility Dimension (location-based services)
│   ├── access_to_education_and_training_facilities/
│   │   └── universities_location/
│   │       ├── universities_location_masked_0.tif
│   │       ├── ETF_output_combined.vrt/qml
│   │       └── universities_location_0.tif.aux.xml
│   ├── access_to_financial_facilities/
│   │   └── banks_location/
│   ├── access_to_health_facilities/
│   │   └── hospital_location/
│   ├── access_to_public_transport/
│   │   └── public_transport_location/
│   └── women_s_travel_patterns/           # Multi-indicator factor
│       ├── kindergartens_location/
│       │   ├── kindergartens_location_area_features_0.shp/dbf/shx/cpg
│       │   ├── kindergartens_location_masked_0.tif
│       │   ├── isochrones_area_0.gpkg
│       │   └── error.txt (if isochrone failed)
│       ├── primary_school_location/
│       ├── groceries_location/
│       ├── pharmacies_location/
│       └── green_space_location/
│
├── place_characterization/                # Place Characterization Dimension
│   ├── active_transport/                  # Active Transport Accessibility
│   ├── digital_inclusion/                 # Ookla broadband scoring
│   │   ├── digital_inclusion_combined.vrt/qml
│   │   └── digital_inclusion/
│   │       ├── digital_inclusion_masked_0.tif
│   │       ├── digital_inclusion_ookla_scored_0.tif.aux.xml
│   │       └── DIG_output_combined.vrt/qml
│   ├── education/                         # Education accessibility
│   ├── fcv/                               # Fragility, Conflict, Violence
│   ├── environmental_hazards/             # Multi-hazard environmental risk
│   │   ├── cyclone/
│   │   ├── drought/
│   │   ├── fire/
│   │   ├── flood/
│   │   └── landslide/
│   │       └── <hazard>_masked_0.tif, <hazard>_combined.vrt/qml
│   ├── safety_perception/                 # Night lights proxy for safety
│   └── water_sanitation/                  # Water/sanitation access
│
├── geoe3_score/                           # Final GeoE3 Analysis Score
│   ├── geoe3_combined_0.tif
│   ├── geoe3_combined.vrt/qml
│   └── ... (one per study area chunk)
│
├── geoe3_by_population_score/             # GeoE3 × Population (1-15 bivariate)
│   ├── geoe3_by_population_0.tif
│   ├── geoe3_by_population_combined.vrt/qml
│   └── ...
│
├── geoe3_score_ghsl_masked/               # GeoE3 masked to GHSL settlements
│   └── ... (same structure)
│
├── geoe3_score_by_population_ghsl_masked/ # GeoE3×Pop masked to opportunities
│   └── ... (same structure)
│
└── subnational_aggregation/               # Aggregated scores by admin boundary
    ├── subnational_geoe3_score.gpkg       # Attributes: fid, name, geoe3_score
    ├── subnational_geoe3_by_population.gpkg
    ├── subnational_*.qml                  # Styled GeoPackages
    └── ...
```

### 2.2 Raster Naming Conventions

**Indicator/Factor Output Files**:
- Pattern: `<indicator_id>_<area_index>.tif` (raw, unmasked)
  - Example: `entrepreneurship_index_0.tif` (area 0)
  - Value range: 0-5 float scale
- Pattern: `<indicator_id>_masked_<area_index>.tif` (masked to study area / GHSL)
  - Example: `entrepreneurship_index_masked_0.tif`
  - Masked by combined clip geometry

**Aggregated Rasters**:
- Pattern: `<factor_id>_aggregated_<area_index>.tif.aux.xml` (GDAL auxiliary metadata)
- Pattern: `<dimension_id>_aggregated_<area_index>.tif.aux.xml`

**VRT Virtual Rasters**:
- Pattern: `<name>_combined.vrt`
  - Example: `FIN_output_combined.vrt`, `Contextual_score_combined.vrt`
  - Merges multiple `<indicator>_masked_*.tif` files across study area chunks
  - GDAL Virtual Raster Format (XML-based)
  - Contains geotransform, SRS/CRS, and band configuration
  - NoData value: typically 255 or -9999.0

**QML Styling Files**:
- Pattern: `<name>_combined.qml`
- QGIS Layer Style File (XML-based)
- Discrete color ramp mapping (0-5 score classes)
- Color scheme: Red (0-1) → Orange → Yellow → Light Green → Dark Blue (4-5)
- Applied to both raster and styled vector layers

### 2.3 Sidecar Metadata Files

**XML Metadata Sidecars** (`*.tif.aux.xml`):
- Format: GDAL Auxiliary Metadata XML
- Purpose: Store raster statistics, histograms, metadata
- Contains: Metadata domain, histogram, statistics (min/max/mean/stddev)
- Example:
  ```xml
  <GDALMetadata>
    <Item name="STATISTICS_MINIMUM" sample="0" role="dataprovider">0</Item>
    <Item name="STATISTICS_MAXIMUM" sample="0" role="dataprovider">5</Item>
    <Item name="STATISTICS_MEAN" sample="0" role="dataprovider">2.345</Item>
  </GDALMetadata>
  ```

**error.txt Files**:
- Location: Factor/indicator subdirectories if processing failed
- Format: ISO timestamp + traceback
- Example: `/accessibility/women_s_travel_patterns/kindergartens_location/error.txt`
  - Records isochrone generation failures, API quota errors, geometry issues

---

## 3. Raster Output Specifications

All raster products follow consistent conventions for interoperability and styling.

### 3.1 Data Type & Value Range

| Metric | Specification |
|--------|---------------|
| **Data Type** | GDT_Float32 (32-bit IEEE floating point) |
| **Value Range** | 0.0 to 5.0 (WEE scoring scale) |
| **NoData Value** | 255.0 (default) or -9999.0 (depending on workflow) |
| **Cell Size** | 1000m (configurable via `analysis_cell_size_m` in model.json) |
| **Compression** | LZW (lossless) with TILED=YES for larger outputs |
| **Blocking** | Tiled (typically 512×512 or native size) |

### 3.2 Coordinate Reference System

- **Default**: EPSG:32735 (WGS 84 / UTM Zone 35S) for DRC
- **Auto-selection**: UTM zone calculated from study area centroid longitude
- **GeoTransform Format** (VRT example):
  ```xml
  <GeoTransform>1.8400000000000000e+05, 1.0000000000000000e+03, 0, 8.8950000000000000e+06, 0, -1.0000000000000000e+03</GeoTransform>
  ```
  - Origin: (184000.0, 8895000.0) meters (lower-left corner)
  - Pixel size: 1000m × 1000m

### 3.3 VRT Assembly Pattern

**Virtual Raster Format (VRT)**:
- XML-based wrapper referencing underlying GeoTIFF files
- Enables seamless multi-file mosaicking without data duplication
- Example structure:
  ```xml
  <VRTDataset rasterXSize="622" rasterYSize="384">
    <SRS>...</SRS>
    <GeoTransform>...</GeoTransform>
    <VRTRasterBand dataType="Float32" band="1">
      <NoDataValue>255</NoDataValue>
      <ComplexSource resampling="nearest">
        <SourceFilename relativeToVRT="1">entrepreneurship_index_masked_0.tif</SourceFilename>
        <SourceBand>1</SourceBand>
      </ComplexSource>
    </VRTRasterBand>
  </VRTDataset>
  ```

**Mosaic Strategy**:
- One VRT file per dimension/factor combining all study area chunks
- Uses relative paths (`relativeToVRT="1"`) for portability
- Supports dynamic extent updates as new areas are processed

### 3.4 QML Styling Specification

**Classification Method**: DISCRETE (step classification, not continuous)

**Class Structure** (Standard WEE 5-class scale):
| Class | Value | Label | RGB Color |
|-------|-------|-------|-----------|
| 1 | 0-1 | Very Low Enablement | #d7191c (Red) |
| 2 | 1-2 | Low Enablement | #fdae61 (Orange) |
| 3 | 2-3 | Moderately Enabling | #ffffbf (Yellow) |
| 4 | 3-4 | Enabling | #bce1b8 (Light Green) |
| 5 | 4-5 | Highly Enabling | #2c7bb6 (Blue) |

**Bivariate 15-class scale** (for GeoE3 × Population):
- 5 enablement classes × 3 population classes = 15 output classes
- Population classes: Low (Yellow), Medium (Orange), High (Dark Red)
- Each combination gets derived color blending

---

## 4. Final Products & Outputs

### 4.1 Raster Products

| Product | Location | Cell Values | Purpose | Used For |
|---------|----------|-------------|---------|----------|
| **Indicator Rasters** | `<dimension>/<factor>/<indicator>/<id>_masked_0.tif` | 0-5 | Individual SDI/OSM indicator scores | Factor aggregation |
| **Factor Rasters** | `<dimension>/<factor>/fac_<id>_masked_0.tif` | 0-5 | Weighted aggregation of factors | Dimension aggregation |
| **Dimension Rasters** | `<dimension>/dim_<id>_masked_0.tif` | 0-5 | Final dimension-level scores | Analysis aggregation |
| **GeoE3 Score** | `geoe3_score/geoe3_combined.vrt` | 0-5 | Final WEE score (0-5 scale) | Main analysis output |
| **GeoE3 × Population** | `geoe3_by_population_score/geoe3_by_population_combined.vrt` | 1-15 | Bivariate score combining enablement + population density | Population-weighted prioritization |
| **GeoE3 Masked (GHSL)** | `geoe3_score_ghsl_masked/geoe3_combined_masked.vrt` | 0-5 | GeoE3 masked to settled areas only | Opportunity-focused analysis |
| **GeoE3×Pop Masked** | `geoe3_score_by_population_ghsl_masked/geoe3_by_population_masked.vrt` | 1-15 | GeoE3×Pop masked to opportunities | Targeted intervention zones |
| **Opportunities Mask** | Grid column `opportunities_mask` (rasterized) | 0/1 | Binary mask of job opportunity zones (GHSL + contextual factors) | Masking all outputs |

### 4.2 Vector Products (GeoPackages)

| Product | Location | Geometry | Attributes | Purpose |
|---------|----------|----------|-----------|---------|
| **Study Area Grid** | `study_area/study_area.gpkg \| study_area_grid` | POLYGON | All 54 columns (indicators, factors, dimensions, aggregates) | Grid-first analysis foundation |
| **Subnational Aggregates** | `subnational_aggregation/subnational_geoe3_score.gpkg` | POLYGON | fid, name, geoe3_score (majority class per admin unit) | Administrative-level reporting |
| **Subnational Pop** | `subnational_aggregation/subnational_geoe3_by_population.gpkg` | POLYGON | fid, name, geoe3_pop_score (1-15 class) | Admin-level prioritization |
| **Settlements (GHSL)** | `study_area/study_area.gpkg \| ghsl_settlements` | MULTIPOLYGON | pixel_value (GHSL density) | Settlement masking |

### 4.3 Reports & Documentation

| Report | Location | Format | Contents |
|--------|----------|--------|----------|
| **Study Area Report** | `study_area_report.pdf` | PDF | Summary maps, statistics, metadata, legend, study area info |
| **Print Template** | `study_area_report.qpt` | QGIS QPT | QGIS print composition template for report generation |
| **Model State** | `model.json` | JSON | Full workflow status, indicator results, execution timestamps, error logs |
| **Error Log** | `error.txt` (if present) | Text | Python traceback if any workflow failed |
| **OSM Error Log** | `osm_download_error.txt` (if present) | Text | OSM Downloader errors (API quota, timeout, etc.) |

### 4.4 QGIS Layer Tree Structure

When layers are added to the QGIS project, they are organized in a hierarchical group structure:

```
GeoE3 (Root Group - Mutually Exclusive)
├── Study Area
│   ├── Boundaries
│   ├── Grid
│   └── GHSL Settlements
├── Contextual (Mutually Exclusive)
│   ├── EPLEX Score
│   ├── Workplace Discrimination
│   │   └── workplace_index (indicator)
│   ├── Regulatory Frameworks
│   │   └── pay_parenthood_index (indicator)
│   └── Financial Inclusion
│       └── entrepreneurship_index (indicator)
├── Accessibility (Mutually Exclusive)
│   ├── Access to Education
│   │   └── universities_location
│   ├── Access to Financial
│   │   └── banks_location
│   ├── Access to Health
│   │   └── hospital_location
│   ├── Access to Public Transport
│   │   └── public_transport_location
│   └── Women's Travel Patterns
│       ├── kindergartens_location
│       ├── primary_school_location
│       ├── groceries_location
│       ├── pharmacies_location
│       └── green_space_location
├── Place Characterization (Mutually Exclusive)
│   ├── Active Transport
│   ├── Digital Inclusion
│   ├── Education
│   ├── FCV
│   ├── Environmental Hazards
│   │   ├── Cyclone
│   │   ├── Drought
│   │   ├── Fire
│   │   ├── Flood
│   │   └── Landslide
│   ├── Safety Perception
│   └── Water & Sanitation
├── GeoE3 Score (Mutually Exclusive)
│   └── [GeoE3 final raster with WEE 5-class legend]
├── GeoE3 × Population (Mutually Exclusive)
│   └── [GeoE3×Pop bivariate raster with 15-class legend]
└── Subnational Aggregates (Mutually Exclusive)
    ├── GeoE3 Score by Admin Boundary
    └── GeoE3×Population by Admin Boundary
```

Each group is set to **mutually exclusive** mode to allow toggling between indicators/dimensions.

---

## 5. State Files & Configuration

### 5.1 model.json Structure

The `model.json` file serves as the complete workflow specification and status tracker. Key top-level attributes:

| Attribute | Type | Example | Purpose |
|-----------|------|---------|---------|
| `analysis_name` | string | "Women's Economic Empowerment - DRC" | Analysis title |
| `working_folder` | string | `/path/to/working/directory` | Base output directory |
| `analysis_cell_size_m` | float | 1000.0 | Grid cell size in meters |
| `analysis_scale` | string | "national" | Analysis geographic scope |
| `guid` | UUID | "4f9f2fd4-a7c7-4c76-a84e-3588fb34463d" | Unique analysis identifier |
| `qgis_project_path` | string | `/path/to/project.qgz` | QGIS project file location |
| `road_network_layer_path` | string | `study_area/active_transport_network.gpkg` | Isochrone routing network |
| `dimensions` | array | [...] | Model hierarchy (see below) |

**Dimension/Factor/Indicator Nested Structure**:
```json
{
  "dimensions": [
    {
      "name": "Contextual",
      "guid": "487d73b2-3834-49f2-b531-156fceda811c",
      "factors": [
        {
          "name": "EPLEX Score",
          "guid": "9c87c164-938f-4c43-b3da-2daf7e9d739c",
          "id": "eplex",
          "output_filename": "eplex_score",
          "indicators": [
            {
              "indicator": "Employment Protection Legislation Index",
              "id": "eplex_score_indicator",
              "output_filename": "EPLEX_output",
              "result": "Workflow Completed",
              "result_file": "/path/to/EPLEX_output_combined.vrt",
              "execution_start_time": "2026-07-09T11:15:00.862371",
              "execution_end_time": "2026-07-09T11:15:02.359760",
              "error": null
            }
          ]
        }
      ]
    }
  ]
}
```

**Indicator Status Attributes**:
- `result` - "Workflow Completed" | error message
- `result_file` - Path to final VRT/raster output
- `error_file` - Path to detailed error log (if failed)
- `execution_start_time` - ISO 8601 timestamp
- `execution_end_time` - ISO 8601 timestamp

### 5.2 QGIS Project Settings (QSettings)

GeoE3 configuration stored in QGIS QSettings registry (profile-specific):
- Location: `~/.local/share/QGIS/QGIS3/profiles/GEOE3/`
- Keys stored: working directories, recent analyses, layer visibility preferences
- Managed by: `geest/core/settings.py`

---

## 6. Backup & Corruption Recovery

### 6.1 Automatic Backups

When `study_area.gpkg` is detected as corrupted:
- Backup created: `study_area.gpkg.corrupt-YYYYMMDD.bak`
- WAL journal files: `study_area.gpkg.corrupt-YYYYMMDD.bak-shm`, `study_area.gpkg.corrupt-YYYYMMDD.bak-wal`
- Recovery performed: PRAGMA wal_checkpoint(TRUNCATE) forces WAL flush

### 6.2 Corruption Detection

Triggered by:
1. OGR layer open failures
2. SQLite "database is locked" after retries
3. Feature insert/update failures
4. CRS metadata inconsistencies

---

## 7. Processing Workflows & Column Population

### 7.1 Grid Column Value Sources

| Column(s) | Source Workflow | Input Data | Write Method |
|-----------|-----------------|-----------|--------------|
| `eplex_score_indicator`, `workplace_index`, `pay_parenthood_index` | `ContextualIndexScoreWorkflow` | Index scores from model.json | `write_uniform_value_to_grid()` |
| `entrepreneurship_index` | `IndexScoreWorkflow` | Contextual index, weighted | `write_uniform_value_to_grid()` |
| `*_location` (8 indicators) | `GeoE3PointPerCellWorkflow` | OSM point buffers | `write_point_count_to_grid()` |
| `active_transport_network` | Isochrone analysis | Road network routing | `write_raster_values_to_grid()` |
| `street_lights` | Nighttime lights | NOAA nighttime radiance | `write_raster_values_to_grid()` |
| `fcv`, `education`, `digital_inclusion` | Contextual processors | External indices/Ookla data | `write_uniform_value_to_grid()` or `write_raster_values_to_grid()` |
| `fac_*` (factor columns) | `FactorAggregationWorkflow` | Indicator columns + weights | `write_aggregation_to_grid()` |
| `dim_*` (dimension columns) | `DimensionAggregationWorkflow` | Factor columns + weights | `write_aggregation_to_grid()` |
| `geoe3` | `AnalysisAggregationWorkflow` | Dimension columns + weights | `write_aggregation_to_grid()` |
| `geoe3_by_population` | `WEEByPopulationScoreProcessingTask` | `geoe3` raster + WorldPop | Rasterized from grid then resampled |
| `geoe3_masked`, `geoe3_by_population_masked` | Mask application | GHSL/opportunities mask | SQL UPDATE with spatial filter |

### 7.2 Aggregation Methods

**Weighted Aggregation (SQL)**:
```sql
UPDATE study_area_grid
SET target_column = (
  w1 * COALESCE(source_col_1, 0) +
  w2 * COALESCE(source_col_2, 0) +
  ...
  wN * COALESCE(source_col_N, 0)
)
```

**Raster to Grid Sampling**:
- Centroid sampling: Get cell centroid, lookup raster pixel value
- Nodata handling: Skip nodata values (pixel_value == -9999.0)
- Batch updates: 500-cell SQL CASE statements for efficiency

---

## 8. Data Integrity & Constraints

### 8.1 Grid Cell Constraints

- **Non-overlapping**: Cells generated via regular grid subdivision
- **Clipped to boundary**: All cells intersect study_area_polygons geometry
- **Unique grid_id**: Sequential numbering per area
- **NULL handling**: Grid columns NULLed before population, then populated per workflow

### 8.2 Raster Constraints

- **Alignment**: All rasters aligned to same geotransform (same origin, cell size, CRS)
- **NoData consistency**: Pixels outside study area = NoData value
- **Range validation**: Output scores clipped to 0-5 range (or 1-15 for bivariate)
- **CRS matching**: All rasters in same UTM zone as vector grid

---

## 9. Performance & Scale Characteristics

### 9.1 Typical Processing Times (DRC Example)

| Step | Duration | Notes |
|------|----------|-------|
| Study area geometry creation | < 1 min | Shapefile to GeoPackage |
| Grid generation (1000m cells) | 5-15 min | Parallelized via GridChunkerTask |
| GHSL data download & processing | 5-10 min | Depends on internet speed |
| OSM data download | 20-40 min | API quota, network latency |
| Single indicator processing | 1-5 min | Depends on algorithm complexity |
| All indicators (18+) | 1-2 hours | Sequential; Ookla/nighttime lights slow |
| Factor aggregation (per factor) | < 1 sec | Pure SQL operation |
| Dimension aggregation (3 total) | 3-5 min | Includes rasterization |
| Analysis aggregation (WEE score) | 2-3 min | Rasterization + VRT assembly |
| Population weighting | 15-20 min | Resampling via gdalwarp -r sum |
| Subnational aggregation | 10-15 min | Zonal statistics per boundary |
| Study area report generation | 2-3 min | PDF layout + rendering |

### 9.2 File Sizes (DRC Example)

| File Type | Count | Total Size | Example |
|-----------|-------|------------|---------|
| study_area.gpkg | 1 | 24 MB | Grid + metadata |
| Indicator TIFs | 18 | 500 KB each | 9 MB total |
| Factor/Dimension TIFs | 19 | 600 KB each | 11 MB total |
| Final analysis TIFs | 4 | 900 KB each | 3.6 MB total |
| VRTs (combined) | ~8 | < 50 KB each | 400 KB total |
| QML stylesheets | ~25 | 3-4 KB each | 100 KB total |
| XML sidecars | ~50+ | 200-400 bytes each | 20 KB total |
| Active transport network | 1 | 18 MB GeoPackage + 175 MB XML | 193 MB |
| OSM layers | 9 | 100-300 KB each GPKG + XML | ~9 MB GPKG, ~10 MB XML |
| Report PDF + QPT | 2 | 7.3 MB + 580 KB | 7.9 MB total |

**Total working directory**: ~280-300 MB for national-scale DRC analysis

---

## 10. API & Extension Points

### 10.1 Key Module Exports

**grid_column_utils.py** (Primary Data Writing API):
- `add_model_columns_to_grid()` - Bulk column creation from model.json
- `write_raster_values_to_grid()` - Sample raster → grid column
- `write_uniform_value_to_grid()` - Write constant value to area
- `write_point_count_to_grid()` - Count points per cell
- `write_joined_values_to_grid()` - SQL join from external source
- `write_aggregation_to_grid()` - Weighted combination of columns
- `write_buffer_values_to_grid()` - Spatial join with buffer features
- `write_spatial_join_to_grid()` - Generic spatial join with aggregation
- `rasterize_grid_column()` - Convert grid column to raster
- `get_grid_column_statistics()` - Compute min/max/mean per column
- `clear_grid_column()` - NULL all values in column

**Workflow Base Classes**:
- `AggregationWorkflowBase` - Factor/dimension/analysis aggregation
- `ContextualIndexScoreWorkflow` - Fixed index scores
- `IndexScoreWithOoklaWorkflow` - Broadband integration
- `GeoE3PointPerCellWorkflow` - OSM point-based indicators

---

## 11. Error Handling & Diagnostics

### 11.1 Common Error Scenarios

| Error | Cause | Recovery |
|-------|-------|----------|
| "database is locked" | Multiple writers, Windows file locking | Automatic retry with exponential backoff (3×, 200ms delay) |
| "Column 'X' not found" | Column not pre-created (Windows race condition) | Lazy creation via `_ensure_column_exists()` on-demand |
| "OSM API quota exceeded" | Too many requests to Overpass API | Logged to `osm_download_error.txt`, manual retry later |
| "Isochrone failed" | No road network coverage for location | Logged to `<factor>/<indicator>/error.txt`, skipped |
| "GHSL data missing" | No settlement data for area | `intersects_ghsl=0` flag set, GeoE3 unmasked |
| "GeoPackage corrupt" | Interrupted write or file system error | Backup created, WAL recovery attempted, new file created |

### 11.2 Debugging Outputs

- **Log messages**: `log_message()` with tags "GeoE3", timestamp, level (Info/Warning/Critical)
- **Stacktraces**: Full Python traceback in error files when workflows fail
- **Model.json status**: `result` and `error` attributes on each indicator

---

## Summary Tables

### Study Area GeoPackage Tables

| Table | Type | Rows | Purpose | Key Field |
|-------|------|------|---------|-----------|
| study_area_bbox | Vector | 1 | Overall bounding box | fid |
| study_area_bboxes | Vector | N | Per-area bounding boxes | fid, area_name |
| study_area_polygons | Vector | N | Study area boundaries | fid, area_name |
| study_area_clip_polygons | Vector | N | Clipped geometries (data extent) | fid, area_name |
| study_area_grid | Vector | 1000s | Grid cells + all attributes | fid, grid_id, area_name |
| chunks | Vector | 10-100 | Parallelization chunks | fid, index |
| ghsl_settlements | Vector | 10s-1000s | Settlement polygons | fid |
| study_area_creation_status | Table | N | Processing metadata | fid, area_name |

### Final Output Products

| Category | Product | Type | Values | Location |
|----------|---------|------|--------|----------|
| **Grid** | Study area grid | Vector (GeoPackage) | 54 columns | study_area/study_area.gpkg |
| **Rasters** | Indicator layers | Raster (GeoTIFF + VRT) | 0-5 | dimension/factor/indicator/ |
| **Rasters** | Factor layers | Raster (GeoTIFF + VRT) | 0-5 | dimension/factor/ |
| **Rasters** | Dimension layers | Raster (GeoTIFF + VRT) | 0-5 | dimension/ |
| **Rasters** | GeoE3 score | Raster (GeoTIFF + VRT) | 0-5 | geoe3_score/ |
| **Rasters** | GeoE3×Pop | Raster (GeoTIFF + VRT) | 1-15 | geoe3_by_population_score/ |
| **Rasters** | Masked variants | Raster (GeoTIFF + VRT) | 0-5 or 1-15 | geoe3_*_ghsl_masked/ |
| **Vector** | Admin aggregates | GeoPackage | Per-boundary stats | subnational_aggregation/ |
| **Report** | Study area report | PDF | Map + stats | study_area_report.pdf |

---

**Document Version**: 1.0
**Date**: 2026-07-13
**GeoE3 Build**: Plugin version in /geest/metadata.txt
**Specification Authority**: Tim Sutton (Kartoza)
