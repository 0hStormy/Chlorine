"""
Handles downloading images off the internet with use by Chlorine.
"""

import aiohttp
import asyncio
import gi
from collections.abc import Callable
from urllib.parse import urlparse

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk  # type: ignore


PFP_CACHE_MAX = 256
_pfp_texture_cache: dict[str, Gdk.Texture] = {}
_pfp_inflight: dict[str, asyncio.Task[Gdk.Texture | None]] = {}


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
        def set_cached():
            img.set_from_paintable(cached_texture)
            img.set_pixel_size(32)
            return False
        GLib.idle_add(set_cached)
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
        _pfp_inflight.pop(url, None)

    if texture is None:
        return

    _pfp_texture_cache[url] = texture
    if len(_pfp_texture_cache) > PFP_CACHE_MAX:
        del _pfp_texture_cache[next(iter(_pfp_texture_cache))]

    def set_texture():
        img.set_from_paintable(texture)
        img.set_pixel_size(32)
        return False
    GLib.idle_add(set_texture)


async def load_image(
    url: str,
    picture: Gtk.Picture,
    on_loaded: Callable[[], None] | None = None,
):
    async with aiohttp.ClientSession() as session:
        data = await download_image(url, session)

    if not data:
        return

    try:
        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
    except GLib.GError:
        return

    width = texture.get_width()
    height = texture.get_height()
    if width <= 0 or height <= 0:
        return

    max_dimension = 320
    scale = min(1.0, max_dimension / max(width, height))
    display_width = int(width * scale)
    display_height = int(height * scale)

    def set_texture():
        picture.set_paintable(texture)
        picture.set_keep_aspect_ratio(True)
        picture.set_can_shrink(True)
        if hasattr(Gtk, "ContentFit"):
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_size_request(display_width, display_height)
        picture.set_halign(Gtk.Align.START)
        if on_loaded is not None:
            on_loaded()
        return False

    GLib.idle_add(set_texture)


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


async def extract_image_urls(text: str) -> tuple[str, list[str]]:
    """
    Extracts image URLs from a message content

    :param text: Message content to extract from
    :type text: str
    :return: Tuple of content with URLs removed and list of URLs
    :rtype: tuple[str, list[str]]
    """
    urls = []
    words = text.split()
    remaining_words = []
    for word in words:
        candidate = word.strip("()[]{}<>.,!?\"'")
        if is_http_url(candidate):
            urls.append(candidate)
            continue
        remaining_words.append(word)

    no_url = " ".join(remaining_words).strip()

    return no_url, urls


async def load_message_images(message: dict) -> list[Gtk.Picture]:
    """
    Loads images from a message content

    :param message: Message to load images from
    :type message: dict
    :return: List of Gtk.Pictures for the message's images
    :rtype: list[Gtk.Picture]
    """
    _, urls = await extract_image_urls(message["content"])
    pictures = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            data = await download_image(url, session)
            if not data:
                continue
            try:
                texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
                picture = Gtk.Picture.new_for_paintable(texture)
                picture.set_can_shrink(False)
                picture.set_keep_aspect_ratio(True)
                pictures.append(picture)
            except GLib.GError:
                continue
    return pictures