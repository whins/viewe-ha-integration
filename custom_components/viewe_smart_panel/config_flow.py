"""Set up the single VIEWE profile hub through the HA UI."""

from homeassistant import config_entries
from homeassistant.components import mqtt

from .const import DEFAULT_PREFIX, DOMAIN, TITLE
from .schema_compat import vol


class VieweConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the hub; broker credentials belong to HA MQTT."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        try:
            mqtt_connected = mqtt.is_connected(self.hass)
        except KeyError:
            mqtt_connected = False
        if user_input is not None:
            prefix = user_input["topic_prefix"].strip()
            if not prefix or any(c in prefix for c in "+#\x00") or prefix.startswith("/") or prefix.endswith("/"):
                errors["topic_prefix"] = "invalid_prefix"
            elif not mqtt_connected:
                errors["base"] = "mqtt_unavailable"
            else:
                return self.async_create_entry(title=TITLE, data={"topic_prefix": prefix})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("topic_prefix", default=DEFAULT_PREFIX): str}),
            errors=errors,
        )
