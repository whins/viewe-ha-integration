# ESPHome Native API and widget forms

Version 0.2.0 supports the `viewe_knob_display` ESPHome component. Legacy MQTT
panels keep their existing assignments and applied snapshots. Existing stored
entries retain MQTT by default; new entries default to Native API only. Use the
integration's **Configure** options to enable/disable legacy MQTT or change its
prefix without removing profiles. Changing options reloads the integration.

## Install and connect

1. Update `custom_components/viewe_smart_panel` on the HA machine and restart HA.
   Updating this repository alone does not install files on the HA machine.
2. Add the display through the standard **ESPHome** integration. Enter its API
   encryption key there; this integration does not keep another copy or open a
   second Native API connection.
3. Enable **Allow the device to perform Home Assistant actions** in the ESPHome
   device options. Widget controls and weather forecast requests need this.
4. Open **VIEWE Smart Panel → Panels → Refresh status**. A connected display
   appears automatically after its four VIEWE actions have been registered.
5. Create or edit a profile, configure each visible widget, **Save**, then
   **Apply**. Assign that applied profile to the display in **Panels**.
6. Refresh status to see **Applied** after a matching device receipt. A
   successful HA action call alone does not prove that a profile was applied.

The new forms are shared between Ukrainian and English. Existing stored
`pages/template/name` fields are retained for compatibility; Native API delivery
converts these to the firmware's `widgets/type/label` schema. An unsaved draft is
never delivered. Different displays can share one applied snapshot.

## Supported widgets

| Editor widget | Native type | Binding and options |
| --- | --- | --- |
| Lighting | `light` | `light.*`, automatic HA capabilities, icon, optional disabled CCT/color/effects pages |
| Switch | `switch` | `switch.*`, power/bulb/Steam icon, normal/full-screen layout |
| BC-250 | `switch` | Running `binary_sensor.*`, Power `button.*`, guarded start-only control, Steam icon and full-screen layout |
| Weather | `weather` | `weather.*`, umbrella threshold/window/hide time, optional forecast page |
| Scripts / automations | `actions` | One or two `script.*` or `automation.*` targets with optional names |
| Clock | `clock` | 12/24-hour format; no entity binding |
| Temperature / humidity | `temperature_humidity` | At least one room `sensor.*`; display only |
| Thermostat | `thermostat` | `climate.*`, auto/heater/air-conditioner variant, auto/Celsius/Fahrenheit unit, optional modes/fan/presets/swing/range pages |

Every widget has a label and a **Show widget label** option. Hiding a widget from
the profile omits it from delivery. Disabling an internal page keeps its widget
and main page. A screensaver remains a component mode configured in ESPHome YAML;
it is not a swipeable widget or a field in a remote profile.

Native profiles permit at most **16 visible widgets**, **8192 UTF-8 bytes** and
**128 UTF-8 bytes per label**. IDs contain 1–64 ASCII letters/digits/underscores/
hyphens. Revisions are integers through 2147483647. The exact firmware Python
validator is bundled in `native_profile_schema.py`; synchronize it when changing
the component contract.

For Native API, lighting must use **AUTO**. Umbrella times must use whole hours;
minute offsets are rejected rather than rounded. Legacy MQTT profiles retain
their manual lighting type and minute-based weather times. Legacy firmware does
not support the three new widget types or the new label/page/icon/layout options;
those configurations are excluded from its compatible profiles.

## BC-250 guard package

Copy `custom_components/viewe_smart_panel/viewe_guarded_start.yaml` into an HA
packages directory and enable packages under `homeassistant`, for example:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart/reload the affected HA configuration and confirm
`script.viewe_guarded_start` exists. Select it in the BC-250 widget. The
integration checks that the selected script exists before assigning/applying a
BC-250 Native profile. Copying the package into the integration folder alone
does **not** load it as an HA script.

The script rechecks confirmed **off**, validates the target domains and calls
`button.press`, then holds its single-run lock while waiting up to ten seconds
for **on**. Button state `unknown` before its first press is permitted;
`unavailable` or missing is blocked. If installing a custom guard script, preserve
the `state_entity_id`/`control_entity_id` variable contract and these checks. Use
independent guard script instances for independently controlled BC-250 devices.

## Delivery and local overrides

The standard ESPHome integration registers these actions, where `NODE` is the
node name with hyphens replaced by underscores:

- `esphome.NODE_viewe_apply_profile`, string argument `payload`;
- `esphome.NODE_viewe_reset_profile`;
- `esphome.NODE_viewe_allow_remote_profiles`;
- `esphome.NODE_viewe_profile_status`.

