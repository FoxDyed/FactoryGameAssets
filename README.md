# Factory Game Assets

**[Open the live art galleries](https://foxdyed.github.io/FactoryGameAssets/)**

FoxDyed's Factory Game art: terrain, units, buildings, resources, props, concept
art and study galleries. Browse by asset type, search collections, and open
images or animation previews in the full-size viewer.

The static site is published by GitHub Pages from `main`, directory `/docs`.
Changes pushed to that directory are published automatically by GitHub Pages.
The gallery uses plain HTML, CSS and JavaScript, with no external tracking,
fonts, CDN scripts, build framework or account requirement.

## What is published

`docs/data/catalog.json` lists every collection and media item.
`docs/data/publication-report.json` records source-gallery coverage, missing
historical references, counts and the publication scope. Media is deduplicated
by SHA-256, with small thumbnails, larger WebP viewing copies and compressed
video previews. The source hash identifies the preserved local original.

These are web viewing copies. The engine repository, editable Blender/Aseprite/
Material Maker sources, acquisition receipts and original images stay in their
existing local locations. Publishing a gallery does not approve candidate art,
change its review status or integrate it into the game. No license to redistribute
third-party references or underlying source assets is implied by this gallery.

Existing study galleries are presented in a consistent image/video viewer.
Some historical HTML files refer to artwork retired during earlier cleanup;
the coverage report records those gaps rather than publishing broken links.
Individual render frames, model texture maps and technical buffers are
represented by their completed previews, animation previews or sprite sheets.

## Refresh from the local art library

Requirements: Python 3.12+, Pillow 12.3.0, and FFmpeg. The importer reads the
current on-disk library, not just the older migration catalog. It follows local
asset links only within the declared source roots and never modifies originals.

```powershell
python tools/animation_previews.py --engine 'PATH/TO/Factory Game Engine'
python tools/build_gallery.py --engine 'PATH/TO/Factory Game Engine' --concepts 'PATH/TO/Factory Game Design Concept Art' --ffmpeg 'PATH/TO/ffmpeg.exe'
python tools/validate_site.py
python -m http.server 8766 --directory docs --bind 127.0.0.1
```

Open `http://127.0.0.1:8766` to review. After reviewing and validating the result,
commit the site and push `main`. New local artwork is added on the next import;
the website cannot read unpublished files from your computer automatically.

Import caches and local source inventory live in ignored `.local/`. Public
metadata contains only artwork titles, relative source locations, dimensions
and content hashes, never private acquisition links or credentials.
