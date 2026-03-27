"""
Main/chat UI logic for Chlorine.
"""

import aiohttp
import gi
import asyncio
import threading
from urllib.parse import quote
import config
import image_utils
import ws

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # type: ignore


def track_message_task(app, task) -> None:
    if not hasattr(app, "message_loading_tasks"):
        app.message_loading_tasks = set()
    app.message_loading_tasks.add(task)
    task.add_done_callback(lambda t: app.message_loading_tasks.discard(t))


def cancel_message_loading(app) -> None:
    if hasattr(app, "messages_build_source_id") and app.messages_build_source_id:
        GLib.source_remove(app.messages_build_source_id)
        app.messages_build_source_id = 0

    if hasattr(app, "message_loading_tasks"):
        for task in list(app.message_loading_tasks):
            task.cancel()
        app.message_loading_tasks.clear()


def extract_image_urls(text: str) -> tuple[str, list[str]]:
    urls = []
    words = text.split()
    remaining_words = []
    for word in words:
        candidate = word.strip("()[]{}<>.,!?\"'")
        if image_utils.is_http_url(candidate):
            urls.append(candidate)
            continue
        remaining_words.append(word)

    no_url = " ".join(remaining_words).strip()
    return no_url, urls


def _handle_messages_get_main_thread(app, channel: str | None, messages: list):
    assert isinstance(app.server, ws.Server)

    if channel is not None and channel != app.server.channel:
        return False

    cancel_message_loading(app)
    build_messages_list(app, messages)
    return False


def _handle_message_new_main_thread(app, message: dict):
    build_single_message(app, message)
    return False


def load_main_ui(app):
    builder = Gtk.Builder()
    builder.add_from_file("../ui/main.ui")
    app.builder = builder

    win = builder.get_object("ChlorineMain")
    assert isinstance(win, Gtk.ApplicationWindow)

    # Load server list buttons
    threading.Thread(
        target=server_buttons_async,
        args=(app, builder),
        daemon=True,
    ).start()

    # Connect to originChats server
    selected_server = config.read_from_config("servers")[0]
    server = ws.Server(selected_server, on_event=app.handle_ws_event_async)
    app.server = server
    threading.Thread(
        target=lambda: asyncio.run(server.listen()),
        daemon=True,
    ).start()

    send_msg_button = builder.get_object("send_message")
    assert isinstance(send_msg_button, Gtk.Button)
    entry = builder.get_object("message_entry")
    assert isinstance(entry, Gtk.Entry)

    def on_send(_):
        text = entry.get_text()
        entry.set_text("")
        assert isinstance(server.loop, asyncio.AbstractEventLoop)
        asyncio.run_coroutine_threadsafe(
            server.send_message(text),
            server.loop,
        )

    send_msg_button.connect("clicked", on_send)
    entry.connect("activate", on_send)

    win.set_application(app)
    win.present()


async def load_server_buttons(app, builder: Gtk.Builder):
    """
    Taskify all servers and gather them to load the server buttons

    :param builder: GTK Builder instance
    :type builder: Gtk.Builder
    """
    servers = config.read_from_config("servers")
    server_box = builder.get_object("server_list")
    assert isinstance(server_box, Gtk.Box)
    async with aiohttp.ClientSession() as session:
        tasks = [
            process_server(server, server_box, session)
            for server in reversed(servers)
        ]
        await asyncio.gather(*tasks)


async def process_server(
    server, server_box: Gtk.Box, session: aiohttp.ClientSession
):
    """
    Add a single server to server list

    :param server: Server list
    :param server_box: Gtk.Box to add to
    """
    info = (await ws.get_server_info(server))["val"]["server"]

    image = Gtk.Image.new_from_icon_name("network-disconnect")

    button = Gtk.Button()
    button.set_child(image)
    button.set_size_request(48, 48)
    button.set_tooltip_text(info["name"])

    GLib.idle_add(server_box.prepend, button)

    await image_utils.load_server_icon(info["icon"], button, session)


def server_buttons_async(app, builder: Gtk.Builder):
    """
    Loads server buttons async

    :param app: Chlorine app instance
    :param builder: GTK Builder instance
    """
    asyncio.run(load_server_buttons(app, builder))


async def handle_ws_event(app, event_type: str, data) -> None:
    """
    Bridge between websocket connection and frontend UI

    :param event_type: Event sent from server
    :type event_type: str
    :param data: Data sent from bridge
    """
    assert app.builder is not None
    match event_type:
        case "ready":
            GLib.idle_add(app.set_server_name, data)

        case "channels_get":
            GLib.idle_add(app.build_channel_list, data)

        case "messages_get":
            if isinstance(data, dict):
                channel = data.get("channel")
                messages = data.get("messages", [])
            else:
                channel = None
                messages = data

            app.messages_build_source_id = GLib.idle_add(
                _handle_messages_get_main_thread,
                app,
                channel,
                messages,
            )

        case "message_new":
            GLib.idle_add(_handle_message_new_main_thread, app, data)


