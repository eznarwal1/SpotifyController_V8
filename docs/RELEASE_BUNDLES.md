# Full-File Release Bundles

Future controller updates should use full-file replacement bundles instead of
source-block/regex patching.

## Bundle format

```text
V9_XX_feature/
    manifest.json
    changed_files/
        companion/
        chrome_extension/
        CrowPanel Firmware/
```

`manifest.json` records:
- release name
- exact required base Git commit
- required branch
- each changed file
- SHA-256 checksum of each replacement file

## Install rule

The installer must check, in this order:

1. Repository exists.
2. Correct branch.
3. Exact base commit.
4. Git working tree is clean.
5. Replacement checksums are valid.
6. Back up only the files being replaced.
7. Copy complete replacement files.
8. Run canonical checks.
9. Hardware-test when firmware changed.
10. Commit.

Do not search source text to guess whether a release applies.

## Release size

Prefer 2–5 related changes in one subsystem per download. Examples:

- Queue model + queue tests + queue UI refinements
- Page navigation + gestures + page tests
- Artwork cache + background cache + serial transfer improvements

Avoid mixing unrelated Queue, artwork, and firmware architecture changes in one
release merely to reduce download count.

## Creating a bundle

From a clean repository:

```bat
python tools\build_release_bundle.py V9_13_page_cleanup ^
  companion\view_controller.py ^
  companion\main.py ^
  "CrowPanel Firmware\CrowPanelSpotify V2\src\SpotifyUI.cpp"
```

The tool copies the complete files and generates the manifest automatically.
