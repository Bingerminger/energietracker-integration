"""What HACS and Home Assistant expect from the repository, checked without Home Assistant.

Standard library only:

    python3 -I -m unittest discover -s tests

* every translation has the keys and placeholders of ``en.json``,
* every translation key the code uses exists,
* manifest.json and hacs.json carry what HACS needs,
* the brand images have the size and the alpha channel Home Assistant wants.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import string
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "energietracker"
TRANSLATIONS = INTEGRATION / "translations"
LANGUAGES = ("de", "en", "es", "fr", "it", "nl", "pt")

#: Where Energietracker 3.12 shows the address of its app in Home Assistant and
#: the API keys, in the words of its own catalogues (``nav.connections``,
#: ``connections.keys.title``, ``settings.security.keysTitle``).
MENU_3_12 = {
    "de": ("Verbindungen → Home Assistant", "Verbindungen → Schlüssel → API-Schlüssel für Skripte"),
    "en": ("Connections → Home Assistant", "Connections → Keys → API keys for scripts"),
    "es": ("Conexiones → Home Assistant", "Conexiones → Claves → Claves de API para scripts"),
    "fr": ("Connexions → Home Assistant", "Connexions → Clés → Clés d’API pour les scripts"),
    "it": ("Connessioni → Home Assistant", "Connessioni → Chiavi → Chiavi API per script"),
    "nl": ("Verbindingen → Home Assistant", "Verbindingen → Sleutels → API-sleutels voor scripts"),
    "pt": ("Ligações → Home Assistant", "Ligações → Chaves → Chaves de API para scripts"),
}

_SPEC = importlib.util.spec_from_file_location("energietracker_logic", INTEGRATION / "logic.py")
logic = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(logic)


def load(name: str) -> dict:
    return json.loads((TRANSLATIONS / f"{name}.json").read_text(encoding="utf-8"))


def flatten(obj: dict, prefix: str = "") -> dict[str, str]:
    out = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, path))
        else:
            out[path] = value
    return out


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def source(name: str) -> str:
    return (INTEGRATION / name).read_text(encoding="utf-8")


class TranslationTest(unittest.TestCase):
    EN = flatten(load("en"))

    def test_all_languages_present(self):
        self.assertEqual(set(LANGUAGES), {p.stem for p in TRANSLATIONS.glob("*.json")})

    def test_same_keys_and_placeholders_as_english(self):
        for lang in LANGUAGES:
            other = flatten(load(lang))
            self.assertEqual(set(self.EN), set(other), lang)
            for key, text in self.EN.items():
                self.assertTrue(other[key].strip(), f"{lang}: {key} empty")
                self.assertEqual(placeholders(text), placeholders(other[key]), f"{lang}: {key}")
                # hassfest: "the string should not contain URLs, please use description placeholders"
                self.assertNotRegex(other[key], r"https?://[\w\[]", f"{lang}: {key}")

    def test_keys_used_in_the_code_exist(self):
        sensor_keys = set(re.findall(r'_attr_translation_key = "(\w+)"', source("sensor.py"))) | set(logic.METER_SENSORS)
        for key in sensor_keys:
            self.assertIn(f"entity.sensor.{key}.name", self.EN, key)
        for key in set(re.findall(r'errors\[[^\]]+\] = "(\w+)"', source("config_flow.py"))):
            self.assertIn(f"config.error.{key}", self.EN, key)
        coordinator = source("coordinator.py")
        for key in set(re.findall(r'translation_key="(\w+)"', coordinator)):
            self.assertTrue(f"exceptions.{key}.message" in self.EN or f"issues.{key}.title" in self.EN, key)
        self.assertIn("issues.app_too_old.description", self.EN)
        for reason in ("already_configured", "reauth_successful"):
            self.assertIn(f"config.abort.{reason}", self.EN)

    def test_setup_names_the_menu_of_energietracker_3_12(self):
        """Since Energietracker 3.12 the address of the app and the API keys sit under "Connections"."""
        for lang, paths in MENU_3_12.items():
            text = load(lang)["config"]["step"]["user"]["description"]
            for path in paths:
                self.assertIn(path, text, lang)
            # up to 3.11 both sat under the settings; that path stays only as a hint for older versions
            self.assertIn("3.11", text, lang)

    def test_attribute_names_match_the_logic(self):
        sensors = load("en")["entity"]["sensor"]
        self.assertEqual(set(logic.BALANCE_ATTRIBUTES), set(sensors["balance"]["state_attributes"]))
        self.assertEqual(set(logic.todo_attributes({})), set(sensors["todo_count"]["state_attributes"]))


class ReadmeTest(unittest.TestCase):
    README = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_menu_paths_of_energietracker_3_12(self):
        """The README leads through the menu of Energietracker 3.12, in English and German."""
        for path in ("Connections → Home Assistant", "Connections → Keys → API keys for scripts",
                     "Connections → Notifications", "Verbindungen → Home Assistant",
                     "Verbindungen → Schlüssel → API-Schlüssel für Skripte", "Verbindungen → Benachrichtigungen"):
            self.assertIn(path, self.README)
        for old in ("Settings → Access → API keys", "Einstellungen → Zugriff → API-Schlüssel",
                    "Settings → Integrations → Notifications", "Einstellungen → Integrationen → Benachrichtigungen"):
            self.assertNotIn(old, self.README)


class ManifestTest(unittest.TestCase):
    def test_manifest(self):
        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        for key in ("domain", "documentation", "issue_tracker", "codeowners", "name", "version"):
            self.assertIn(key, manifest)
        self.assertEqual("energietracker", manifest["domain"])
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(["domain", "name"], list(manifest)[:2], "hassfest: domain, name, then sorted")
        self.assertEqual(sorted(list(manifest)[2:]), list(manifest)[2:])
        self.assertTrue(manifest["config_flow"])
        self.assertEqual([], manifest["requirements"], "no packages to install")

    def test_hacs_json(self):
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertEqual("Energietracker", hacs["name"])
        self.assertNotIn("country", hacs, "works with every country profile")
        self.assertGreaterEqual(tuple(int(n) for n in hacs["homeassistant"].split(".")), (2026, 3, 0),
                                "brand images from the integration folder need 2026.3")


def png_header(path: Path) -> tuple[int, int, int]:
    """(width, height, colour type) of a PNG; colour type 6 = RGBA."""
    data = path.read_bytes()[:33]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"{path.name} is not a PNG")
    width, height, _depth, colour = struct.unpack(">IIBB", data[16:26])
    return width, height, colour


class BrandTest(unittest.TestCase):
    BRAND = INTEGRATION / "brand"

    def test_icons(self):
        for prefix in ("", "dark_"):
            self.assertEqual((256, 256, 6), png_header(self.BRAND / f"{prefix}icon.png"), prefix)
            self.assertEqual((512, 512, 6), png_header(self.BRAND / f"{prefix}icon@2x.png"), prefix)

    def test_logos(self):
        for prefix in ("", "dark_"):
            w, h, colour = png_header(self.BRAND / f"{prefix}logo.png")
            self.assertEqual(6, colour)
            self.assertTrue(128 <= min(w, h) <= 256 and w > h, (w, h))
            w2, h2, colour = png_header(self.BRAND / f"{prefix}logo@2x.png")
            self.assertEqual(6, colour)
            self.assertTrue(256 <= min(w2, h2) <= 512 and w2 > h2, (w2, h2))

    def test_dark_variants_really_differ(self):
        for name in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
            self.assertNotEqual((self.BRAND / name).read_bytes(), (self.BRAND / f"dark_{name}").read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
