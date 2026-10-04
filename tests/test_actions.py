"""Action page validation and safe HA routing."""
from copy import deepcopy
from types import SimpleNamespace
import json
import unittest
import test_hub as fixtures
from viewe_test_package.models import new_page, validate_profile

class ActionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.HubTests.asyncSetUp(self)
        self.page = new_page("actions")
        self.page["actions"] = [{"entity_id":"script.scene", "name":""}, {"entity_id":"automation.scene", "name":"Custom"}]
        self.profile["pages"] = [self.page]
        self.hass.states.async_all = lambda: [SimpleNamespace(entity_id=a["entity_id"], attributes={"friendly_name":"HA name"}) for a in self.page["actions"]]
        self.hass.states.get = lambda target: SimpleNamespace(entity_id=target, state="off", attributes={})
        self.hub.data["panels"]["panel1"]["capabilities"]["templates"]["actions"] = 1
        self.profile = await self.hub.async_save_profile(self.profile)
        await self.hub.async_apply_profile(self.profile["id"])
        self.hub.online.add("panel1")
        applied = self.hub.data["applied"][self.profile["id"]]
        self.payload = {"profile_id":applied["id"], "revision":applied["revision"], "page_id":self.page["id"], "action":"run"}

    async def test_routes_both_targets_and_resolves_names(self):
        applied = self.hub.data["applied"][self.profile["id"]]
        self.assertEqual(applied["pages"][0]["actions"][0]["name"], "HA name")
        for i, domain, service in [(0,"script","turn_on"),(1,"automation","trigger")]:
            await self.hub._command("panel1", {**self.payload,"action_index":i})
            self.hass.services.async_call.assert_awaited_with(domain,service,{"entity_id":self.page["actions"][i]["entity_id"]},blocking=True)

    async def test_rejects_bad_index_parameters_and_offline_target(self):
        for index in [-1,2,True,"0"]:
            with self.assertRaises(ValueError):
                await self.hub._command("panel1",{**self.payload,"action_index":index})
        with self.assertRaises(ValueError):
            await self.hub._command("panel1",{**self.payload,"action_index":0,"parameters":{"entity_id":"script.other"}})
        self.hass.states.get = lambda _: None
        with self.assertRaises(ValueError):
            await self.hub._command("panel1",{**self.payload,"action_index":0})

    async def test_data_and_change_updates(self):
        await self.hub._data("panel1")
        packet=json.loads(fixtures.mqtt.async_publish.call_args.args[2])
        self.assertEqual(packet["pages"][self.page["id"]]["actions"], [{"state":"off"},{"state":"off"}])
        fixtures.mqtt.async_publish.reset_mock()
        await self.hub._state_changed(SimpleNamespace(data={"entity_id":"automation.scene"}))
        self.assertTrue(fixtures.mqtt.async_publish.await_count)

    async def test_rejects_wrong_domain_and_counts(self):
        for items in [[], self.page["actions"]*2, [{"entity_id":"light.bad","name":"Bad"}]]:
            profile=deepcopy(self.profile); profile["pages"][0]["actions"]=items
            with self.assertRaises(ValueError): validate_profile(profile)
        profile=deepcopy(self.profile); profile["pages"][0]["actions"]=self.page["actions"][:1]
        validate_profile(profile,apply=True,states={"script.scene":{"friendly_name":"Scene"}})
