"""Guards for the one-file build: same inputs as the folder build, user data beside the EXE."""
from __future__ import annotations

import re
import struct
import unittest
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    # newline="" keeps CRLF visible, so the .cmd line-ending check below is real.
    with (ROOT / name).open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _analysis(spec: str) -> str:
    match = re.search(r"a = Analysis\(.*?\)\r?\n(?=pyz = PYZ)", spec, re.S)
    assert match, "Analysis block not found"
    return re.sub(r"\s+", " ", match.group(0))


class OneFilePackagingTests(unittest.TestCase):
    def test_both_specs_collect_the_same_inputs(self):
        folder, single = _read("ManifestCleaner.spec"), _read("ManifestCleaner-onefile.spec")
        self.assertEqual(_analysis(folder), _analysis(single))
        for line in ("hiddenimports = [profile.adapter for profile in profiles.values()]",
                     "profiles = run_path(str(root / 'manifest_cleaner' / 'carriers' / '__init__.py'))"):
            self.assertIn(line, folder)
            self.assertIn(line, single)

    def test_onefile_spec_puts_everything_in_the_exe(self):
        single = _read("ManifestCleaner-onefile.spec")
        self.assertIn("EXE(pyz, a.scripts, a.binaries, a.datas, splash, splash.binaries, []", single)
        self.assertNotIn("COLLECT(", single)
        self.assertNotIn("exclude_binaries=True", single)
        self.assertIn("console=False", single)
        # The folder build is unchanged: support files stay in a directory.
        folder = _read("ManifestCleaner.spec")
        self.assertIn("COLLECT(", folder)
        self.assertIn("exclude_binaries=True", folder)

    def test_only_the_onefile_build_shows_a_splash_and_the_image_is_valid(self):
        single, folder = _read("ManifestCleaner-onefile.spec"), _read("ManifestCleaner.spec")
        self.assertIn("Splash(str(root / 'assets' / 'splash.png')", single)
        self.assertIn("text_pos=None", single)
        self.assertNotIn("Splash", folder)
        image = (ROOT / "assets" / "splash.png").read_bytes()
        self.assertEqual(image[:8], bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10]))
        width, height = struct.unpack(">II", image[16:24])
        self.assertEqual((width, height), (560, 180))
        self.assertLess(len(image), 100_000)

    def test_build_script_writes_beside_not_over_the_folder_build(self):
        script = _read("BUILD_ONEFILE.cmd")
        self.assertIn("ManifestCleaner-onefile.spec", script)
        self.assertIn('--distpath "dist\\onefile"', script)
        self.assertIn('--workpath "build\\onefile"', script)
        self.assertNotIn("dist\\ManifestCleaner", script)
        self.assertIn("unittest discover", script)
        # .gitattributes keeps *.cmd as CRLF in the working tree; a bare LF breaks cmd labels.
        self.assertEqual(script.count("\r\n"), script.count("\n"))

    def test_user_data_is_never_placed_in_the_temp_unpack_folder(self):
        # In a one-file build sys._MEIPASS is deleted on exit, so settings and the recent list
        # must follow sys.executable, which is the real .exe path.
        offenders = [str(path.relative_to(ROOT)) for path in (ROOT / "manifest_cleaner").rglob("*.py")
                     if "_MEIPASS" in path.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])
        gui = _read("manifest_cleaner/gui.py")
        self.assertIn('Path(sys.executable).parent if getattr(sys, "frozen", False)', gui)
        self.assertIn("_recent_file_path(self.config_path)", gui)


class SplashHookTests(unittest.TestCase):
    def test_close_splash_is_silent_without_pyinstaller_and_closes_once_inside_it(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        from manifest_cleaner import gui

        with patch.dict(sys.modules, {"pyi_splash": None}):  # None makes the import raise ImportError
            gui._close_splash()
        closing = Mock()
        with patch.dict(sys.modules, {"pyi_splash": SimpleNamespace(close=closing)}):
            gui._close_splash()
        closing.assert_called_once_with()
        failing = Mock(side_effect=RuntimeError("splash already closed"))
        with patch.dict(sys.modules, {"pyi_splash": SimpleNamespace(close=failing)}):
            gui._close_splash()  # must not stop the app from starting
        failing.assert_called_once_with()

    def test_main_closes_the_splash_after_the_window_is_built_and_before_the_event_loop(self):
        from unittest.mock import patch

        from manifest_cleaner import gui

        order = []
        with ExitStack() as stack:
            stack.enter_context(patch.object(gui, "_enable_dpi_awareness"))
            tk_class = stack.enter_context(patch.object(gui.tk, "Tk"))
            stack.enter_context(patch.object(gui, "ManifestApp", side_effect=lambda root: order.append("window")))
            stack.enter_context(patch.object(gui, "_close_splash", side_effect=lambda: order.append("splash")))
            tk_class.return_value.mainloop.side_effect = lambda: order.append("loop")
            gui.main()
        self.assertEqual(order, ["window", "splash", "loop"])


if __name__ == "__main__":
    unittest.main()
