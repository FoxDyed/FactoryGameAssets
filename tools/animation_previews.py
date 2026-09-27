#!/usr/bin/env python3
"""Build compact motion viewing copies from existing local gallery artwork.

Only Pillow is required. Inputs are read-only. This helper does not generate art,
publish anything, or replace original all-direction sheets. Its output manifest
can be consumed by the gallery importer without copying private source reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

VERSION = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def js_data(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text.split("=", 1)[1].strip().rstrip(";"))


def evenly_spaced_durations(frames: int, milliseconds: int) -> list[int]:
    return [round((i + 1) * milliseconds / frames) - round(i * milliseconds / frames)
            for i in range(frames)]


class Builder:
    def __init__(self, engine: Path, output: Path):
        self.engine = engine.resolve(strict=True)
        self.output = output.resolve()
        if self.output == self.engine or self.output.is_relative_to(self.engine):
            raise ValueError("Animation outputs must be outside the read-only engine source.")
        self.output.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []
        self.digests: dict[Path, str] = {}

    def source(self, value: str | Path) -> Path:
        path = (self.engine / value).resolve(strict=True)
        if not path.is_relative_to(self.engine):
            raise ValueError(f"Source escapes the declared engine root: {value}")
        return path

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.engine).as_posix()

    def digest(self, path: Path) -> str:
        if path not in self.digests:
            self.digests[path] = sha256(path)
        return self.digests[path]

    def build(self, name: str, frames: list[Image.Image], durations: list[int],
              inputs: list[Path], *, maximum: int = 384) -> dict:
        if len(frames) != len(durations) or not frames or min(durations) <= 0:
            raise ValueError(f"Invalid frame timing for {name}")
        converted = []
        for image in frames:
            image = image.convert("RGBA")
            image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
            converted.append(image)
        if len({im.size for im in converted}) != 1:
            raise ValueError(f"Changing frame dimensions for {name}")
        destination = self.output / f"{name}.webp"
        converted[0].save(destination, "WEBP", save_all=True,
                          append_images=converted[1:], duration=durations,
                          loop=0, quality=82, method=4, minimize_size=True)
        decoded_durations, decoded_hashes = [], set()
        with Image.open(destination) as decoded:
            size = decoded.size
            for i in range(decoded.n_frames):
                decoded.seek(i)
                decoded.load()
                decoded_durations.append(decoded.info.get("duration", 0))
                decoded_hashes.add(hashlib.sha256(decoded.convert("RGBA").tobytes()).digest())
            decoded_loop = decoded.info.get("loop")
        if sum(decoded_durations) != sum(durations):
            raise ValueError(f"Encoded duration differs for {name}")
        if len(decoded_hashes) < 2 or decoded_loop != 0:
            raise ValueError(f"Expected a moving, repeating preview for {name}")
        print(f"Verified {name}: {len(decoded_durations)} frames, "
              f"{sum(durations)} ms, {destination.stat().st_size:,} bytes", flush=True)
        return {
            "path": str(destination), "sha256": sha256(destination),
            "bytes": destination.stat().st_size, "width": size[0], "height": size[1],
            "inputFrames": len(frames), "encodedFrames": len(decoded_durations),
            "durationMs": sum(durations), "animated": True, "loop": 0,
            "verified": True, "uniqueDecodedFrames": len(decoded_hashes),
            "helperVersion": VERSION,
            "sourceDigests": [{"source": self.relative(p), "sha256": self.digest(p)}
                              for p in dict.fromkeys(inputs)],
        }

    def add(self, result: dict, gallery: Path, source: Path, title: str, note: str,
            **metadata) -> None:
        self.entries.append({**result, "gallerySource": self.relative(gallery),
                             "source": self.relative(source),
                             "sourceSha256": self.digest(source), "title": title,
                             "note": note, **metadata})

    def queen_comparison(self) -> None:
        base = self.source("experiments/queen-mesh2motion-comparison-20260921")
        three = base / "three-way-data.js"
        two = base / "review-data.js"
        data = js_data(three)
        two_data = js_data(two)
        for provider in ("meshy", "mesh2motion"):
            if data["providers"][provider] != two_data["providers"][provider]:
                raise ValueError("Comparison galleries no longer share identical source clips.")
        for provider, content in data["providers"].items():
            for clip, spec in content["clips"].items():
                atlas = self.source(base / spec["directions"]["se"]["atlas"])
                with Image.open(atlas) as image:
                    frames = [image.crop(((i % 8) * 384, (i // 8) * 384,
                                           (i % 8 + 1) * 384, (i // 8 + 1) * 384))
                              for i in range(spec["frames"])]
                durations = list(spec["durations_ms"])
                hold = 0 if spec["loop"] else 750
                durations[-1] += hold
                result = self.build(f"queen-comparison-{provider}-{clip}", frames,
                                    durations, [three, atlas])
                label = {"meshy": "Meshy", "mesh2motion": "Mesh2Motion",
                         "codex": "Codex-authored"}[provider]
                note = ("Southeast facing; source integer-millisecond native timing. "
                        "Other directions remain in the original review sheets. " +
                        ("Looping clip." if not hold else
                         "One-shot clip with a 750 ms final-pose hold before replay; "
                         "independent previews do not synchronize providers."))
                self.add(result, base / "REVIEW_THREE_WAY.html", three,
                         f"Queen · {label} · {clip} · southeast", note,
                         provider=provider, clip=clip, direction="se",
                         sourceLoop=spec["loop"], replayHoldMs=hold)
                if provider in {"meshy", "mesh2motion"}:
                    # The two-way page references these exact same source atlases.
                    copy = {**result, "sourceDigests": [
                        {"source": self.relative(two), "sha256": self.digest(two)},
                        {"source": self.relative(atlas), "sha256": self.digest(atlas)}]}
                    self.add(copy, base / "REVIEW.html", two,
                             f"Queen · {label} · {clip} · southeast", note,
                             provider=provider, clip=clip, direction="se",
                             sourceLoop=spec["loop"], replayHoldMs=hold)

    def queen_visibility(self) -> None:
        base = self.source("experiments/queen-humanoid-visibility-v2-20260915/previews")
        source = base / "viewer-data.js"
        data = js_data(source)
        row = next(i for i, d in enumerate(data["plan"]["directions"]) if d["id"] == "se")
        for spec in data["sheets"]:
            frames, inputs = [], [source]
            for relative in spec["pages"]:
                page = self.source(base / relative)
                inputs.append(page)
                with Image.open(page) as image:
                    for column in range(min(8, spec["frames"] - len(frames))):
                        x = column * spec["cell"] + spec["gutter"]
                        y = row * spec["cell"] + spec["gutter"]
                        frames.append(image.crop((x, y, x + 384, y + 384)))
            durations = list(spec["durations"])
            hold = 0 if spec["loop"] else 900
            durations[-1] += hold
            result = self.build(f"queen-visibility-{spec['id']}", frames, durations, inputs)
            self.add(result, base / "index.html", source,
                     f"Queen · brighter violet and ivory · {spec['id']} · southeast",
                     "Southeast facing; source frame durations and 384px atlas crop. " +
                     ("Looping clip." if not hold else
                      "One-shot clip with the original viewer's 900 ms final-pose hold before replay."),
                     clip=spec["id"], direction="se", sourceLoop=spec["loop"],
                     replayHoldMs=hold)

    def queen_live(self) -> None:
        base = self.source("experiments/queen-humanoid-20260915")
        source = base / "previews/live.html"
        inputs, frames = [source], []
        for i in range(60):
            path = self.source(base / "renders/idle/s" / f"{i:04}.png")
            inputs.append(path)
            with Image.open(path) as image:
                frames.append(image.crop((160, 96, 352, 288)))
        result = self.build("queen-original-idle-inspection", frames,
                            evenly_spaced_durations(60, 4000), inputs, maximum=192)
        self.add(result, source, source, "Queen · original idle close-up · south",
                 "Original live inspector crop (160,96,192,192), south facing. "
                 "60 frames at 15 fps; millisecond rounding preserves the 4-second cycle. "
                 "This is the earlier darker study, separate from the brighter revision.",
                 clip="idle", direction="s", sourceLoop=True, replayHoldMs=0)

    def relic_sentinel(self) -> None:
        base = self.source("experiments/relic-sentinel-20260921/eight-directions-v1")
        for clip in ("idle", "run", "damage", "shield-bash", "death"):
            source = self.source(base / "review" / f"{clip}-eight-directions.gif")
            frames, durations = [], []
            with Image.open(source) as image:
                for i in range(image.n_frames):
                    image.seek(i)
                    image.load()
                    frames.append(image.convert("RGBA"))
                    durations.append(image.info["duration"])
            result = self.build(f"relic-sentinel-{clip}", frames, durations,
                                [source, base / "review.html"], maximum=768)
            self.add(result, base / "review.html", source,
                     f"Relic Sentinel · {clip.replace('-', ' ')} · eight directions",
                     "WebP viewing copy of the existing composed eight-direction GIF. "
                     "Original GIF frame timing is preserved; frame size is reduced for the web. " +
                     ("Death includes its original guard pause and final corpse hold before replay."
                      if clip == "death" else "Original repeating review playback."),
                     clip=clip, direction="all-eight", sourceLoop=True,
                     reusedExistingPreview=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / ".local/animation-previews")
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).resolve().parents[1] / ".local/animation-import.json")
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    engine = args.engine.resolve(strict=True)
    if manifest == engine or manifest.is_relative_to(engine):
        raise ValueError("The output manifest must be outside the read-only engine source.")
    builder = Builder(args.engine, args.output)
    builder.queen_comparison()
    builder.queen_visibility()
    builder.queen_live()
    builder.relic_sentinel()
    # Do not emit a success manifest until every generated animation has decoded
    # successfully with its exact intended total duration and changing frames.
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(builder.entries, indent=2) + "\n", encoding="utf-8")
    unique = {entry["path"]: entry["bytes"] for entry in builder.entries}
    print(f"Wrote {len(builder.entries)} gallery entries, {len(unique)} unique animations, "
          f"{sum(unique.values()):,} bytes to {args.manifest}")


if __name__ == "__main__":
    main()
