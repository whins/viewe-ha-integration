# VIEWE Smart Panel for Home Assistant

A custom Home Assistant integration for VIEWE smart panels, with shared profiles
and a sidebar editor. The first page templates are **Lighting** and **Weather**.
Panel communication uses the MQTT integration already configured in Home Assistant.

**Development version:** this integration has not yet been tested in a running
Home Assistant instance or on a physical panel. The existing panel firmware does
not implement the MQTT contract yet. You can test the profile editor independently;
physical panel control requires compatible firmware.

## Features

- Initial setup through Config Flow; one profile hub per Home Assistant instance.
- Sidebar editor with **Profiles** and **Panels** sections.
- New profiles start with Weather, followed by Lighting.
- Multiple instances of each template, up to 64 pages per profile.
- Page names, entity selection, visibility, and ordering by drag and drop or buttons.
- Profile deletion with confirmation and protection against deleting assigned profiles.
- Automatic or manually selected compatible lighting control types.
- Configurable “Take an umbrella” banner settings.
- Separate **Save** and **Apply** actions, with independent draft and applied versions.
- Validation before applying, and a delivery result for each assigned panel.
- Delivery of the latest applied version when an unavailable panel reconnects.
- A catalog of compatible applied profiles for selection on the panel.
- Lighting commands, entity state updates, and raw daily/hourly weather forecasts.
- Panel acknowledgements, heartbeat monitoring, and bounded command deduplication.

The sidebar editor follows the Home Assistant user language: Ukrainian uses
`frontend/locales/uk.js`; English and other languages use `frontend/locales/en.js`.
Both files share one editor implementation and must be updated together.
New page names follow the current language; existing names are preserved.
The integration setup flow provides English strings and a Ukrainian translation.

## Requirements

- Home Assistant with a configured MQTT integration connected to a broker.
- An administrator account for access to the profile editor.
- HACS for installation through a custom GitHub repository, or file access for
  manual installation.
- Compatible panel firmware for panel discovery, configuration delivery, and control.

A minimum supported Home Assistant version has not been established by runtime
testing yet.

## Installation with HACS (Home Assistant OS)

After this repository has been published as a public GitHub repository:

1. Open **HACS** in Home Assistant.
2. Open the menu and select **Custom repositories**.
3. Paste `https://github.com/whins/viewe-ha-integration` and select **Integration**
   as the category.
4. Add the repository, find **VIEWE Smart Panel**, and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and select
   **VIEWE Smart Panel**.
7. Keep the MQTT topic prefix `viewe`, unless you need to isolate a different set
   of panels.
8. Open **VIEWE Smart Panel** in the sidebar.

