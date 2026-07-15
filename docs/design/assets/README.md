# Asset Standards

## Place
- Drop images, diagrams, and any non-text artefact under `docs/design/assets/`.
- Keep filenames kebab-case with an extension: `arch-overview.png`,
  `class-diagram.svg`.

## Format
| Asset type | Preferred format | Rationale |
|:-----------|:-----------------|:----------|
| Diagrams | SVG | Vector; scales without loss. |
| Screenshots | PNG | Lossless; preserves text. |
| Photos | PNG | Lossless. Avoid JPG. |
| Plots (data) | PDF + source CSV in `configs/` | Reproducible from data. |

## Versioning
- When updating an asset, append a date suffix and link from the relevant
  ADR (e.g. `class-diagram-2026-07-15.svg`).
