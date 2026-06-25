# Scripts

This directory will contain development, testing, packaging, and release helper
scripts.

Scripts should be documented, deterministic, and safe to run from a clean
checkout. They should not silently modify a user's QGIS or Python environment.


## Available Scripts

- `package_plugin.py`: builds `dist/pyforestscan_qgis.zip` and can optionally sync the plugin folder into a local QGIS profile.
- `validate_plugin_package.py`: validates the ZIP structure and required plugin files.
