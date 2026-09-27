# Factory Game Assets

This repository publishes the user's art galleries on GitHub Pages. The engine
repository and original art sources are separate. Never copy credentials,
acquisition receipts, signed download URLs, runtime packages, or vendor assets.
Keep generated web previews under docs/media and their sanitized provenance in
docs/data. Publication is a viewing copy, not engine integration or art approval.

Use tools/build_gallery.py with explicit local source roots to refresh content.
Originals are read-only. Keep all gallery coverage outcomes in the generated
publication report. Do not remove original artwork or follow links outside the
declared source roots. Validate with tools/validate_site.py before publication.

The site is plain HTML/CSS/JavaScript, served from main:/docs. Avoid a framework
or dependencies unless a requested feature needs them. Keep all site paths
relative so GitHub's /FactoryGameAssets/ project URL works.
