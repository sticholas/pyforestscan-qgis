# PBM Runtime Version Contract

PBM processing protocol 2 adds the `inspect_runtime_contract` command. It reports backend API and protocol versions, runner SHA256, plugin version, Python executable/version, dependency versions, and module file locations.

Before a production subprocess starts scientific work, the plugin compares the backend protocol with the request protocol. An incompatible or unreadable identity is blocked with **Processing backend needs an update** and directs the user to Repair Backend.

PBM backend Python is launched with the plugin parent as its working directory, so normal ZIP-installed execution imports the active plugin's `pyforestscan_qgis` package. Every job records the observed paths in `backend_module_locations.json`; this evidence remains authoritative if install layout or Python import behavior changes.

