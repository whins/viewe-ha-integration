"""Strict shared YAML/JSON profile contract for the VIEWE ESPHome widgets."""
import json
import re

MAX_BYTES = 8192
MAX_WIDGETS = 16
TOKEN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
ENTITY = re.compile(r"^([a-z_]+)\.[a-z0-9_]+$")
TYPES = {"switch", "light", "weather", "actions", "clock", "temperature_humidity", "thermostat"}
PAGES = {"light": {"cct", "color", "effects"}, "weather": {"forecast"}, "thermostat": {"modes", "fan", "presets", "swing", "range"}}
COMMON = {"id", "type", "label", "show_label", "disabled_pages"}
FIELDS = {
    "switch": {"entity_id", "state_entity_id", "control", "icon", "layout"},
    "light": {"entity_id", "icon"},
    "weather": {"entity_id", "umbrella"},
    "actions": {"targets"},
    "clock": {"format"},
    "temperature_humidity": {"temperature_entity_id", "humidity_entity_id"},
    "thermostat": {"entity_id", "variant", "temperature_unit"},
}


def entity(value, domains):
    if not isinstance(value, str) or len(value) > 128 or not ENTITY.fullmatch(value) or value.split(".")[0] not in domains:
        raise ValueError("Expected " + "/".join(sorted(domains)) + ".* entity_id")
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 128:
        raise ValueError(f"{name} must contain 1..128 UTF-8 bytes")
    return value


def seconds(value):
    if type(value) is int and 1 <= value <= 120:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+s", value):
        return seconds(int(value[:-1]))
    raise ValueError("confirmation_timeout must be 1..120 seconds")


def validate_profile(value):
    if not isinstance(value, dict) or set(value) - {"schema_version", "id", "revision", "widgets"}:
        raise ValueError("Invalid profile fields")
    result = dict(value)
    if type(result.get("schema_version", 1)) is not int or result.get("schema_version", 1) != 1:
        raise ValueError("Unsupported schema_version")
    result["schema_version"] = 1
    if not isinstance(result.get("id"), str) or not TOKEN.fullmatch(result["id"]):
        raise ValueError("Invalid profile id")
    revision = result.get("revision", 0)
    if type(revision) is not int or not 0 <= revision <= 2147483647:
        raise ValueError("Invalid revision")
    result["revision"] = revision
    widgets = result.get("widgets")
    if not isinstance(widgets, list) or len(widgets) > MAX_WIDGETS:
        raise ValueError("Expected at most 16 widgets")
    seen = set()
    result["widgets"] = []
    for item in widgets:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str) or item["type"] not in TYPES:
            raise ValueError("Invalid widget type")
        kind = item["type"]
        if set(item) - COMMON - FIELDS[kind]:
            raise ValueError("Invalid fields for " + kind)
        widget = dict(item)
        wid = widget.get("id")
        if not isinstance(wid, str) or not TOKEN.fullmatch(wid) or wid in seen:
            raise ValueError("Invalid or duplicate widget id")
        seen.add(wid)
        text(widget.get("label"), "label")
        if type(widget.get("show_label", True)) is not bool:
            raise ValueError("show_label must be boolean")
        widget["show_label"] = widget.get("show_label", True)
        disabled = widget.get("disabled_pages", [])
        if not isinstance(disabled, list) or any(type(p) is not str or p not in PAGES.get(kind, set()) for p in disabled) or len(set(disabled)) != len(disabled):
            raise ValueError("Invalid disabled_pages")
        widget["disabled_pages"] = disabled
        if kind == "switch":
            if "control" in widget:
                if "entity_id" in widget:
                    raise ValueError("Use state_entity_id with control, not entity_id")
                entity(widget.get("state_entity_id"), {"binary_sensor", "switch"})
                control = widget["control"]
                if not isinstance(control, dict) or set(control) - {"mode", "action", "entity_id", "confirmation_timeout", "guard_script"}:
                    raise ValueError("Invalid control fields")
                if control.get("mode") != "start_only" or control.get("action") != "button.press":
                    raise ValueError("Only guarded start_only/button.press control is supported")
                entity(control.get("entity_id"), {"button"})
                widget["control"] = {**control, "confirmation_timeout": seconds(control.get("confirmation_timeout", 10)),
                                     "guard_script": entity(control.get("guard_script", "script.viewe_guarded_start"), {"script"})}
            else:
                entity(widget.get("entity_id"), {"switch"})
                if "state_entity_id" in widget:
                    raise ValueError("state_entity_id requires control")
            if widget.get("layout", "normal") not in ("normal", "fullscreen"):
                raise ValueError("Invalid layout")
            widget["layout"] = widget.get("layout", "normal")
        elif kind in {"light", "weather", "thermostat"}:
            entity(widget.get("entity_id"), {{"thermostat": "climate"}.get(kind, kind)})
        elif kind == "temperature_humidity":
            if not {"temperature_entity_id", "humidity_entity_id"} & widget.keys():
                raise ValueError("At least one room sensor is required")
            for key in ("temperature_entity_id", "humidity_entity_id"):
                if key in widget:
                    entity(widget[key], {"sensor"})
        elif kind == "clock":
            if widget.get("format", "24h") not in ("12h", "24h"):
                raise ValueError("Invalid clock format")
            widget["format"] = widget.get("format", "24h")
        elif kind == "actions":
            targets = widget.get("targets")
            if not isinstance(targets, list) or not 1 <= len(targets) <= 2:
                raise ValueError("Expected one or two action targets")
            widget["targets"] = []
            for target in targets:
                if not isinstance(target, dict) or set(target) - {"entity_id", "label"}:
                    raise ValueError("Invalid action target fields")
                target = dict(target)
                entity(target.get("entity_id"), {"script", "automation"})
                if "label" in target:
                    text(target["label"], "target.label")
                widget["targets"].append(target)
        if kind in {"switch", "light"}:
            icon = widget.get("icon", "bulb" if kind == "light" else "power")
            if icon not in ("power", "bulb", "steam"):
                raise ValueError("Unknown icon")
            widget["icon"] = icon
        if kind == "thermostat":
            if widget.get("variant", "auto") not in ("auto", "heater", "air_conditioner"):
                raise ValueError("Invalid thermostat variant")
            widget["variant"] = widget.get("variant", "auto")
            if widget.get("temperature_unit", "auto") not in ("auto", "°C", "°F"):
                raise ValueError("Invalid thermostat temperature_unit")
            widget["temperature_unit"] = widget.get("temperature_unit", "auto")
        if kind == "weather":
            alert = widget.get("umbrella", {})
            if not isinstance(alert, dict) or set(alert) - {"enabled", "probability", "start_hour", "end_hour", "limit_time", "hide_hour"}:
                raise ValueError("Invalid umbrella fields")
            alert = {"enabled": True, "probability": 40, "start_hour": 8, "end_hour": 18, "limit_time": True, "hide_hour": 10, **alert}
            if any(type(alert[k]) is not bool for k in ("enabled", "limit_time")):
                raise ValueError("Umbrella flags must be boolean")
            if type(alert["probability"]) is not int or not 0 <= alert["probability"] <= 100:
                raise ValueError("Invalid umbrella probability")
            if any(type(alert[k]) is not int or not 0 <= alert[k] <= 23 for k in ("start_hour", "hide_hour")) or type(alert["end_hour"]) is not int or not alert["start_hour"] < alert["end_hour"] <= 24:
                raise ValueError("Invalid umbrella hours")
            widget["umbrella"] = alert
        result["widgets"].append(widget)
    if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
        raise ValueError("Profile exceeds 8192 bytes")
    return result
