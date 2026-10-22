import sys

print("python", sys.version)
for m in ("fastapi", "starlette", "httpx", "aiohttp", "certifi", "huggingface_hub", "cryptography", "tqdm", "torch"):
    try:
        mod = __import__(m)
        print(m, getattr(mod, "__version__", "?"))
    except Exception as exc:
        print(m, "MISSING", exc)
