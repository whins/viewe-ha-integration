"""Model tests without requiring a running Home Assistant."""

import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).parents[1] / "custom_components/viewe_smart_panel/models.py"
spec = importlib.util.spec_from_file_location("viewe_models", path)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class ProfileTests(unittest.TestCase):
    def ready(self):
        profile = models.new_profile("Дім")
        profile["pages"][0]["entity_id"] = "weather.home"
        profile["pages"][1]["entity_id"] = "light.kitchen"
        return profile

    def test_initial_pages_and_umbrella(self):
        profile = models.new_profile("Дім")
        self.assertEqual([p["template"] for p in profile["pages"]], ["weather", "lighting"])
        self.assertEqual(profile["pages"][0]["umbrella"]["probability"], 40)
        models.validate_profile(profile)

    def test_unfinished_draft_cannot_apply(self):
        profile = models.new_profile("Дім")
        models.validate_profile(profile)
        with self.assertRaises(ValueError):
            models.validate_profile(profile, apply=True, states={})

    def test_hidden_empty_page_does_not_block_apply(self):
        profile = self.ready()
        profile["pages"][1].update(visible=False, entity_id="")
        models.validate_profile(profile, apply=True, states={"weather.home": {}})
        profile["pages"][0]["visible"] = False
        with self.assertRaises(ValueError):
            models.validate_profile(profile, apply=True, states={})

    def test_duplicate_ids_rejected(self):
        profile = self.ready()
        profile["pages"][1]["id"] = profile["pages"][0]["id"]
        with self.assertRaises(ValueError):
            models.validate_profile(profile)

    def test_bad_weather_threshold_and_window(self):
        profile = self.ready()
        u = profile["pages"][0]["umbrella"]
        for value in (-1, 101, True, 40.5):
            u["probability"] = value
            with self.assertRaises(ValueError):
                models.validate_profile(profile)
        u["probability"] = 40
        u["forecast_start"] = "19:00"
        with self.assertRaises(ValueError):
            models.validate_profile(profile)

    def test_auto_rgbw_and_incompatible_override(self):
        page = models.new_page("lighting")
        attrs = {"supported_color_modes": ["rgbw"]}
        self.assertEqual(models.resolve_light_type(page, attrs), "RGBW")
        page["control_type"] = "RGBCCT"
        with self.assertRaises(ValueError):
            models.resolve_light_type(page, attrs)

    def test_apply_returns_independent_snapshot(self):
        profile = self.ready()
        validated = models.validate_profile(profile, apply=True, states={"weather.home": {}, "light.kitchen": {"supported_color_modes": ["rgbww"]}})
        self.assertEqual(validated["pages"][1]["resolved_type"], "RGBCCT")
        self.assertNotIn("resolved_type", profile["pages"][1])

    def test_input_capabilities_and_obsolete_requirements_do_not_filter_profiles(self):
        profile = self.ready()
        profile["requirements"] = {"encoder": True, "touch": True}
        panel = {"capabilities": {"templates": {"lighting": 1, "weather": 1}}}
        self.assertTrue(models.panel_compatible(panel, profile))
        panel["capabilities"]["inputs"] = {"encoder": False, "touch": False}
        self.assertTrue(models.panel_compatible(panel, profile))
        self.assertNotIn("requirements", models.validate_profile(profile))
        self.assertNotIn("requirements", models.new_profile("Home"))
        panel["capabilities"]["templates"].pop("weather")
        self.assertFalse(models.panel_compatible(panel, profile))

    def test_new_english_page_names(self):
        profile = models.new_profile("Home", "en")
        self.assertEqual([p["name"] for p in profile["pages"]], ["Weather", "Lighting"])

    def test_cct_auto_manual_and_color_only_rejection(self):
        page = models.new_page("lighting")
        attributes = {"supported_color_modes": ["color_temp"]}
        self.assertEqual(models.resolve_light_type(page, attributes), "CCT")
        page["control_type"] = "CCT"
        self.assertEqual(models.resolve_light_type(page, attributes), "CCT")
        self.assertIn("CCT", models.supported_light_types({"supported_color_modes": ["rgbww"]}))
        self.assertNotIn("CCT", models.supported_light_types({"supported_color_modes": ["rgbw"]}))
        with self.assertRaises(ValueError):
            models.resolve_light_type(page, {"supported_color_modes": ["rgb"]})

    def test_applied_cct_snapshot_and_rgb_types(self):
        profile = self.ready()
        profile["pages"][1]["control_type"] = "CCT"
        result = models.validate_profile(profile, apply=True, states={"weather.home": {}, "light.kitchen": {"supported_color_modes": ["color_temp"]}})
        self.assertEqual(result["pages"][1]["resolved_type"], "CCT")
        for mode, expected in (("rgb", "RGB"), ("rgbw", "RGBW"), ("rgbww", "RGBCCT")):
            self.assertEqual(models.resolve_light_type(models.new_page("lighting"), {"supported_color_modes": [mode]}), expected)


if __name__ == "__main__":
    unittest.main()
