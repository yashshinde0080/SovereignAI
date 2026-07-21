# Pydantic

A Python library for data validation and settings management using Python type annotations.

## Role in SovereignAI Edge

[[Pydantic]] provides ==strict data validation== across the SovereignAI Edge backend:

- **API Request Validation:** Enforces bounds on parameters (e.g., temperature 0.0–2.0)
- **Response Models:** Ensures consistent JSON structure for API responses
- **Configuration Management:** Validates application settings at startup

## Key Usage

- Input payloads for `/v1/chat/*` endpoints
- Model configuration schemas
- Plugin hook parameter validation
- Hardware profiler output models

## See Also

- [[FastAPI]] — Backend API framework that relies on Pydantic
- [[TRD]] — Technical requirements and stack details
- [[Pipelines]] — End-to-end inference pipeline
