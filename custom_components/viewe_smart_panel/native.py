"""ESPHome profile encoding and the small HA ESPHome discovery boundary.

No second API connection or encryption keys: use HA's existing ESPHome entry.
The bundled schema is copied verbatim from the firmware's profile.py.
"""

import json

from .native_profile_schema import validate_profile

ACTIONS = ("viewe_apply_profile", "viewe_reset_profile", "viewe_allow_remote_profiles", "viewe_profile_status")


def encode_profile(profile):
    widgets = []
    for page in profile["pages"]:
        if not page["visible"]:
            continue
        kind = page["template"]
        widget = {"id": page["id"], "type": {"lighting": "light", "bc250": "switch"}.get(kind, kind),
                  "label": page["name"], "show_label": page.get("show_label", True),
                  "disabled_pages": page.get("disabled_pages", [])}
        if kind == "bc250":
            widget.update(state_entity_id=page["entity_id"], icon="steam", layout="fullscreen",
                          control={"mode": "start_only", "action": "button.press", "entity_id": page["power_entity_id"],
                                   "confirmation_timeout": 10, "guard_script": page.get("guard_script", "script.viewe_guarded_start")})
        elif kind == "actions":
            widget["targets"] = [{"entity_id": action["entity_id"], **({"label": action["name"]} if action.get("name", "").strip() else {})}
                                 for action in page["actions"]]
        elif kind == "clock":
            widget["format"] = page.get("format", "24h")
        elif kind == "temperature_humidity":
            widget.update({key: page[key] for key in ("temperature_entity_id", "humidity_entity_id") if page.get(key)})
        else:
            widget["entity_id"] = page["entity_id"]
            if kind == "thermostat":
                widget.update(variant=page.get("variant", "auto"), temperature_unit=page.get("temperature_unit", "auto"))
            elif kind == "weather":
                alert = page["umbrella"]
                hours = {}
                for field, key in (("forecast_start", "start_hour"), ("forecast_end", "end_hour"), ("hide_after", "hide_hour")):
                    value = alert[field]
                    if not value.endswith(":00"):
                        raise ValueError("ESPHome: use whole hours for the umbrella banner")
                    hours[key] = int(value[:2])
                widget["umbrella"] = {key: alert[key] for key in ("enabled", "probability", "limit_time")}
                widget["umbrella"].update(hours)
            elif kind == "lighting":
                if page.get("control_type", "AUTO") != "AUTO":
                    raise ValueError("ESPHome: lighting control type must be AUTO")
                widget["icon"] = page.get("icon", "bulb")
            elif kind == "switch":
                widget.update(icon=page.get("icon", "power"), layout=page.get("layout", "normal"))
        widgets.append(widget)
    result = validate_profile({"schema_version": 1, "id": profile["id"], "revision": profile["revision"], "widgets": widgets})
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def discover(hass):
    """Return verified main-device identities and registered actions (HA 2026.10).

    ESPHome's RuntimeEntryData is intentionally isolated here. If its interface
    changes, fail closed; never guess a device from its friendly name.
    """
    from homeassistant.helpers import device_registry as dr

    registry = dr.async_get(hass)
    result = {}
    action_owners = {}
    for entry in hass.config_entries.async_entries("esphome"):
        runtime = getattr(entry, "runtime_data", None)
        info = getattr(runtime, "device_info", None)
        if info is None:
            continue
        offered = {s.name for s in getattr(runtime, "services", {}).values()}
        if not set(ACTIONS) <= offered:
            continue
        device = registry.async_get_device(connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(info.mac_address))})
        if device is None or entry.entry_id not in device.config_entries:
            continue
        names = {action: f"{info.name.replace('-', '_')}_{action}" for action in ACTIONS}
        available = bool(getattr(runtime, "available", False)) and all(hass.services.has_service("esphome", name) for name in names.values())
        result[f"esp_{entry.entry_id}"] = {"id": f"esp_{entry.entry_id}", "name": info.friendly_name or info.name,
                                            "node_name": info.name, "device_id": device.id, "actions": names, "available": available}
        action_owners.setdefault(names["viewe_apply_profile"], []).append(f"esp_{entry.entry_id}")
    for owners in action_owners.values():
        if len(owners) > 1:
            for panel_id in owners:
                result.pop(panel_id, None)  # Duplicate node names cannot be routed safely.
    return result
