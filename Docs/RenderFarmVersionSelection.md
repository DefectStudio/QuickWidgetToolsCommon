# Render farm version selection

The Rendering Tool has V1 and V2 checkboxes to the right of Send Render Queue
to Farm. They behave as a radio group: exactly one version stays selected.
Every new tool instance starts with V1 checked. Selection is not persisted.

The button passes the selection directly to the publisher. The confirmation
dialog identifies the destination version. It never falls back to the other
service if the selected version is unavailable or lacks credentials.

Administrator-provisioned local profiles:

- V1: `%LOCALAPPDATA%/DefectStudio/RenderFarm/cloud_connection.json`.
- V2: `%LOCALAPPDATA%/DefectStudio/RenderFarmV2/company-submit.json`.

Each profile contains the corresponding company's `api_url` and `submit_token`.
Profiles and credentials must remain outside Git. Separate environment overrides
are supported as `DEFECT_FARM_V1_API_URL` / `DEFECT_FARM_V1_SUBMIT_TOKEN` and
`DEFECT_FARM_V2_API_URL` / `DEFECT_FARM_V2_SUBMIT_TOKEN`.
The URL must match the selected company's V1 or V2 endpoint.

Legacy `DEFECT_FARM_SUBMIT_TOKEN` is accepted only when its corresponding
`DEFECT_FARM_API_URL` matches the selected service. A legacy token without a URL
is treated as V1. A previous V2 session override cannot redirect a V1 selection.

The selector only controls farm submission from the Rendering Tool. The existing
embedded Render Farm Viewer is unchanged.

Validation: 39 Python regression tests passed, including six routing tests.
The live Unreal widget's defaults, exclusive check events, active-choice re-click,
and actual Send button were tested with submission intercepted (V1, V2, V1).
The saved widget can be rebuilt with `Tests/Unreal/apply_render_farm_version_selector.py`
and checked in Unreal with `Tests/Unreal/verify_render_farm_version_selector.py`.
