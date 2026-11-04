# VIEWE Smart Panel for Home Assistant

A custom Home Assistant integration for VIEWE smart panels, with shared profiles
and a sidebar editor. Version **0.2.1** supports **ESPHome Native API** and
optional legacy **MQTT** transport. Widgets include Lighting, Weather, Switch,
Actions, Clock, Temperature / humidity, Thermostat and the BC-250 switch preset.

**Development version:** local tests pass, but this version still requires
verification in a running Home Assistant instance and on the physical display.
Firmware compatible with the selected transport is required.

## Features

- Initial setup through Config Flow; one profile hub per Home Assistant instance.
- Sidebar editor with **Profiles** and **Panels** sections.
- New profiles start with Weather, followed by Lighting.
- Multiple widget instances: up to 16 visible widgets / 8 KB for ESPHome;
  the legacy editor storage supports up to 64 pages.
- Page names, entity selection, visibility, and ordering by drag and drop or buttons.
- Profile deletion with confirmation and protection against deleting assigned profiles.
- Automatic lighting capabilities in ESPHome; optional manual types for legacy MQTT.
- Configurable “Take an umbrella” banner settings.
- Separate **Save** and **Apply** actions, with independent draft and applied versions.
- Validation before applying, and a delivery result for each assigned panel.
- Delivery of the latest applied version when an unavailable panel reconnects.
- Compatible applied profiles in HA; legacy MQTT also sends an on-panel catalog.
- Native API state/control/forecast handling through the standard ESPHome integration;
  legacy MQTT retains its state and command adapter.
- Panel acknowledgements, heartbeat monitoring, and bounded command deduplication.

The sidebar editor follows the Home Assistant user language: Ukrainian uses
`frontend/locales/uk.js`; English and other languages use `frontend/locales/en.js`.
Both files share one editor implementation and must be updated together.
New page names follow the current language; existing names are preserved.
The integration setup flow provides English strings and a Ukrainian translation.

## ESPHome Native API (0.2.1)

The new ESPHome firmware is supported alongside the legacy MQTT firmware.
See [ESPHome setup and the widget forms](docs/esphome-native-api.md) before
assigning a profile. The editor now includes Clock, Temperature / humidity and
Thermostat widgets, label visibility, internal-page selection and icon options.

Each widget now has a **Demo** checkbox for local sample data and interactive
controls without real HA entities. See the Native API guide for firmware requirements.

## Requirements

- Home Assistant with the standard ESPHome integration for Native API panels.
- For legacy panels only: a configured MQTT integration connected to a broker.
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
7. Leave MQTT disabled for ESPHome. For legacy firmware, enable MQTT and keep
   the topic prefix `viewe` unless your panels use a different prefix.
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
and refreshes online panels' catalogs. Offline MQTT panels receive the authoritative
catalog and active configuration on reconnect; `profile: null` clears an MQTT
assignment. Native API unassignment queues a device reset to YAML.

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
template compatibility, Native API discovery/receipts/reset/resume, firmware limits,
language selection, locale parity, and editor rendering.
Frontend tests use a lightweight DOM boundary fake, not a real browser.

The GitHub validation workflow checks local tests, syntax, Home Assistant integration
metadata with hassfest, and HACS repository requirements after publication.
Remote validation has not been run yet. See
[HACS publishing](docs/hacs-publishing.md) for the remaining publication steps.

Runtime verification still requires a test Home Assistant instance, desktop and
mobile inspection of the editor and compatible firmware. An MQTT broker is
required only when verifying legacy transport.

## Current limitations

- Native API discovery uses HA ESPHome runtime fields isolated in `native.py`.
  Real HA runtime compatibility must be checked; no minimum HA version is claimed.
- ESPHome profile compatibility uses the exact bundled firmware schema. Legacy
  MQTT compatibility uses advertised template versions and excludes new options.
- ESPHome supports automatic lighting types and whole-hour umbrella settings.
  Existing MQTT profiles with manual types or minute offsets need adjustment
  before Native API assignment; conversion does not silently change them.
- Native profile selection is currently in HA; the component has no profile
  catalog action. Display-side reset returns to YAML and blocks remote overrides
  until explicitly resumed in HA.
- Screensaver and hardware settings remain in ESPHome YAML.
- BC-250 requires a guard script installed separately in HA; its existence is
  checked, but custom script behavior cannot be inferred by this integration.
- Diagnostic entities, panel deletion, export/import and display-shape adaptation
  are not implemented. Editor status updates use **Refresh status**.
- Legacy MQTT's bounded command cache is not a persistent replay journal.
  Configure broker topic ACLs for legacy devices; panel IDs are not credentials.

## Documentation

- [ESPHome Native API setup and widget forms](docs/esphome-native-api.md)

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

## Switch template (legacy MQTT)

The Switch template selects a `switch.*` entity and sends `turn_on`, `turn_off`, or `toggle` without lighting parameters. Firmware must advertise `switch: 1`; older panels cannot apply profiles containing a visible switch page. State updates come from HA. Update the integration and firmware together.

Switch support is packaged in version 0.1.4. Add a page, choose Switch, select
a switch entity, then Save and Apply the profile. New profiles still start with
Weather and Lighting; Switch is added explicitly. Runtime verification of
Switch in HA and on the panel is pending.

## Scripts and automations (2026-10-05)

The Actions template displays one or two script/automation names. Two targets occupy the upper and lower halves separated by a horizontal line. Tap a name to run it; unavailable targets are disabled independently. Add Scripts / automations in the profile editor, select 1 or 2 actions, choose script.* or automation.* entities, and optionally supply display names (blank uses the HA friendly name when applying). Update both firmware and integration before applying. Firmware advertises actions template version 1. Device and real HA verification remain pending.

Scripts use script.turn_on. Automations use automation.trigger with HA default condition skipping, including disabled automations. This runs actions manually; it does not enable the automation. Script variables and simulated trigger data are not configurable in this template.
## BC-250 power page (legacy MQTT)

Add a **BC-250** page in the profile editor. Select the ESPHome **BC250 Power**
button and **BC250 Running** binary sensor (TPMS1); entity IDs depend on your
installation. Save and apply the profile after updating firmware that advertises
`capabilities.templates.bc250: 1`. ESPHome setup uses the guarded switch preset
described in the [Native API guide](docs/esphome-native-api.md).

The page starts only while confirmed off. The Steam icon pulses for up to 10
seconds, returns to gray on timeout and allows retry; on confirmation it becomes
blue/white. Offline is crossed out and disabled. HA rechecks Running before
pressing the controller button; the page cannot request shutdown. The UI timeout
does not change ESPHome's own startup deadlines or cut PSU power. Runtime checks
on the panel and in Home Assistant remain pending.
