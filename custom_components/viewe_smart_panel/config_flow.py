"""Set up the single VIEWE profile hub through the HA UI."""

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback

from .const import DEFAULT_PREFIX, DOMAIN, TITLE
from .schema_compat import vol


def _mqtt_available(hass):
    try:
        return mqtt.is_connected(hass)
    except KeyError:
        return False


class VieweConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the hub; broker credentials belong to HA MQTT."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return VieweOptionsFlow()

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        mqtt_connected = _mqtt_available(self.hass)
        if user_input is not None:
            prefix = user_input.get("topic_prefix", DEFAULT_PREFIX).strip()
            mqtt_enabled = user_input.get("mqtt_enabled", False)
            if not prefix or any(c in prefix for c in "+#\x00") or prefix.startswith("/") or prefix.endswith("/"):
                errors["topic_prefix"] = "invalid_prefix"
            elif mqtt_enabled and not mqtt_connected:
                errors["base"] = "mqtt_unavailable"
            else:
                return self.async_create_entry(title=TITLE, data={"topic_prefix": prefix, "mqtt_enabled": mqtt_enabled})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional("mqtt_enabled", default=False): bool, vol.Optional("topic_prefix", default=DEFAULT_PREFIX): str}),
            errors=errors,
        )


class VieweOptionsFlow(config_entries.OptionsFlow):
    """Allow existing MQTT installations to switch to Native API only."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            prefix = user_input.get("topic_prefix", DEFAULT_PREFIX).strip()
            if not prefix or any(c in prefix for c in "+#\x00") or prefix.startswith("/") or prefix.endswith("/"):
                errors["topic_prefix"] = "invalid_prefix"
            elif user_input.get("mqtt_enabled") and not _mqtt_available(self.hass):
                errors["base"] = "mqtt_unavailable"
            else:
                return self.async_create_entry(title="", data={"topic_prefix": prefix, "mqtt_enabled": user_input.get("mqtt_enabled", False)})
        values = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional("mqtt_enabled", default=values.get("mqtt_enabled", True)): bool,
            vol.Optional("topic_prefix", default=values.get("topic_prefix", DEFAULT_PREFIX)): str,
        }), errors=errors)
