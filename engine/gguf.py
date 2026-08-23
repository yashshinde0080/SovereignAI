"""GGUF binary format parser.

Reads GGUF v3 files: header, KV metadata, tensor descriptors.
Tensor data is accessed lazily via mmap — never copied into RAM
until explicitly requested.

GGUF format layout:
    [header] magic(4) + version(4) + n_tensors(8) + n_kv(8)
    [kv pairs]  key_str + type_tag + value  × n_kv
    [tensor info]  name_str + ndims(8) + dims(8×ndims) + type(4) + offset(8)  × n_tensors
    [alignment padding]
    [tensor data]  raw bytes, referenced by absolute offsets from file start
"""

from __future__ import annotations

import mmap
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


# ── GGML quantization type IDs ──────────────────────────────────────
GGML_TYPE_F32 = 0
GGML_TYPE_F16 = 1
GGML_TYPE_Q4_0 = 2
GGML_TYPE_Q4_1 = 3
GGML_TYPE_Q5_0 = 6
GGML_TYPE_Q5_1 = 7
GGML_TYPE_Q8_0 = 8
GGML_TYPE_Q8_1 = 9

GGML_TYPE_NAMES: dict[int, str] = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1",
    6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1",
}

# ── GGML type → numpy dtype ─────────────────────────────────────────
GGML_TO_NP: dict[int, type] = {
    GGML_TYPE_F32: np.float32,
    GGML_TYPE_F16: np.float16,
}

# Quantized block sizes (GGUF spec)
_Q8_0_BLOCK_SIZE = 32
_Q8_0_BLOCK_BYTES = 4 + 32   # fp32 scale + 32 × int8
_Q4_0_BLOCK_SIZE = 32
_Q4_0_BLOCK_BYTES = 2 + 16   # fp16 scale + 16 × packed int4 (32 nibbles)


def _quantized_nbytes(n_elements: int, ggml_type: int) -> int:
    """Compute byte size for a quantized tensor."""
    if ggml_type == GGML_TYPE_Q8_0:
        n_blocks = (n_elements + _Q8_0_BLOCK_SIZE - 1) // _Q8_0_BLOCK_SIZE
        return n_blocks * _Q8_0_BLOCK_BYTES
    elif ggml_type == GGML_TYPE_Q4_0:
        n_blocks = (n_elements + _Q4_0_BLOCK_SIZE - 1) // _Q4_0_BLOCK_SIZE
        return n_blocks * _Q4_0_BLOCK_BYTES
    return 0


def dequantize_q8_0(raw: bytes, shape: tuple[int, ...]) -> np.ndarray:
    """Dequantize Q8_0 blocks to float32.

    Block layout: fp32 scale (4 bytes) + 32 int8 values (32 bytes).
    Each element = scale * int8_value.
    """
    n_elements = int(np.prod(shape))
    n_blocks = (n_elements + _Q8_0_BLOCK_SIZE - 1) // _Q8_0_BLOCK_SIZE
    buf = np.frombuffer(raw, dtype=np.uint8)

    scales = np.zeros(n_blocks, dtype=np.float32)
    indices = np.zeros((n_blocks, _Q8_0_BLOCK_SIZE), dtype=np.int8)

    pos = 0
    for b in range(n_blocks):
        scales[b] = np.frombuffer(buf[pos:pos + 4], dtype=np.float32)[0]
        pos += 4
        indices[b] = np.frombuffer(buf[pos:pos + 32], dtype=np.int8)
        pos += 32

    # Dequantize: scale * index, then trim to exact element count
    dequant = (scales[:, np.newaxis] * indices.astype(np.float32)).ravel()
    return dequant[:n_elements].reshape(shape)


def dequantize_q4_0(raw: bytes, shape: tuple[int, ...]) -> np.ndarray:
    """Dequantize Q4_0 blocks to float32.

    Block layout: fp16 scale (2 bytes) + 16 packed bytes (32 int4 nibbles).
    Each byte = lo_nibble | (hi_nibble << 4), signed 4-bit [-8, 7].
    Each element = scale * int4_value.
    """
    n_elements = int(np.prod(shape))
    n_blocks = (n_elements + _Q4_0_BLOCK_SIZE - 1) // _Q4_0_BLOCK_SIZE
    buf = np.frombuffer(raw, dtype=np.uint8)

    scales = np.zeros(n_blocks, dtype=np.float16)
    quants = np.zeros((n_blocks, _Q4_0_BLOCK_SIZE), dtype=np.float32)

    pos = 0
    for b in range(n_blocks):
        scales[b] = np.frombuffer(buf[pos:pos + 2], dtype=np.float16)[0]
        pos += 2
        packed = buf[pos:pos + 16]
        pos += 16
        # Unpack: byte = lo | (hi << 4), signed 4-bit
        lo = (packed & 0x0F).astype(np.int8)
        hi = ((packed >> 4) & 0x0F).astype(np.int8)
        # Two's complement: convert to signed [-8, 7]
        lo = np.where(lo >= 8, lo - 16, lo)
        hi = np.where(hi >= 8, hi - 16, hi)
        # Interleave: [lo0, hi0, lo1, hi1, ...]
        quants[b, 0::2] = lo
        quants[b, 1::2] = hi

    # Dequantize: scale * quant
    dequant = (scales[:, np.newaxis].astype(np.float32) * quants).ravel()
    return dequant[:n_elements].reshape(shape)


