"""VIEWE Smart Panel integration setup."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN, PANEL_URL, STATIC_URL, TITLE
from .hub import VieweHub
from .websocket import async_register_commands


async def async_setup_entry(hass, entry):
    settings = {**entry.data, **entry.options}
    hub = VieweHub(hass, settings.get("topic_prefix", "viewe"), settings.get("mqtt_enabled", True))
    await hub.async_start()
    hass.data[DOMAIN] = hub
    try:
        if not hass.data.get(f"{DOMAIN}_registered"):
            await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)])
            async_register_commands(hass)
            hass.data[f"{DOMAIN}_registered"] = True
        await panel_custom.async_register_panel(
            hass, frontend_url_path=PANEL_URL, webcomponent_name="viewe-panel",
            sidebar_title=TITLE, sidebar_icon="mdi:tablet-dashboard",
            module_url=f"{STATIC_URL}/panel.js", require_admin=True,
        )
    except Exception:
        hub.async_stop()
        hass.data.pop(DOMAIN, None)
        raise
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    hub = hass.data.pop(DOMAIN)
    hub.async_stop()
    frontend.async_remove_panel(hass, PANEL_URL)
    return True
