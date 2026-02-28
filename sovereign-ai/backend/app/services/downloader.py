import asyncio

class Downloader:
    @staticmethod
    async def download_model(model_name: str, callback=None):
        # Dummy download implementation
        total_size = 4.3 * 1024 # MB
        downloaded = 0
        chunk_size = 512

        while downloaded < total_size:
            await asyncio.sleep(0.5)
            downloaded += chunk_size
            if downloaded > total_size:
                downloaded = total_size
            if callback:
                await callback(model_name, (downloaded/total_size)*100.0)

        return True
