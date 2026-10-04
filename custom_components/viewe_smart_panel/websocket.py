"""Admin-only editor API."""

from homeassistant.components import websocket_api

from .const import DOMAIN
from .models import new_page, supported_light_types
from .schema_compat import vol


def async_register_commands(hass):
    websocket_api.async_register_command(hass, editor_command)


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/editor",
    vol.Required("action"): vol.In(["get", "create", "save", "apply", "assign", "page", "delete"]),
    vol.Optional("payload", default={}): dict,
})
@websocket_api.async_response
async def editor_command(hass, connection, msg):
    hub = hass.data.get(DOMAIN)
    if hub is None:
        connection.send_error(msg["id"], "not_loaded", "Інтеграція не завантажена")
        return
    try:
        action, payload = msg["action"], msg["payload"]
        if action == "get":
            result = hub.snapshot()
            result["entities"] = [
                {"entity_id": s.entity_id, "name": s.attributes.get("friendly_name", s.entity_id),
                 "types": supported_light_types(s.attributes) if s.domain == "light" else []}
                for s in hass.states.async_all() if s.domain in {"light", "weather", "switch"}
            ]
        elif action == "create":
            result = await hub.async_create_profile(payload["name"], payload.get("language", "uk"))
        elif action == "save":
            result = await hub.async_save_profile(payload["profile"])
        elif action == "apply":
            result = await hub.async_apply_profile(payload["profile_id"])
        elif action == "assign":
            result = await hub.async_assign(payload["panel_id"], payload["profile_id"])
        elif action == "delete":
            result = await hub.async_delete_profile(payload["profile_id"], payload["revision"])
        else:
            result = new_page(payload["template"], payload.get("language", "uk"))
        connection.send_result(msg["id"], result)
    except (ValueError, KeyError, TypeError) as err:
        connection.send_error(msg["id"], "invalid_config", str(err))
    except OSError:
        connection.send_error(msg["id"], "storage_error", "Не вдалося зберегти конфігурацію. Перевірте сховище Home Assistant")
