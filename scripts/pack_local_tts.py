"""pack_local_tts.py builds deterministic offline speech archives for Cloud and Edge.
The operator selects eSpeak-NG or Sherpa and supplies the matching runtime,
language data or model, MP3 encoder, and redistribution licenses. Engine-specific
validation fixes the resource layout before the shared manifest records hashes.

Each host activates one archive, so the package names a supported runtime
contract rather than combining engines behind an implicit selection rule. The
package version and model version identify the supplied upstream binary and
language data release. Archive entries have stable ordering and timestamps, and
failed writes remove their incomplete output. This script neither downloads
dependencies nor changes an installed host resource.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

# Runtime contracts select host-supported invocation rules, while package and
# model versions preserve the operator's exact upstream executable and data identity.
RUNTIME_VERSIONS = {"espeak-ng": "espeak-ng-1.52.0", "sherpa-onnx": "sherpa-onnx-2.0.1"}
SHERPA_MODEL_FILES = ("model.onnx", "lexicon.txt", "tokens.txt", "date.fst", "number.fst")
ESPEAK_DATA_FILES = ("cmn_dict", "phontab", "phondata", "phonindex", "intonations", "lang/sit/cmn")


def digest(path: Path) -> str:
    """digest hashes a source file without loading the complete model into memory."""
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def package(args: argparse.Namespace) -> dict:
    """package creates the selected engine archive and immutable download identity.

    Engine selection determines both required files and their archive paths;
    eSpeak callers pass the espeak-ng-data directory itself, while Sherpa callers
    pass the Melo model directory. Only a completely written archive receives
    source metadata. A preexisting output is never overwritten, because its
    package version may already identify published immutable content for hosts.
    Every included payload file participates in the manifest's digest map.
    """
    suffix = ".exe" if args.platform == "win-x64" else ""
    executable = "espeak-ng" if args.engine == "espeak-ng" else "sherpa-onnx-offline-tts"
    required = args.runtime_dir / "bin" / (executable + suffix)
    if not required.is_file():
        raise ValueError(f"Missing runtime executable: {required}")
    files: dict[str, Path] = {}
    files["runtime/bin/" + required.name] = required
    for path in sorted(args.runtime_dir.rglob("*")):
        relative = path.relative_to(args.runtime_dir)
        if path.is_file() and relative.parts[0] in ("bin", "lib") and (
                path.name.endswith((".dll", ".dylib")) or ".so" in path.name):
            files["runtime/" + relative.as_posix()] = path
    if args.engine == "sherpa-onnx" and args.platform == "win-x64":
        for name in ("onnxruntime.dll", "onnxruntime_providers_shared.dll"):
            if not (args.runtime_dir / "bin" / name).is_file():
                raise ValueError(f"Windows requires {name} beside the executable in runtime/bin; PATH cannot override System32 DLL loading")
    required_data = ESPEAK_DATA_FILES if args.engine == "espeak-ng" else SHERPA_MODEL_FILES
    for name in required_data:
        path = args.model_dir / name
        if not path.is_file():
            raise ValueError(f"Missing {args.engine} language/model file: {path}")
    if args.engine == "espeak-ng":
        for path in sorted(args.model_dir.rglob("*")):
            if path.is_file():
                files["model/espeak-ng-data/" + path.relative_to(args.model_dir).as_posix()] = path
    else:
        for name in SHERPA_MODEL_FILES:
            files["model/" + name] = args.model_dir / name
    if not args.ffmpeg.is_file():
        raise ValueError(f"Missing MP3 encoder: {args.ffmpeg}")
    files["runtime/bin/ffmpeg" + suffix] = args.ffmpeg
    for path in sorted(args.licenses_dir.rglob("*")):
        if path.is_file():
            files["licenses/" + path.relative_to(args.licenses_dir).as_posix()] = path
    if not any(name.startswith("licenses/") for name in files):
        raise ValueError("Include engine, language/model data and FFmpeg licenses before packaging")
    manifest = dict(formatVersion=1, version=args.version, modelVersion=args.model_version,
                    runtimeVersion=RUNTIME_VERSIONS[args.engine], platform=args.platform,
                    files={name: digest(path) for name, path in sorted(files.items())})
    if args.output.exists():
        raise ValueError(f"Output already exists; publish a new immutable version: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(args.output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            # Fixed timestamps and sorted entries make mirror copies reproducible
            # without changing any executable or language-data bytes supplied by operators.
            for name, path in sorted(files.items()):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = (0o100755 if name.startswith("runtime/bin/") else 0o100644) << 16
                with path.open("rb") as source, archive.open(entry, "w") as target:
                    shutil.copyfileobj(source, target)
            entry = zipfile.ZipInfo("resource.json", (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except BaseException:
        # An interrupted archive is never a usable download; remove only the
        # exclusive output created by this invocation before reporting its failure.
        args.output.unlink(missing_ok=True)
        raise
    source = dict(version=args.version, url=args.url or "https://YOUR-MIRROR/" + args.output.name,
                  sha256=digest(args.output), sizeBytes=args.output.stat().st_size)
    args.output.with_suffix(args.output.suffix + ".source.json").write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return source


def main() -> None:
    """main parses release inputs and emits Cloud/Edge download source fields.

    eSpeak-NG is the default engine. Callers selecting Sherpa must explicitly name
    that engine and provide its separate executable and Melo model resource set.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("espeak-ng", "sherpa-onnx"), default="espeak-ng")
    parser.add_argument("--runtime-dir", type=Path, required=True, help="Official runtime directory containing bin/ and lib/")
    parser.add_argument("--model-dir", type=Path, required=True, help="eSpeak espeak-ng-data directory itself, or the extracted Melo model directory for Sherpa")
    parser.add_argument("--ffmpeg", type=Path, required=True, help="Matching platform FFmpeg with libmp3lame support")
    parser.add_argument("--licenses-dir", type=Path, required=True, help="Directory with all redistributed component licenses")
    parser.add_argument("--version", required=True, help="Immutable package version, unique per platform")
    parser.add_argument("--model-version", required=True, help="Pinned language-data or model release identity")
    parser.add_argument("--platform", choices=("linux-arm64", "linux-x64", "win-x64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", help="Published HTTP(S) package URL")
    args = parser.parse_args()
    try:
        print(json.dumps(package(args), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Resource packaging failed: {error}\n")


if __name__ == "__main__":
    main()