@dataclass
class TensorInfo:
    name: str
    n_dims: int
    shape: tuple[int, ...]
    ggml_type: int
    offset: int  # absolute byte offset from file start

    @property
    def dtype(self) -> np.dtype | None:
        return GGML_TO_NP.get(self.ggml_type)

    @property
    def nbytes(self) -> int:
        if self.ggml_type in GGML_TO_NP:
            return int(np.prod(self.shape)) * np.dtype(GGML_TO_NP[self.ggml_type]).itemsize
        return _quantized_nbytes(int(np.prod(self.shape)), self.ggml_type)


@dataclass
class GGUFData:
    version: int
    metadata: dict[str, Any]
    tensors: list[TensorInfo]
    data_offset: int  # byte offset where tensor data section starts
    data_size: int    # total bytes of data section

    @property
    def n_tensors(self) -> int:
        return len(self.tensors)

    @property
    def alignment(self) -> int:
        return self.metadata.get("general.alignment", 32)


class GGUFParser:
    """Parse a GGUF file and provide lazy tensor access via mmap."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"GGUF file not found: {self.path}")
        self._fh = None
        self._mm = None
        self.data: GGUFData | None = None

    def load(self) -> GGUFData:
        """Parse header, KV metadata, and tensor descriptors. mmap tensor data."""
        self._fh = open(self.path, "rb")
        self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)

        mm = self._mm
        pos = 0

        # ── Header ──────────────────────────────────────────────────
        magic = struct.unpack_from("<I", mm, pos)[0]
        if magic != 0x46554747:
            raise ValueError(f"Not a GGUF file (magic=0x{magic:08X}): {self.path}")
        pos += 4

        version = struct.unpack_from("<I", mm, pos)[0]
        if version < 3:
            raise ValueError(f"Unsupported GGUF version {version} (need ≥3)")
        pos += 4

        n_tensors = struct.unpack_from("<Q", mm, pos)[0]
        pos += 8

        n_kv = struct.unpack_from("<Q", mm, pos)[0]
        pos += 8

        # ── KV metadata ─────────────────────────────────────────────
        metadata: dict[str, Any] = {}
        for _ in range(n_kv):
            key, pos = self._read_string(mm, pos)
            val, pos = self._read_value(mm, pos)
            metadata[key] = val

        # ── Tensor descriptors ──────────────────────────────────────
        tensors: list[TensorInfo] = []
        for _ in range(n_tensors):
            name, pos = self._read_string(mm, pos)
            n_dims = struct.unpack_from("<Q", mm, pos)[0]
            pos += 8

            shape = tuple(
                struct.unpack_from("<Q", mm, pos + i * 8)[0]
                for i in range(n_dims)
            )
            pos += n_dims * 8

            ggml_type = struct.unpack_from("<I", mm, pos)[0]
            pos += 4

            offset = struct.unpack_from("<Q", mm, pos)[0]
            pos += 8

            tensors.append(TensorInfo(
                name=name, n_dims=n_dims, shape=shape,
                ggml_type=ggml_type, offset=offset,
            ))

        # ── Data section offset ─────────────────────────────────────
        alignment = metadata.get("general.alignment", 32)
        data_offset = self._align(pos, alignment)

        # Compute data section size from last tensor offset + size
        if tensors:
            last = tensors[-1]
            last_size = last.nbytes if last.ggml_type in GGML_TO_NP else 0
            data_size = (last.offset + last_size) - data_offset if last_size else 0
        else:
            data_size = len(mm) - data_offset

        self.data = GGUFData(
            version=version,
            metadata=metadata,
            tensors=tensors,
            data_offset=data_offset,
            data_size=data_size,
        )
        return self.data

    def get_tensor(self, name: str) -> np.ndarray:
        """Read a tensor by name from mmap'd data. F32/F16 only."""
        if self.data is None:
            raise RuntimeError("Call load() first")
        if self._mm is None:
            raise RuntimeError("File already closed")

        for ti in self.data.tensors:
            if ti.name == name:
                nbytes = ti.nbytes
                raw = bytes(self._mm[ti.offset:ti.offset + nbytes])

                if ti.ggml_type == GGML_TYPE_F32:
                    return np.frombuffer(raw, dtype=np.float32).reshape(ti.shape).copy()
                elif ti.ggml_type == GGML_TYPE_F16:
                    return np.frombuffer(raw, dtype=np.float16).reshape(ti.shape).copy()
                elif ti.ggml_type == GGML_TYPE_Q8_0:
                    return dequantize_q8_0(raw, ti.shape)
                elif ti.ggml_type == GGML_TYPE_Q4_0:
                    return dequantize_q4_0(raw, ti.shape)
                else:
                    raise NotImplementedError(
                        f"Quantized tensor '{name}' (type {GGML_TYPE_NAMES.get(ti.ggml_type, ti.ggml_type)}). "
                        f"Dequantization not implemented."
                    )

        raise KeyError(f"Tensor '{name}' not found")

    def tensor_names(self) -> list[str]:
        if self.data is None:
            raise RuntimeError("Call load() first")
        return [t.name for t in self.data.tensors]

    def close(self) -> None:
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, *exc):
        self.close()

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _read_string(mm: mmap.mmap, pos: int) -> tuple[str, int]:
        n = struct.unpack_from("<Q", mm, pos)[0]
        pos += 8
        s = mm[pos:pos + n].decode("utf-8")
        return s, pos + n

    @staticmethod
    def _read_value(mm: mmap.mmap, pos: int) -> tuple[Any, int]:
        """Read a GGUF KV value. Returns (value, new_pos)."""
        vtype = struct.unpack_from("<I", mm, pos)[0]
        pos += 4

        if vtype == 0:  # UINT8
            return struct.unpack_from("<B", mm, pos)[0], pos + 1
        elif vtype == 1:  # INT8
            return struct.unpack_from("<b", mm, pos)[0], pos + 1
        elif vtype == 2:  # UINT16
            return struct.unpack_from("<H", mm, pos)[0], pos + 2
        elif vtype == 3:  # INT16
            return struct.unpack_from("<h", mm, pos)[0], pos + 2
        elif vtype == 4:  # UINT32
            return struct.unpack_from("<I", mm, pos)[0], pos + 4
        elif vtype == 5:  # INT32
            return struct.unpack_from("<i", mm, pos)[0], pos + 4
        elif vtype == 6:  # FLOAT32
            return struct.unpack_from("<f", mm, pos)[0], pos + 4
        elif vtype == 7:  # BOOL
            return struct.unpack_from("<B", mm, pos)[0] != 0, pos + 1
        elif vtype == 8:  # STRING
            s, pos = GGUFParser._read_string(mm, pos)
            return s, pos
        elif vtype == 9:  # ARRAY
            atype = struct.unpack_from("<I", mm, pos)[0]
            pos += 4
            alen = struct.unpack_from("<Q", mm, pos)[0]
            pos += 8
            arr = []
            for _ in range(alen):
                elem, pos = GGUFParser._read_value_from_type(mm, pos, atype)
                arr.append(elem)
            return arr, pos
        elif vtype == 10:  # UINT64
            return struct.unpack_from("<Q", mm, pos)[0], pos + 8
        elif vtype == 11:  # INT64
            return struct.unpack_from("<q", mm, pos)[0], pos + 8
        elif vtype == 12:  # FLOAT64
            return struct.unpack_from("<d", mm, pos)[0], pos + 8
        else:
            raise ValueError(f"Unknown GGUF value type: {vtype}")

    @staticmethod
    def _read_value_from_type(mm: mmap.mmap, pos: int, vtype: int) -> tuple[Any, int]:
        """Read a value when the type tag is already known (for arrays)."""
        if vtype == 0:
            return struct.unpack_from("<B", mm, pos)[0], pos + 1
        elif vtype == 1:
            return struct.unpack_from("<b", mm, pos)[0], pos + 1
        elif vtype == 2:
            return struct.unpack_from("<H", mm, pos)[0], pos + 2
        elif vtype == 3:
            return struct.unpack_from("<h", mm, pos)[0], pos + 2
        elif vtype == 4:
            return struct.unpack_from("<I", mm, pos)[0], pos + 4
        elif vtype == 5:
            return struct.unpack_from("<i", mm, pos)[0], pos + 4
        elif vtype == 6:
            return struct.unpack_from("<f", mm, pos)[0], pos + 4
        elif vtype == 7:
            return struct.unpack_from("<B", mm, pos)[0] != 0, pos + 1
        elif vtype == 8:
            return GGUFParser._read_string(mm, pos)
        elif vtype == 10:
            return struct.unpack_from("<Q", mm, pos)[0], pos + 8
        elif vtype == 11:
            return struct.unpack_from("<q", mm, pos)[0], pos + 8
        elif vtype == 12:
            return struct.unpack_from("<d", mm, pos)[0], pos + 8
        else:
            raise ValueError(f"Unknown array element type: {vtype}")

    @staticmethod
    def _align(pos: int, alignment: int) -> int:
        return ((pos + alignment - 1) // alignment) * alignment


def demo():
    """Quick sanity: parse a GGUF file if provided, print header info."""
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m engine.gguf <model.gguf>")
        print("gguf parser: module loads OK")
        return
    with GGUFParser(sys.argv[1]) as gp:
        d = gp.data
        print(f"GGUF v{d.version}: {d.n_tensors} tensors, {len(d.metadata)} KV pairs")
        for k, v in list(d.metadata.items())[:10]:
            print(f"  {k} = {v}")
        for t in d.tensors[:5]:
            print(f"  {t.name}: {t.shape} type={GGML_TYPE_NAMES.get(t.ggml_type, t.ggml_type)}")


if __name__ == "__main__":
    demo()
