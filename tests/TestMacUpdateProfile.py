"""The in-app updater installs Mac packages on macOS, not the Windows requirements.txt."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_ONLY = ("pywin32", "pycaw", "comtypes", "pydirectinput", "ok-pyside-minimal", "openvino")


def requirement_names(text):
    names = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            names.append(re.split(r"[\[<>=!~; ]", line, 1)[0].lower())
    return names


class TestMacUpdateProfile(unittest.TestCase):
    def macos_profile(self):
        try:
            from pyappify import standalone
        except ImportError:
            self.skipTest("pyappify is not installed")
        profiles = standalone.parse_profiles((ROOT / "pyappify.yml").read_text(encoding="utf-8"))
        return standalone.select_profile(profiles, "macOS")

    def test_macos_profile_installs_mac_requirements(self):
        profile = self.macos_profile()
        self.assertEqual(profile["name"], "macOS")
        self.assertEqual(profile["requirements"], "requirements-macos.txt")
        # The first profile's --no-deps would skip ok-script's dependencies.
        self.assertNotIn("--no-deps", profile["pip_args"].split())

    def test_windows_requirements_are_not_installable_on_mac(self):
        # Why the profile exists: the default requirements.txt pins Windows-only wheels.
        self.assertIn("pywin32", requirement_names((ROOT / "requirements.txt").read_text(encoding="utf-8")))

    def test_mac_requirements_have_no_windows_only_packages(self):
        names = requirement_names((ROOT / "requirements-macos.txt").read_text(encoding="utf-8"))
        self.assertFalse(set(names) & set(WINDOWS_ONLY), names)
        self.assertIn("pyappify", names)

    def test_mac_requirements_carry_the_ok_script_build_version(self):
        # The updater reinstalls only when this file changes, and the upstream
        # sync bumps this line whenever ok-script changes.
        ok_script = json.loads((ROOT / ".github/upstream.json").read_text())["ok_script"]
        text = (ROOT / "requirements-macos.txt").read_text(encoding="utf-8")
        self.assertIn(f"# ok-script build: {ok_script}+macos.1", text)
        self.assertIn("-e ./ok-script[", text)

    def test_launchers_select_the_macos_profile(self):
        self.assertIn("export PYAPPIFY_APP_PROFILE=macOS", (ROOT / "run_macos.sh").read_text())
        for name in ("config.py", "main_updater.py"):
            self.assertIn("os.environ.setdefault('PYAPPIFY_APP_PROFILE', 'macOS')", (ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
