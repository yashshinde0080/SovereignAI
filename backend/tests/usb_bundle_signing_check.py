"""Self-check for USB bundle signing (ed25519).

Runs offline, no model file needed beyond a few bytes. Verifies:
- signed bundle verifies at parse when keys match
- tampered payload is refused (parse returns None)
- unsigned bundles parse fine without any key
"""
import asyncio
import hashlib
import tempfile
from pathlib import Path

from app.providers.usb_bundle import USBBundleProvider


def _make_provider(enc_key=None, verify_key=None):
    return USBBundleProvider(config={
        "encryption_key": enc_key,
        "verify_key": verify_key,
    })


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp) / "tiny.gguf"
        model.write_bytes(b"fake-model-bytes")

        # 1. Sign with encryption_key, verify with the same key -> listed
        p = _make_provider(enc_key="hunter2")
        out = await p._create_sovereign_bundle(
            model_path=model,
            output_path=Path(tmp) / "m.sovereign",
            metadata={"id": "tiny"},
            encrypt=False,
            sign=True,
        )
        info = await p._parse_sovereign_bundle(out)
        assert info is not None, "signed bundle must verify with matching key"
        assert info.signature is not None and len(info.signature) == 64
        assert info.signature != b"\\x00" * 64, "signature placeholder still being written"

        # 2. Tamper with metadata -> verification must refuse the bundle
        # Layout: magic(0-3) ver(4) flags(5) meta_len(6-9) metadata(10..)
        # Flip one letter ("id" -> "hd"): still valid JSON, different signed payload.
        raw = bytearray(out.read_bytes())
        raw[12] ^= 0x01
        out.write_bytes(bytes(raw))
        bad = await p._parse_sovereign_bundle(out)
        assert bad is None, "tampered signed bundle must be refused"

        # 3. Verifier without any key -> refuse signed bundle
        out2 = await p._create_sovereign_bundle(
            model_path=model,
            output_path=Path(tmp) / "m2.sovereign",
            metadata={"id": "tiny"},
            encrypt=False,
            sign=True,
        )
        keyless = _make_provider()
        assert await keyless._parse_sovereign_bundle(out2) is None, \
            "signed bundle without configured verify key must be refused"

        # 4. Unsigned bundle still parses without keys
        out3 = await p._create_sovereign_bundle(
            model_path=model,
            output_path=Path(tmp) / "m3.sovereign",
            metadata={"id": "tiny"},
            encrypt=False,
            sign=False,
        )
        assert await keyless._parse_sovereign_bundle(out3) is not None, \
            "unsigned bundles must keep working"

    print("SIGNING SELF-CHECK OK")


if __name__ == "__main__":
    asyncio.run(main())
