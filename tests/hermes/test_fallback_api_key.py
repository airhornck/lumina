"""兜底 API Key 读取测试：DEEPSEEK_API_KEY 缺省时从 hermes config.yaml 读取。"""

from __future__ import annotations


def test_fallback_key_from_hermes_config():
    from services.hermes_adapter import _load_fallback_api_key

    key = _load_fallback_api_key()
    # data/hermes/config.yaml 中配置了 lumina.fallback_api_key（私有部署）
    assert key.startswith("sk-")


def test_fallback_key_missing_file(tmp_path, monkeypatch):
    import services.hermes_adapter as adapter_mod

    monkeypatch.setattr(adapter_mod, "_HERMES_HOME", tmp_path)
    assert adapter_mod._load_fallback_api_key() == ""
