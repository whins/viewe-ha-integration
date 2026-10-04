"""Check the local HACS package before publication, without external services."""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "viewe_smart_panel"
REPOSITORY = "https://github.com/whins/viewe-ha-integration"


def check():
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    components = ROOT / "custom_components"
    integration_dirs = sorted(p.name for p in components.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__")
    require(integration_dirs == [DOMAIN], "Exactly one integration must be packaged under custom_components.")
    integration = components / DOMAIN
    for relative in ("__init__.py", "config_flow.py", "frontend/panel.js", "frontend/locales/en.js", "frontend/locales/uk.js", "frontend/locales/errors.js", "strings.json", "translations/uk.json"):
        require((integration / relative).is_file(), f"Missing runtime asset: {relative}")

    json_values = {}
    for path in [ROOT / "hacs.json", *sorted(integration.rglob("*.json"))]:
        try:
            json_values[path] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            errors.append(f"Invalid or missing JSON file {path.relative_to(ROOT)}: {err}")

    manifest = json_values.get(integration / "manifest.json", {})
    for key in ("domain", "name", "documentation", "issue_tracker", "codeowners", "version"):
        require(bool(manifest.get(key)), f"Missing HACS integration metadata: {key}")
    require(manifest.get("domain") == DOMAIN, "Manifest domain must match its directory.")
    require(manifest.get("documentation") == REPOSITORY, "Documentation must point to the project repository.")
    require(manifest.get("issue_tracker") == REPOSITORY + "/issues", "Issue tracker must point to the project Issues page.")
    require(manifest.get("codeowners") == ["@whins"], "Use the actual maintainer handle in codeowners.")
    require(bool(re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", "")))), "Expected a numeric major.minor.patch version.")

    hacs = json_values.get(ROOT / "hacs.json", {})
    require(hacs.get("name") == manifest.get("name"), "HACS and integration display names must match.")
    require(hacs.get("content_in_root") is False, "Runtime content belongs in custom_components, not the repository root.")
    require(hacs.get("render_readme") is True, "HACS should render the English README.")
    require(not hacs.get("zip_release"), "This package uses repository files, not a release archive.")

    locale_values = {}
    for language in ("en", "uk"):
        path = integration / "frontend" / "locales" / f"{language}.js"
        try:
            source = path.read_text(encoding="utf-8")
            locale_values[language] = json.loads(source.removeprefix("export default ").strip().removesuffix(";"))
        except (OSError, ValueError) as err:
            errors.append(f"Invalid interface dictionary {language}: {err}")
    if "en" in locale_values and "uk" in locale_values:
        require(locale_values["en"].keys() == locale_values["uk"].keys(), "Update English and Ukrainian interface dictionaries together.")
        panel_source = (integration / "frontend" / "panel.js").read_text(encoding="utf-8")
        for key in re.findall(r'this\.t\("([A-Za-z]+)"\)', panel_source):
            require(key in locale_values["en"], f"Missing interface translation key: {key}")

    documents = [ROOT / "README.md", ROOT / "AGENTS.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for path in documents:
        text = path.read_text(encoding="utf-8")
        require(not re.search(r"[\u0400-\u04ff]", text), f"Documentation must be in English: {path.relative_to(ROOT)}")
        require(not re.search(r"[A-Za-z]:[/\\]Users[/\\]", text), f"Remove personal absolute paths from {path.relative_to(ROOT)}")
        for target in re.findall(r"\]\(([^\s)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            require((path.parent / target.split("#", 1)[0]).exists(), f"Broken documentation link in {path.relative_to(ROOT)}: {target}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Local HACS packaging checks passed. Remote HACS/hassfest and HA runtime validation remain separate checks.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
