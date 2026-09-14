# QGIS Profile Deployment

Plugin replacement and Processing Engine repair are independent operations. Reinstalling the plugin must not remove or modify the user-local backend under `%LOCALAPPDATA%\PyForestScan\backend`.

For Windows development builds, close QGIS and run:

```powershell
python scripts/install_qgis_plugin.py --zip dist/pyforestscan_qgis.zip --profile default --comparison-output qgis_profile_deployment_comparison.json
```

The installer extracts to staging, verifies `build_info.json`, removes only the exact `pyforestscan_qgis` plugin directory, copies the new package, and verifies the installed hashes. Replacement semantics ensure deleted or obsolete Python modules cannot survive as an overlay. Restart QGIS after installation so stale imported modules cannot remain in `sys.modules`.

Use `--verify-only` to compare an existing profile against the ZIP without changing it. `--profiles-root` supports nonstandard profile locations, and `--tested-plugin-root` adds an isolated QA profile to the comparison report.

QGIS Plugin Manager ZIP installation remains supported for normal users. During development or manual replacement, a complete directory replacement plus QGIS restart is required.
