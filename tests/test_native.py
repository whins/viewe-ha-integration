"""Native API contract and delivery tests using explicit HA boundary fakes."""

from copy import deepcopy
import importlib
import json
from time import monotonic
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import sys
from types import ModuleType

from test_hub import hub_module, mqtt

native = importlib.import_module("viewe_test_package.native")
models = importlib.import_module("viewe_test_package.models")
transport = importlib.import_module("viewe_test_package.native_hub")


def ready_profile():
    pages = []
    bindings = {"lighting": "light.room", "switch": "switch.room", "weather": "weather.home", "thermostat": "climate.room", "bc250": "binary_sensor.running"}
    for kind in ("lighting", "switch", "weather", "actions", "clock", "temperature_humidity", "thermostat", "bc250"):
        page = models.new_page(kind, "en")
        page["entity_id"] = bindings.get(kind, "")
        if kind == "actions":
            page["actions"] = [{"entity_id": "script.scene", "name": "Scene"}, {"entity_id": "automation.scene", "name": ""}]
        if kind == "temperature_humidity":
            page.update(temperature_entity_id="sensor.temperature", humidity_entity_id="sensor.humidity")
        if kind == "bc250":
            page["power_entity_id"] = "button.power"
        pages.append(page)
    return {"id": "home", "name": "Home", "revision": 1, "pages": pages}


