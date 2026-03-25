"""
Handles downloading images off the internet with use by Chlorine.
"""

import aiohttp
import asyncio
import gi
import requests

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk  # type: ignore


PFP_CACHE_MAX = 256
_pfp_texture_cache: dict[str, Gdk.Texture] = {}
_pfp_inflight: dict[str, asyncio.Task[Gdk.Texture | None]] = {}


def url_is_image(url: str) -> bool:
    """
    Check if a URL points to or is an image via head requests.

    :param url: URL to page
    :type url: str
    :return: Whether the URL is an image
    :rtype: bool
    """
    response = requests.head(url)
    if response.headers["Content-Type"].startswith("image/"):
        return True
    return False


async def download_image(url: str, session: aiohttp.ClientSession) -> bytes:
    """
    Downloads image off the internet based on URL

    :param url: URL to download from
    :type url: str
    :return: Raw image bytes
    :rtype: bytes
    """
    try:
        async with session.get(url) as resp:
            if resp.status >= 400:
                return b""

            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return b""

            return await resp.read()
    except Exception:
        return b""


async def load_pfp(url: str, img: Gtk.Image):
    cached_texture = _pfp_texture_cache.get(url)
    if cached_texture is not None:

        def apply_cached():
            img.set_from_paintable(cached_texture)
            img.set_pixel_size(32)

        GLib.idle_add(apply_cached)
        return

    task = _pfp_inflight.get(url)
    if task is None:

        async def fetch_texture() -> Gdk.Texture | None:
            async with aiohttp.ClientSession() as session:
                data = await download_image(url, session)

            if not data:
                return None

            try:
                return Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            except GLib.GError:
                return None

        task = asyncio.create_task(fetch_texture())
        _pfp_inflight[url] = task

    try:
        texture = await task
    finally:
        if _pfp_inflight.get(url) is task:
            del _pfp_inflight[url]

    if texture is None:
        return

    _pfp_texture_cache[url] = texture
    if len(_pfp_texture_cache) > PFP_CACHE_MAX:
        oldest = next(iter(_pfp_texture_cache))
        del _pfp_texture_cache[oldest]

    def apply():
        img.set_from_paintable(texture)
        img.set_pixel_size(32)

    GLib.idle_add(apply)


async def load_server_icon(
    url: str, widget: Gtk.Button, session: aiohttp.ClientSession
):
    """
    Downloads a single server icon and apply it to a widget's child

    :param url: URL to icon
    :type url: str
    :param widget: Widget to set child Gtk.Image on
    :type widget: Gtk.Button
    """
    data = await download_image(url, session)
    if not data:
        return
    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
    image = Gtk.Image.new_from_paintable(texture)
    image.set_pixel_size(34)

    GLib.idle_add(widget.set_child, image)
