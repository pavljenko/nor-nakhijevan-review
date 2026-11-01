# Նոր Նախիջևան — Armenian glyph construction review

Mobile drawing stand for reviewing 38 Armenian uppercase/lowercase pairs of Nor Nakhijevan / Ростовтрам.

## Use

Open the shared Pages link and select a letter pair and case. The page starts in scrollable view mode. Tap the drawing button to enter the dedicated editor, draw with a finger, stylus, or mouse, then tap Done to return to the page. The drawing toolbar stays at the bottom of the editor. Each page load starts a clean drawing session. Changes are automatically submitted; wait for the saved confirmation before closing the page. Saved SVG and JSON files remain public in the `drawings` branch, grouped by session.

The `main` branch contains the stand and collector source. GitHub Pages serves `docs/`. Drawing submissions go to `drawings`, so they do not rebuild Pages. The collector on the owner's server validates submissions, stores them durably, and pushes immutable SVG/JSON pairs. GitHub credentials are never sent to a visitor's browser. The shared link contains only the stand's submission capability.

## Files

- `docs/`: static website for GitHub Pages.
- `server.py`: Python standard-library collector and Git archive uploader.
- `glyphs.json`: approved reference contours used by the stand.
- `test_archive.py`: collector and uploader checks without GitHub credentials.
- `deployment/`: service and nginx configuration.

Font contours and submitted artwork are published for review. This repository does not grant a font distribution or reuse license.

## Build

Edit `src/review.html`, then run `python3 build.py`. The build embeds the approved reference paths in an immutable JavaScript asset and updates `docs/index.html`. No dependencies are required.
