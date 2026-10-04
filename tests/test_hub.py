"""Exercise persistence and MQTT semantics with explicit HA boundary fakes.

These tests do not verify loading in a real Home Assistant installation.
"""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from time import monotonic
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock


def module(name, **attrs):
    result = ModuleType(name)
    result.__dict__.update(attrs)
    sys.modules[name] = result
    return result


class MemoryStore:
    def __init__(self, *args):
        self.saved = None

    async def async_load(self):
        return deepcopy(self.saved)

    async def async_save(self, value):
        self.saved = deepcopy(value)


module("homeassistant")
module("homeassistant.components")
mqtt = module("homeassistant.components.mqtt", is_connected=lambda hass: True, async_publish=AsyncMock())
module("homeassistant.core", callback=lambda fn: fn)
module("homeassistant.const", EVENT_STATE_CHANGED="state_changed")
module("homeassistant.helpers")
module("homeassistant.helpers.event", async_track_time_interval=lambda *args: lambda: None)
module("homeassistant.helpers.storage", Store=MemoryStore)
package = module("viewe_test_package")
package.__path__ = [str(Path(__file__).parents[1] / "custom_components/viewe_smart_panel")]
hub_module = importlib.import_module("viewe_test_package.hub")


class HubTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        mqtt.async_publish.reset_mock()
        self.hass = SimpleNamespace(
            states=SimpleNamespace(async_all=lambda: [], get=lambda _: None),
            services=SimpleNamespace(async_call=AsyncMock()),
        )
        self.hub = hub_module.VieweHub(self.hass, "viewe")
        self.profile = await self.hub.async_create_profile("Дім")
        for page in self.profile["pages"]:
            page["entity_id"] = "weather.home" if page["template"] == "weather" else "light.kitchen"
        self.hass.states.async_all = lambda: [
            SimpleNamespace(entity_id="weather.home", attributes={}),
            SimpleNamespace(entity_id="light.kitchen", attributes={"supported_color_modes": ["rgbw"]}),
        ]
        self.profile = await self.hub.async_save_profile(self.profile)
        self.hub.data["panels"]["panel1"] = {"id": "panel1", "name": "Кухня", "profile_id": self.profile["id"], "capabilities": {"templates": {"lighting": 1, "weather": 1}, "inputs": {"encoder": True, "touch": True}}}

    async def message(self, suffix, payload, retain=False):
        await self.hub._message(SimpleNamespace(topic=f"viewe/panels/panel1/{suffix}", payload=json.dumps({"protocol": 1, **payload}), retain=retain))

    async def test_save_does_not_publish_and_apply_queues_offline(self):
        self.assertEqual(mqtt.async_publish.call_count, 0)
        result = await self.hub.async_apply_profile(self.profile["id"])
        self.assertEqual(result["panels"], {"panel1": "offline"})
        self.assertEqual(mqtt.async_publish.call_count, 0)
        self.assertEqual(self.hub.store.saved["applied"][self.profile["id"]]["revision"], 1)

    async def test_reconnect_delivers_applied_not_new_draft(self):
        await self.hub.async_apply_profile(self.profile["id"])
        self.profile["name"] = "Чернетка"
        await self.hub.async_save_profile(self.profile)
        await self.message("availability", {"state": "online"})
        configs = [json.loads(call.args[2]) for call in mqtt.async_publish.call_args_list if call.args[1].endswith("/config")]
        self.assertEqual(configs[-1]["profile"]["name"], "Дім")
        self.assertEqual(configs[-1]["profile"]["revision"], 1)

    async def test_stale_save_rejected(self):
        await self.hub.async_save_profile(self.profile)
        with self.assertRaises(ValueError):
            await self.hub.async_save_profile(self.profile)

    async def test_wrong_ack_does_not_mark_applied(self):
        await self.hub.async_apply_profile(self.profile["id"])
        await self.message("availability", {"state": "online"})
        await self.message("ack", {"profile_id": self.profile["id"], "revision": 99, "status": "applied"})
        self.assertEqual(self.hub.results["panel1"], "pending")
        await self.message("ack", {"profile_id": self.profile["id"], "revision": 1, "status": "applied"})
        self.assertEqual(self.hub.results["panel1"], "applied")

    async def test_retained_online_and_toggle_ignored(self):
        await self.message("availability", {"state": "online"}, retain=True)
        self.assertNotIn("panel1", self.hub.online)
        await self.message("command", {"action": "toggle"}, retain=True)
        self.hass.services.async_call.assert_not_called()

    async def test_incompatible_apply_keeps_previous_snapshot(self):
        await self.hub.async_apply_profile(self.profile["id"])
        self.hub.data["panels"]["panel1"]["capabilities"]["templates"].pop("weather")
        self.profile["name"] = "Нова версія"
        await self.hub.async_save_profile(self.profile)
        with self.assertRaises(ValueError):
            await self.hub.async_apply_profile(self.profile["id"])
        self.assertEqual(self.hub.data["applied"][self.profile["id"]]["name"], "Дім")

    async def test_duplicate_toggle_executed_once(self):
        await self.hub.async_apply_profile(self.profile["id"])
        await self.message("availability", {"state": "online"})
        payload = {"request_id": "unique1", "action": "toggle", "profile_id": self.profile["id"], "revision": 1, "page_id": self.profile["pages"][1]["id"]}
        await self.message("command", payload)
        await self.message("command", payload)
        self.hass.services.async_call.assert_awaited_once_with("light", "toggle", {"entity_id": "light.kitchen"}, blocking=True)

    async def test_target_cannot_be_overridden(self):
        await self.hub.async_apply_profile(self.profile["id"])
        await self.message("availability", {"state": "online"})
        await self.message("command", {"request_id": "unique2", "action": "turn_on", "profile_id": self.profile["id"], "revision": 1, "page_id": self.profile["pages"][1]["id"], "parameters": {"entity_id": "light.other"}})
        self.hass.services.async_call.assert_not_called()

    async def test_heartbeat_and_ack_timeout(self):
        self.hub.online.add("panel1")
        self.hub.last_seen["panel1"] = monotonic() - 100
        await self.hub._maintenance(None)
        self.assertNotIn("panel1", self.hub.online)
        self.hub.online.add("panel1")
        self.hub.last_seen["panel1"] = monotonic()
        self.hub.results["panel1"] = "pending"
        self.hub.pending_since["panel1"] = monotonic() - 40
        await self.hub._maintenance(None)
        self.assertEqual(self.hub.results["panel1"], "timeout")

    async def test_failed_persistence_does_not_change_memory(self):
        before = deepcopy(self.hub.data)
        self.hub.store.async_save = AsyncMock(side_effect=OSError("Disk full"))
        with self.assertRaises(OSError):
            await self.hub.async_create_profile("Новий")
        self.assertEqual(self.hub.data, before)

    async def test_weather_forecasts_and_units_are_forwarded_and_cached(self):
        await self.hub.async_apply_profile(self.profile["id"])
        state = SimpleNamespace(entity_id="weather.home", state="rainy", attributes={"temperature_unit": "°F"})
        self.hass.states.get = lambda entity_id: state if entity_id == "weather.home" else None
        self.hass.services.async_call.return_value = {"weather.home": {"forecast": [{"datetime": "2026-10-03T12:00:00+03:00", "temperature": 65}]}}
        await self.hub._data("panel1")
        await self.hub._data("panel1")
        self.assertEqual(self.hass.services.async_call.await_count, 2)
        data = json.loads(mqtt.async_publish.call_args.args[2])
        weather = data["pages"][self.profile["pages"][0]["id"]]
        self.assertEqual(weather["attributes"]["temperature_unit"], "°F")
        self.assertEqual(weather["forecasts"]["hourly"][0]["temperature"], 65)

    async def test_unsupported_forecast_returns_null(self):
        await self.hub.async_apply_profile(self.profile["id"])
        state = SimpleNamespace(entity_id="weather.home", state="rainy", attributes={})
        self.hass.states.get = lambda entity_id: state if entity_id == "weather.home" else None
        self.hass.services.async_call.side_effect = ValueError("Forecast not supported")
        await self.hub._data("panel1")
        data = json.loads(mqtt.async_publish.call_args.args[2])
        weather = data["pages"][self.profile["pages"][0]["id"]]
        self.assertEqual(weather["forecasts"], {"daily": None, "hourly": None})

    async def test_delete_assigned_profile_is_rejected(self):
        before = deepcopy(self.hub.data)
        with self.assertRaises(ValueError):
            await self.hub.async_delete_profile(self.profile["id"], self.profile["revision"])
        self.assertEqual(self.hub.data, before)

    async def test_unassign_then_delete_removes_draft_and_applied_snapshot(self):
        await self.hub.async_apply_profile(self.profile["id"])
        self.hub.online.add("panel1")
        await self.hub.async_assign("panel1", None)
        config = json.loads(mqtt.async_publish.call_args.args[2])
        self.assertIsNone(config["profile"])
        await self.hub.async_delete_profile(self.profile["id"], self.profile["revision"])
        self.assertNotIn(self.profile["id"], self.hub.data["profiles"])
        self.assertNotIn(self.profile["id"], self.hub.store.saved["applied"])
        catalog = json.loads(mqtt.async_publish.call_args.args[2])
        self.assertEqual(catalog["profiles"], [])

    async def test_delete_stale_revision_rejected(self):
        await self.hub.async_assign("panel1", None)
        with self.assertRaises(ValueError):
            await self.hub.async_delete_profile(self.profile["id"], -1)
        self.assertIn(self.profile["id"], self.hub.data["profiles"])

    async def test_input_requirements_block_application_and_catalog(self):
        await self.hub.async_apply_profile(self.profile["id"])
        self.hub.data["panels"]["panel1"]["capabilities"]["inputs"]["encoder"] = False
        self.assertEqual(self.hub.snapshot()["panels"]["panel1"]["compatible_profiles"], [])
        with self.assertRaises(ValueError):
            await self.hub.async_apply_profile(self.profile["id"])

    async def test_delete_failed_save_preserves_profile(self):
        await self.hub.async_assign("panel1", None)
        before = deepcopy(self.hub.data)
        self.hub.store.async_save = AsyncMock(side_effect=OSError("Disk full"))
        with self.assertRaises(OSError):
            await self.hub.async_delete_profile(self.profile["id"], self.profile["revision"])
        self.assertEqual(self.hub.data, before)

    async def test_offline_unassignment_clears_after_reconnect(self):
        await self.hub.async_apply_profile(self.profile["id"])
        result = await self.hub.async_assign("panel1", None)
        self.assertEqual(result, "offline")
        mqtt.async_publish.reset_mock()
        await self.message("availability", {"state": "online"})
        configs = [json.loads(c.args[2]) for c in mqtt.async_publish.call_args_list if c.args[1].endswith("/config")]
        self.assertIsNone(configs[-1]["profile"])

    async def test_malformed_input_capabilities_do_not_replace_panel(self):
        before = deepcopy(self.hub.data)
        await self.message("hello", {"name":"Bad", "capabilities":{"templates":{"weather":1},"inputs":{"touch":"true"}}})
        self.assertEqual(self.hub.data, before)


if __name__ == "__main__":
    unittest.main()
