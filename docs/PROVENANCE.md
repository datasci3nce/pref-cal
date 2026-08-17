# Provenance and immutable evidence

The GitHub release incorporates the original `pref-cal-v1.4-nvidia-20260815` source package and the two archived result packages used in the report.

| Artifact | Status | SHA-256 |
| --- | --- | --- |
| GPT-OSS raw log | Confirmatory, prospectively stopped | `41831de58ebce32a1252bf8aabde1205e977969a0896c7b97ca78c1afac323ab` |
| GPT-OSS design file | Frozen | `9d96c6ace66654b37f9573756bb734f1043686c4bed84e55499f65686c4af856` |
| Llama raw log | Interrupted, exploratory only | `30dc5a3b4ed5e155b9bc012852efa99df33068ca33ac61d6ebea65dcc919f84c` |
| Llama design file | Frozen | `63b3a15baa6b82cfc5fc192283f5bb67654b8b3c39caab24a2ab4e822ffe18f6` |

The design hashes embedded inside the experiment artifacts are:

- GPT-OSS: `312616be206bc8e1b1bc921014632242aac2c2a733680aba2afc4f3e4f88ea5b`
- Llama: `3d0dc352ddc52025f627bfd3067c5eb51ebe8a390312bfcf96ab01d5d81a094a`

The embedded design hash is a canonical hash of the scientific design object; the file hash is the SHA-256 of its serialized JSON bytes. They answer different integrity questions and should not be expected to match.

The top-level `MANIFEST.sha256` fingerprints the rest of the repository. It excludes itself so it can be regenerated with:

```bash
find . -type f ! -path './.git/*' ! -name MANIFEST.sha256 -print0 \
  | sort -z \
  | xargs -0 sha256sum > MANIFEST.sha256
```

Raw JSONL logs are canonical experimental records. Reformatting them or normalizing line endings changes their hashes.

## Report synchronization — 2026-08-17

The public report and its editable source were synchronized in this release after the final related-work and claim-contract pass.

- Report PDF SHA-256: `f3abd6314f6f5f76d0e7290ba368a496bd09d02adc55379976ad31aa3fcffdac`
- LaTeX source SHA-256: `d00849d1f5df455cd6cb79eac61254ea20feeb03025f8b1815879c07629dd911`
- Bibliography SHA-256: `a1d2ec26d91021183c4c1a9d1a5aa43216105448adaecebcbcf179ee9e25864c`

The LaTeX source is configured for XeLaTeX + BibTeX and intentionally omits `microtype` to avoid TU/OpenType protrusion warnings seen in some local TeX installations. The compiled PDF resolves all bibliography citations; remaining Computer Modern math design-size substitutions are non-fatal font warnings.

`CLAIM_CONTRACT.json` is a machine-readable summary of the inference boundary. `scripts/verify_release.py` checks its frozen thresholds and transport dependency against the GPT-OSS configuration and archived prospective stop.
