"""Persistent profiles and the first version of the MQTT panel contract."""

import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import timedelta
import json
import logging
import re
from time import monotonic

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.const import EVENT_STATE_CHANGED

from .const import DOMAIN, PROTOCOL_VERSION, STORAGE_VERSION
from .models import new_profile, validate_profile, panel_compatible

_LOGGER = logging.getLogger(__name__)
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class VieweHub:
    def __init__(self, hass, prefix):
        self.hass = hass
        self.prefix = prefix
        self.store = Store(hass, STORAGE_VERSION, DOMAIN)
        self.data = {"profiles": {}, "applied": {}, "panels": {}}
        self.online = set()
        self.results = {}
        self.last_seen = {}
        self.pending_since = {}
        self.command_ids = OrderedDict()
        self.forecast_cache = {}
        self.unsubscribers = []
        self.lock = asyncio.Lock()

    async def async_start(self):
        saved = await self.store.async_load()
        if saved:
            self.data = saved
            for collection in ("profiles", "applied"):
                for profile in self.data[collection].values():
                    profile.pop("requirements", None)
            await self.store.async_save(self.data)
        try:
            for suffix in ("hello", "availability", "ack", "command"):
                self.unsubscribers.append(await mqtt.async_subscribe(self.hass, f"{self.prefix}/panels/+/{suffix}", self._message, qos=1))
            self.unsubscribers.append(self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed))
            self.unsubscribers.append(async_track_time_interval(self.hass, self._refresh, timedelta(minutes=15)))
            self.unsubscribers.append(async_track_time_interval(self.hass, self._maintenance, timedelta(seconds=30)))
            self.unsubscribers.append(mqtt.async_subscribe_connection_status(self.hass, self._connection_changed))
            if mqtt.is_connected(self.hass):
                await self._request_hello()
        except Exception:
            self.async_stop()
            raise

    @callback
    def async_stop(self):
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        self.unsubscribers.clear()
        self.online.clear()
        self.last_seen.clear()

    @callback
    def _connection_changed(self, connected):
        self.online.clear()
        self.last_seen.clear()
        if connected:
            self.hass.async_create_task(self._request_hello())

    async def _request_hello(self):
        try:
            await mqtt.async_publish(self.hass, f"{self.prefix}/request", json.dumps({"protocol": PROTOCOL_VERSION, "action": "announce"}), qos=1, retain=False)
        except Exception:
            _LOGGER.exception("Panel announcement request failed")

    async def _maintenance(self, _now):
        now = monotonic()
        for panel_id in list(self.online):
            if now - self.last_seen.get(panel_id, 0) > 90:
                self.online.discard(panel_id)
                self.results[panel_id] = "offline"
            elif self.results.get(panel_id) == "pending" and now - self.pending_since.get(panel_id, now) > 30:
                self.results[panel_id] = "timeout"

    def snapshot(self):
        result = deepcopy(self.data)
        for panel_id, panel in result["panels"].items():
            panel["online"] = panel_id in self.online and mqtt.is_connected(self.hass)
            panel["result"] = self.results.get(panel_id, "offline") if panel["online"] else "offline"
            panel["compatible_profiles"] = [profile_id for profile_id, profile in self.data["applied"].items() if self.compatible(panel, profile)]
        return result

    async def _persist(self, updated):
        await self.store.async_save(updated)
        self.data = updated

    async def async_create_profile(self, name, language="uk"):
        async with self.lock:
            profile = validate_profile(new_profile(name, language))
            updated = deepcopy(self.data)
            updated["profiles"][profile["id"]] = profile
            await self._persist(updated)
            return profile

    async def async_save_profile(self, value):
        async with self.lock:
            profile = validate_profile(value)
            current = self.data["profiles"].get(profile["id"])
            if current is None:
                raise ValueError("Профіль не знайдено")
            if profile.get("revision") != current["revision"]:
                raise ValueError("Профіль змінено в іншому вікні. Оновіть редактор")
            profile["revision"] = current["revision"] + 1
            updated = deepcopy(self.data)
            updated["profiles"][profile["id"]] = profile
            await self._persist(updated)
            return profile

    def compatible(self, panel, profile):
        return panel_compatible(panel, profile)

    async def async_delete_profile(self, profile_id, revision):
        async with self.lock:
            current = self.data["profiles"].get(profile_id)
            if current is None:
                raise ValueError("Профіль не знайдено")
            if current["revision"] != revision:
                raise ValueError("Профіль змінено в іншому вікні. Оновіть редактор")
            if any(p.get("profile_id") == profile_id for p in self.data["panels"].values()):
                raise ValueError("Спочатку змініть або скасуйте призначення профілю панелям")
            updated = deepcopy(self.data)
            del updated["profiles"][profile_id]
            updated["applied"].pop(profile_id, None)
            await self._persist(updated)
            for panel_id in self.online:
                if panel_id in self.data["panels"]:
                    try:
                        await self._catalog(panel_id)
                    except Exception:
                        _LOGGER.exception("Could not refresh catalog after profile deletion for %s", panel_id)
            return {"deleted": profile_id}

    async def async_apply_profile(self, profile_id):
        async with self.lock:
            if profile_id not in self.data["profiles"]:
                raise ValueError("Профіль не знайдено")
            states = {s.entity_id: s.attributes for s in self.hass.states.async_all()}
            profile = validate_profile(self.data["profiles"][profile_id], apply=True, states=states)
            incompatible = [p["name"] for p in self.data["panels"].values() if p.get("profile_id") == profile_id and not self.compatible(p, profile)]
            if incompatible:
                raise ValueError("Профіль несумісний із панелями: " + ", ".join(incompatible))
            updated = deepcopy(self.data)
            updated["applied"][profile_id] = profile
            await self._persist(updated)
            results = {}
            for panel_id, panel in self.data["panels"].items():
                if panel.get("profile_id") == profile_id:
                    results[panel_id] = await self._deliver(panel_id)
                elif panel_id in self.online:
                    try:
                        await self._catalog(panel_id)
                    except Exception:
                        _LOGGER.exception("Could not update profile catalog for %s", panel_id)
            return {"revision": profile["revision"], "panels": results}

    async def async_assign(self, panel_id, profile_id):
        async with self.lock:
            if panel_id not in self.data["panels"] or (profile_id is not None and profile_id not in self.data["applied"]):
                raise ValueError("Виберіть панель і застосований профіль")
            if profile_id is not None and not self.compatible(self.data["panels"][panel_id], self.data["applied"][profile_id]):
                raise ValueError("Профіль несумісний із панеллю")
            updated = deepcopy(self.data)
            updated["panels"][panel_id]["profile_id"] = profile_id
            await self._persist(updated)
            return await self._deliver(panel_id)

    async def _publish(self, panel_id, suffix, payload):
        await mqtt.async_publish(self.hass, f"{self.prefix}/panels/{panel_id}/{suffix}", json.dumps(payload, ensure_ascii=False, default=str), qos=1, retain=False)

    async def _catalog(self, panel_id):
        panel = self.data["panels"][panel_id]
        profiles = [p for p in self.data["applied"].values() if self.compatible(panel, p)]
        await self._publish(panel_id, "profiles", {"protocol": PROTOCOL_VERSION, "profiles": profiles})

    async def _deliver(self, panel_id):
        if panel_id not in self.online or not mqtt.is_connected(self.hass):
            self.results[panel_id] = "offline"
            return "offline"
        panel = self.data["panels"][panel_id]
        profile = self.data["applied"].get(panel.get("profile_id"))
        if not profile:
            try:
                await self._publish(panel_id, "config", {"protocol": PROTOCOL_VERSION, "profile": None})
                self.results[panel_id] = "unassigned"
            except Exception:
                _LOGGER.exception("Could not clear profile for panel %s", panel_id)
                self.results[panel_id] = "error"
            return self.results[panel_id]
        if not self.compatible(panel, profile):
            self.results[panel_id] = "incompatible"
            return "incompatible"
        try:
            self.results[panel_id] = "pending"
            self.pending_since[panel_id] = monotonic()
            await self._catalog(panel_id)
            await self._publish(panel_id, "config", {"protocol": PROTOCOL_VERSION, "profile": profile})
            await self._data(panel_id)
        except Exception:
            _LOGGER.exception("Could not send profile to panel %s", panel_id)
            self.results[panel_id] = "error"
        return self.results[panel_id]

    async def _message(self, message):
        parts = message.topic[len(self.prefix) + 1:].split("/")
        if len(parts) != 3 or not _ID.fullmatch(parts[1]):
            return
        panel_id, suffix = parts[1:]
        try:
            if len(message.payload) > 65536:
                raise ValueError("Повідомлення завелике")
            payload = json.loads(message.payload)
            if not isinstance(payload, dict) or payload.get("protocol") != PROTOCOL_VERSION:
                raise ValueError("Непідтримуваний протокол")
            async with self.lock:
                if suffix == "hello":
                    name, capabilities = payload.get("name"), payload.get("capabilities")
                    if not isinstance(name, str) or not 1 <= len(name) <= 128 or not isinstance(capabilities, dict) or not isinstance(capabilities.get("templates"), dict):
                        raise ValueError("Некоректний опис панелі")
                    inputs = capabilities.get("inputs", {})
                    if not isinstance(inputs, dict) or any(type(v) is not bool for v in inputs.values()):
                        raise ValueError("Некоректні можливості вводу панелі")
                    updated = deepcopy(self.data)
                    panel = updated["panels"].setdefault(panel_id, {"id": panel_id, "profile_id": None})
                    panel.update(name=name, capabilities=capabilities)
                    await self._persist(updated)
                    # hello describes capabilities; only availability indicates liveness.
                    if panel_id in self.online:
                        self.last_seen[panel_id] = monotonic()
                        await self._deliver(panel_id)
                elif suffix == "availability":
                    if message.retain:
                        return  # A retained "online" is not evidence of a live device.
                    if payload.get("state") == "offline":
                        self.online.discard(panel_id)
                    elif payload.get("state") == "online":
                        newly_online = panel_id not in self.online
                        self.online.add(panel_id)
                        self.last_seen[panel_id] = monotonic()
                        if newly_online and panel_id in self.data["panels"]:
                            await self._catalog(panel_id)
                            await self._deliver(panel_id)
                elif panel_id in self.data["panels"] and suffix == "ack":
                    if message.retain or panel_id not in self.online:
                        return
                    panel = self.data["panels"][panel_id]
                    profile = self.data["applied"].get(panel.get("profile_id"))
                    if profile and payload.get("profile_id") == profile["id"] and payload.get("revision") == profile["revision"]:
                        self.results[panel_id] = "applied" if payload.get("status") == "applied" else "error"
                elif suffix == "command" and not message.retain and panel_id in self.online:
                    request_id = payload.get("request_id")
                    if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
                        raise ValueError("Потрібен унікальний request_id")
                    key = (panel_id, request_id)
                    if key not in self.command_ids:
                        self.command_ids[key] = "error"
                        try:
                            await self._command(panel_id, payload)
                            self.command_ids[key] = "ok"
                        except Exception:
                            _LOGGER.warning("Panel command rejected for %s", panel_id)
                        if len(self.command_ids) > 1024:
                            self.command_ids.popitem(last=False)
                    await self._publish(panel_id, "command_result", {"protocol": PROTOCOL_VERSION, "request_id": request_id, "status": self.command_ids[key]})
        except (ValueError, TypeError, KeyError):
            _LOGGER.warning("Ignored invalid panel message on %s", message.topic)
        except Exception:
            _LOGGER.exception("Panel message processing failed on %s", message.topic)

    async def _command(self, panel_id, payload):
        if payload.get("action") == "select_profile":
            profile = self.data["applied"].get(payload.get("profile_id"))
            if profile is None or not self.compatible(self.data["panels"][panel_id], profile):
                raise ValueError("Несумісний профіль")
            updated = deepcopy(self.data)
            updated["panels"][panel_id]["profile_id"] = profile["id"]
            await self._persist(updated)
            await self._deliver(panel_id)
            return
        panel = self.data["panels"][panel_id]
        profile = self.data["applied"].get(panel.get("profile_id"))
        if not profile or payload.get("profile_id") != profile["id"] or payload.get("revision") != profile["revision"]:
            raise ValueError("Команда застарілого профілю")
        page = next((p for p in profile["pages"] if p["id"] == payload.get("page_id") and p["visible"] and p["template"] in {"lighting", "switch", "actions", "bc250"}), None)
        if page is None:
            raise ValueError("Сторінка не підтримує керування")
        if page["template"] == "bc250":
            running = self.hass.states.get(page["entity_id"])
            power = self.hass.states.get(page["power_entity_id"])
            if payload.get("action") != "start" or payload.get("parameters", {}) or running is None or running.state != "off" or power is None or power.state in {"unknown", "unavailable"}:
                raise ValueError("BC-250 недоступний або вже увімкнений")
            await self.hass.services.async_call("button", "press", {"entity_id": page["power_entity_id"]}, blocking=True)
            return
        if page["template"] == "actions":
            index = payload.get("action_index")
            if payload.get("action") != "run" or type(index) is not int or not 0 <= index < len(page["actions"]) or payload.get("parameters", {}):
                raise ValueError("Некоректні параметри")
            target = page["actions"][index]["entity_id"]
            state = self.hass.states.get(target)
            if state is None or state.state in {"unknown", "unavailable"}:
                raise ValueError("Сутність недоступна")
            domain = target.split(".", 1)[0]
            await self.hass.services.async_call(domain, "trigger" if domain == "automation" else "turn_on", {"entity_id": target}, blocking=True)
            return
        action = payload.get("action")
        if action not in {"turn_on", "turn_off", "toggle"}:
            raise ValueError("Невідома команда")
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, dict) or (action != "turn_on" and parameters):
            raise ValueError("Некоректні параметри")
        allowed = set() if page["template"] == "switch" else {"brightness", "color_temp_kelvin", "rgb_color", "rgbw_color", "rgbww_color", "effect"}
        if parameters.keys() - allowed:
            raise ValueError("Непідтримувані параметри")
        # HA validates parameter ranges and entity capabilities; the entity target
        # is always resolved from the applied profile, never accepted over MQTT.
        await self.hass.services.async_call("switch" if page["template"] == "switch" else "light", action, {**parameters, "entity_id": page["entity_id"]}, blocking=True)

    async def _data(self, panel_id):
        panel = self.data["panels"][panel_id]
        profile = self.data["applied"].get(panel.get("profile_id"))
        if profile is None:
            return
        pages = {}
        for page in profile["pages"]:
            if not page["visible"]:
                continue
            if page["template"] == "bc250":
                running = self.hass.states.get(page["entity_id"])
                power = self.hass.states.get(page["power_entity_id"])
                ready = running is not None and running.state in {"on", "off"} and power is not None and power.state not in {"unknown", "unavailable"}
                pages[page["id"]] = {"state": running.state if ready else "unavailable", "available": ready}
                continue
            if page["template"] == "actions":
                items = []
                for action in page["actions"]:
                    target = self.hass.states.get(action["entity_id"])
                    items.append({"state": target.state if target else "unavailable"})
                pages[page["id"]] = {"actions": items}
                continue
            state = self.hass.states.get(page["entity_id"])
            item = {"state": state.state if state else "unavailable", "attributes": dict(state.attributes) if state else {}}
            if page["template"] == "weather" and state and state.state not in {"unknown", "unavailable"}:
                cached = self.forecast_cache.get(state.entity_id)
                if cached is None or monotonic() - cached[0] >= 900:
                    forecasts = {}
                    for forecast_type in ("daily", "hourly"):
                        try:
                            response = await self.hass.services.async_call("weather", "get_forecasts", {"entity_id": state.entity_id, "type": forecast_type}, blocking=True, return_response=True)
                            forecasts[forecast_type] = response.get(state.entity_id, {}).get("forecast", [])
                        except Exception:
                            forecasts[forecast_type] = None
                    cached = (monotonic(), forecasts)
                    self.forecast_cache[state.entity_id] = cached
                item["forecasts"] = cached[1]
            pages[page["id"]] = item
        await self._publish(panel_id, "data", {"protocol": PROTOCOL_VERSION, "profile_id": profile["id"], "revision": profile["revision"], "pages": pages})

    async def _refresh(self, _now=None):
        if not mqtt.is_connected(self.hass):
            self.online.clear()
            return
        for panel_id in list(self.online):
            if panel_id not in self.data["panels"]:
                continue
            try:
                await self._data(panel_id)
            except Exception:
                _LOGGER.exception("Panel data refresh failed for %s", panel_id)

    async def _state_changed(self, event):
        entity_id = event.data["entity_id"]
        if not entity_id.startswith(("light.", "weather.", "switch.", "script.", "automation.", "button.", "binary_sensor.")):
            return
        if entity_id.startswith("weather."):
            self.forecast_cache.pop(entity_id, None)
        for panel_id in list(self.online):
            if panel_id not in self.data["panels"]:
                continue
            panel = self.data["panels"][panel_id]
            profile = self.data["applied"].get(panel.get("profile_id"))
            if profile and any(p["visible"] and (p.get("entity_id") == entity_id or p.get("power_entity_id") == entity_id or any(a["entity_id"] == entity_id for a in p.get("actions", []))) for p in profile["pages"]):
                try:
                    await self._data(panel_id)
                except Exception:
                    _LOGGER.exception("Panel state update failed for %s", panel_id)
