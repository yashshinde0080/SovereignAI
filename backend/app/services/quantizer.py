"""Model quantization entry point.

Quantization is already implemented, just not here:

* ``app.engines.layerstream.splitter.WeightSplitter`` — splits a checkpoint into
  per-layer safetensors and quantizes to ``none`` / ``int8`` / ``int4``.
* ``app.engines.layerstream.quant_config`` — persisted quantization metadata
  (``quant_config.json`` next to the split layers).

This module is an explicit placeholder rather than a zero-byte file so the
splitter stays the single implementation. Wrapping it in a second "quantizer"
service would create two places to change when the scheme changes.
"""


class Quantizer:
    """Reserved. Use ``WeightSplitter`` for real quantization."""

    def __init__(self):
        raise NotImplementedError(
            "Quantization lives in app.engines.layerstream.splitter.WeightSplitter "
            "(quant: none|int8|int4). Use that instead of this placeholder."
        )