Discovery verifies the node's ESPHome config-entry membership and main-device
MAC in the device registry. Duplicate action prefixes are ignored. Incoming
`esphome.viewe_panel` events must match both device ID and node name. An apply
receipt must also match the expected profile ID and revision. HA states, widget
commands and forecast responses travel directly through ESPHome Native API;
this integration only manages profile delivery for these panels.

Connected nodes are probed every 30 seconds. The editor refreshes every five seconds while open and also probes
them. Delivery waits for `profile_applied` or a matching `profile_status`.
Pending receipts expire on the maintenance tick after 30 seconds. Rejected
profiles expose their firmware reason; a timeout/rejection does not repeatedly
resend a profile on each status response. Reconnection sends the latest applied
snapshot when a profile is assigned. No light/switch/start commands are replayed.

Choosing the YAML profile on the display sets its persistent local-override
latch. Reconnection does **not** clear that latch. The editor shows the desired
HA assignment together with **YAML profile selected on the display**. An explicit
assignment or **Resume HA profile** requests `viewe_allow_remote_profiles`, waits
for its receipt, then sends the profile. Selecting **No profile** queues a reset
even while the display is offline; the reset receipt returns it to YAML.
Native firmware currently has no remote profile-catalog action: select a remote
profile in HA; the display's existing local reset remains available.

Discovery's use of ESPHome `RuntimeEntryData.device_info/services/available` is
isolated in `native.py`. Its expected boundary and action naming were checked
against the [Home Assistant ESPHome manager](https://github.com/home-assistant/core/blob/dev/homeassistant/components/esphome/manager.py)
and [runtime data](https://github.com/home-assistant/core/blob/dev/homeassistant/components/esphome/entry_data.py).
If that internal interface changes, discovery fails closed. No minimum HA
version is claimed from local tests alone.

## Verification limits

Python tests exercise profile encoding, firmware limits, identity routing,
discovery, receipts, queues, rejection/timeouts, reset/resume and MQTT coexistence
using HA boundary fakes. Frontend tests cover all forms and option handlers.
Packaging checks validate runtime asset placement and both languages. Loading
this version in a real HA instance and controlling the physical display remain
separate verification steps.


## Per-widget Demo (0.2.1)

Each widget form includes a **Demo** checkbox (disabled by default). Enable it,
Save and Apply the profile, then assign it normally. Entity selections are
retained for later use but are not required or consulted in demo mode. Turning
Demo off restores entity validation and normal live control.

Update the display firmware to the version supporting `demo` before enabling
this option. Older ESPHome firmware rejects this new field; the editor keeps
normal profiles compatible by omitting the field when it is disabled. Demo
profiles are not compatible with legacy MQTT firmware.

Demo widgets use per-widget local state and sample data; they do not execute
HA actions or YAML widget triggers. The same profile can mix demo and live
widgets. BC-250 demo does not require the guard script or real power/sensor
entities. The clock begins at 08:30; weather includes an umbrella alert and
three days of details. Toggle, light and climate controls update only the
simulated display state. Profile-management actions and receipts still use HA's
ESPHome connection. A small badge identifies demo widgets on the screen.


## Editor updates and missing panels (0.2.2)

After installing/reinstalling the integration, restart Home Assistant to load the
new Python code. The editor header displays its frontend version. Every release
uses a different static asset path and custom element name, including relative
locale imports, so an older module already loaded in the browser cannot take
its place. Refresh the HA browser page after restart if it is still showing the
old panel. Backend and frontend version strings are checked during packaging.

Panels refreshes every five seconds while this panel is mounted. Polling stops
when it is removed and never redraws an unsaved widget form. A pending save or
assignment takes precedence over an older background response.

VIEWE does not independently discover Wi-Fi displays. First configure the display
using HA's standard ESPHome integration, entering its reachable address, port
6053 and Native API encryption key. Its four VIEWE actions must be registered.
The Panels tab shows setup guidance when no VIEWE Native API nodes are detected,
even if old MQTT panel records are still listed. These old records are retained;
refreshing or reinstalling is not a migration from MQTT identity to ESPHome.


## Removing panel records and connection badges (0.2.3)

Each panel card has a green Online or red Offline pill with an icon and text.
Connection status is separate from profile delivery: an online panel can still
show an application error or pending acknowledgement.

**Remove panel** removes only that VIEWE panel record and its assignment. It
keeps profiles, the standard ESPHome device and the current display configuration.
A confirmation explains the scope. The removed identity is suppressed for the
current HA session: background polling and late receipts cannot recreate it.
**Refresh status** explicitly clears suppression, probes configured ESPHome
nodes and requests fresh announcements from live MQTT panels. Rediscovered
records start unassigned. Restarting the VIEWE integration also clears this
session-only suppression. This is removal from the list, not an HA device ban.
