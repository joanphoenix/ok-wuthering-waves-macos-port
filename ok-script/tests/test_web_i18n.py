import json
from pathlib import Path

import pytest

from scripts import generate_web_i18n


def test_web_catalog_is_generated_from_qt_webui_context(tmp_path, monkeypatch):
    output = tmp_path / "catalogs.json"
    monkeypatch.setattr(generate_web_i18n, "OUTPUT", output)

    catalogs = generate_web_i18n.generate()

    assert set(catalogs) == {"en_US", "es_ES", "ja_JP", "ko_KR", "zh_CN", "zh_TW"}
    assert all(set(catalog) == set(catalogs["en_US"]) for catalog in catalogs.values())
    assert catalogs["zh_CN"]["Automation control"] == "自动化控制"
    assert json.loads(output.read_text(encoding="utf-8")) == catalogs


def test_frontend_source_is_outside_python_package():
    root = Path(__file__).resolve().parents[1]

    assert (root / "package.json").exists()
    assert (root / "web_src" / "src" / "App.tsx").exists()
    assert not (root / "ok" / "ui" / "web" / "frontend").exists()


def test_partial_webui_context_is_rejected(tmp_path, monkeypatch):
    # All-or-nothing: the committed catalog is only the source when no TS file has the context.
    (tmp_path / "en_US.ts").write_text(
        '<TS language="en_US"><context><name>WebUI</name><message><source>A</source>'
        '<translation>A</translation></message></context></TS>', encoding="utf-8")
    (tmp_path / "zh_CN.ts").write_text('<TS language="zh_CN"></TS>', encoding="utf-8")
    monkeypatch.setattr(generate_web_i18n, "QT_I18N_DIR", tmp_path)

    with pytest.raises(ValueError, match="Missing WebUI context in zh_CN.ts"):
        generate_web_i18n.read_qt_catalogs()
