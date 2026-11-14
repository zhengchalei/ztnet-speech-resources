"""prepare_local_tts.py builds independent ready-to-install speech release assets.
Maintainers invoke Docker to build both supported Linux architectures, then
publish them to the dedicated GitHub resource repository. End users never supply
build tools, download URLs, checksums, or archives during ordinary installation.

Docker layer caching avoids rebuilding unchanged native components on every
release. A local cache is keyed by the complete build recipe, and every cached
archive is checked against its generated size and digest before reuse. Partial
builds cannot replace the destination catalog because preparation finishes before
files are copied into the Cloud publication directory. The standard archive
validator remains responsible for platform checks and trial synthesis at install.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

# ROOT and PLATFORMS constrain publication inputs to this repository and the two
# supported Linux package contracts, independently of the Docker builder's CPU.
ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ('linux-x64', 'linux-arm64')


def prepare(destination: Path, platforms: list[str] | None = None) -> None:
    """prepare builds verified archives before publishing the matching deployment catalog.

    An amd64 Docker builder compiles x64 directly and cross-compiles ARM64,
    validating ARM64 executables with an explicit userspace emulator inside the
    build container. No host binfmt registration or privileged container is needed.
    A failed build leaves the published destination untouched and surfaces the
    original tool failure instead of producing a release with unusable defaults.
    """
    files = [ROOT / 'scripts/pack_local_tts.py', ROOT / 'scripts/local_tts/Dockerfile',
             ROOT / 'scripts/local_tts/build_package.py']
    recipe = hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()[:20]
    cache = ROOT / '.cache/local-tts' / recipe
    catalog = {}
    for platform in platforms or list(PLATFORMS):
        if platform not in PLATFORMS:
            raise ValueError(f'Unsupported platform: {platform}')
        output = cache / platform
        metadata = output / (platform + '.zip.source.json')
        if not metadata.is_file():
            with tempfile.TemporaryDirectory(prefix='x-local-tts-') as folder:
                context = Path(folder)
                for source in files:
                    shutil.copy2(source, context / source.name)
                # Native and cross builds share cached host tools; platform is a
                # package contract rather than a request to change host emulation.
                subprocess.run([shutil.which('docker') or 'docker', 'build', '--platform', 'linux/amd64',
                    '--build-arg', f'RESOURCE_PLATFORM={platform}', '--output', f'type=local,dest={output}',
                    '--file', str(context / 'Dockerfile'), str(context)], check=True)
        source = json.loads(metadata.read_text(encoding='utf-8'))
        archive = output / (platform + '.zip')
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if archive.stat().st_size != source['sizeBytes'] or digest != source['sha256']:
            raise ValueError(f'Cached speech archive failed verification: {archive}')
        catalog[platform] = {**source, 'url': '', 'systemManaged': True}
    destination.mkdir(parents=True, exist_ok=True)
    for platform in catalog:
        shutil.copy2(cache / platform / (platform + '.zip'), destination / (platform + '.zip'))
    (destination / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--platform', action='append', choices=PLATFORMS)
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.platform)
