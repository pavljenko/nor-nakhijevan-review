# Зарисовки Nor Nakhijevan

**[Открыть галерею →](https://tools.pavljenko.ru/nor-gallery)** · [Архив на GitHub](https://github.com/pavljenko/nor-nakhijevan-review/tree/drawings)

<a href="https://tools.pavljenko.ru/nor-gallery"><img src="https://raw.githubusercontent.com/pavljenko/nor-nakhijevan-review/drawings/gallery/latest-1.svg" width="200" alt="Зарисовка 1"></a>

---

# Նոր Նախիջևան — Armenian glyph construction review

Mobile drawing stand for reviewing 38 Armenian uppercase/lowercase pairs of Nor Nakhijevan / Ростовтрам.

## Use

Open the shared stand link, select a letter, and draw directly on the canvas. The canvas, tools and Save button fit on one screen. The grid icon opens the public gallery. Each page load starts a clean drawing session. Changes are backed up locally after each stroke (and periodically during drawing), then automatically submitted. Undelivered drawings survive reload in a browser outbox while the canvas starts fresh. Retries use bounded request timeouts and exponential backoff; the online event retries immediately. Wait for the saved confirmation before closing the page. Saved SVG and JSON files remain public in the `drawings` branch, grouped by session.

The `main` branch contains the stand and collector source. GitHub Pages serves `docs/`; the short stand link uses the same generated `stand.html` served directly by the collector to avoid deployment/cache delays and cross-origin preflights. Drawing submissions go to `drawings`, so they do not rebuild Pages. The collector on the owner's server validates submissions, stores them durably, and pushes immutable SVG/JSON pairs. GitHub credentials are never sent to a visitor's browser. The shared link contains only the stand's submission capability.

## Files

- `docs/`: static website for GitHub Pages.
- `server.py`: Python standard-library collector and Git archive uploader.
- `glyphs.json`: approved reference contours used by the stand.
- `test_archive.py`: collector and uploader checks without GitHub credentials.
- `deployment/`: service and nginx configuration.

Font contours and submitted artwork are published for review. This repository does not grant a font distribution or reuse license.

## Build

Edit `src/review.html`, then run `python3 build.py`. The build embeds the approved reference paths in an immutable JavaScript asset and updates `docs/index.html`. No dependencies are required.

Saved constructions automatically update `gallery.json`, thumbnail aliases and the visual README in the `drawings` branch. The gallery groups revisions by session and glyph, with the newest saved variant first. Original SVG/JSON versions remain in the archive.

## Owner controls

The owner receives a separate private gallery link. It enables deletion only after server-side verification of a dedicated owner capability; the shared submission key cannot delete. Deleting a card removes every intermediate revision for that session and glyph from the current archive, gallery and preview aliases. Git history retains previous commits. Never publish the owner key in this repository or share the private management link.

A successful save receipt is returned only after the SQLite transaction commits with WAL/FULL durability. GitHub publication is a separate retrying background job. The public gallery and SVG/JSON endpoints include durable queued drawings immediately. Monotonic revisions prevent a delayed older request from replacing newer strokes. Browser backups are removed only for the exact confirmed snapshot.

The public gallery reads the live `/api/gallery` endpoint with no-store caching and refreshes every five seconds while visible, plus on focus. Deletion tombstones are excluded immediately, before GitHub cleanup completes.

The live gallery HTML is also served by the collector at `/api/gallery-ui` with no-store headers. Public and private short links route to it directly, so gallery fixes do not wait for GitHub Pages deployment. GitHub remains the SVG/JSON archive and source repository.

The editor uses a fixed page and stable small-viewport height (`svh`), explicit touch/gesture/drag cancellation, and an independent scrollable alphabet dialog. Save messages overlay the stage without changing its dimensions. Older browsers keep their initial height until a width/orientation change. Pointer coordinates use one transform per stroke; moving a pen updates only that stroke.

## Drawing demonstration

The main stand opens with the author's recorded two-stroke demonstration of Ա (1,666 ms). The supplied finger SVG follows the recorded contact point as the new contour appears. A repeat button replays it; Start closes the demonstration and leaves a clean drawing canvas. The demo never creates sketch submissions. Reduced-motion preferences show the finished contour with manual replay available.

`src/motion.js` implements capture, time-preserving polyline simplification, and a dependency-free SVG/requestAnimationFrame player. `src/tutorial-motion.json` is the author's accepted recording. `src/assets/finger.svg` preserves the silhouette supplied by the author as `point_483772.svg`; its fingertip hotspot is `(234.667, 0)`.

`recorder.html` is a separate author tool. It records `[x,y,time_ms]`, including pen lifts and pauses, previews with the same player, backs up the draft locally, and exports JSON. Saving and reading `/api/motions` requires the existing owner capability; the shared sketch key cannot access it. Recordings commit durably to SQLite and separate JSON files under the collector's private `motions/` directory, independently of the public sketch gallery. Do not publish owner links or keys.

Checks: `node test_motion.cjs`, `python3 test_motion_store.py`, and the existing save/owner/canvas checks.
