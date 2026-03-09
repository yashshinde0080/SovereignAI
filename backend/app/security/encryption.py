"""Model Encryption"""
import os
import hashlib
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class ModelEncryption:
    """Encrypt and decrypt model files"""
    
    def __init__(self, key: Optional[str] = None):
        if key:
            self.key = self._derive_key(key)
        else:
            # Generate machine-specific key
            self.key = self._generate_machine_key()
        
        self.fernet = Fernet(self.key)
    
    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password"""
        salt = b"sovereign_ai_salt"  # In production, use random salt stored securely
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _generate_machine_key(self) -> bytes:
        """Generate key from machine identifiers"""
        import platform
        import uuid
        
        # Combine machine identifiers
        machine_id = f"{platform.node()}-{uuid.getnode()}"
        
        return self._derive_key(machine_id)
    
    async def encrypt_model(self, model_path: Path) -> Path:
        """Encrypt model files"""
        if model_path.is_dir():
            encrypted_files = []
            for root, dirs, files in os.walk(model_path):
                for file in files:
                    if file.endswith(('.bin', '.safetensors', '.pt', '.json', '.gguf')):
                        target_file = Path(root) / file
                        encrypted_path = target_file.with_suffix(target_file.suffix + ".enc")
                        
                        chunk_size = 64 * 1024 * 1024
                        with open(target_file, "rb") as f_in:
                            with open(encrypted_path, "wb") as f_out:
                                while chunk := f_in.read(chunk_size):
                                    encrypted_chunk = self.fernet.encrypt(chunk)
                                    f_out.write(len(encrypted_chunk).to_bytes(8, "big"))
                                    f_out.write(encrypted_chunk)
                        
                        target_file.unlink()
                        encrypted_files.append(encrypted_path)
            return model_path  # Return directory root if it was a directory
        else:
            encrypted_path = model_path.with_suffix(model_path.suffix + ".enc")
            
            chunk_size = 64 * 1024 * 1024
            
            with open(model_path, "rb") as f_in:
                with open(encrypted_path, "wb") as f_out:
                    while chunk := f_in.read(chunk_size):
                        encrypted_chunk = self.fernet.encrypt(chunk)
                        f_out.write(len(encrypted_chunk).to_bytes(8, "big"))
                        f_out.write(encrypted_chunk)
            
            model_path.unlink()
            return encrypted_path
    
    async def decrypt_model(self, encrypted_path: Path) -> bytes:
        """Decrypt model to memory"""
        decrypted_data = bytearray()
        
        with open(encrypted_path, "rb") as f:
            while True:
                size_bytes = f.read(8)
                if not size_bytes:
                    break
                
                chunk_size = int.from_bytes(size_bytes, "big")
                encrypted_chunk = f.read(chunk_size)
                decrypted_chunk = self.fernet.decrypt(encrypted_chunk)
                decrypted_data.extend(decrypted_chunk)
        
        return bytes(decrypted_data)
    
    def compute_checksum(self, data: bytes) -> str:
        """Compute SHA256 checksum"""
        return hashlib.sha256(data).hexdigest()