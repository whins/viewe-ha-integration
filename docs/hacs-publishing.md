# HACS packaging and publication

This repository is prepared for installation as a **custom integration repository**
in HACS. Preparation does not publish the repository, create a commit, create a
GitHub release, or submit it to the default HACS catalog.

## Repository identity

- Public repository: https://github.com/whins/viewe-ha-integration
- Maintainer: `@whins`
- Integration domain: `viewe_smart_panel`
- Initial integration version: `0.1.0`
- Suggested GitHub description: “Home Assistant integration for VIEWE smart panels
  with shared lighting and weather profiles over MQTT.”
- Suggested topics: `home-assistant`, `hacs`, `mqtt`, `viewe`, `smart-panel`.

These addresses describe the intended public repository. Its publication and
availability have not been verified as part of local packaging preparation.

## Package layout

```text
hacs.json
README.md
AGENTS.md
docs/
scripts/check_packaging.py
.github/workflows/validate.yml
custom_components/
  viewe_smart_panel/
    manifest.json
    __init__.py
    config_flow.py
    frontend/panel.js
    strings.json
    translations/uk.json
    ...
```

HACS manages the single integration directory inside `custom_components`.
All required Python modules, translations, and sidebar assets are inside that
directory. The root documentation, checks, tests, and workflows are development
files and do not need to be installed in Home Assistant.

`hacs.json` sets the display name and `render_readme: true`. Runtime content is
not at the repository root. Installation uses repository files rather than a
release ZIP, so no archive build or release attachment is required.

The integration manifest includes the domain, name, version, actual maintainer,
project documentation URL, and Issues URL required by HACS. Credentials and
Home Assistant configuration remain outside the repository.

## Local verification

```text
python scripts/check_packaging.py
python -m compileall -q custom_components scripts
node --check custom_components/viewe_smart_panel/frontend/panel.js
```

The packaging check validates the single-integration layout, JSON metadata,
runtime assets, English documentation, and local documentation links. It does
not contact GitHub, validate a live HACS installation, or load Home Assistant.
Behavior changes should also run the logic tests documented in README.md.

## Before the first publication

1. Obtain the user's explicit instruction before creating commits or publishing.
2. Publish this checkout to the public repository listed above.
3. Set its description and topics in GitHub. Enable Issues, since the manifest
   links to that page.
4. Run the **Validate** workflow and review each job's result.
5. Install through HACS in a test Home Assistant instance and verify setup,
   sidebar loading, profile editing, and MQTT behavior.

The workflow includes local packaging/syntax/logic checks, Home Assistant's
**hassfest**, and **hacs/action** with category `integration`. It runs on pushes,
pull requests, and manual dispatch. Remote validation is not considered passed
until these jobs actually complete successfully.

The HACS job skips only the `brands` check while targeting installation as a
custom repository. No Home Assistant Brands submission has been made. Preparing
for the default HACS catalog is a separate task and requires satisfying its
additional publication requirements.

## Install on Home Assistant OS with HACS

1. Open HACS and choose **Custom repositories** from its menu.
2. Enter `https://github.com/whins/viewe-ha-integration`.
3. Select **Integration**, add the repository, and download **VIEWE Smart Panel**.
4. Restart Home Assistant.
5. Ensure HA's MQTT integration is configured and connected.
6. Add **VIEWE Smart Panel** through **Settings → Devices & services**.

The editor can be tested before compatible firmware is available. The current
firmware cannot discover or control a panel through this integration yet.

## Versioning and updates

HACS can install the public repository's default branch without a GitHub release.
For published releases, update `manifest.json` and use a matching release tag
(for example, manifest version `0.1.0` and release tag `v0.1.0`). Create a GitHub
release, not just a Git tag, when offering a release version through HACS.

After downloading an integration update through HACS, restart Home Assistant
to load the updated Python modules. Keep documentation clear about which
versions have actually been tested in HA and on physical hardware.

## References

- [HACS integration requirements](https://www.hacs.dev/docs/publish/integration/)
- [HACS general repository requirements](https://www.hacs.dev/docs/publish/start/)
- [HACS validation action](https://www.hacs.dev/docs/publish/action/)
- [HACS custom repositories](https://www.hacs.dev/docs/faq/custom_repositories/)
