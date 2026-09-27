"""Conservative demo-art membership from a verified delivered package.

This module reads originals only. The active-reference rules are deliberately
bound to one inspected package digest. A changed/missing delivery becomes
unknown until its graphics definitions are reviewed; loose mod directories and
historical launch logs never establish membership. No Lua is executed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


DEMO_ROOT = "experiments/factorio-overhaul-demo"
PACKAGE_SOURCE = f"{DEMO_ROOT}/delivery/brood-overhaul_0.1.0.zip"
RECEIPT_SOURCE = f"{DEMO_ROOT}/meadows-v1/tree-art-retirement/package.json"
QUALIFICATION_SOURCE = f"{DEMO_ROOT}/meadows-v1/tree-art-retirement/qualification.json"
RETIREMENT_SOURCE = f"{DEMO_ROOT}/meadows-v1/tree-art-retirement/retirement.json"
AUDITED_PACKAGE_SHA256 = "1e1d94d1b0733a09c4e007cee240407c65462fce3e2c8907f80964da4a1459ce"
ZIP_ROOT = "brood-overhaul_0.1.0/"
STATUSES = ("in-demo", "not-in-demo", "unknown")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _inside(root: Path, source: str) -> Path | None:
    """Accept only relative public source paths resolving inside the engine."""
    if not isinstance(source, str) or "\\" in source or ":" in source:
        return None
    relative = PurePosixPath(source)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    path = (root / source).resolve()
    return path if path.is_relative_to(root) else None


def _active_graphics() -> dict[str, str]:
    """Exact paths read from the hash-bound package's current graphics modules.

    These are current Queen/Ravager/Sentinel/Gatekeeper animation definitions,
    current terrain/tree definitions, and revised-economy organs/materials.
    Legacy still-unit art, unused resource layouts, and old hidden-building
    variants are intentionally not inferred active merely because they ship.
    """
    paths: dict[str, str] = {}

    def add(path, module):
        paths[f"graphics/{path}"] = module

    upper = "N NE E SE S SW W NW".split()
    lower = [d.lower() for d in upper]

    def animation(folder, clips, directions, module, fx=()):
        for clip in clips:
            for direction in directions:
                for plane in (("body", "shadow", "fx") if clip in fx else ("body", "shadow")):
                    add(f"{folder}/{clip}-{direction}-{plane}.png", module)

    queen = "idle aim-idle walk run mine work shoot melee hit hit-back hit-left hit-right death".split()
    queen += [f"shoot-move-{i}" for i in range(8)]
    animation("queen-animation", queen, upper, "queen-graphics.lua")
    add("queen-animation/icon.png", "queen-graphics.lua")
    animation("ravager-animation", "walk run sprint attack hit death".split(), upper, "ravager-graphics.lua")
    animation("relic-sentinel-animation", "idle run damage shield-bash death".split(), lower, "relic-graphics.lua")
    add("relic-sentinel-animation/icon.png", "relic-graphics.lua")
    gatekeeper = "idle walk plant fire-left fire-right recover hit hit-braced death wreck turn-left turn-right".split()
    animation("gatekeeper-animation", gatekeeper, lower, "gatekeeper-graphics.lua",
              fx={"fire-left", "fire-right", "hit", "hit-braced"})
    add("gatekeeper-animation/icon.png", "gatekeeper-graphics.lua")
    for plane in ("body", "shadow"):
        for page in (0, 1):
            add(f"gatekeeper-animation/corpse-{plane}-{page}.png", "gatekeeper-graphics.lua")
    for direction in lower:
        for plane in ("body", "fx"):
            add(f"relic-muzzle-flash/{direction}-{plane}.png", "relic-fire-graphics.lua")

    ravager = ["idle", "hatch", "turn-left", "turn-right"]
    for gait, frames in (("walk", 48), ("run", 24), ("sprint", 16)):
        ravager.append(f"{gait}-start")
        ravager += [f"{gait}-stop-{letter}" for letter in "abcd"]
        ravager += [f"{gait}-stop-from-{i + 1:02}" for i in range(frames) if i % (frames // 4)]
    sentinel = ["shoot", "turn-left", "turn-right", "move-start"]
    sentinel += [f"move-stop-p{i:02}" for i in (0, 6, 12, 18)]
    sentinel += [f"move-stop-enter-p{i:02}" for i in range(24) if i % 6]
    animation("unit-animation-completion/ravager", ravager, upper, "unit-animation-graphics.lua")
    animation("unit-animation-completion/sentinel", sentinel, lower, "unit-animation-graphics.lua", fx={"shoot"})

    for tree in ("acacia", "baobab", "thorn"):
        for plane in ("tree", "shadow"):
            for frame in range(1, 81):
                add(f"savannah-trees/{tree}/{plane}-{frame:04}.png", "savannah-trees-data.lua")
    for terrain in ("creep", "barren", "crust", "meadow-earth", "meadow-grass", "meadow-clover"):
        for suffix in ("", "-transitions"):
            add(f"terrain/{terrain}{suffix}.png", "terrain-graphics.lua")
    add("terrain/barrens-details.png", "barrens-details-data.lua")
    add("terrain/meadow-details.png", "meadows-data.lua")

    organs = "storage-sac digestion-chamber brood-chamber morphogenesis-chamber nerve-node root-harvester bioelectric-heart hive-core".split()
    for asset in organs:
        add(f"{asset}/direction-00.png", "early-prototypes.lua")
        add(f"{asset}/icon.png", "early-prototypes.lua")
        for plane in ("shadow", "ground", "lip"):
            add(f"grounding/{asset}/direction-00-{plane}.png", "grounding-graphics.lua")
    add("brood-cocoon/direction-00.png", "early-prototypes.lua")
    materials = "fibrous-tissue raw-biomass enzyme-compound healing-bolus mineral-nodule chitin-plate repair-enzyme basic-genome adaptive-genome nutrient-pellet conductive-nerve brood-cocoon".split()
    for asset in materials + ["spine-caster", "thorn-pod", "ravager"]:
        add(f"{asset}/icon.png", "early-prototypes.lua / static-graphics.lua")
    for asset in ("raw-biomass", "mineral-nodule"):
        for plane in ("body", "shadow", "ground", "lip"):
            add(f"resources/{asset}/{plane}-variations.png", "resource-graphics.lua")
    return paths


def _verified_index(engine: Path) -> tuple[dict, dict[str, list[tuple[str, str]]], set[str], set[str]]:
    package = _inside(engine, PACKAGE_SOURCE)
    receipt = _read_json(engine / RECEIPT_SOURCE)
    qualification = _read_json(engine / QUALIFICATION_SOURCE)
    if package is None or not package.is_file():
        raise ValueError("Current delivered package is unavailable.")
    digest = _digest(package)
    if digest != AUDITED_PACKAGE_SHA256 or receipt.get("sha256") != digest:
        raise ValueError("Current package has changed; its active artwork needs a new reference audit.")
    if package.stat().st_size != receipt.get("bytes"):
        raise ValueError("Current package does not match its release receipt size.")
    if qualification.get("status") != "PASS" or qualification.get("package_sha256") != digest:
        raise ValueError("Current package qualification does not match the delivery.")
    launcher = (engine / f"{DEMO_ROOT}/delivery/Launch.ps1").read_text(encoding="utf-8-sig")
    if "$packagePath = Join-Path $demoRoot 'brood-overhaul_0.1.0.zip'" not in launcher:
        raise ValueError("The player launcher package selection needs a new audit.")

    active = _active_graphics()
    by_hash = defaultdict(list)
    with zipfile.ZipFile(package) as archive:
        members = set(archive.namelist())
        if any(ZIP_ROOT + name not in members for name in active):
            raise ValueError("An audited active image is missing from the current package.")
        # Verify the actual member bytes, not the loose working mod or a path name.
        for name, module in sorted(active.items()):
            with archive.open(ZIP_ROOT + name) as stream:
                image_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if image_digest != receipt["files"].get(name):
                raise ValueError("An active image differs from its release receipt.")
            by_hash[image_digest].append((name, module))
    retired = _read_json(engine / RETIREMENT_SOURCE)
    retired_hashes = {entry["sha256"] for entry in retired.get("concept_files", {}).values()
                      if SHA256.fullmatch(entry.get("sha256", ""))}
    packaged_hashes = {value for key, value in receipt["files"].items()
                       if key.startswith("graphics/") and SHA256.fullmatch(value)}
    snapshot = {
        "verification": "verified", "packageSource": PACKAGE_SOURCE,
        "sourceReceipt": RECEIPT_SOURCE, "packageSha256": digest,
        "packageBytes": package.stat().st_size, "activeGraphicsCount": len(active),
        "qualificationSource": QUALIFICATION_SOURCE,
        "definition": "In demo means exact source-image bytes match an inspected active graphics reference in the current delivered package. It does not mean the image is visible in every scene.",
        "limits": "Conservative snapshot. Unproven previews, screenshots, concepts and inactive packaged files remain unknown; loose mod files and historical launch logs are not evidence of current use.",
    }
    return snapshot, dict(by_hash), retired_hashes, packaged_hashes


def attach_demo_metadata(data: dict, engine: Path | str) -> dict:
    """Mutate and return catalog data; read-only with respect to all source files."""
    engine = Path(engine).resolve()
    checked = datetime.now(timezone.utc).isoformat()
    try:
        snapshot, active_hashes, retired_hashes, packaged_hashes = _verified_index(engine)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        # Public fallback strings are controlled, never exception paths/receipt text.
        snapshot = {"verification": "unverified", "packageSource": PACKAGE_SOURCE,
                    "sourceReceipt": RECEIPT_SOURCE,
                    "limits": "The current delivered package could not be matched to the audited graphics snapshot; all demo memberships are unknown."}
        for item in data["media"].values():
            item["demoStatus"] = "unknown"
            item["demoEvidence"] = "Current demo package or active-reference verification is unavailable."
        snapshot["checkedAt"] = checked
        snapshot["counts"] = {status: (len(data["media"]) if status == "unknown" else 0) for status in STATUSES}
        data["demo"] = snapshot
        return data

    # Optional local derivation receipts are never copied into the public catalog.
    derivations = {}
    receipt_path = Path(__file__).resolve().parents[1] / ".local/animation-import.json"
    if receipt_path.is_file():
        try:
            preview_receipts = _read_json(receipt_path)
        except (OSError, ValueError):
            preview_receipts = []
        for entry in preview_receipts if isinstance(preview_receipts, list) else []:
            if not isinstance(entry, dict):
                continue
            if entry.get("verified") and SHA256.fullmatch(entry.get("sha256", "")):
                derivations[entry["sha256"]] = entry
    standalone_cache = {}
    for item in data["media"].values():
        digest = item.get("sha256", "")
        source = item.get("source", "")
        status = "unknown"
        evidence = "No exact active-version link is proven for this image, concept or review preview."
        if item.get("derivedPreview"):
            lineage = derivations.get(item.get("previewSha256"))
            images = [entry for entry in (lineage or {}).get("sourceDigests", [])
                      if PurePosixPath(entry.get("source", "")).suffix.lower() in IMAGE_EXTENSIONS]
            if (lineage and lineage.get("sourceSha256") == digest and images and
                    all(entry.get("sha256") in active_hashes for entry in images)):
                status = "in-demo"
                evidence = "Recorded preview inputs exactly match active demo graphics; the preview presentation may differ."
        elif digest in active_hashes:
            status = "in-demo"
            member, module = active_hashes[digest][0]
            evidence = f"Exact source SHA-256 matches active {member} ({module})."
        elif digest in retired_hashes:
            status = "not-in-demo"
            evidence = "This Meadow tree artwork was explicitly retired to concept art in the current delivery."
        elif digest in packaged_hashes:
            evidence = "Image ships in the package, but active use is not established; retained files alone are insufficient."
        else:
            path = _inside(engine, source)
            if path is not None:
                library = engine / "experiments/art-library"
                # Only the owning asset manifest may explicitly declare exclusion.
                lexical = engine / source
                if lexical.is_relative_to(library) and len(lexical.relative_to(library).parts) >= 3:
                    relative = lexical.relative_to(library)
                    manifest = library / relative.parts[0] / relative.parts[1] / "manifest.json"
                    if manifest not in standalone_cache:
                        try:
                            value = _read_json(manifest)
                            standalone_cache[manifest] = value.get("installed_in_demo") is False
                        except (OSError, ValueError):
                            standalone_cache[manifest] = False
                    if standalone_cache[manifest]:
                        status = "not-in-demo"
                        evidence = "The owning asset manifest explicitly marks this standalone set as not installed in the demo."
        item["demoStatus"], item["demoEvidence"] = status, evidence
    counts = Counter(item["demoStatus"] for item in data["media"].values())
    snapshot["checkedAt"] = checked
    snapshot["counts"] = {status: counts[status] for status in STATUSES}
    data["demo"] = snapshot
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[1] / "docs/data/catalog.json")
    parser.add_argument("--audit", type=Path, default=Path(__file__).resolve().parents[1] / ".local/demo-metadata-audit.json")
    args = parser.parse_args()
    audit_path = args.audit.resolve()
    if audit_path == args.catalog.resolve() or audit_path.is_relative_to(args.engine.resolve()):
        raise ValueError("The audit output must not overwrite the catalog or any engine source.")
    data = attach_demo_metadata(_read_json(args.catalog), args.engine)
    # This audit CLI deliberately does not rewrite the input catalog.
    audit = {"demo": data["demo"], "media": {key: {field: item.get(field) for field in
             ("title", "source", "demoStatus", "demoEvidence")} for key, item in data["media"].items()}}
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(data["demo"], indent=2))


if __name__ == "__main__":
    main()