class EncodingTests(unittest.TestCase):
    def test_each_clock_theme_reaches_native_profile_and_defaults_remain_compatible(self):
        page=models.new_page("clock","en")
        self.assertEqual(page["theme"],"digital")
        profile={"id":"clocks","name":"Clocks","revision":1,"pages":[page]}
        for theme in ("digital","stacked","analog","seconds_ring"):
            page["theme"]=theme
            checked=models.validate_profile(profile,apply=True,states={})
            widget=json.loads(native.encode_profile(checked))["widgets"][0]
            self.assertEqual(widget.get("theme","digital"),theme)
            self.assertEqual(widget["format"],"24h")
            if theme=="digital":self.assertNotIn("theme",widget)
        del page["theme"]
        widget=json.loads(native.encode_profile(profile))["widgets"][0]
        self.assertNotIn("theme",widget)
        for bad in ("other","",None,True,[],{}):
            page["theme"]=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):models.validate_profile(profile)
            with self.assertRaises(ValueError):native.encode_profile(profile)

    def test_names_and_optional_labels_are_distinct_in_native_v2(self):
        profile=ready_profile();page=profile["pages"][0]
        page.update(name="Editor name",label="Display caption",show_label=False)
        payload=json.loads(native.encode_profile(profile))
        self.assertEqual(payload["schema_version"],2)
        self.assertEqual(payload["widgets"][0]["name"],"Editor name")
        self.assertEqual(payload["widgets"][0]["label"],"Display caption")
        self.assertFalse(payload["widgets"][0]["show_label"])
        self.assertEqual(payload["widgets"][1]["label"],"")
        self.assertEqual(profile["pages"][0]["name"],"Editor name")

    def test_demo_all_templates_apply_without_live_entities(self):
        profile=ready_profile()
        for page in profile["pages"]:
            page["demo"]=True
            page["entity_id"]=""
            if page["template"]=="bc250": page["power_entity_id"]=""
            if page["template"]=="temperature_humidity": page.update(temperature_entity_id="",humidity_entity_id="")
            if page["template"]=="actions": page["actions"]=[{"entity_id":"","name":"Scene"}]
        applied=models.validate_profile(profile,apply=True,states={})
        widgets=json.loads(native.encode_profile(applied))["widgets"]
        self.assertTrue(all(w["demo"] for w in widgets))
        self.assertEqual(widgets[0]["entity_id"],"light.viewe_demo")
        self.assertEqual(widgets[-1]["control"]["entity_id"],"button.viewe_demo")
        self.assertFalse(models.panel_compatible({"capabilities":{"templates":{p["template"]:1 for p in profile["pages"]}}},applied))

    def test_demo_false_never_bypasses_live_validation_and_bad_flag_rejected(self):
        profile=ready_profile()
        for page in profile["pages"]: page["demo"]=False
        with self.assertRaises(ValueError): models.validate_profile(profile,apply=True,states={})
        profile["pages"][0]["demo"]="true"
        with self.assertRaisesRegex(ValueError,"demo"): models.validate_profile(profile)

    def test_normal_delivery_does_not_add_demo_field_to_old_firmware(self):
        widgets=json.loads(native.encode_profile(ready_profile()))["widgets"]
        self.assertTrue(all("demo" not in w for w in widgets))

    def test_onoff_light_can_use_automatic_type(self):
        self.assertEqual(models.resolve_light_type({"control_type": "AUTO"}, {"supported_color_modes": ["onoff"]}), "MONO")

    def test_all_types_and_bc250_guard(self):
        profile = json.loads(native.encode_profile(ready_profile()))
        self.assertEqual([w["type"] for w in profile["widgets"]], ["light", "switch", "weather", "actions", "clock", "temperature_humidity", "thermostat", "switch"])
        bc = profile["widgets"][-1]
        self.assertEqual(bc["control"]["guard_script"], "script.viewe_guarded_start")
        self.assertEqual(bc["control"]["confirmation_timeout"], 10)
        self.assertNotIn("entity_id", bc)
        self.assertEqual(bc["layout"], "fullscreen")

    def test_hidden_widgets_and_options(self):
        profile = ready_profile()
        profile["pages"][0].update(show_label=False, disabled_pages=["cct"], icon="steam")
        profile["pages"][1]["visible"] = False
        widgets = json.loads(native.encode_profile(profile))["widgets"]
        self.assertEqual(len(widgets), 7)
        self.assertEqual(widgets[0]["disabled_pages"], ["cct"])
        self.assertFalse(widgets[0]["show_label"])

    def test_device_limits_utf8_ids_and_page_names(self):
        for change in ("count", "bytes", "id", "page", "label"):
            profile = ready_profile()
            if change == "count":
                profile["pages"] = [dict(profile["pages"][4], id=f"clock_{i}") for i in range(17)]
            elif change == "bytes":
                profile["pages"] = [dict(profile["pages"][-1], id="x"*60+str(i), name="n"*128, power_entity_id="button."+"b"*120, entity_id="binary_sensor."+"a"*110, guard_script="script."+"c"*120) for i in range(16)]
            elif change == "id":
                profile["id"] = "invalid/id"
            elif change == "page":
                profile["pages"][0]["disabled_pages"] = ["main"]
            else:
                profile["pages"][0]["name"] = "ї"*65
            with self.subTest(change=change), self.assertRaises(ValueError):
                native.encode_profile(profile)

    def test_minute_weather_and_forced_light_type_are_not_silently_changed(self):
        profile = ready_profile()
        profile["pages"][2]["umbrella"]["forecast_start"] = "08:30"
        with self.assertRaisesRegex(ValueError, "whole hours"):
            native.encode_profile(profile)
        profile = ready_profile()
        profile["pages"][0]["control_type"] = "RGB"
        with self.assertRaisesRegex(ValueError, "AUTO"):
            native.encode_profile(profile)

    def test_new_widget_drafts_and_entity_validation(self):
        states = {target: {"supported_color_modes": ["rgbw"]} for page in ready_profile()["pages"] for target in [page.get("entity_id"), page.get("power_entity_id"), page.get("temperature_entity_id"), page.get("humidity_entity_id"), "script.scene", "automation.scene"] if target}
        models.validate_profile(ready_profile(), apply=True, states=states)
        for kind in ("clock", "temperature_humidity", "thermostat"):
            profile = {"id": "draft", "name": "Draft", "revision": 0, "pages": [models.new_page(kind)]}
            models.validate_profile(profile)
            if kind != "clock":
                with self.assertRaises(ValueError):
                    models.validate_profile(profile, apply=True, states={})

    def test_mqtt_does_not_claim_new_widgets_or_options(self):
        panel = {"capabilities": {"templates": {"lighting": 1}}}
        profile = ready_profile()
        self.assertFalse(models.panel_compatible(panel, profile))
        profile["pages"] = profile["pages"][:1]
        profile["pages"][0]["label"]=profile["pages"][0]["name"]
        self.assertTrue(models.panel_compatible(panel, profile))
        profile["pages"][0]["show_label"] = False
        self.assertFalse(models.panel_compatible(panel, profile))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.device = SimpleNamespace(id="device", config_entries={"entry", "other"})
        self.info = SimpleNamespace(name="viewe-panel", friendly_name="Panel", mac_address="aa:bb:cc:dd:ee:ff")
        self.runtime = SimpleNamespace(device_info=self.info, available=True, services={i: SimpleNamespace(name=name) for i, name in enumerate(native.ACTIONS)})
        self.entry = SimpleNamespace(entry_id="entry", runtime_data=self.runtime)
        self.hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _: [self.entry]), services=SimpleNamespace(has_service=lambda *args: True))
        self.registry = SimpleNamespace(async_get_device=lambda **kwargs: self.device)
        self.dr = ModuleType("homeassistant.helpers.device_registry")
        self.dr.async_get = lambda _: self.registry
        self.dr.CONNECTION_NETWORK_MAC = "mac"
        self.dr.format_mac = lambda mac: mac.lower()

    def discover(self):
        with patch.dict(sys.modules, {"homeassistant.helpers.device_registry": self.dr}):
            return native.discover(self.hass)

    def test_verified_config_entry_device_and_action_mapping(self):
        result = self.discover()["esp_entry"]
        self.assertEqual(result["device_id"], "device")
        self.assertEqual(result["actions"]["viewe_apply_profile"], "viewe_panel_viewe_apply_profile")
        self.assertTrue(result["available"])
        self.runtime.available = False
        self.assertFalse(self.discover()["esp_entry"]["available"])

    def test_non_viewe_devices_missing_actions_and_wrong_device_are_ignored(self):
        self.runtime.services = {}
        self.assertEqual(self.discover(), {})
        self.runtime.services = {i: SimpleNamespace(name=name) for i, name in enumerate(native.ACTIONS)}
        self.device.config_entries = {"unrelated"}
        self.assertEqual(self.discover(), {})

    def test_duplicate_node_names_fail_closed(self):
        self.hass.config_entries.async_entries = lambda _: [self.entry, SimpleNamespace(entry_id="other", runtime_data=self.runtime)]
        self.assertEqual(self.discover(), {})


class NativeDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_native_panel_waits_for_explicit_refresh_to_rediscover(self):
        self.hass.config_entries=SimpleNamespace()
        await self.event()
        await self.hub.async_delete_panel("esp_one")
        self.hass.services.async_call.reset_mock()
        with patch.object(transport,"discover",return_value={"esp_one":self.node}):
            await self.hub._native_poll()
            self.assertNotIn("esp_one",self.hub.data["panels"])
            self.assertTrue(self.hub.native_detected)
            self.hass.services.async_call.assert_not_awaited()
            await self.hub.async_refresh_panels()
        self.assertIn("esp_one",self.hub.data["panels"])
        self.assertIsNone(self.hub.data["panels"]["esp_one"]["profile_id"])
        self.assertTrue(self.hass.services.async_call.call_args.args[1].endswith("viewe_profile_status"))

    async def test_late_native_receipt_cannot_restore_a_deleted_panel(self):
        await self.event()
        await self.hub.async_delete_panel("esp_one")
        await self.event("profile_applied","home","1")
        self.assertNotIn("esp_one",self.hub.data["panels"])
        self.assertNotIn("esp_one",self.hub.online)

    async def test_bc250_demo_does_not_require_guard_or_real_entities(self):
        for page in self.hub.data["applied"]["home"]["pages"]: page["demo"]=True
        self.hass.states.get=lambda _:None
        await self.event()
        self.assertEqual(self.hub.results["esp_one"],"pending")
        self.assertTrue(all(w["demo"] for w in json.loads(self.hass.services.async_call.call_args.args[2]["payload"])["widgets"]))
        self.assertEqual(self.hass.services.async_call.call_args.args[0],"esphome")

    async def test_mqtt_demo_command_never_controls_real_entity(self):
        page=self.hub.data["applied"]["home"]["pages"][1];page["demo"]=True
        with self.assertRaises(ValueError):
            await self.hub._command("esp_one",{"profile_id":"home","revision":1,"page_id":page["id"],"action":"toggle"})
        self.hass.services.async_call.assert_not_awaited()

    async def asyncSetUp(self):
        self.hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: SimpleNamespace(state="on"), async_all=lambda: []), services=SimpleNamespace(async_call=AsyncMock()))
        self.hub = hub_module.VieweHub(self.hass, "viewe", mqtt_enabled=False)
        self.profile = ready_profile()
        self.hub.data["profiles"]["home"] = deepcopy(self.profile)
        self.hub.data["applied"]["home"] = deepcopy(self.profile)
        self.hub.data["panels"]["esp_one"] = {"id": "esp_one", "name": "Panel", "transport": "esphome", "profile_id": "home"}
        self.node = {"id": "esp_one", "name": "Panel", "device_id": "device-one", "node_name": "viewe-panel", "available": True, "actions": {action: "viewe_panel_"+action for action in native.ACTIONS}}
        self.hub.native_nodes = {"esp_one": self.node}
        mqtt.async_publish.reset_mock()

    async def event(self, name="profile_status", profile_id="yaml", revision="0", **fields):
        await self.hub._native_event(SimpleNamespace(data={"device_id": "device-one", "panel": "viewe-panel", "event": name, "profile_id": profile_id, "revision": revision, "detail": "active", **fields}))

    async def test_reconnect_delivers_applied_snapshot_and_waits_for_receipt(self):
        self.hub.data["profiles"]["home"]["revision"] = 2
        await self.event()
        self.assertEqual(self.hub.results["esp_one"], "pending")
        call = self.hass.services.async_call.call_args
        self.assertEqual(call.args[1], "viewe_panel_viewe_apply_profile")
        self.assertEqual(json.loads(call.args[2]["payload"])["revision"], 1)
        await self.event("profile_applied", "home", "99")
        self.assertEqual(self.hub.results["esp_one"], "pending")
        await self.event("profile_applied", "home", "1")
        self.assertEqual(self.hub.results["esp_one"], "applied")
        self.assertTrue(self.hub.snapshot()["panels"]["esp_one"]["online"])
        mqtt.async_publish.assert_not_called()

    async def test_wrong_device_or_node_cannot_acknowledge(self):
        await self.event(device_id="other")
        await self.event(panel="other")
        self.hass.services.async_call.assert_not_awaited()
        self.assertNotIn("esp_one", self.hub.online)

    async def test_local_reset_survives_reconnect_and_explicit_resume_waits_for_allow(self):
        await self.event(detail="yaml_override_active")
        self.hass.services.async_call.assert_not_awaited()
        self.hub.online.clear()
        await self.event(detail="yaml_override_active")
        self.hass.services.async_call.assert_not_awaited()
        self.assertTrue(self.hub.store.saved["panels"]["esp_one"]["remote_blocked"])
        await self.hub.async_assign("esp_one", "home")
        self.assertTrue(self.hass.services.async_call.call_args.args[1].endswith("viewe_allow_remote_profiles"))
        await self.event("remote_profiles_allowed")
        self.assertTrue(self.hass.services.async_call.call_args.args[1].endswith("viewe_apply_profile"))
        await self.event("profile_applied", "home", "1")
        self.assertFalse(self.hub.data["panels"]["esp_one"]["remote_blocked"])

    async def test_offline_unassign_resets_on_next_connection(self):
        self.assertEqual(await self.hub.async_assign("esp_one", None), "offline")
        await self.event("profile_status", "home", "1")
        self.assertTrue(self.hass.services.async_call.call_args.args[1].endswith("viewe_reset_profile"))
        await self.event("profile_reset", detail="yaml_override_active")
        self.assertEqual(self.hub.results["esp_one"], "unassigned")
        self.assertNotIn("reset_requested", self.hub.data["panels"]["esp_one"])

    async def test_local_reset_cancels_an_older_pending_resume(self):
        await self.event(detail="yaml_override_active")
        await self.hub.async_assign("esp_one", "home")
        self.hass.services.async_call.reset_mock()
        await self.event("profile_reset", detail="yaml_override_active")
        self.assertNotIn("resume_requested", self.hub.data["panels"]["esp_one"])
        self.hass.services.async_call.assert_not_awaited()
        await self.event(detail="yaml_override_active")
        self.hass.services.async_call.assert_not_awaited()

    async def test_failed_native_call_queues_applied_profile_until_reconnect(self):
        self.hass.services.async_call.side_effect = OSError("Disconnected")
        with self.assertLogs(transport.__name__, level="ERROR"):
            await self.event()
        self.assertEqual(self.hub.results["esp_one"], "offline")
        self.assertNotIn("esp_one", self.hub.online)
        self.hass.services.async_call.side_effect = None
        await self.event()
        self.assertEqual(self.hub.results["esp_one"], "pending")

    async def test_rejected_profile_keeps_detail_and_does_not_retry_every_poll(self):
        await self.event()
        await self.event("profile_rejected", detail="storage_failed")
        self.assertEqual(self.hub.results["esp_one"], "error")
        self.assertEqual(self.hub.native_errors["esp_one"], "storage_failed")
        self.hass.services.async_call.reset_mock()
        await self.event()
        self.hass.services.async_call.assert_not_awaited()

    async def test_timeout_does_not_retry_without_reconnect(self):
        await self.event()
        self.hub.pending_since["esp_one"] = monotonic()-31
        await self.hub._maintenance(None)
        self.assertEqual(self.hub.results["esp_one"], "timeout")
        self.hass.services.async_call.reset_mock()
        await self.event()
        self.hass.services.async_call.assert_not_awaited()

    async def test_new_revision_waits_for_previous_receipt(self):
        await self.event()
        self.hub.data["applied"]["home"]["revision"] = 2
        await self.hub._deliver("esp_one")
        self.assertEqual(self.hass.services.async_call.await_count, 1)
        await self.event("profile_applied", "home", "1")
        self.assertEqual(json.loads(self.hass.services.async_call.call_args.args[2]["payload"])["revision"], 2)
        self.assertEqual(self.hub.results["esp_one"], "pending")

    async def test_missing_bc250_guard_rejects_assignment_before_saving(self):
        self.hass.states.get = lambda _: None
        before = deepcopy(self.hub.data)
        with self.assertRaisesRegex(ValueError, "guard script"):
            await self.hub.async_assign("esp_one", "home")
        self.assertEqual(self.hub.data, before)

    async def test_native_states_never_use_mqtt_and_mqtt_disconnect_preserves_native(self):
        await self.event("profile_status", "home", "1")
        await self.hub._data("esp_one")
        self.hub._connection_changed(False)
        self.assertIn("esp_one", self.hub.online)
        await self.hub._refresh()
        mqtt.async_publish.assert_not_called()

    async def test_mqtt_cannot_acknowledge_or_replace_a_native_panel(self):
        await self.event()
        before = deepcopy(self.hub.data)
        for suffix, values in (("hello", {"name": "Other", "capabilities": {"templates": {"switch": 1}}}),
                               ("ack", {"profile_id": "home", "revision": 1, "status": "applied"})):
            await self.hub._message(SimpleNamespace(topic=f"viewe/panels/esp_one/{suffix}", payload=json.dumps({"protocol": 1, **values}), retain=False))
        self.assertEqual(self.hub.data, before)
        self.assertEqual(self.hub.results["esp_one"], "pending")

    async def test_discovery_does_not_reset_an_unassigned_yaml_profile(self):
        self.hass.config_entries = SimpleNamespace()
        self.hub.data["panels"] = {}
        with patch.object(transport, "discover", return_value={"esp_one": self.node}):
            await self.hub._native_poll()
        self.assertTrue(self.hass.services.async_call.call_args.args[1].endswith("viewe_profile_status"))
        self.hass.services.async_call.reset_mock()
        await self.event()
        self.hass.services.async_call.assert_not_awaited()

    async def test_start_migrates_drafts_and_applied_without_overwriting_empty_labels(self):
        self.hass.bus=SimpleNamespace(async_listen=lambda *args:lambda:None)
        legacy=ready_profile();legacy["pages"][0].pop("label")
        self.hub.store.saved={"profiles":{"home":deepcopy(legacy)},"applied":{"home":deepcopy(legacy)},"panels":{}}
        await self.hub.async_start()
        for collection in ("profiles","applied"):
            pages=self.hub.store.saved[collection]["home"]["pages"]
            self.assertEqual(pages[0]["label"],pages[0]["name"])
            self.assertEqual(pages[1]["label"],"")
        self.hub.async_stop()

    async def test_native_only_start_does_not_subscribe_to_mqtt(self):
        self.hass.bus = SimpleNamespace(async_listen=lambda *args: lambda: None)
        await self.hub.async_start()
        mqtt.async_publish.assert_not_called()
        self.hub.async_stop()
