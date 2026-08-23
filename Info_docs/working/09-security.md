# Security

Opt-in Bearer auth, Fernet encryption for model files, rate limiting.

## Auth Middleware

**File:** `backend/app/security/middleware.py`

`lan_auth_middleware` — runs on every HTTP request:

1. Read security settings from `SettingsService.get_security()`
2. If `bind_localhost_only = false` (server exposed to LAN):
   - If `api_token` is configured → require `Authorization: Bearer {token}`
   - Uses `secrets.compare_digest()` (constant-time comparison)
   - 401 on invalid/missing token
3. If `bind_localhost_only = true` (default) → no auth enforced
   - Electron/CLI loopback stays auth-free

**Opt-in design:** Auth only enforced when both conditions met:
- Server bound to `0.0.0.0` (not localhost-only)
- `api_token` is configured

## Rate Limiting

`slowapi` Limiter — 60 requests/minute per IP:
```python
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
```

## Encryption

**File:** `backend/app/security/encryption.py`

`ModelEncryption` — Fernet symmetric encryption:
- Key derivation: `PBKDF2HMAC` (480,000 iterations)
- Salt: `platform.node()` + `uuid.getnode()` (machine-unique)
- Chunked encrypted file format: `SOVEREIGN_ENC_v1` header
- Used for `.gguf.enc` / `.safetensors.enc` model files

## Password Hashing

- `bcrypt` for password and parental PIN storage
- `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`
- `bcrypt.checkpw(password.encode(), stored_hash)`

## Security Settings

From `SecuritySettings` schema:
- `bind_localhost_only` — default `True` (localhost only)
- `api_token` — Bearer token for LAN access
- `require_password` — enable password gate
- `password_hash` — bcrypt hash

## CORS

```python
allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "app://-"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

`app://-` is the Electron custom protocol.

## Trust Remote Code

`settings.trust_remote_code` (default: False) — gates `AutoModelForCausalLM.from_pretrained(trust_remote_code=...)`. Enable only for trusted repos that ship custom modeling code.

## Path-Root Guard

`ModelManager.delete_model()` — never `rmtree` outside the models directory, even if registry metadata was tampered with:
```python
root = self.models_dir.resolve()
resolved = model_dir.resolve()
if root not in resolved.parents:
    raise RuntimeError("Refusing to delete path outside models directory")
```

## CVE Mitigation

CVE-2025-32434: torch < 2.6 refuses `.bin` checkpoints (pickle deserialization). `ensure_safetensors()` converts `.bin` → `.safetensors` before loading.

## Related

- [[08-settings-system]] — Security settings storage
- [[00-architecture-overview]] — Auth middleware placement in startup
- [[01-database-system]] — Settings DB holds security config
