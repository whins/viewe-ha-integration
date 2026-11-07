# VIEWE Smart Panel — Home Assistant integration

- 2026-10-09: BC-250 start-only template added (`bc250: 1`). Editor selects
  BC250 Power (`button.*`) and BC250 Running / TPMS1 (`binary_sensor.*`).
  Both entities must be available; `start` rechecks confirmed off before
  button.press because the controller's Power button toggles shutdown when on.
  Panel pulse timeout is 10 seconds. Physical/HA runtime verification pending.

- 2026-10-23: Version 0.2.0 adds ESPHome Native API profile delivery alongside
  optional legacy MQTT. Standard HA ESPHome owns the API session and credentials.
  Native discovery uses RuntimeEntryData (device_info/services/available) isolated
  in native.py and registry MAC/config-entry identity. All four VIEWE actions are
  required; duplicate node names are ignored. Firmware profile.py is bundled
  verbatim as native_profile_schema.py; keep it synchronized with the component.
  New forms cover clock, room sensors, thermostat, label visibility, disabled
  internal pages and icon/layout options. BC-250 requires the bundled HA guard
  script or an equivalent selected script. Local reset latches persist; only an
  explicit assignment/resume may call allow_remote_profiles. Native profiles
  are limited to 16 widgets/8192 UTF-8 bytes. HA runtime verification is pending;
  local boundary tests do not prove installation or hardware behavior.

- 2026-11-05: Version 0.2.1 adds per-widget demo (strict boolean, default
  false) to both editor languages and Native profile delivery. Visible demos
  bypass live entity/guard existence checks but retain structural validation.
  Normal profile payloads omit demo for older firmware compatibility; legacy
  MQTT panels reject demo profiles and MQTT demo commands are blocked. The
  bundled firmware schema fills missing demo bindings. Update display firmware
  before enabling Demo. Live HA/display verification and installation are pending.

- 2026-11-05: Version 0.2.2 fixes stale editor modules with release-specific
  static asset paths and custom element names, and shows the frontend version.
  Panels polls every five seconds; disconnect cancels its timer and invalidates
  late responses, while unsaved profile forms are preserved. Setup guidance is
  shown when there are no VIEWE Native nodes. A user's missing display was not
  added to HA's standard ESPHome integration: Wi-Fi alone is insufficient.
  Preserve legacy MQTT records. Restart HA after updating Python code.

- 2026-11-05: Version 0.2.3 adds panel removal and Online/Offline badges.
  Removal persists before clearing transient state, leaves HA devices/profiles
  untouched, and suppresses rediscovery for this HA session. Explicit Refresh
  clears suppression, probes ESPHome and requests MQTT announcements. Background
  get/poll and late receipts must not resurrect a removed record. Rediscovered
  panels start unassigned. Connection badges use online, not delivery result.
  75 Python tests, 26 frontend tests and local packaging checks passed;
  real HA acceptance remains pending.

## Language and collaboration

- Communicate with the user in Ukrainian.
- Write and maintain README files, AGENTS files, and all repository documentation
  in English. This is a public-repository requirement approved on 2026-10-03.
- The editor supports Ukrainian and English using shared logic and separate
  `frontend/locales/uk.js` and `frontend/locales/en.js` dictionaries. Update both
  dictionaries for every UI change and run `node --test tests/test_frontend.mjs`.
- Do not create commits or publish anything without the user's explicit instruction.
- Never add broker credentials, tokens, or local Home Assistant configuration to Git.

## Project boundaries

- This repository contains the Home Assistant integration.
- The firmware project is a separate sibling checkout: `../viewe-smart-panel`.
- Agreed requirements are recorded in the firmware project's
  `docs/panel-profiles-design.md`, `docs/lighting-design.md`, and
  `docs/weather-design.md`. Do not treat open questions as approved decisions.
- Do not change firmware hardware settings when working on the integration.

## Architecture and current state

- MQTT was approved by the user on 2026-10-03. Use Home Assistant's MQTT
  integration rather than storing separate broker credentials.
- The initial implementation includes Config Flow, a sidebar editor with Profiles
  and Panels, lighting and weather templates, Store persistence, and MQTT protocol v1.
- Drafts and applied snapshots are separate. Saving does not update panels.
  Unavailable panels receive the latest applied snapshot after reconnection.
- Version 0.1.2 removes profile-level encoder/touch requirements at the user's
  request (2026-10-04). Compatibility uses template versions only. Strip legacy
  requirements from loaded drafts/applied snapshots and during validation.
