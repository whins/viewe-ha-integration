"""Transport-independent profile model and validation."""

from copy import deepcopy
from datetime import time
from uuid import uuid4

LIGHT_TYPES = {"MONO", "RGB", "RGBW", "RGBCCT", "ADDRESS"}
TEMPLATES = {"lighting", "weather"}


def new_page(template):
    if template not in TEMPLATES:
        raise ValueError("Невідомий шаблон сторінки")
    page = {"id": uuid4().hex, "template": template, "name": "Освітлення" if template == "lighting" else "Погода", "visible": True, "entity_id": "", "name_auto": True}
    if template == "lighting":
        page.update(control_type="AUTO")
    else:
        page["umbrella"] = {"enabled": True, "probability": 40, "forecast_start": "08:00", "forecast_end": "18:00", "limit_time": True, "hide_after": "10:00"}
    return page


def new_profile(name):
    return {"id": uuid4().hex, "name": name, "revision": 0, "pages": [new_page("weather"), new_page("lighting")]}


def supported_light_types(attributes):
    modes = set(attributes.get("supported_color_modes", []))
    result = ["MONO"] if modes - {"onoff", "unknown"} else []
    if modes & {"hs", "xy", "rgb", "rgbw", "rgbww"}:
        result.append("RGB")
    if "rgbw" in modes:
        result.append("RGBW")
    if "rgbww" in modes or ("color_temp" in modes and "RGB" in result):
        result.append("RGBCCT")
    if "RGB" in result and attributes.get("effect_list"):
        result.append("ADDRESS")
    return result


def resolve_light_type(page, attributes):
    supported = supported_light_types(attributes)
    chosen = page.get("control_type", "AUTO")
    if chosen == "AUTO":
        for candidate in ("ADDRESS", "RGBCCT", "RGBW", "RGB", "MONO"):
            if candidate in supported:
                return candidate
    elif chosen in supported:
        return chosen
    raise ValueError("Тип керування не підтримується вибраним світлом")


def _clock(value):
    if not isinstance(value, str) or len(value) != 5:
        raise ValueError("Час має бути у форматі HH:MM")
    return time.fromisoformat(value)


def validate_profile(value, *, apply=False, states=None):
    """Allow unfinished drafts, but reject malformed data and unsafe application."""
    if not isinstance(value, dict):
        raise ValueError("Очікується профіль")
    profile = deepcopy(value)
    for field in ("id", "name"):
        if not isinstance(profile.get(field), str) or not profile[field].strip() or len(profile[field]) > 128:
            raise ValueError("Профіль повинен мати ID та назву до 128 символів")
    pages = profile.get("pages")
    if not isinstance(pages, list) or len(pages) > 64:
        raise ValueError("Профіль може містити до 64 сторінок")
    seen = set()
    for page in pages:
        if not isinstance(page, dict) or page.get("template") not in TEMPLATES:
            raise ValueError("Невідомий шаблон сторінки")
        page_id = page.get("id")
        if not isinstance(page_id, str) or not page_id or page_id in seen:
            raise ValueError("ID сторінок мають бути унікальними")
        seen.add(page_id)
        if not isinstance(page.get("name"), str) or not page["name"].strip() or len(page["name"]) > 128:
            raise ValueError("Сторінка повинна мати назву до 128 символів")
        if type(page.get("visible")) is not bool or type(page.get("name_auto", True)) is not bool:
            raise ValueError("Некоректна видимість або режим назви")
        entity = page.get("entity_id", "")
        domain = "light" if page["template"] == "lighting" else "weather"
        if not isinstance(entity, str) or (entity and (not entity.startswith(domain + ".") or entity == domain + ".")):
            raise ValueError("Невідповідна сутність сторінки")
        if page["template"] == "lighting":
            if page.get("control_type") not in LIGHT_TYPES | {"AUTO"}:
                raise ValueError("Невідомий тип освітлення")
        else:
            u = page.get("umbrella")
            if not isinstance(u, dict) or type(u.get("enabled")) is not bool or type(u.get("limit_time")) is not bool:
                raise ValueError("Некоректні налаштування парасолі")
            if type(u.get("probability")) is not int or not 0 <= u["probability"] <= 100:
                raise ValueError("Ймовірність має бути від 0 до 100%")
            start, end = _clock(u.get("forecast_start")), _clock(u.get("forecast_end"))
            _clock(u.get("hide_after"))
            if start >= end:
                raise ValueError("Кінець вікна прогнозу має бути після початку")
        if apply and page["visible"]:
            if not entity or states is None or entity not in states:
                raise ValueError(f"Виберіть наявну сутність для сторінки «{page['name']}»")
            if domain == "light":
                page["resolved_type"] = resolve_light_type(page, states[entity])
    if apply and not any(p["visible"] for p in pages):
        raise ValueError("Потрібно додати або показати хоча б одну сторінку")
    return profile
