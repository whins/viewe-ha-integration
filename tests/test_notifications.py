"""Persistent notification grace periods, lifecycle and HA boundary behavior."""
from copy import deepcopy
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import test_hub as fixtures

PanelNotifications = importlib.import_module("viewe_test_package.notifications").PanelNotifications


class NotificationTests(unittest.TestCase):
    def setUp(self):
        fixtures.notifications.async_create.reset_mock()
        fixtures.notifications.async_dismiss.reset_mock()
        self.manager = PanelNotifications(SimpleNamespace(config=SimpleNamespace(language="en")), "viewe")
        self.problem = {"profile_id":"home", "revision":1, "reason":"delivery", "name":"Kitchen", "profile_name":"Home"}

    def update(self, time, **changes):
        self.manager.update({"panel":{**self.problem,**changes}},time)

    def test_delivery_failure_requires_two_minutes_and_notifies_once_per_episode(self):
        self.update(10);self.update(129)
        fixtures.notifications.async_create.assert_not_called()
        self.update(130);self.update(999)
        fixtures.notifications.async_create.assert_called_once()
        call=fixtures.notifications.async_create.call_args
        self.assertIn("2 minutes",call.args[1])
        self.assertEqual(call.kwargs["notification_id"],self.manager.notification_id("panel"))

    def test_offline_requires_five_minutes(self):
        self.update(0,reason="offline");self.update(299,reason="offline")
        fixtures.notifications.async_create.assert_not_called()
        self.update(300,reason="offline")
        fixtures.notifications.async_create.assert_called_once()
        self.assertIn("5 minutes",fixtures.notifications.async_create.call_args.args[1])

    def test_recovery_clears_own_notification_and_a_new_episode_has_a_new_grace_period(self):
        self.update(0);self.update(120)
        self.manager.update({},121)
        fixtures.notifications.async_dismiss.assert_called_once_with(self.manager.hass,self.manager.notification_id("panel"))
        self.update(122);self.update(241)
        self.assertEqual(fixtures.notifications.async_create.call_count,1)
        self.update(242)
        self.assertEqual(fixtures.notifications.async_create.call_count,2)

    def test_revision_or_reason_change_resets_timer_and_replaces_the_old_issue(self):
        self.update(0);self.update(120)
        self.update(121,revision=2)
        fixtures.notifications.async_dismiss.assert_called_once()
        self.update(240,revision=2)
        self.assertEqual(fixtures.notifications.async_create.call_count,1)
        self.update(241,revision=2)
        self.assertEqual(fixtures.notifications.async_create.call_count,2)
        self.update(242,revision=2,reason="offline")
        self.update(541,revision=2,reason="offline")
        self.assertEqual(fixtures.notifications.async_create.call_count,2)

    def test_manual_dismissal_is_not_undone_by_repeated_checks(self):
        self.update(0);self.update(120)
        fixtures.notifications.async_dismiss(self.manager.hass,self.manager.notification_id("panel"))
        self.update(1000)
        self.assertEqual(fixtures.notifications.async_create.call_count,1)

    def test_ids_are_scoped_and_unload_clears_only_own_issues(self):
        self.update(0);self.update(120)
        other=PanelNotifications(self.manager.hass,"other_prefix")
        self.assertNotEqual(self.manager.notification_id("panel"),other.notification_id("panel"))
        self.assertNotEqual(self.manager.notification_id("panel"),self.manager.notification_id("second"))
        self.manager.close();self.manager.close()
        fixtures.notifications.async_dismiss.assert_called_once()
        self.assertEqual(self.manager.issues,{})

    def test_ukrainian_messages_escape_names_and_link_back_to_editor(self):
        self.manager.hass.config.language="uk"
        self.update(0,name="[Panel](unsafe)");self.update(120,name="[Panel](unsafe)")
        message=fixtures.notifications.async_create.call_args.args[1]
        self.assertIn("понад 2 хвилини",message)
        self.assertIn("(/viewe-smart-panel)",message)
        self.assertNotIn("[Panel](unsafe)",message)
        self.assertIn("Panel",message)


class HubNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.HubTests.asyncSetUp(self)
        fixtures.notifications.async_create.reset_mock();fixtures.notifications.async_dismiss.reset_mock()
        self.hub.data["applied"][self.profile["id"]]=deepcopy(self.profile)

    def sync(self,time):
        with patch("viewe_test_package.hub.monotonic",return_value=time):self.hub._sync_notifications()

    async def test_maintenance_notifies_for_assigned_offline_panel_and_recovery_clears(self):
        self.sync(0);self.hub._native_poll=AsyncMock()
        with patch("viewe_test_package.hub.monotonic",return_value=301):await self.hub._maintenance(None)
        fixtures.notifications.async_create.assert_called_once()
        self.hub.online.add("panel1");self.hub.results["panel1"]="applied";self.sync(302)
        fixtures.notifications.async_dismiss.assert_called_once()

    async def test_unassigned_panels_and_deliberate_local_override_do_not_notify(self):
        self.hub.results["panel1"]="local_override";self.sync(0);self.sync(1000)
        fixtures.notifications.async_create.assert_not_called()
        self.hub.data["panels"]["panel1"]["profile_id"]=None;self.hub.results["panel1"]="offline"
        self.sync(1001);self.sync(2000)
        fixtures.notifications.async_create.assert_not_called()

    async def test_panel_deletion_dismisses_and_failed_persistence_keeps_the_warning(self):
        self.sync(0);self.sync(301)
        self.hub.store.async_save=AsyncMock(side_effect=OSError("Disk full"))
        with self.assertRaises(OSError):await self.hub.async_delete_panel("panel1")
        fixtures.notifications.async_dismiss.assert_not_called()
        self.hub.store.async_save=AsyncMock()
        await self.hub.async_delete_panel("panel1")
        fixtures.notifications.async_dismiss.assert_called_once()
        self.assertNotIn("panel1",self.hub.notifications.issues)

    async def test_unassigning_profile_dismisses_and_unloading_cleans_notifications(self):
        self.sync(0);self.sync(301)
        await self.hub.async_assign("panel1",None)
        fixtures.notifications.async_dismiss.assert_called_once()
        self.assertEqual(self.hub.notifications.issues,{})
        self.hub.async_stop()
        self.assertEqual(fixtures.notifications.async_dismiss.call_count,1)
