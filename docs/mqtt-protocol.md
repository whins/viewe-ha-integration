# MQTT protocol v1 — initial implementation

MQTT was approved by the user on 2026-10-03. This document describes the first
integration contract; current panel firmware does not implement it yet. Future
changes must be coordinated between the integration and firmware.

The default prefix is `viewe`. A panel ID contains 1–64 characters from
`A-Z a-z 0-9 _ -`. Messages use UTF-8 JSON and QoS 1. Every message includes
`"protocol": 1`.

| Topic | Direction | Purpose | Retain |
| --- | --- | --- | --- |
| `viewe/request` | HA → all panels | `action: announce`: request hello and online | No |
| `viewe/panels/<id>/hello` | Panel → HA | Name and capabilities | Optional |
| `viewe/panels/<id>/availability` | Panel → HA | online/offline and heartbeat | No for online |
| `viewe/panels/<id>/profiles` | HA → panel | All compatible applied profiles | No |
| `viewe/panels/<id>/config` | HA → panel | Active applied profile | No |
| `viewe/panels/<id>/ack` | Panel → HA | Profile application result | No |
| `viewe/panels/<id>/data` | HA → panel | Entity states and forecasts | No |
| `viewe/panels/<id>/command` | Panel → HA | Lighting control or profile selection | No |
| `viewe/panels/<id>/command_result` | HA → panel | request_id and ok/error status | No |

## Connection and availability

The panel subscribes to request, profiles, config, data, and command_result topics.
On connection and on an `announce` request, it publishes hello followed by a live
online message:

```json
{"protocol":1,"name":"Kitchen","capabilities":{"templates":{"lighting":1,"weather":1},"inputs":{"encoder":true,"touch":true}}}
```

```json
{"protocol":1,"state":"online"}
```

Publish online heartbeats every 30 seconds. After more than 90 seconds without a
heartbeat, HA considers the panel unavailable; the maintenance timer checks every
30 seconds. Repeated heartbeats alone do not resend configuration. Configure the
Last Will as the same JSON with state `offline`.

Retained online messages, commands, and acknowledgements are ignored. After a
restart or MQTT reconnection, HA requests announcements. If the request is lost,
heartbeats restore availability for panels already known to HA.

## Profiles and application

`profiles`: `{ "protocol": 1, "profiles": [<complete applied profile>, ...] }`.
HA sends only compatible applied profiles, never unapplied drafts. The panel caches
these locally; limits and cache eviction policies remain open questions.

`config`: `{ "protocol": 1, "profile": <profile> }`.
A profile contains id, name, revision, and an ordered pages array. Each page includes
id, template, name, visible, entity_id, name_auto, and template-specific settings.
Lighting pages include control_type and resolved_type. Weather pages include umbrella.
Hidden pages are transferred to preserve configuration, but are not displayed.

Profile-level encoder/touch requirements were removed in integration version 0.1.2.
Legacy `requirements` fields are ignored and removed when loaded or saved.
Panel input capabilities can still be reported for information, but do not filter
profiles. Compatibility checks supported template versions for visible pages.
The same rule is used by Apply, assignment, panel-side selection, catalogs, and
the editor's list of selectable profiles.

HA can remove an assignment with `config: {"protocol":1,"profile":null}`.
The panel must clear its active profile and disable controls tied to the old
profile. Offline panels receive this on reconnection. The current integration
reports an online unassignment after sending it; there is no separate clear ack.

The profiles catalog is authoritative: replace the cached catalog and remove
entries absent from it, including an empty catalog. Profile deletion removes
both draft and applied snapshots and is blocked while any panel is assigned.
After deletion, connected panels receive a refreshed catalog; offline panels
receive it after reconnecting. This requires compatible firmware cache handling.

The panel validates and atomically accepts the profile, stores it locally, then
acknowledges success:

```json
{"protocol":1,"profile_id":"profile-id","revision":1,"status":"applied"}
```

Use status `error` on failure. HA matches the active profile's ID and revision.
MQTT delivery alone is not confirmation of application. After 30 seconds without
an acknowledgement, the next maintenance check marks the result as `timeout`.
Reapplying or reconnecting triggers another delivery. Repeated configuration
messages for the same version must be idempotent.

HA saves the applied snapshot before sending it to panels. An unavailable panel
receives the latest applied snapshot after reconnecting. A delivery failure does
not roll back the snapshot and does not mean that the panel confirmed it. If a
new profile is incompatible with any panel already assigned to it, application is
blocked for all panels using that profile.

## Data

```json
{"protocol":1,"profile_id":"profile-id","revision":1,"pages":{"page-id":{"state":"on","attributes":{"brightness":128}}}}
```

Data is associated with a page ID and applied profile revision. The panel must
ignore data for other revisions. Weather additionally includes `forecasts.daily`
and `forecasts.hourly` obtained through `weather.get_forecasts`. `null` means an
unsupported or unavailable forecast; an empty array means a response with no
entries. If the weather entity itself is unavailable, the forecast keys may be
absent; the page state indicates unavailability.

Units are provided in weather entity attributes. Do not assume degrees Celsius
or millimeters. Data updates follow entity state changes and a 15-minute timer.
Forecast responses are cached for up to 15 minutes and invalidated when the
weather entity changes. Aggregated time slots and a computed umbrella banner
are not sent yet.

## Commands

```json
{"protocol":1,"request_id":"boot123-42","profile_id":"profile-id","revision":1,"page_id":"page-id","action":"turn_on","parameters":{"brightness":128}}
```

Lighting actions are turn_on, turn_off, and toggle. Only turn_on accepts parameters:
brightness, color_temp_kelvin, rgb_color, rgbw_color, rgbww_color, and effect.
HA validates ranges through its light service. The target entity is always resolved
from a visible lighting page in the applied profile. Supplying an entity_id in the
command parameters is forbidden.

A request_id must be unique per action and contain 1–64 characters using the same
alphabet as panel IDs. Within the most recent 1024 commands in the current HA
process, a duplicate does not execute the action again; it returns the stored result.
This guarantee does not survive HA restarts or eviction of old IDs. Firmware must
not replay old commands in those cases.

`command_result: ok` means that the HA service call completed. It does not confirm
the physical light state; actual entity state is transmitted separately in data.

Selecting an already applied compatible profile:

```json
{"protocol":1,"request_id":"boot123-43","action":"select_profile","profile_id":"another-profile-id"}
```

The initial concurrency rule is that the last processed selection from HA or a
panel becomes active. This is a provisional implementation of the open priority
question. An offline local selection cannot be processed by HA; firmware must
store it and reconcile it after reconnecting. That behavior is not implemented yet.

## Lighting types in integration 0.1.3

Allowed resolved types: MONO, CCT, RGB, RGBW, RGBCCT, ADDRESS.
CCT opens the temperature screen; RGB and RGBW both open rgbw, using mixed
RGB white or a separate white channel respectively. CCT requires color_temp
or rgbww support in the HA entity. Existing firmware must be updated to
accept CCT. Re-save and apply AUTO profiles to resolve the new type.

### Switch template v1

Pages use `template: "switch"` and `entity_id: "switch.*"`, with the common id, name, name_auto and visible fields. No control_type or umbrella is required. Capability `templates.switch: 1` is required. Commands use the existing page_id/profile_id/revision envelope with turn_on, turn_off or toggle and empty parameters. Targets are resolved from the applied profile; state/data and availability follow the existing contract.
