import sys
import types
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import evaluator


def test_openai_request_does_not_send_temperature_for_gpt5(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, model, messages, **kwargs):
            captured["model"] = model
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"decision": "Fit"}'))])

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    result = evaluator._generate_with_openai("prompt", "test-key", "gpt-5.5")

    assert result["decision"] == "Fit"
    assert captured["api_key"] == "test-key"
    assert captured["model"] == "gpt-5.5"
    assert "temperature" not in captured["kwargs"]
