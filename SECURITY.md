# Security Policy

PyForestScan QGIS is planned as a desktop QGIS plugin that processes local lidar
and vector data. Security considerations include file handling, dependency
management, and safe execution of external scientific libraries.

## Supported Versions

No public release is currently supported. Security support will be defined once
the plugin reaches an installable release.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the maintainers instead of
opening a public issue. Include:

- Affected version or commit.
- Operating system and QGIS version.
- Steps to reproduce.
- Example inputs when safe to share.
- Impact and suggested mitigation, if known.

## Security Principles

- Do not execute user-provided scripts.
- Treat all lidar, raster, vector, and project files as untrusted input.
- Avoid writing outside user-selected output locations.
- Pin and document release dependencies.
- Prefer transparent error messages that do not expose sensitive paths in
  public logs.

