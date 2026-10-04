"""Switch validation and command routing with HA boundary fakes."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
import test_hub as fixtures
mqtt = fixtures.mqtt
from viewe_test_package.models import new_page, validate_profile, panel_compatible

class SwitchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.HubTests.asyncSetUp(self)
        self.page = new_page("switch", "en")
        self.page["entity_id"] = "switch.socket"
        self.profile["pages"] = [self.page]
        self.hass.states.async_all = lambda: [SimpleNamespace(entity_id="switch.socket", attributes={})]
        self.hass.states.get = lambda _: SimpleNamespace(entity_id="switch.socket", state="on", attributes={})
        self.hub.data["panels"]["panel1"]["capabilities"]["templates"]["switch"] = 1
        self.profile = await self.hub.async_save_profile(self.profile)
        await self.hub.async_apply_profile(self.profile["id"])
        self.hub.online.add("panel1")

    async def test_switch_actions_and_parameter_rejection(self):
        applied = self.hub.data["applied"][self.profile["id"]]
        payload = {"profile_id": applied["id"], "revision": applied["revision"], "page_id": self.page["id"]}
        for action in ("turn_on", "turn_off", "toggle"):
            await self.hub._command("panel1", {**payload, "action": action})
            self.hass.services.async_call.assert_awaited_with("switch", action, {"entity_id": "switch.socket"}, blocking=True)
        with self.assertRaises(ValueError):
            await self.hub._command("panel1", {**payload, "action": "turn_on", "parameters": {"brightness": 50}})

    async def test_state_data_and_domain_validation(self):
        await self.hub._data("panel1")
        import json
        packet = json.loads(mqtt.async_publish.call_args.args[2])
        self.assertEqual(packet["pages"][self.page["id"]]["state"], "on")
        wrong = deepcopy(self.profile)
        wrong["pages"][0]["entity_id"] = "light.socket"
        with self.assertRaises(ValueError):
            validate_profile(wrong)
        self.assertFalse(panel_compatible({"capabilities": {"templates": {"lighting": 1}}}, self.profile))

    async def test_switch_changes_push_state_to_panel(self):
        mqtt.async_publish.reset_mock()
        await self.hub._state_changed(SimpleNamespace(data={"entity_id": "switch.socket"}))
        self.assertTrue(mqtt.async_publish.await_count)
        self.assertTrue(mqtt.async_publish.call_args.args[1].endswith("/data"))
