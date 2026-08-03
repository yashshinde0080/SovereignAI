
## [2026-08-03] implement | Reasoning Support (Thinking) for LLMs
- Added `reasoning` field to `Message` type in frontend/types to capture model's internal reasoning (e.g., Qwen3.5 \<think\> blocks)
- Updated `useChat` hook to handle thinking toggle and stream reasoning separately
- Added `ThinkingBlock` component to display collapsible reasoning traces with auto-open while streaming
- Updated chat UI to show thinking toggle button and display reasoning for assistant messages
- Enhanced FullRAM executor to handle reasoning model outputs (masked LM support)
- Updated tests for model loading and split auto mode
- Updated freebuff.txt timestamp
