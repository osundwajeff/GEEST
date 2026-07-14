# GeoE3 — Software Requirements Specification

Reverse-engineered SRS for the GeoE3 QGIS plugin, produced in the Kartoza
document system.

## Deliverables

- `dist/GeoE3_SRS_v1.0.0.docx` — the Word document (built on the Kartoza
  Document Template: branded cover, headers/footers, house table and callout
  styles).
- `dist/GeoE3_SRS_v1.0.0.pdf` — PDF generated from the Word document.
- `diagrams/*.svg` — every UML diagram as an individual SVG (PlantUML sources
  alongside as `*.puml`; `*.png` renders are embedded in the document).

## Layout

| Path | Purpose |
|------|---------|
| `GeoE3_SRS.md` | The SRS content (single source of truth for the text). |
| `generated/model-catalogue.md` | Chapter 8, generated from `geest/resources/model.json` on every build (do not edit by hand). |
| `diagrams/` | PlantUML sources + SVG/PNG renders, `kartoza.iuml` brand skin. Figures 19–22 (model trees) and 23 (indicator × processor matrix) are generated. |
| `assets/` | Generated cover page and brand artwork extracts. |
| `scripts/build_docx.py` | Writes the markdown directly into the Kartoza Word template (python-docx — no pandoc), harvesting the template's own exemplar formatting. Supports `<!-- include: … -->` and `<!-- pagebreak -->` markers. |
| `scripts/gen_model_catalogue.py` | Generates the model catalogue chapter, the per-dimension WBS diagrams and the indicator × processor matrix (SVG + PNG from one geometry). |
| `notes/` | Reverse-engineering research notes the SRS was synthesised from. |
| `build.sh` | One-shot build: catalogue → diagrams → docx → pdf (brand fonts provisioned via a throwaway fontconfig). |

## Building

```bash
nix develop         # provides plantuml, python-docx, pillow, libreoffice, lato
./srs/build.sh
```

The Kartoza brand templates are expected in `srs-gitignore/Kartoza_BrandTemplates_v1.0.0/`
(not committed — part of the brand pack).

---

Made with 💗 by [Kartoza](https://kartoza.com) · [Donate!](https://github.com/sponsors/kartoza) · [GitHub](https://github.com/worldbank/GeoE3)