- Profile deletion, unassignment, and the bilingual editor remain available.
  Deleting an assigned profile is blocked; remove its assignments first.
- Lighting capability mapping and the priority of profile selections in v0.1 are
  provisional. Limitations are documented in README.md and docs/mqtt-protocol.md.
- On 2026-10-04, the user confirmed profile application, weather display, and
  opening lighting pages on physical firmware v1. This specific integration
  update still requires runtime verification.
- HACS packaging targets installation as a custom public GitHub repository.
  The intended repository is `https://github.com/whins/viewe-ha-integration`,
  maintained by `@whins`; hacs.json, manifest metadata, and CI are prepared.
  Remote HACS/hassfest validation and runtime checks must not be reported as
  passed unless they have actually run.

## Maintenance and verification

- Keep exactly one integration directory under `custom_components`.
- Keep all runtime files inside `custom_components/viewe_smart_panel`, including
  frontend assets and translations; root documentation is not installed by HACS.
- Keep the integration version in manifest.json consistent with any published release.
- Use the actual public repository URL and actual maintainer handles in metadata.
  Never invent GitHub identities or mark placeholder metadata as publication-ready.
- Run `python -m unittest discover -s tests -v` for logic changes. Tests use fakes
  at Home Assistant boundaries; passing tests do not prove actual HA loading.
- Run syntax and packaging checks appropriate to the changed files. Documentation
  changes alone do not require rerunning behavior tests.
- Update this file and README when the project state changes materially.

- Version 0.1.3 adds CCT (2026-10-05). AUTO selects CCT for temperature-only
  lights. RGB/RGBW share the firmware rgbw screen. Update firmware before
  applying CCT; older firmware rejects the type. Device verification pending.

- 2026-10-05: Switch template added for switch.* entities, bilingual editor, template compatibility and MQTT On/Off commands. 33 Python tests, 9 frontend tests and local packaging checks passed. Device/HA runtime verification pending.

- Version 0.1.4 packages the existing Switch implementation for HACS updates
  (2026-10-05). New profiles retain Weather/Lighting defaults; Switch pages
  are added explicitly. Firmware requires capabilities.templates.switch: 1.

- 2026-10-05: Added Actions template (scripts/automations), one or two named touch targets, vertically stacked with a horizontal divider. Integration editor configures targets and optional names. MQTT run uses a validated action_index resolved against the applied profile; offline targets are disabled independently. Firmware build and 37 Python tests passed; physical panel/HA runtime verification pending. No upload or commits performed.

- 2026-11-08: Version 0.2.4 adds active-profile controls inside each panel card.
  Targets come from the assigned applied snapshot, deduplicated original HA
  entities, excluding hidden/demo widgets. Direct HA service calls and native
  more-info dialogs leave entity/device registry ownership unchanged. BC-250
  starts exclusively through its guard script with confirmed off state; raw
  Power button control is never exposed. State changes refresh Panels without
  interrupting profile editing or an open selector. Offline displays do not
  disable available HA entity controls; unconfirmed delivery is labelled.
  Local checks: 75 Python and 34 frontend tests. Real HA verification pending.
  Publication is authorized by the user; HA installation will be performed
  by the user independently after the release.

- 2026-11-08: Version 0.2.5 packages 0.2.4 functionality with sorted manifest
  keys and the MIT License explicitly selected by the user. Repository
  description/topics are set for HACS. The packaging check enforces manifest
  ordering. Initial 0.2.4 remote CI passed local checks but failed on these
  pre-existing repository metadata omissions; final remote checks are pending.
  Firmware diagnostics were installed through COM10; encrypted Native API
  confirmed all seven entities and all six diagnostic sensor states. The user
  will update the HA integration independently.

- 2026-11-08: Version 0.2.6 separates required widget name (editor/diagnostics)
  from optional label (display only). New pages have an empty label. Startup
  migration copies old names only where label is absent in drafts/applied;
  empty labels, IDs, revisions and assignments survive. Native schema v2
  requires name; firmware accepts v1 caches with old-label-to-name fallback.
  Firmware profile.py and bundled native_profile_schema.py are identical.
  Legacy MQTT supports only label==name; reject other captions explicitly.
  Checks: 80 Python, 36 frontend tests and packaging passed; real HA pending.
  Firmware installed via COM10 with verified flash; encrypted API confirms
  the existing active profile/widget survived the upgrade. HA installation
  is performed independently by the user after publication.
