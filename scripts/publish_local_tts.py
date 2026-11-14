"""publish_local_tts.py releases speech resources independently of Cloud builds.
It prepares the two Linux packages or verifies an existing prepared directory,
then generates version-pinned GitHub URLs in catalog.json. Maintainers publish
the catalog and archives together; Cloud and Edge consume these ordinary release
assets without GitHub credentials or native compilation tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from prepare_local_tts import prepare

# The resource repository is public software distribution; application releases
# carry its small catalog rather than rebuilding native binaries each time.
DEFAULT_REPOSITORY = 'zhengchalei/ztnet-speech-resources'


def catalog_for_release(directory: Path, repository: str, tag: str) -> dict:
    """catalog_for_release verifies package bytes before writing pinned download metadata.

    Existing package versions remain unchanged. Invalid repository names, tags,
    sizes or hashes fail before any GitHub mutation, so a draft cannot advertise
    another set of bytes under the original immutable package identity.
    """
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', tag):
        raise ValueError('Release tag must use letters, digits, dots, underscores or hyphens')
    sources = json.loads((directory / 'catalog.json').read_text(encoding='utf-8'))
    if not sources:
        raise ValueError('No speech packages to publish')
    for platform, source in sources.items():
        if platform not in ('linux-arm64', 'linux-x64', 'win-x64'):
            raise ValueError('Unsupported platform')
        archive = directory / (platform + '.zip')
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if archive.stat().st_size != source['sizeBytes'] or digest != source['sha256']:
            raise ValueError(f'Package verification failed: {platform}')
        source.update(url=f'https://github.com/{repository}/releases/download/{tag}/{platform}.zip', systemManaged=True)
    (directory / 'catalog.json').write_text(json.dumps(sources, indent=2) + '\n', encoding='utf-8')
    return sources


def main() -> None:
    """main publishes a complete draft before making the resource release discoverable.

    The repository must already exist and gh must be authenticated. Preparation
    is independent of the application build. A failed upload leaves a draft for
    inspection rather than exposing an incomplete release through latest.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default=DEFAULT_REPOSITORY)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--directory', type=Path, default=Path('output/speech-release'))
    parser.add_argument('--prepared', action='store_true', help='Use already built and verified packages')
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--extra-asset', type=Path, action='append', default=[])
    arguments = parser.parse_args()
    if not arguments.prepared:
        prepare(arguments.directory)
    sources = catalog_for_release(arguments.directory, arguments.repository, arguments.tag)
    files = [arguments.directory / 'catalog.json', *(arguments.directory / (p + '.zip') for p in sources), *arguments.extra_asset]
    for file in files:
        if not file.is_file():
            raise ValueError(f'Missing release asset: {file}')
    subprocess.run(['gh', 'release', 'create', arguments.tag, '--repo', arguments.repository,
        '--draft', '--title', arguments.tag, '--notes-file', str(arguments.notes), *map(str, files)], check=True)
    # Publishing latest follows successful upload of every asset; consumers see
    # a complete manifest and its matching platform packages in one release.
    subprocess.run(['gh', 'release', 'edit', arguments.tag, '--repo', arguments.repository,
        '--draft=false', '--latest'], check=True)


if __name__ == '__main__':
    main()
