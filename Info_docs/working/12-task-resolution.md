# Task Resolution

`TaskResolver` determines what a model can do by inspecting its HuggingFace config.

## Resolution

`TaskResolver.resolve(model_path)` (`backend/app/core/task_resolver.py`):

```python
config = AutoConfig.from_pretrained(model_path, trust_remote_code=False, local_files_only=True)
```

Returns:
```python
{
    "model_path": "...",
    "architectures": ["Qwen2ForCausalLM"],
    "model_type": "qwen2",
    "task_type": "causal_lm|seq2seq_lm|masked_lm|...",
    "input_modality": "text|image|audio|multimodal",
    "is_generative": True|False
}
```

## Task Type Mapping

| Architecture Pattern | task_type | is_generative |
|---|---|---|
| `CausalLM` | `causal_lm` | True |
| `ForConditionalGeneration` + encoder-decoder | `seq2seq_lm` | True |
| `ForConditionalGeneration` + decoder-only | `causal_lm` | True |
| `MaskedLM` | `masked_lm` | False |
| `SequenceClassification` | `sequence_classification` | False |
| `TokenClassification` | `token_classification` | False |
| `QuestionAnswering` | `question_answering` | False |
| `Vision2Seq` / `llava` | `vision2seq` | True |
| `Whisper` | `speech_seq2seq` | True |
| Others | mapped per suffix | varies |

## Key Design Decisions

1. **Decoder-only ForConditionalGeneration → causal_lm**: Models like Qwen3.5 use `ForConditionalGeneration` in their arch name but are NOT encoder-decoder. They must load via `AutoModelForCausalLM`, not `AutoModelForSeq2SeqLM`.

2. **Vision config heuristic**: If arch check returns `unknown` but `config.vision_config` exists → `vision2seq`. Guarded by `task_category == "unknown"` to avoid misclassifying text-only models with vision config stubs.

3. **Fallback for GGUF/unconfigured**: If `AutoConfig` fails entirely → defaults to `causal_lm`, `is_generative=True`, `input_modality=text`.

## TaskRouter

`TaskRouter` (`backend/app/core/task_router.py`) — maps task_type → model class:

| task_type | Model Class |
|---|---|
| `causal_lm` | `AutoModelForCausalLM` |
| `seq2seq_lm` | `AutoModelForSeq2SeqLM` |
| `masked_lm` | `AutoModelForMaskedLM` |
| `sequence_classification` | `AutoModelForSequenceClassification` |
| `vision2seq` | `AutoModelForCausalLM` |
| `speech_seq2seq` | `AutoModelForSeq2SeqLM` |

`TaskRouter.execute()` — runs the appropriate forward/generate pass based on task_type.

## Where Task Resolution Runs

1. **EngineFactory.create_engine()** — determines is_generative → mode selection
2. **FullRAMEngine.load()** — uses pre-resolved metadata or resolves again
3. **LayerStreamEngine.generate()** — resolves for metadata reporting

The `EngineFactory` passes `task_metadata` to `FullRAMEngine` to avoid a redundant second `AutoConfig` load.

## Related

- [[04-engine-system]] — Engines use task metadata for routing
- [[11-hardware-memory]] — Non-generative + layerstream → forced fullram
- [[00-architecture-overview]] — Task resolution in the load flow
- [[03-model-loading]] — When task resolution happens
