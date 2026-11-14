"""test_publish_local_tts.py protects integrity and publication ordering for resource releases.
The checks use real package files and replace only the GitHub command boundary.
A corrupted package or failed asset upload must never become a discoverable
latest release that Cloud could select for its Edge nodes.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import publish_local_tts as release


class SpeechReleaseTests(unittest.TestCase):
    """SpeechReleaseTests checks immutable metadata and failed external publication behavior."""

    def prepare(self, root: Path) -> None:
        """prepare creates a real payload with matching size and digest metadata."""
        payload = b'fixture-native-package-bytes'
        (root / 'linux-arm64.zip').write_bytes(payload)
        (root / 'catalog.json').write_text(json.dumps({'linux-arm64': {
            'version': 'espeak-test-1', 'url': '', 'sizeBytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest(),
        }}), encoding='utf-8')
        (root / 'notes.md').write_text('中文资源发布说明', encoding='utf-8')

    def test_metadata_pins_release_and_preserves_package_identity(self) -> None:
        """A prepared archive receives its fixed public Release URL without changing its identity.
        The persisted catalog exposes the same digest used before publication.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.prepare(root)
            catalog = release.catalog_for_release(root, 'owner/voice', 'v1')
            source = catalog['linux-arm64']
            self.assertEqual('https://github.com/owner/voice/releases/download/v1/linux-arm64.zip', source['url'])
            self.assertEqual('espeak-test-1', source['version'])
            self.assertEqual(source, json.loads((root / 'catalog.json').read_text())['linux-arm64'])

    def test_changed_bytes_do_not_rewrite_catalog(self) -> None:
        """A modified native archive must be rejected before any release mutation is attempted.
        Its previous catalog remains unchanged for inspection and correction.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.prepare(root)
            before = (root / 'catalog.json').read_bytes()
            (root / 'linux-arm64.zip').write_bytes(b'changed-payload')
            with self.assertRaisesRegex(ValueError, 'verification failed'):
                release.catalog_for_release(root, 'owner/voice', 'v1')
            self.assertEqual(before, (root / 'catalog.json').read_bytes())

    def test_failed_asset_upload_never_publishes_latest(self) -> None:
        """A GitHub draft upload failure must prevent the subsequent public latest transition.
        The command boundary records only the failed draft creation attempt.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.prepare(root)
            arguments = ['publish', '--repository', 'owner/voice', '--tag', 'v1', '--prepared',
                '--directory', str(root), '--notes', str(root / 'notes.md')]
            with patch.object(sys, 'argv', arguments), patch.object(release.subprocess, 'run',
                side_effect=subprocess.CalledProcessError(1, 'gh')) as command:
                with self.assertRaises(subprocess.CalledProcessError):
                    release.main()
            self.assertEqual(1, command.call_count)
            self.assertIn('--draft', command.call_args.args[0])
            self.assertNotIn('--latest', command.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
