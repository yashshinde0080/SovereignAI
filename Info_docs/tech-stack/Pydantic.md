---
tags: [backend, validation, data-models]
source: "[[Docs/Pydantic.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Pydantic

Pydantic provides strict data validation across the SovereignAI Edge backend using Python type annotations. It validates API request payloads -- enforcing bounds on parameters such as temperature (0.0-2.0), top-p, and max tokens -- ensures consistent JSON structure for API responses, and validates application configuration settings at startup. FastAPI relies on Pydantic models for all request and response schemas, making validation automatic and zero-cost.

Pydantic models are used for input payloads on all `/v1/chat/*` endpoints, model configuration schemas, plugin hook parameter validation, and hardware profiler output structures. This ensures that invalid data is caught at the boundary before it reaches the inference engine, preventing runtime errors from malformed input.

## Key Points

- Type-annotation-based data validation integrated with FastAPI
- Enforces bounds on all inference parameters (temperature, top-k, top-p, max tokens)
- Used for API payloads, model configs, plugin parameters, and hardware profiler output
- Catches invalid input at the API boundary before it reaches the inference engine
- Ensures consistent JSON response structure across all endpoints

## Related
- [[FastAPI]]
- [[Technical Architecture]]
- [[Pipelines]]
