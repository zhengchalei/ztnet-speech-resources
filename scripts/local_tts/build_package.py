"""build_package.py assembles one native platform inside the release container.
The release runs this script for both Linux architectures and includes Chinese
language data, static executables, and component license/source information.
Users receive these prepared archives through Cloud instead of building them.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

from pack_local_tts import package


def main() -> None:
    """main freezes compiled bytes into a content-identified standard speech archive.

    Docker supplies the compiled runtime, language data, encoder and licenses at
    fixed build paths before invoking this entry point. Trial synthesis exercises
    the same stdin, WAV and MP3 contract used by the production engine, using an
    explicit emulator only for ARM64. Payload-derived versions keep rebuilt native
    dependencies distinct, while the existing packager supplies the shared manifest
    and immutable archive layout accepted by both Cloud and Edge installations.
    """
    platform = sys.argv[1]
    root = Path('/src')
    runtime = root / 'runtime'
    (runtime / 'bin').mkdir(parents=True)
    shutil.copy2(root / 'espeak-build/src/espeak-ng', runtime / 'bin/espeak-ng')
    encoder = Path('/opt/encoder/bin/ffmpeg')
    licenses = root / 'licenses'
    licenses.mkdir()
    for path in (root / 'espeak').glob('COPYING*'):
        shutil.copy2(path, licenses / ('espeak-' + path.name))
    shutil.copy2(root / 'ffmpeg-7.1.1/COPYING.LGPLv2.1', licenses / 'ffmpeg-LGPLv2.1')
    shutil.copy2(Path('/usr/share/doc/libmp3lame-dev/copyright'), licenses / 'lame-copyright')
    (licenses / 'SOURCES.txt').write_text(
        'eSpeak-NG 1.52.0: https://github.com/espeak-ng/espeak-ng/tree/1.52.0\n'
        'FFmpeg 7.1.1: https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz\n'
        'LAME 3.100: https://lame.sourceforge.io/download.php\n'
        'Rebuild: X_IOT scripts/local_tts/Dockerfile and build_package.py\n', encoding='utf-8')
    model = root / 'espeak-build/espeak-ng-data'
    # Exercise the exact stdin/WAV/MP3 contract during release preparation. A
    # package is not emitted when its native encoder lacks a required format.
    wave, audio = root / 'trial.wav', root / 'trial.mp3'
    runner = ['qemu-aarch64-static'] if platform == 'linux-arm64' else []
    subprocess.run([*runner, str(runtime / 'bin/espeak-ng'), '--path=' + str(model.parent), '-v', 'cmn',
        '-s', '175', '-w', str(wave), '--stdin'], input='您好，语音资源已经准备就绪。'.encode(), check=True)
    subprocess.run([*runner, str(encoder), '-nostdin', '-loglevel', 'error', '-y', '-i', str(wave),
        '-ac', '1', '-ar', '22050', '-c:a', 'libmp3lame', '-b:a', '64k', str(audio)], check=True)
    if audio.stat().st_size < 128:
        raise ValueError('Native speech trial produced incomplete MP3')
    identity = hashlib.sha256()
    # Resource versions follow payload bytes, so rebuilding dependencies cannot
    # silently replace an immutable version already activated by another host.
    for path in [runtime / 'bin/espeak-ng', encoder, *sorted(p for p in model.rglob('*') if p.is_file()),
                 *sorted(p for p in licenses.rglob('*') if p.is_file())]:
        identity.update(path.read_bytes())
    version = f'espeak-ng-1.52.0-{platform}-{identity.hexdigest()[:16]}'
    package(argparse.Namespace(engine='espeak-ng', runtime_dir=runtime, model_dir=model,
        ffmpeg=encoder, licenses_dir=licenses, version=version, model_version='espeak-data-1.52.0',
        platform=platform, output=Path('/out') / (platform + '.zip'), url='http://localhost/unused'))


if __name__ == '__main__':
    main()