def handle_ws_event_async(app, event_type: str, data) -> None:
    """
    Bridge between websocket connection and frontend UI

    :param event_type: Event sent from server
    :type event_type: str
    :param data: Data sent from bridge
    """
    assert app.server is not None
    assert app.server.loop is not None
    asyncio.run_coroutine_threadsafe(
        handle_ws_event(app, event_type, data), app.server.loop
    )


def scroll_to_bottom(scrollable: Gtk.ScrolledWindow):
    def do_scroll():
        adj = scrollable.get_vadjustment()
        bottom = max(0.0, adj.get_upper() - adj.get_page_size())
        adj.set_value(bottom)
        return False

    GLib.idle_add(do_scroll, priority=GLib.PRIORITY_DEFAULT_IDLE)
    GLib.timeout_add(16, do_scroll)


def build_single_message(app, message: dict) -> None:
    """
    Builds widget for a single message

    Only useful when ran via `GLib.idle_add()`

    :param messages: User message from originChats server
    :type messages: list
    """
    assert app.builder is not None

    container = app.builder.get_object("messages_list")
    assert isinstance(container, Gtk.Box)
    scroll = app.builder.get_object("messages_list_scroll")
    assert isinstance(scroll, Gtk.ScrolledWindow)

    message_box = build_message(app, message, scroll)
    container.append(message_box)
    scroll_to_bottom(scroll)

    app.last_user = message["user"]


def build_messages_list(app, messages: list) -> None:
    """
    Builds widget for a list of messages

    Only useful when ran via `GLib.idle_add()`

    :param messages: List of messages from originChats server
    :type messages: list
    """
    assert app.builder is not None

    # Messages list
    container = app.builder.get_object("messages_list")
    assert isinstance(container, Gtk.Box)
    scroll = app.builder.get_object("messages_list_scroll")
    assert isinstance(scroll, Gtk.ScrolledWindow)

    # Clear old messages
    child = container.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        container.remove(child)
        child = next_child

    for message in messages:
        message_box = build_message(app, message, scroll)
        container.append(message_box)
        app.last_user = message["user"]
    scroll_to_bottom(scroll)


def build_message(
    app, message: dict, scroll: Gtk.ScrolledWindow | None = None
) -> Gtk.Box:
    is_new_user = app.last_user != message["user"]

    # Base message box
    message_box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL)

    # Extract image URLs from message content
    content, image_urls = extract_image_urls(message["content"])

    # Image box
    images_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

    # Message content
    message_content = Gtk.Label(label=content)
    message_content.set_wrap(True)
    message_content.set_wrap_mode(Pango.WrapMode.WORD)
    message_content.set_halign(Gtk.Align.START)
    message_content.set_selectable(True)

    # Content box
    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    if is_new_user:
        # Profile picture
        pfp = Gtk.Image.new_from_icon_name("pfp")
        pfp.set_pixel_size(32)
        pfp.set_valign(Gtk.Align.START)
        message_box.append(pfp)

        username = quote(message["user"], safe="")
        url = f"https://avatars.rotur.dev/{username}"
        assert isinstance(app.server, ws.Server)
        assert app.server.loop is not None
        pfp_task = asyncio.run_coroutine_threadsafe(
            image_utils.load_pfp(url, pfp),
            app.server.loop,
        )
        track_message_task(app, pfp_task)

        # Username label
        user_label = Gtk.Label(label=message["user"])
        user_label.set_halign(Gtk.Align.START)
        content_box.append(user_label)
    else:
        message_box.set_margin_bottom(0)
        message_content.set_margin_start(38)
        images_box.set_margin_start(38)

    content_box.append(message_content)
    if image_urls:
        def keep_scrolled_to_bottom() -> None:
            if scroll is not None:
                scroll_to_bottom(scroll)

        for url in image_urls:
            picture = Gtk.Picture()
            picture.set_halign(Gtk.Align.START)
            picture.set_keep_aspect_ratio(True)
            picture.set_can_shrink(True)
            if hasattr(Gtk, "ContentFit"):
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            images_box.append(picture)
            assert isinstance(app.server, ws.Server)
            assert app.server.loop is not None
            image_task = asyncio.run_coroutine_threadsafe(
                image_utils.load_image(
                    url,
                    picture,
                    on_loaded=keep_scrolled_to_bottom,
                ),
                app.server.loop,
            )
            track_message_task(app, image_task)

        content_box.append(images_box)

    message_box.append(content_box)
    return message_box

