"""Generate the browser translation catalog.

The WebUI strings used to live in the Qt Linguist TS files. Upstream ok-script
dropped the web UI, so vendored merges replace those files without a WebUI
context. When no TS file carries one, the committed catalog is the source of
truth and this script validates and normalizes it instead.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QT_I18N_DIR = ROOT / "ok" / "ui" / "qt" / "i18n"
CATALOG = ROOT / "web_src" / "src" / "i18n" / "catalogs.json"
OUTPUT = CATALOG
CONTEXT = "WebUI"


class MissingContext(ValueError):
    pass


def read_context(path: Path) -> tuple[str, dict[str, str]]:
    root = ET.parse(path).getroot()
    locale = root.get("language") or path.stem
    for context in root.findall("context"):
        if context.findtext("name") != CONTEXT:
            continue
        messages: dict[str, str] = {}
        for message in context.findall("message"):
            source = message.findtext("source")
            translation = message.find("translation")
            if not source or translation is None:
                continue
            if translation.get("type") == "unfinished" or translation.text is None:
                raise ValueError(f"Unfinished {CONTEXT} translation in {path.name}: {source}")
            messages[source] = translation.text
        return locale, messages
    raise MissingContext(f"Missing {CONTEXT} context in {path.name}")


def read_qt_catalogs() -> dict[str, dict[str, str]] | None:
    """Return the TS catalogs, or None when no TS file has the WebUI context."""
    catalogs: dict[str, dict[str, str]] = {}
    missing: list[MissingContext] = []
    paths = sorted(QT_I18N_DIR.glob("*.ts"))
    for path in paths:
        try:
            locale, messages = read_context(path)
        except MissingContext as error:
            missing.append(error)
        else:
            catalogs[locale] = messages
    if missing and len(missing) < len(paths):
        # Some locales still carry the context; a partial set must not be merged silently.
        raise missing[0]
    return catalogs or None


def generate() -> dict[str, dict[str, str]]:
    catalogs = read_qt_catalogs()
    if catalogs is None:
        catalogs = json.loads(CATALOG.read_text(encoding="utf-8"))
    if "en_US" not in catalogs:
        raise ValueError("The en_US web translation catalog is required")
    expected = set(catalogs["en_US"])
    for locale, messages in catalogs.items():
        missing = expected - set(messages)
        extra = set(messages) - expected
        if missing or extra:
            raise ValueError(
                f"Web catalog keys differ for {locale}; missing={sorted(missing)}, extra={sorted(extra)}"
            )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(catalogs, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return catalogs


if __name__ == "__main__":
    result = generate()
    print(f"Generated {OUTPUT.relative_to(ROOT)} for {len(result)} locales")
