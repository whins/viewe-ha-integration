"""BC-250 start-only routing and confirmed state."""
from types import SimpleNamespace
import json
import unittest
import test_hub as fixtures
from viewe_test_package.models import new_page, validate_profile

class BC250Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.HubTests.asyncSetUp(self)
        self.page = new_page('bc250')
        self.page.update(entity_id='binary_sensor.bc250_running', power_entity_id='button.bc250_power')
        self.profile['pages'] = [self.page]
        self.running = 'off'
        self.power = '2026-10-09T12:00:00'
        self.hass.states.get = lambda target: SimpleNamespace(entity_id=target,state=self.running if target.startswith('binary_sensor.') else self.power,attributes={})
        self.hass.states.async_all = lambda: [SimpleNamespace(entity_id=self.page[key],attributes={}) for key in ('entity_id','power_entity_id')]
        self.hub.data['panels']['panel1']['capabilities']['templates']['bc250'] = 1
        self.profile = await self.hub.async_save_profile(self.profile)
        await self.hub.async_apply_profile(self.profile['id'])
        self.hub.online.add('panel1')
        self.payload = dict(profile_id=self.profile['id'],revision=self.profile['revision'],page_id=self.page['id'],action='start')

    async def test_start_uses_configured_button(self):
        await self.hub._command('panel1', self.payload)
        self.hass.services.async_call.assert_awaited_with('button','press',{'entity_id':'button.bc250_power'},blocking=True)

    async def test_running_and_offline_never_press(self):
        for value in ('on','unknown','unavailable'):
            self.running=value
            with self.assertRaises(ValueError): await self.hub._command('panel1',self.payload)
        self.running='off';self.power='unavailable'
        with self.assertRaises(ValueError): await self.hub._command('panel1',self.payload)
        self.hass.services.async_call.assert_not_awaited()

    async def test_state_and_sensor_updates(self):
        self.running='on'
        await self.hub._data('panel1')
        packet=json.loads(fixtures.mqtt.async_publish.call_args.args[2])
        self.assertEqual(packet['pages'][self.page['id']], {'state':'on','available':True})
        fixtures.mqtt.async_publish.reset_mock()
        await self.hub._state_changed(SimpleNamespace(data={'entity_id':self.page['entity_id']}))
        self.assertTrue(fixtures.mqtt.async_publish.await_count)
        self.power='unavailable'
        await self.hub._data('panel1')
        packet=json.loads(fixtures.mqtt.async_publish.call_args.args[2])
        self.assertFalse(packet['pages'][self.page['id']]['available'])

    async def test_rejects_toggle_and_parameters(self):
        for changes in ({'action':'toggle'},{'parameters':{'entity_id':'button.other'}}):
            with self.assertRaises(ValueError): await self.hub._command('panel1',{**self.payload,**changes})

    def test_requires_correct_entities(self):
        self.profile['pages'][0]['power_entity_id']='switch.psu'
        with self.assertRaises(ValueError):validate_profile(self.profile)
