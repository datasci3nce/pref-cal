# PREF-CAL v1.4 public-release maintenance pass — 2026-08-17

This pass changes release engineering and report synchronization, not the frozen experimental evidence or scientific thresholds.

## Updated

- synchronized the report PDF, LaTeX source, and bibliography;
- added the final related-work discussion of claim contracts, crossed symmetrization, preference-to-behavior transport, and the utility–behavior gap;
- fixed the report wording `unique, valid parses` to `unique and parsed successfully`;
- configured the report source for XeLaTeX + BibTeX and removed `microtype` to avoid TU/OpenType protrusion warnings on some local TeX installations;
- added `CLAIM_CONTRACT.json` and verifier checks tying it to the frozen source gates;
- added report-number snapshot checking with `scripts/reproduce_report_numbers.py --check`;
- added portable manifest generation/checking with `scripts/regenerate_manifest.py`;
- expanded CI to check manifest integrity, the evidence reconstruction, report-number snapshot, release regressions, and the full test suite;
- added `scripts/build_github_release.py` for the current public archive;
- marked `scripts/build_release.py` as the historical 2026-08-15 source-package builder;
- improved `CITATION.cff` and documented current licensing status;
- aligned `requirements.txt` dependency ranges with `pyproject.toml`.

## Unchanged scientific record

The frozen designs, raw provider logs, prospective stop, GPT-OSS `7/48` semantic/physical consistency, `119/160 = 74.375%` best-case bound, and matched GPT-OSS/Llama 16-prompt fingerprints are unchanged.

### CI integrity hardening

The byte-level manifest is now checked against the pristine Git checkout before
package installation or tests.  Manifest generation ignores transient build and
cache metadata (including `*.egg-info`), reports the paths responsible for a
stale-manifest failure, and `.gitattributes` pins release text files to LF line
endings for deterministic cross-platform Git checkouts.  CI uses a regular local
package install rather than editable mode.
