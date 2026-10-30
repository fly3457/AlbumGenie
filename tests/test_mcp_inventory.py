"""Check advisory install states without launching InDesign or installing Nutria."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell') or shutil.which('pwsh')


@unittest.skipUnless(POWERSHELL and shutil.which('node'), 'PowerShell and Node required')
class McpInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='albumgenie-mcp-inventory-')
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name) / 'nutria'

    def write(self, path, value='{}'):
        target = self.runtime / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding='utf-8')

    def check(self, state, exit_code=2, env=None):
        result = subprocess.run(
            [POWERSHELL, '-NoProfile', '-File', str(ROOT/'tools/check_indesign_mcp.ps1'),
             '-RuntimePath', str(self.runtime)],
            cwd=self.temp.name, capture_output=True, text=True, encoding='utf-8', env=env,
        )
        self.assertEqual(result.returncode, exit_code, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], state)
        self.assertEqual(report['clientToolDiscovery'], 'not-checked-by-this-script')
        self.assertTrue(report['liveBridgeHealth'].startswith('not-probed'))
        return report

    def package(self):
        self.write('package.json', '{"name":"indesign-nutria-mcp","version":"1.4.2"}')

    def test_missing_runtime(self):
        self.check('missing-runtime')
        self.assertFalse(self.runtime.exists())

    def test_wrong_package(self):
        self.write('package.json', '{"name":"unrelated-project"}')
        self.check('unexpected-or-invalid-package')

    def test_invalid_package_json(self):
        self.write('package.json', 'invalid')
        self.check('unexpected-or-invalid-package')

    def test_missing_dependencies(self):
        self.package()
        self.check('missing-dependencies')

    def test_missing_build(self):
        self.package()
        self.write('node_modules/@modelcontextprotocol/sdk/package.json')
        self.check('needs-build')

    def test_existing_files_do_not_assert_live_health(self):
        self.package()
        self.write('node_modules/@modelcontextprotocol/sdk/package.json')
        self.write('dist/index.js', '// Inventory fixture, never executed.')
        report = self.check('installed-unverified', exit_code=0)
        self.assertFalse(report['albumExtensionSourcePresent'])

    def test_missing_node(self):
        env = os.environ.copy()
        env['PATH'] = self.temp.name
        self.check('missing-or-unsupported-node', env=env)


if __name__ == '__main__':
    unittest.main()
