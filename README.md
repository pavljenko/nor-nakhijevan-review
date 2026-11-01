# Նոր Նախիջևան — Armenian glyph construction review

Mobile drawing stand for reviewing 38 Armenian uppercase/lowercase pairs of Nor Nakhijevan / Ростовтрам.

## Use

Open the shared Pages link, select a letter pair, and draw with a finger, stylus, or mouse. Each page load starts a clean drawing session. Changes are automatically submitted; wait for the saved confirmation before closing the page. Saved SVG and JSON files remain public in the `drawings` branch, grouped by session.

The `main` branch contains the stand and collector source. GitHub Pages serves `docs/`. Drawing submissions go to `drawings`, so they do not rebuild Pages. The collector on the owner's server validates submissions, stores them durably, and pushes immutable SVG/JSON pairs. GitHub credentials are never sent to a visitor's browser. The shared link contains only the stand's submission capability.

## Files

- `docs/`: static website for GitHub Pages.
- `server.py`: Python standard-library collector and Git archive uploader.
- `glyphs.json`: approved reference contours used by the stand.
- `test_archive.py`: collector and uploader checks without GitHub credentials.
- `deployment/`: service and nginx configuration.

Font contours and submitted artwork are published for review. This repository does not grant a font distribution or reuse license.
