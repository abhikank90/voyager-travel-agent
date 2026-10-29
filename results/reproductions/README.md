# Independent reproductions

Each folder records a benchmark reproduction run by someone other than the maintainer, on
their own machine, with the raw logs and a short report.

Folder name: `YYYY-MM-DD-<github-handle>-<version>-<quick|full>/`, containing `REPORT.md` and
the run logs.

| Date | Reproducer | Version | Command | Result |
|---|---|---|---|---|
| 2026-10-07 | @KalyanMatta-SDE | v1.3 | `reproduce.sh --quick` ×2 | 10/12, 10/12 (q0 variance, #23) |
| 2026-10-28 | @KalyanMatta-SDE | v1.4.0 | `reproduce.sh --quick` ×2 | 12/12, 12/12 |

To add one, follow the steps in CONTRIBUTING.md.