HACS downloads the integration files; adding the integration through Home Assistant
is a separate step. A GitHub release is optional for custom repository installation:
HACS can download the default branch. See the official
[HACS integration requirements](https://www.hacs.dev/docs/publish/integration/)
and [custom repository instructions](https://www.hacs.dev/docs/faq/custom_repositories/).

## Manual installation

1. Copy `custom_components/viewe_smart_panel` into
   `<config>/custom_components/viewe_smart_panel` on the Home Assistant machine.
   On Home Assistant OS, the resulting manifest path is normally
   `/config/custom_components/viewe_smart_panel/manifest.json`.
2. Restart Home Assistant.
3. Follow steps 6–8 in the HACS installation instructions above.

## First profile

1. Create a profile. Its page list contains Weather, followed by Lighting.
2. Configure each visible page and select its Home Assistant entity.
3. **Save** stores the draft without updating panels.
4. **Apply** validates the saved profile and records an applied snapshot, then
   sends it to all panels assigned to that profile.
5. Once a panel with compatible firmware connects, assign an applied profile in
   **Panels**. Use **Refresh status** to see its acknowledgement.

You can save an unfinished profile or a profile with no visible pages. Applying
requires at least one visible page and valid entity bindings for all visible pages.
An unavailable panel receives the latest applied snapshot after reconnecting;
unapplied draft changes are never delivered.

To delete a profile, use **Delete profile** in the profile list and confirm.
Assigned profiles cannot be deleted: first assign another profile or select
**No profile** in Panels. Deletion removes both the draft and applied snapshot
and refreshes online panels' catalogs. Offline panels receive the authoritative
catalog and active configuration on reconnect; `profile: null` clears an assignment.

Broker credentials belong exclusively to the Home Assistant MQTT integration.
Do not add secrets, local `configuration.yaml`, or `.storage` files to this repository.

## Development checks

```text
python scripts/check_packaging.py
python -m unittest discover -s tests -v
python -m compileall -q custom_components
node --check custom_components/viewe_smart_panel/frontend/panel.js
node --test tests/test_frontend.mjs
```

The model and MQTT behavior tests use explicit fakes at Home Assistant boundaries.
They verify local logic, not actual loading or compatibility with an installed
Home Assistant version. The suite covers profile lifecycle, MQTT behavior,
template compatibility, language selection, locale parity, and editor rendering.
Frontend tests use a lightweight DOM boundary fake, not a real browser.

The GitHub validation workflow checks local tests, syntax, Home Assistant integration
metadata with hassfest, and HACS repository requirements after publication.
Remote validation has not been run yet. See
[HACS publishing](docs/hacs-publishing.md) for the remaining publication steps.

Runtime verification still requires a test Home Assistant instance, desktop and
mobile inspection of the editor, an MQTT broker, and compatible firmware or a
panel emulator.

## Current limitations

- Compatibility checks template versions (`lighting: 1`, `weather: 1`).
  Encoder and touch requirements were removed in version 0.1.2; legacy fields
  are ignored and removed when loaded or saved.
  Layout adaptation for different display shapes and sizes is not implemented.
- Automatic lighting type selection is provisional: ADDRESS when color support
  and an effect list are available, then RGBCCT, RGBW, RGB, CCT, MONO. These rules need
  verification against real entities. Color-temperature-only lights now
  use CCT control. CCT is selectable for color_temp or rgbww capabilities;
  RGB and RGBW both use the firmware rgbw screen.
- Weather passes raw forecasts and entity units. Time-slot aggregation, the
  meaning of the large overview temperature, the start of the umbrella display
  window, and missing-forecast display behavior remain open design questions.
- Color preview, knob confirmation/cancellation, parameter restoration, and
  encoder behavior belong to a future firmware implementation.
- Diagnostic entities, Home Assistant device registration, panel deletion,
  and export/import are not implemented.
- Editor status updates are manual, using **Refresh status**.
- The command cache holds up to 1024 entries in memory. Firmware must not replay
  old commands after a Home Assistant restart or after they leave the cache.
- Configure MQTT access and topic ACLs in the broker. Panel IDs are not credentials;
  each panel should be restricted to its permitted topics.

## Documentation

- [MQTT protocol v1](docs/mqtt-protocol.md)
- [HACS packaging and publication](docs/hacs-publishing.md)
- [Contributor and agent instructions](AGENTS.md)

The firmware project is maintained separately as `viewe-smart-panel`. In a sibling
checkout, the agreed design requirements are in its `docs/panel-profiles-design.md`,
`docs/lighting-design.md`, and `docs/weather-design.md`. That sibling checkout is
not required to install this integration.

The implementation follows Home Assistant's
[Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
and [custom panel](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/)
interfaces. All runtime assets, including the sidebar JavaScript, are bundled inside
`custom_components/viewe_smart_panel`.

## CCT support (0.1.3)

Update panel firmware before applying a CCT profile: previous firmware rejects
that resolved type. After updating HA, save and apply existing AUTO profiles
again so temperature-only lights resolve to CCT instead of MONO. CCT has a
single temperature button opening cct; RGB and RGBW both open rgbw.

## Switch template

The Switch template selects a `switch.*` entity and sends `turn_on`, `turn_off`, or `toggle` without lighting parameters. Firmware must advertise `switch: 1`; older panels cannot apply profiles containing a visible switch page. State updates come from HA. Update the integration and firmware together.
