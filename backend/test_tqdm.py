import asyncio
from huggingface_hub import snapshot_download
from tqdm.auto import tqdm

total_bytes = 0
downloaded_bytes = 0

class ProgressTracker(tqdm):
    def __init__(self, *args, **kwargs):
        self.is_bytes = kwargs.get('unit', '') == 'B'
        super().__init__(*args, **kwargs)
        if self.is_bytes and hasattr(self, 'total'):
            global total_bytes
            total_bytes += (self.total or 0)

    def update(self, n=1):
        super().update(n)
        if self.is_bytes:
            global downloaded_bytes
            downloaded_bytes += n
            print(f"Progress: {downloaded_bytes}/{total_bytes} bytes")

def test():
    snapshot_download(
        "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF", 
        allow_patterns="*.json", 
        tqdm_class=ProgressTracker
    )

if __name__ == "__main__":
    test()
