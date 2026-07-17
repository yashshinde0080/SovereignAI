# Hardware Profiler

The ==engine selection component== that analyzes system resources at runtime to choose the optimal inference mode for SovereignAI Edge.

## Role in SovereignAI Edge

The ==Hardware Profiler== is the decision-making layer that determines whether [[FullRAM]] or [[LayerStream]] mode is used for each inference request:

1. **Query System:** Checks `psutil` and OS-level APIs for available RAM and VRAM
2. **Calculate:** Compares model size against available resources with 20% safety buffer
3. **Select:** Routes to [[FullRAM]] if memory is sufficient, otherwise [[LayerStream]]
4. **Fallback:** Automatically switches between modes if resource availability changes

## Decision Logic

```text
Is Free_VRAM > ModelSize?
  → Execute on GPU (FullRAM)
Is Free_VRAM + Free_RAM > ModelSize * 1.2?
  → Execute on CPU (FullRAM)
Otherwise?
  → Initialize LayerStream
```

## See Also

- [[FullRAM]] — High-memory inference engine
- [[LayerStream]] — Low-memory inference engine
- [[Algorithms]] — Adaptive memory allocation algorithm
- [[Technical Architecture]] — System component interactions
