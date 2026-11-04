"""Unsupported-model-type errors must become actionable, not a raw 400."""
from app.services.model_manager import _unsupported_arch_error

# Exact shape of the transformers 4.45 message for an unknown model_type.
HF_MSG = (
    "The checkpoint you are trying to load has model type `qwen3_5_text` but "
    "Transformers does not recognize this architecture. This could be because "
    "of an issue with the checkpoint, or because your version of Transformers "
    "is out of date."
)


def test_unknown_model_type_becomes_supported_arch_error():
    err = _unsupported_arch_error(ValueError(HF_MSG))
    assert isinstance(err, RuntimeError)  # API maps "not supported" -> 422
    assert "qwen3_5_text" in str(err)
    assert "not supported" in str(err)


def test_other_failures_pass_through_unchanged():
    assert _unsupported_arch_error(ValueError("CUDA out of memory")) is None
    assert _unsupported_arch_error(OSError("No space left on device")) is None
