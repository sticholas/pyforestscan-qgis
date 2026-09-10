"""Optional runtime safety and packaging tests without Qt or downloads."""
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.point_cloud.runtime import ViewerRuntimeService, runtime_spec, viewer_environment


class ViewerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = ViewerRuntimeService(resolve_backend_paths(self.root, BackendPlatform.WINDOWS))

    def test_missing_runtime_is_optional_and_read_only(self):
        before = list(self.root.rglob("*"))
        with self.assertRaisesRegex(RuntimeError, "needs setup"):
            self.service.executable()
        self.assertEqual(list(self.root.rglob("*")), before)

    def test_setup_requires_confirmation_before_mutation(self):
        with self.assertRaises(PermissionError):
            self.service.setup()
        self.assertEqual(list(self.root.rglob("*")), [])

    def test_environment_excludes_host_qt_python_and_conda(self):
        poison = {"PYTHONPATH": "qgis/dependencies", "PYTHONHOME": "qgis", "QT_PLUGIN_PATH": "qgis/plugins",
                  "QML2_IMPORT_PATH": "qgis/qml", "CONDA_PREFIX": "science", "PATH": "qgis/bin"}
        with patch.dict(os.environ, poison):
            env = viewer_environment(self.root / "python.exe")
        for key in poison:
            if key == "PATH":
                continue
            if os.name == "nt" and key.startswith(("QT_", "QML")):
                self.assertIn(key, env)
                self.assertNotEqual(env[key], poison[key])
                self.assertNotIn("qgis", env[key].lower())
            else:
                self.assertNotIn(key, env)
        self.assertNotIn("qgis", env["PATH"].lower())
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(self.root))

    def test_windows_environment_uses_only_runtime_local_qt_plugins(self):
        executable = self.root / "python.exe"
        pyside = self.root / "Lib" / "site-packages" / "PySide6"
        poison = {
            "QT_PLUGIN_PATH": r"C:\\Program Files\\QGIS 3.44\\apps\\Qt5\\plugins",
            "QT_QPA_PLATFORM_PLUGIN_PATH": r"C:\\Program Files\\QGIS 3.44\\apps\\Qt5\\plugins\\platforms",
            "QML2_IMPORT_PATH": r"C:\\Program Files\\QGIS 3.44\\apps\\Qt5\\qml",
            "PATH": r"C:\\Program Files\\QGIS 3.44\\bin;C:\\Windows\\System32",
            "SystemRoot": r"C:\\Windows",
        }
        with patch.dict(os.environ, poison):
            env = viewer_environment(executable, platform_name="nt")
        self.assertEqual(env["QT_PLUGIN_PATH"], str(pyside / "plugins"))
        self.assertEqual(env["QT_QPA_PLATFORM_PLUGIN_PATH"], str(pyside / "plugins" / "platforms"))
        self.assertEqual(env["QT_QPA_PLATFORM"], "windows")
        self.assertEqual(env["QML2_IMPORT_PATH"], str(pyside / "qml"))
        self.assertNotIn("QGIS", env["PATH"])
        self.assertIn(str(pyside), env["PATH"])

    def test_runtime_pointer_cannot_escape_owned_directory(self):
        executable = self.root / "outside/python.exe"
        executable.parent.mkdir()
        executable.touch()
        self.service.root.mkdir()
        self.service.config_path.write_text(json.dumps({"python": str(executable), "spec_sha256": runtime_spec()[1]}))
        with self.assertRaisesRegex(RuntimeError, "needs repair"):
            self.service.executable()

    def test_ui_callback_cannot_remove_activated_runtime(self):
        self.service.paths.micromamba_executable.parent.mkdir()
        self.service.paths.micromamba_executable.touch()
        commands = []
        class Process:
            returncode = 0
            def __init__(inner, command, **kwargs):
                commands.append((command, kwargs))
                if "--prefix" in command:
                    prefix = Path(command[command.index("--prefix") + 1])
                    executable = prefix / ("python.exe" if os.name == "nt" else "bin/python")
                    executable.parent.mkdir(parents=True, exist_ok=True)
                    executable.touch()
            def poll(inner): return 0
        def progress(message):
            if message == "Viewer component ready":
                raise RuntimeError("UI destroyed")
        with patch("pyforestscan_qgis.core.point_cloud.runtime.subprocess.Popen", Process), patch(
            "pyforestscan_qgis.core.point_cloud.runtime.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "6.11.2\n", "")):
            executable = self.service.setup(confirmed=True, progress=progress)
        self.assertTrue(executable.is_file())
        self.assertEqual(self.service.executable(), executable.resolve())
        self.assertIn("--isolated", commands[1][0])
        self.assertIn("--only-binary=:all:", commands[1][0])
        self.assertEqual(commands[1][1]["env"]["PYTHONNOUSERSITE"], "1")
        self.assertFalse(self.service.paths.environment_path.exists())

    def test_navigation_and_renderer_isolation(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "pyforestscan_qgis/ui/mission_control.py").read_text()
        tree = ast.parse(source)
        names = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                     any(isinstance(target, ast.Name) and target.id == "PAGE_NAMES" for target in node.targets))
        self.assertEqual(ast.literal_eval(names.value), ("Process", "Point Cloud", "Tools & Setup"))
        page = (root / "pyforestscan_qgis/ui/point_cloud_page.py").read_text()
        self.assertNotIn("import PySide6", page)
        self.assertNotIn("import pdal", page)
        self.assertIn("worker.stop()", page)
        self.assertNotIn("self.worker.wait(", page)

    def test_packaged_assets_have_recorded_hashes(self):
        import hashlib
        root = Path(__file__).resolve().parents[1] / "pyforestscan_qgis/viewer/assets"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["commit"], "5636cd471d9eb464969e758be45c44d7613d3859")
        for name, item in manifest["files"].items():
            with self.subTest(name=name):
                data = (root / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                self.assertEqual(len(data), item["bytes"])
        self.assertLess(sum(item["bytes"] for item in manifest["files"].values()), 5_000_000)

    def test_embedded_renderer_owns_one_timer_loop_and_recovers_stale_camera(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "pyforestscan_qgis/viewer/viewer.js").read_text()
        self.assertIn("viewer.renderer.setAnimationLoop(null)", source)
        self.assertIn('state.render_loop = "INTERVAL_16_MS"', source)
        self.assertIn("setInterval(() =>", source)
        self.assertIn("syncRenderCameras();", source)
        self.assertIn("cloud.minimumNodePixelSize = threshold", source)
        self.assertIn('fitSource("source_open")', source)


if __name__ == "__main__":
    unittest.main()
