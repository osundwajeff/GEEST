# 8. Shipped model catalogue

This chapter is generated from `geest/resources/model.json` at build time and enumerates every node of the shipped analysis model: each dimension and each factor has its own page, every indicator is described with its defaults, and a matrix maps each indicator to the processors (chapter 6) that can run it. The shipped model contains **3 dimensions**, **16 factors** and **24 indicators**. All indicators ship in the `Do Not Use` state — the analyst activates exactly one processor per indicator in the data-source dialog (except the EPLEX indicator, which is pre-set to `use_eplex_score`).

![Figure 17 — The shipped analysis model — three weighted dimensions decompose into sixteen factors; the indicator counts show where the model is broad (women's travel patterns, environmental hazards) versus single-indicator.](diagrams/fig19-model-overview.png)

| Dimension | Default weight | Factors | Indicators |
|-----------|----------------|---------|------------|
| Contextual | 0.1 | 4 | 4 |
| Accessibility | 0.45 | 5 | 9 |
| Place Characterization | 0.45 | 7 | 11 |

<!-- pagebreak -->

## 8.1 Indicator × processor matrix

Each indicator declares, through its `use_*` flags, which of the seventeen processor types can compute it. The matrix below is the complete capability map: rows are the shipped indicators grouped by dimension, columns are the processors grouped into the families of chapter 6. Where several processors are available for one indicator (for example street lights, which can be computed from point buffers, classified polygons, a raster, or a fixed index score), the choice is made per indicator in the data-source dialog and depends on which input data exist for the study area.

![Figure 18 — Indicator × processor capability matrix — every dot is a valid indicator/processor pairing declared in model.json; the families along the bottom mirror the processor reference sections (§6.1–§6.6).](diagrams/fig23-indicator-processor-matrix.png)

The same matrix as a reference table, using the processor section numbers:

| Indicator | Available processors (§) |
|-----------|--------------------------|
| EPLEX score | EPLEX score (§6.1.3) |
| WBL Workplace Index | Contextual index (§6.1.2) |
| WBL Pay & Parenthood Index | Contextual index (§6.1.2) |
| WBL Entrepreneurship Index | Contextual index (§6.1.2) |
| Kindergartens / childcare | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Primary schools | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Groceries | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Pharmacies | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Green spaces | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Public transport stops | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Hospitals & clinics | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Universities & tech schools | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Banks & financial facilities | Multi-buffer / isochrone (§6.3.2–6.3.3) |
| Active transport network | Polylines per cell (§6.2.1) · OSM transport (§6.2.3) |
| Street / night-time lights | Index score (§6.1.1) · Street lights (§6.3.4) · Night-time lights (§6.4.2) · Classify safety (§6.5.1) |
| ACLED conflict events | Single buffer (§6.3.1) · ACLED CSV (§6.6.1) |
| Labour force with degrees | Index score (§6.1.1) · Index + GHSL (§6.1.4) · Polygons per cell (§6.2.2) · Classify polygons (§6.5.1) |
| Internet use (% population) | Index + Ookla (§6.1.5) · Classify polygons (§6.5.1) |
| Fire hazard | Hazard raster (§6.4.1) |
| Flood hazard | Hazard raster (§6.4.1) |
| Landslide hazard | Hazard raster (§6.4.1) |
| Tropical cyclone hazard | Hazard raster (§6.4.1) |
| Drought hazard | Hazard raster (§6.4.1) |
| Water & sanitation facilities | Single buffer (§6.3.1) |

<!-- pagebreak -->

## 8.2 The Contextual dimension

The Contextual Dimension refers to the laws and policies that shape workplace gender discrimination, financial autonomy, and overall gender empowerment. Although this dimension may vary between countries due to differences in legal frameworks, it remains consistent within a single country, as national policies and regulations are typically applied uniformly across countries.

| Property | Value |
|---|---|
| Dimension ID | `contextual` |
| Default analysis weight | 0.1 |
| Factors | 4 |
| Indicators | 4 |
| Output raster | `Contextual_score.tif` |

![Figure 19 — The Contextual dimension — factors with their default weights and their indicators, as shipped in model.json.](diagrams/fig20-dim-contextual.png)

<!-- pagebreak -->

### 8.2.1 EPLEX Score

The Employment Protection Legislation Index (EPLEX) measures the strictness and coverage of laws protecting workers from dismissal, covering areas like fixed-term contracts, probationary periods, unfair dismissal grounds, and severance pay. This indicator is used when women-specific contextual factors are not being analyzed.

| Property | Value |
|---|---|
| Factor ID | `eplex` |
| Default weight in Contextual | 1 |
| Indicators | 1 |
| Output raster | `eplex_score.tif` |

**Employment Protection Legislation Index** (`eplex_score_indicator`)

EPLEX score representing employment protection legislation strength

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Pre-configured mode | `use_eplex_score` |
| Available processors | EPLEX score (§6.1.3) |

<!-- pagebreak -->

### 8.2.2 Workplace Discrimination

Workplace Discrimination involves laws that address gender biases and stereotypes that hinder women's career advancement, especially in male-dominated fields.

| Property | Value |
|---|---|
| Factor ID | `workplace_discrimination` |
| Default weight in Contextual | 0.33 |
| Indicators | 1 |
| Output raster | `workplace_discrimination.tif` |

**WBL 2024 Workplace Index Score** (`Workplace_Index`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Contextual index (§6.1.2) |

<!-- pagebreak -->

### 8.2.3 Regulatory Frameworks

Regulatory Frameworks pertain to laws and policies that protect women’s employment rights, such as childcare support and parental leave, influencing their workforce participation

| Property | Value |
|---|---|
| Factor ID | `regulatory_frameworks` |
| Default weight in Contextual | 0.33 |
| Indicators | 1 |
| Output raster | `regulatory_frameworks.tif` |

**Average value of WBL Pay Score and Parenthood Index Score** (`Pay_Parenthood_Index`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Contextual index (§6.1.2) |

<!-- pagebreak -->

### 8.2.4 Financial Inclusion

Financial Inclusion involves laws concerning women’s access to financial resources like loans and credit, which is crucial for starting businesses and investing in economic opportunities.

| Property | Value |
|---|---|
| Factor ID | `financial_inclusion` |
| Default weight in Contextual | 0.33 |
| Indicators | 1 |
| Output raster | `financial_inclusion.tif` |

**WBL 2024 Entrepreneurship Index Score** (`Entrepreneurship_Index`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Contextual index (§6.1.2) |

<!-- pagebreak -->

## 8.3 The Accessibility dimension

The Accessibility Dimension evaluates daily mobility by examining access to essential services. Levels of enablement for work access in this dimension are determined by service areas, which represent the geographic zones that facilities like childcare, supermarkets, universities, banks, and clinics can serve based on proximity. The nearer these facilities are to where people live, the more supportive and enabling the environment becomes for their participation in the workforce.

| Property | Value |
|---|---|
| Dimension ID | `accessibility` |
| Default analysis weight | 0.45 |
| Factors | 5 |
| Indicators | 9 |
| Output raster | `Accessibility_score.tif` |

![Figure 20 — The Accessibility dimension — factors with their default weights and their indicators, as shipped in model.json.](diagrams/fig21-dim-accessibility.png)

<!-- pagebreak -->

### 8.3.1 Women's Travel Patterns

Women’s Travel Patterns (WTP) refer to the unique travel behaviors of women, often involving multiple stops for household or caregiving tasks, making proximity to essential services like markets, supermarkets, childcare centers, primary schools, pharmacies, and green spaces crucial.

| Property | Value |
|---|---|
| Factor ID | `women_s_travel_patterns` |
| Default weight in Accessibility | 0.2 |
| Indicators | 5 |
| Output raster | `women_s_travel_patterns.tif` |

**Location of kindergartens/childcare** (`Kindergartens_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 400, 800, 1200, 1500, 2000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

**Location of primary schools** (`Primary_School_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 400, 800, 1200, 1500, 2000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

**Location of groceries** (`Groceries_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 400, 800, 1200, 1500, 2000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

**Location of pharmacies** (`Pharmacies_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 400, 800, 1200, 1500, 2000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

**Location of green spaces** (`Green_Space_location`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 400, 800, 1200, 1500, 2000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

<!-- pagebreak -->

### 8.3.2 Access to Public Transport

Access to Public Transport focuses on the availability and proximity of public transportation stops, especially those who rely on buses, trains, or trams to access jobs, education, and essential services.

| Property | Value |
|---|---|
| Factor ID | `access_to_public_transport` |
| Default weight in Accessibility | 0.2 |
| Indicators | 1 |
| Output raster | `access_to_public_transport.tif` |

**Location of public transportation stops, including maritime** (`Public_Transport_location`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 250, 500, 750, 1000, 1500 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

<!-- pagebreak -->

### 8.3.3 Access to Health Facilities

Access to Health Facilities evaluates how easily women can reach healthcare services in terms of distance, impacting their well-being and ability to participate in the workforce.

| Property | Value |
|---|---|
| Factor ID | `access_to_health_facilities` |
| Default weight in Accessibility | 0.2 |
| Indicators | 1 |
| Output raster | `access_to_health_facilities.tif` |

**Location of hospitals and clinics** (`Hospital_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 2000, 4000, 6000, 8000, 10000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

<!-- pagebreak -->

### 8.3.4 Access to Education and Training Facilities

Access to Education and Training Facilities assesses the proximity to higher education institutions and training centers, influencing the ability to gain necessary qualifications.

| Property | Value |
|---|---|
| Factor ID | `access_to_education_and_training_facilities` |
| Default weight in Accessibility | 0.2 |
| Indicators | 1 |
| Output raster | `access_to_education_and_training_facilities.tif` |

**Location of universities and technical schools** (`Universities_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 2000, 4000, 6000, 8000, 10000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

<!-- pagebreak -->

### 8.3.5 Access to Financial Facilities

Access to Financial Facilities focuses on the proximity of banks and financial institutions, which is essential for economic empowerment and the ability to access credit.

| Property | Value |
|---|---|
| Factor ID | `access_to_financial_facilities` |
| Default weight in Accessibility | 0.2 |
| Indicators | 1 |
| Output raster | `access_to_financial_facilities.tif` |

**Location of Banks and other FF** (`Banks_Location`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default multi-buffer bands | 500, 1000, 1500, 2000, 3000 m |
| Available processors | Multi-buffer / isochrone (§6.3.2–6.3.3) |

<!-- pagebreak -->

## 8.4 The Place Characterization dimension

The Place-Characterization Dimension refers to the social, environmental, and infrastructural attributes of geographical locations, such as walkability, safety, and vulnerability to natural hazards. Unlike the Accessibility Dimension, these factors do not involve mobility but focus on the inherent characteristics of a place that influence the ability to participate in the workforce.

| Property | Value |
|---|---|
| Dimension ID | `place_characterization` |
| Default analysis weight | 0.45 |
| Factors | 7 |
| Indicators | 11 |
| Output raster | `Place_score.tif` |

![Figure 21 — The Place Characterization dimension — factors with their default weights and their indicators, as shipped in model.json.](diagrams/fig22-dim-place-characterization.png)

<!-- pagebreak -->

### 8.4.1 Active Transport

Active Transport refers to the presence of walkable infrastructure and is based on different road types that are assessed with respect to the possibility of walking and/ or cycling.

| Property | Value |
|---|---|
| Factor ID | `active_transport` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 1 |
| Output raster | `AT_output.tif` |

**Active Transport Network (walkable and cyclable infrastructure)** (`Active_Transport_Network`)

Walkable environments and cycling infrastructure using unified OSM highway and cycleway categories. Uses best score methodology when multiple road types exist in a cell.

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Polylines per cell (§6.2.1) · OSM transport (§6.2.3) |

<!-- pagebreak -->

### 8.4.2 Safety Perception

Safety addresses the perceived security of public spaces, evaluated through the availability of adequate lighting, which affects women’s ability to move freely, seek employment, and access essential services.

| Property | Value |
|---|---|
| Factor ID | `safety_perception` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 1 |
| Output raster | `safety_perception.tif` |

**Street lights/Night time lights** (`Street_Lights`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Index score (§6.1.1) · Street lights (§6.3.4) · Night-time lights (§6.4.2) · Classify safety (§6.5.1) |

<!-- pagebreak -->

### 8.4.3 FCV

Fragility, Conflict, and Violence (FCV) considers the frequency of events related to political unrest, conflict, and violence in a region, which can increase vulnerability and limit access to employment and essential services.

| Property | Value |
|---|---|
| Factor ID | `fcv` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 1 |
| Output raster | `fcv.tif` |

**ACLED data (Violence Estimated Events)** (`FCV`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Default single-buffer distance | 5000 m |
| Available processors | Single buffer (§6.3.1) · ACLED CSV (§6.6.1) |

<!-- pagebreak -->

### 8.4.4 Education

Education refers to the proportion of people in a region who have attained higher education, particularly in the specific field of analysis, serving as an indicator of the general education level and workforce qualifications in that sector.

| Property | Value |
|---|---|
| Factor ID | `education` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 1 |
| Output raster | `education.tif` |

**Percentage of the labor force with university degrees** (`Education`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Index score (§6.1.1) · Index + GHSL (§6.1.4) · Polygons per cell (§6.2.2) · Classify polygons (§6.5.1) |

<!-- pagebreak -->

### 8.4.5 Digital Inclusion

Digital Inclusion assesses the presence of digital infrastructure in a specific location, which is essential for people to pursue job opportunities, access training and education opportunities, and use financial services. Each polygon is assigned a normalized value on a scale from 0 to 5 based on the proportion of people with internet access, masked using the Ookla dataset where internet coverage has been mapped.

| Property | Value |
|---|---|
| Factor ID | `digital_inclusion` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 1 |
| Output raster | `digital_inclusion.tif` |

**Individuals using the Internet (% of population)** (`Digital_Inclusion`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| Available processors | Index + Ookla (§6.1.5) · Classify polygons (§6.5.1) |

<!-- pagebreak -->

### 8.4.6 Environmental Hazards

Environmental Hazards relate to the impact of environmental risks, such as floods, droughts, landslides, fires, and extreme weather events, which can disrupt job stability.

| Property | Value |
|---|---|
| Factor ID | `environmental_hazards` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 5 |
| Output raster | `environmental_hazards.tif` |

**Fire Hazards** (`Fire`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| Available processors | Hazard raster (§6.4.1) |

**Flood Hazards** (`Flood`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| Available processors | Hazard raster (§6.4.1) |

**Landslide** (`Landslide`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| Available processors | Hazard raster (§6.4.1) |

**Tropical Cyclone** (`Cyclone`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| Available processors | Hazard raster (§6.4.1) |

**Drought** (`Drought`)

| Property | Value |
|---|---|
| Default factor weighting | 0.2 |
| Available processors | Hazard raster (§6.4.1) |

<!-- pagebreak -->

### 8.4.7 Water sanitation

This factor captures access to water and sanitation indirectly, using the spatial distribution of facilities whose operation depends on reliable water supply and sanitation services. The presence of these points of interest suggests the existence of minimum water and sanitation infrastructure necessary for service delivery, even where direct household level data are unavailable.

| Property | Value |
|---|---|
| Factor ID | `water_sanitation` |
| Default weight in Place Characterization | 0.14 |
| Indicators | 1 |
| Output raster | `water_sanitation.tif` |

**Location of facilities that need water supply and sanitation services to function** (`Water_Sanitation`)

| Property | Value |
|---|---|
| Default factor weighting | 1 |
| OSM auto-download | Yes — one-click Overpass acquisition |
| Default single-buffer distance | 3000 m |
| Available processors | Single buffer (§6.3.1) |
