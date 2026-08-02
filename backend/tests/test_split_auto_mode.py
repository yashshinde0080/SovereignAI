"""Split models (offload_cache per-layer weights) are layerstream-only.

Auto mode must never hand a split directory to the full-ram engine: the
full-ram engine looks for a consolidated model.safetensors that only exists
in the base model's directory, and the factory's auto heuristic (RAM-based)
has no idea the split view can't run full-ram.
"""
import asyncio

from app.services.model_manager import ModelManager, _fuzzy_match_model


def _fake_app(model_manager):
    class _State:
        def __init__(self):
            self.active_engine = None
            self.active_model = None
            self.active_mode = None
            self.hardware_profile = {}

    class _App:
        state = _State()

    return _App()


def _split_model():
    return {
        "id": "split:Qwen-Qwen3.5-0.8B",
        "name": "Qwen-Qwen3.5-0.8B (Split)",
        "path": "D:/SovereignAI/workspace/offload_cache/Qwen-Qwen3.5-0.8B",
        "modes_supported": ["layerstream"],
        "size_gb": 1.9,
    }


def _patch_factory(monkeypatch, create_engine):
    """load_model does `from app.core.engine_factory import EngineFactory` lazily;
    the from-import re-reads the name from app.core.engine_factory at call time,
    so patch the class there."""
    import app.core.engine_factory as ef_module
    FakeFactory = type(
        "FakeFactory",
        (),
        {"__init__": lambda self, hw: None, "create_engine": create_engine},
    )
    monkeypatch.setattr(ef_module, "EngineFactory", FakeFactory)


def test_split_auto_forced_layerstream(monkeypatch):
    """auto on a split model must resolve to layerstream before engine creation."""
    mm = ModelManager()
    app = _fake_app(mm)
    mm.app = app

    async def _fake_get_model(self, name):
        return _split_model() if name == "split:Qwen-Qwen3.5-0.8B" else None

    async def _fake_unload(self):
        pass

    monkeypatch.setattr(ModelManager, "get_model", _fake_get_model)
    monkeypatch.setattr(ModelManager, "unload_model", _fake_unload)

    created = {}

    async def _fake_create_engine(self, model_path, mode, model_metadata=None):
        created["mode"] = mode
        created["path"] = model_path

        class _Engine:
            mode = mode
            task_metadata = {}

        return _Engine()

    _patch_factory(monkeypatch, _fake_create_engine)

    result = asyncio.run(mm.load_model("split:Qwen-Qwen3.5-0.8B", mode="auto"))
    assert created["mode"] == "layerstream", f"expected layerstream, got {created['mode']}"
    assert result["mode"] == "layerstream"


def test_explicit_fullram_split_swaps_to_base(monkeypatch):
    """Explicit fullram on a split model redirects to the base model path."""
    mm = ModelManager()
    app = _fake_app(mm)
    mm.app = app

    created = {}

    async def _fake_list_models(self):
        return [
            _split_model(),
            {**_split_model(), "id": "Qwen/Qwen3.5-0.8B",
             "path": "D:/SovereignAI/workspace/models/installed/Qwen-Qwen3.5-0.8B",
             "modes_supported": ["fullram", "layerstream"]},
        ]

    async def _fake_create_engine(model_path, mode, model_metadata=None):
        created["mode"] = mode
        created["path"] = model_path

        class _Engine:
            mode = mode
            task_metadata = {}

        return _Engine()

    async def _fake_get_model(self, name):
        return _split_model() if name == "split:Qwen-Qwen3.5-0.8B" else None

    async def _fake_unload(self):
        pass

    monkeypatch.setattr(ModelManager, "get_model", _fake_get_model)
    monkeypatch.setattr(ModelManager, "unload_model", _fake_unload)
    monkeypatch.setattr(ModelManager, "list_models", _fake_list_models)
    _patch_factory(monkeypatch, _fake_create_engine)

    result = asyncio.run(mm.load_model("split:Qwen-Qwen3.5-0.8B", mode="fullram"))
    assert created["mode"] == "fullram"
    assert "installed" in created["path"], f"expected base path, got {created['path']}"
    assert result["mode"] == "fullram"


def test_fuzzy_prefers_base_over_split():
    """A display-name fuzzy match must never resolve to a split variant."""
    models = [
        _split_model(),
        {**_split_model(), "id": "Qwen/Qwen3.5-0.8B"},
    ]
    match = _fuzzy_match_model(models, "Qwen3.5-0.8B")
    assert match is not None
    assert not match["id"].startswith("split:")
