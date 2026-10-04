# VIEWE Smart Panel — Home Assistant integration

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
- Version 0.1.1 adds profile deletion, unassignment, bilingual editor files, and
  explicit encoder/touch requirements (2026-10-04). Deleting an assigned profile
  is blocked; remove its assignments first. Deletion removes draft and snapshot.
- Panels advertise `capabilities.inputs.encoder` and `capabilities.inputs.touch`
  as booleans. Missing capabilities are unknown and fail required-input checks.
  Legacy profiles require both inputs; requirements are part of applied snapshots.
- Lighting capability mapping and the priority of profile selections in v0.1 are
  provisional. Limitations are documented in README.md and docs/mqtt-protocol.md.
- As of 2026-10-03, actual loading in Home Assistant and operation on a physical
  device have not been verified. Current firmware does not implement this contract.
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
