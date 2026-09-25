"""Download Service.

Resumable plain-HTTP file downloads. For HuggingFace repos use
``HuggingFaceProvider.download`` / ``download_repo`` instead — that path talks to
the Hub API and supports quantization selection.

Correctness notes (all previously broken):

* **No timeout.** ``aiohttp``'s default is 5 minutes *total*, but a stalled
  server sends keep-alive bytes forever, so a hung download never returned.
  Now: explicit connect/read/total timeouts.
* **Path traversal.** ``filename`` went straight into a path join, so
  ``download("...", "../../.env")`` wrote outside the download directory.
  Now rejected.
* **Server ignores Range.** On resume we send ``Range: bytes=N-``. A server may
  answer ``200`` with the *whole* file; appending that to the existing ``.part``
  in ``ab`` mode silently corrupted it. Now we restart the file when the
  response is not ``206``.
* **Cancel was a no-op.** ``active_downloads`` was never written, so
  ``cancel_download`` always did nothing. Now the running task is tracked.
* **HTTP 416.** Sent when the ``.part`` is already complete; treated as success
  (matching the HuggingFace provider) instead of an error.
"""

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Callable, Dict, Optional

import aiofiles
import aiohttp

from app.providers.exceptions import DownloadError

logger = logging.getLogger("sovereign.services.downloader")

# 30s to connect, 60s of silence between reads, 1h ceiling for a whole file.
_TIMEOUT = aiohttp.ClientTimeout(total=3600, connect=30, sock_read=60)
_CHUNK = 1024 * 1024

# Absolute paths, drive letters, and any path separator are all rejected. The
# download name is a filename, never a path.
_UNSAFE_NAME = re.compile(r"[\\/]|^[A-Za-z]:|^\.\.$|^\.$")


def _safe_filename(filename: str) -> str:
    """Validate ``filename`` is a bare name that stays inside the download dir."""
    name = (filename or "").strip()
    if not name or _UNSAFE_NAME.search(name) or "\x00" in name:
        raise ValueError(f"Unsafe download filename: {filename!r}")
    if Path(name).name != name:
        raise ValueError(f"Unsafe download filename: {filename!r}")
    return name


class DownloadManager:
    """Download files with resume support."""

    def __init__(self, download_dir: Path, timeout: aiohttp.ClientTimeout = _TIMEOUT):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.download_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.active_downloads: Dict[str, asyncio.Task] = {}

    async def download(
        self,
        url: str,
        filename: str,
        progress_callback: Optional[Callable[[float, int, int], None]] = None,
        expected_checksum: Optional[str] = None,
    ) -> Path:
        """Download ``url`` to ``download_dir/filename``, resuming if possible."""
        filename = _safe_filename(filename)
        cache_path = self.cache_dir / f"{filename}.part"
        final_path = self.download_dir / filename

        task = asyncio.current_task()
        if task is not None:
            self.active_downloads[filename] = task
        try:
            await self._transfer(url, cache_path, progress_callback)

            if expected_checksum:
                actual = await self._compute_checksum(cache_path)
                if actual != expected_checksum:
                    cache_path.unlink(missing_ok=True)
                    raise DownloadError(
                        message=(
                            f"Checksum mismatch for {filename}: "
                            f"expected {expected_checksum}, got {actual}"
                        ),
                        model_id=filename,
                        provider="http",
                    )

            cache_path.replace(final_path)
            return final_path
        finally:
            if self.active_downloads.get(filename) is task:
                self.active_downloads.pop(filename, None)

    async def _transfer(
        self,
        url: str,
        cache_path: Path,
        progress_callback: Optional[Callable[[float, int, int], None]],
    ):
        """Stream the body into ``cache_path``, appending only on a real 206."""
        start_byte = cache_path.stat().st_size if cache_path.exists() else 0
        headers = {"Range": f"bytes={start_byte}-"} if start_byte else {}

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 416:
                    # Range not satisfiable: our .part is already the whole file.
                    logger.info("Range rejected (416); %s is already complete", cache_path.name)
                    return

                if resp.status not in (200, 206):
                    raise DownloadError(
                        message=f"Download failed: HTTP {resp.status} for {url}",
                        model_id=cache_path.name,
                        provider="http",
                        resumable=resp.status >= 500,
                    )

                # Server ignored the Range header and is sending the whole file
                # from byte 0 — truncate instead of appending.
                if start_byte and resp.status != 206:
                    logger.warning(
                        "Server ignored Range for %s; restarting download", cache_path.name
                    )
                    start_byte = 0

                total_size = int(resp.headers.get("content-length", 0)) + start_byte

                async with aiofiles.open(cache_path, "ab" if start_byte else "wb") as f:
                    downloaded = start_byte
                    async for chunk in resp.content.iter_chunked(_CHUNK):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress = (downloaded / total_size * 100) if total_size else 0.0
                            progress_callback(progress, downloaded, total_size)

    async def _compute_checksum(self, path: Path) -> str:
        """Streaming SHA256 of a file."""
        sha256 = hashlib.sha256()
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(1024 * 1024):
                sha256.update(chunk)
        return sha256.hexdigest()

    def cancel_download(self, filename: str) -> bool:
        """Cancel an in-flight download. Returns whether one was running."""
        task = self.active_downloads.get(filename)
        if task is None:
            return False
        task.cancel()
        return True

    def cleanup_cache(self):
        """Remove abandoned partial downloads."""
        for path in self.cache_dir.glob("*.part"):
            path.unlink(missing_ok=True)
