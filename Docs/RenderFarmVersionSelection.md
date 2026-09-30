# Render farm version selection

The Rendering Tool has V1 and V2 checkboxes to the right of Send Render Queue
to Farm. Clicking either checkbox selects it and clears the other, keeping the
active choice selected even when it is clicked again.

Initialization preserves the checkboxes' current states, so new tool instances
use the defaults saved in the widget. Set `FarmVersionV1` unchecked and
`FarmVersionV2` checked in the widget to start on V2. Selection is not persisted
between tool instances. If both boxes are checked or both are unchecked, the
publisher rejects the selection until one version is chosen.

The Blueprint call remains `render_farm_version_selector.initialize(v1_checkbox,
v2_checkbox)`. After editing the Python module in an open editor session, reload
it with `importlib.reload(render_farm_version_selector)` and reopen the tool,
or restart Unreal, to load the updated initialization behavior.

The button passes the selection directly to the publisher. The confirmation
dialog identifies the destination version. It never falls back to the other
service if the selected version is unavailable or lacks credentials.

V2 works immediately with the company submit credential bundled in
`Content/Python/render_farm_v2_submit.json`. Artists only update the complete
plugin and select V2; no credential installation or environment setup is needed.
The file is intentionally distributed and tracked with the plugin, as authorized
by the company. It contains only the V2 submit credential, with no worker or
manager credential. Anyone who can read the plugin can read this shared submit
credential; rotating it requires updating the bundled file and redistributing.

Optional administrator-provisioned local profiles (take priority over the bundle):

- V1: `%LOCALAPPDATA%/DefectStudio/RenderFarm/cloud_connection.json`.
- V2: `%LOCALAPPDATA%/DefectStudio/RenderFarmV2/company-submit.json`.

Each profile contains the corresponding company's `api_url` and `submit_token`.
Machine-local profiles remain outside Git; the bundled V2 submit profile is the
explicit exception. Separate environment overrides
are supported as `DEFECT_FARM_V1_API_URL` / `DEFECT_FARM_V1_SUBMIT_TOKEN` and
`DEFECT_FARM_V2_API_URL` / `DEFECT_FARM_V2_SUBMIT_TOKEN`.
The URL must match the selected company's V1 or V2 endpoint.

Legacy `DEFECT_FARM_SUBMIT_TOKEN` is accepted only when its corresponding
`DEFECT_FARM_API_URL` matches the selected service. A legacy token without a URL
is treated as V1. A previous V2 session override cannot redirect a V1 selection.

The selector only controls farm submission from the Rendering Tool. The existing
embedded Render Farm Viewer is unchanged.

Routing regression tests cover a fresh account with no profiles or environment
credentials, administrator overrides, invalid bundles, and V1/V2 isolation.
All 45 Python regression tests pass. The bundled connection was also verified
against the hosted V2 service with no local profile or credential environment:
the database was connected and authentication returned the `submit` role.
The original live Unreal widget's exclusive check events, active-choice re-click,
and actual Send button were tested with submission intercepted (V1, V2, V1).
The current live verification script checks the saved widget defaults instead
of requiring V1 and intercepts submission while testing either starting version.
The saved widget can be rebuilt with `Tests/Unreal/apply_render_farm_version_selector.py`
and checked in Unreal with `Tests/Unreal/verify_render_farm_version_selector.py`.
The rebuild helper preserves existing checkbox defaults; newly created selectors
start with V2 selected. Pure Python selector tests cover default preservation,
exclusive clicks, reinitialization, and rejection of ambiguous selections.
