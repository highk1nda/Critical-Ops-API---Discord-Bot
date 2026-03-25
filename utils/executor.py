import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from PIL import Image

# One shared pool for all CPU-bound image work; 2 workers is plenty for a Discord bot.
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="img_render")


async def render_image_async(
    renderer: Callable[[dict], Image.Image],
    data: dict,
) -> Image.Image:
    """
    Run a synchronous Pillow renderer in a thread-pool executor so it does
    not block the asyncio event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, renderer, data)
