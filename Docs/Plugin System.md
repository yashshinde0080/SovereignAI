# Plugin System

An extensibility framework that allows users to inject custom Python scripts into the SovereignAI Edge processing pipeline.

## Role in SovereignAI Edge

The ==Plugin System== enables dynamic extension of SovereignAI Edge without modifying core code:

- **Hooks:** Register callbacks via decorators (`@hook('pre_prompt')`, `@hook('post_generation')`)
- **Discovery:** Backend scans `./plugins/` directory on startup for `.py` files
- **Sandboxing:** Plugins execute in a controlled environment via Python `importlib`

## Use Cases

- **Local RAG:** Inject retrieved document context into prompts
- **Custom Formatting:** Transform input/output for specific models
- **Safety Filters:** Add content moderation layers
- **Metrics Logging:** Capture custom usage statistics

## See Also

- [[FastAPI]] — Backend API that integrates plugin middleware
- [[Technical Architecture]] — System component interactions
- [[PRD]] — Product vision for extensibility
