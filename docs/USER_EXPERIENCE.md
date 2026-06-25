# User Experience

The primary user experience should be QGIS Processing workflows that are clear,
discoverable, and reproducible.

## UX Principles

- Prefer Processing algorithms over custom dialogs for scientific workflows.
- Use plain language for parameters while preserving scientific precision.
- Validate early and explain what the user can do next.
- Make defaults explicit and documented.
- Keep generated outputs organized and predictable.
- Support QGIS Model Builder and Processing history.

## Parameter Design

Parameters should:

- Use QGIS-native parameter types where possible.
- Avoid hidden assumptions.
- Include meaningful descriptions.
- Clearly distinguish required and optional inputs.
- Use units in labels where relevant.

## Error Design

Errors should:

- Identify the invalid input or missing dependency.
- Explain whether the problem is with QGIS, PyForestScan, input data, or plugin
  parameters.
- Avoid raw tracebacks unless shown in an advanced diagnostic context.

