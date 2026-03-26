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
            asyncio.create_task(app.build_messages_list(data))

        case "message_new":
            asyncio.create_task(app.build_single_message(data))


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


def set_server_name(app, data: dict):
    """
    Sets name of server in channel list

    Only useful when ran via `GLib.idle_add()`

    :param data: Description
    :type data: dict
    """
    assert app.builder is not None

    # Get widget and set title
    server_name_label = app.builder.get_object("server_name_label")
    assert isinstance(server_name_label, Gtk.Label)
    server_name_label.set_text(data["val"]["server"]["name"])


def build_channel_list(app, channels: list) -> None:
    """
    Builds widget for a list of channels

    Only useful when ran via `GLib.idle_add()`

    :param channels: List of channels
    :type channels: list
    """
    assert app.builder is not None
    assert isinstance(app.server, ws.Server)

    # Channel list
    container = app.builder.get_object("channel_list")
    assert isinstance(container, Gtk.Box)

    # Build channel list widgets
    for channel in channels:
        match channel["type"]:
            case "text":
                box = Gtk.Box(spacing=6)
                box.set_orientation(Gtk.Orientation.HORIZONTAL)

                image = Gtk.Image.new_from_icon_name("mail-read")
                label = Gtk.Label(label=channel["name"])
                label.set_halign(Gtk.Align.START)

                box.append(image)
                box.append(label)

                button = Gtk.ToggleButton(css_classes=["flat"])
                button.set_child(box)
                if channel["name"] == app.server.channel:
                    button.set_active(True)

                container.append(button)
            case "voice":
                box = Gtk.Box(spacing=6)
                box.set_orientation(Gtk.Orientation.HORIZONTAL)

                image = Gtk.Image.new_from_icon_name("call-start")
                label = Gtk.Label(label=channel["name"])
                label.set_halign(Gtk.Align.START)

                box.append(image)
                box.append(label)

                button = Gtk.Button(css_classes=["flat"])
                button.set_child(box)

                container.append(button)
            case "separator":
                separator = Gtk.Separator()
                container.append(separator)


async def build_single_message(app, message: dict) -> None:
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
    container.append(await message_box)
    scroll_to_bottom(scroll)

    app.last_user = message["user"]


async def build_messages_list(app, messages: list) -> None:
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
        container.append(await message_box)
        app.last_user = message["user"]
    scroll_to_bottom(scroll)


async def build_message(
    app, message: dict, scroll: Gtk.ScrolledWindow | None = None
) -> Gtk.Box:
    is_new_user = app.last_user != message["user"]

    # Base message box
    message_box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL)

    # Extract image URLs from message content
    content, image_urls = await image_utils.extract_image_urls(message["content"])

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
        asyncio.create_task(image_utils.load_pfp(url, pfp))

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
            asyncio.create_task(
                image_utils.load_image(
                    url,
                    picture,
                    on_loaded=keep_scrolled_to_bottom,
                )
            )

        content_box.append(images_box)

    message_box.append(content_box)
    return message_box

