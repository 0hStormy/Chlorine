"""
Frontend/UI for Chlorine, handles user actions and displays content to user.
Made with <3 by Stormy
"""

import gi
import aiohttp
import asyncio
import os
import platform
import sys
import threading
import time
import webbrowser
import auth
import config
import ws

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk, Gio, Pango  # type: ignore


class Chlorine(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="xyz.xhlowi.Chlorine")
        self.stop_event = threading.Event()
        self.auth_thread_obj = None
        self.builder: Gtk.Builder | None = None
        self.server: ws.Server | None = None
        self.last_user = ""

    def do_activate(self):
        icon_theme = Gtk.IconTheme.get_for_display(Gtk.Window().get_display())
        icon_theme.add_search_path("../assets")
        load_css("../ui/style.css")

        if auth.is_authenticated():
            self.load_main_ui()
        else:
            self.load_auth_ui()

    def load_main_ui(self):
        builder = Gtk.Builder()
        builder.add_from_file("../ui/main.ui")
        self.builder = builder

        win = builder.get_object("ChlorineMain")
        assert isinstance(win, Gtk.ApplicationWindow)

        # Load server list buttons
        threading.Thread(
            target=self.server_buttons_async, args=(builder,), daemon=True
        ).start()

        # Connect to originChats server
        selected_server = config.read_from_config("servers")[0]
        server = ws.Server(
            selected_server, on_event=self.handle_ws_event_async
        )
        self.server = server
        threading.Thread(
            target=lambda: asyncio.run(server.listen()), daemon=True
        ).start()

        send_msg_button = builder.get_object("send_message")
        assert isinstance(send_msg_button, Gtk.Button)
        entry = builder.get_object("message_entry")
        assert isinstance(entry, Gtk.Entry)

        def on_send(btn):
            text = entry.get_text()
            entry.set_text("")
            assert isinstance(server.loop, asyncio.AbstractEventLoop)
            asyncio.run_coroutine_threadsafe(
                server.send_message(text),
                server.loop
            )

        send_msg_button.connect("clicked", on_send)
        entry.connect("activate", on_send)

        win.set_application(self)
        win.present()

    def load_auth_ui(self):
        builder = Gtk.Builder()
        builder.add_from_file("../ui/auth.ui")
        self.builder = builder

        win = builder.get_object("ChlorineAuth")
        assert isinstance(win, Gtk.ApplicationWindow)
        linking_button = builder.get_object("linking_button")

        assert linking_button is not None
        linking_button.connect("clicked", self.open_linking_page)

        threading.Thread(target=self.auth_thread, args=(builder,), daemon=True).start()

        win.set_application(self)
        win.present()

    def auth_thread(self, builder: Gtk.Builder) -> None:
        """
        Handles account linking on authentication UI.
        Should be ran as a thread instead of a function.

        :param builder: GTK Builder instance
        :type builder: Gtk.Builder
        """

        # Display linking code to end user
        code = auth.get_linking_code()
        code_label = builder.get_object("code_label")
        assert isinstance(code_label, Gtk.Label)
        GLib.idle_add(code_label.set_markup, f"Code: <tt>{code}</tt>")

        # Wait for user to link account
        while True:
            response = auth.try_get_token(code)
            if response[0] is auth.LinkedStatus.LINKED:
                config.write_to_config("token", response[1])
                GLib.idle_add(self.load_main_ui)
                break
            time.sleep(2.5)

    def open_linking_page(self, *_):
        """Opens linking page in web browser"""
        webbrowser.open("https://rotur.dev/link")

    async def load_server_buttons(self, builder: Gtk.Builder):
        """
        Taskify all servers and gather them to load the server buttons

        :param builder: GTK Builder instance
        :type builder: Gtk.Builder
        """
        servers = config.read_from_config("servers")
        server_box = builder.get_object("server_list")
        assert isinstance(server_box, Gtk.Box)
        tasks = [
            self.process_server(server, server_box) for server in reversed(servers)
        ]
        await asyncio.gather(*tasks)

    async def process_server(self, server, server_box: Gtk.Box):
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

        await load_server_icon(info["icon"], button)

    def server_buttons_async(self, builder: Gtk.Builder):
        """
        Loads server buttons async

        :param self: Description
        :param builder: Description
        """
        asyncio.run(self.load_server_buttons(builder))

    async def handle_ws_event(self, event_type: str, data) -> None:
        """
        Bridge between websocket connection and frontend UI

        :param event_type: Event sent from server
        :type event_type: str
        :param data: Data sent from bridge
        """
        assert self.builder is not None
        match event_type:
            case "ready":
                GLib.idle_add(self.set_server_name, data)

            case "channels_get":
                GLib.idle_add(self.build_channel_list, data)

            case "messages_get":
                asyncio.create_task(self.build_messages_list(data))

            case "message_new":
                asyncio.create_task(self.build_single_message(data))

    def handle_ws_event_async(self, event_type: str, data) -> None:
        """
        Bridge between websocket connection and frontend UI

        :param event_type: Event sent from server
        :type event_type: str
        :param data: Data sent from bridge
        """
        assert self.server is not None
        assert self.server.loop is not None
        asyncio.run_coroutine_threadsafe(
            self.handle_ws_event(event_type, data),
            self.server.loop
        )

    def scroll_to_bottom(self, scrollable: Gtk.ScrolledWindow):
        def do_scroll():
            adj = scrollable.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False

        GLib.idle_add(do_scroll)

    def set_server_name(self, data: dict):
        """
        Sets name of server in channel list

        Only useful when ran via `GLib.idle_add()`

        :param data: Description
        :type data: dict
        """
        assert self.builder is not None

        # Get widget and set title
        server_name_label = self.builder.get_object("server_name_label")
        assert isinstance(server_name_label, Gtk.Label)
        server_name_label.set_text(data["val"]["server"]["name"])

    def build_channel_list(self, channels: list) -> None:
        """
        Builds widget for a list of channels

        Only useful when ran via `GLib.idle_add()`

        :param channels: List of channels
        :type channels: list
        """
        assert self.builder is not None
        assert isinstance(self.server, ws.Server)

        # Channel list
        container = self.builder.get_object("channel_list")
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
                    if channel["name"] == self.server.channel:
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

    async def build_single_message(self, message: dict) -> None:
        """
        Builds widget for a single message

        Only useful when ran via `GLib.idle_add()`

        :param messages: User message from originChats server
        :type messages: list
        """
        assert self.builder is not None

        container = self.builder.get_object("messages_list")
        assert isinstance(container, Gtk.Box)

        message_box = self.build_message(message)
        container.append(await message_box)

        scroll = self.builder.get_object("messages_list_scroll")
        assert isinstance(scroll, Gtk.ScrolledWindow)
        self.scroll_to_bottom(scroll)

        self.last_user = message["user"]

    async def build_messages_list(self, messages: list) -> None:
        """
        Builds widget for a list of messages

        Only useful when ran via `GLib.idle_add()`

        :param messages: List of messages from originChats server
        :type messages: list
        """
        assert self.builder is not None

        # Messages list
        container = self.builder.get_object("messages_list")
        assert isinstance(container, Gtk.Box)

        # Clear old messages
        child = container.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            container.remove(child)
            child = next_child

        for message in messages:
            message_box = self.build_message(message)
            container.append(await message_box)
            self.last_user = message["user"]
        
        scroll = self.builder.get_object("messages_list_scroll")
        assert isinstance(scroll, Gtk.ScrolledWindow)
        self.scroll_to_bottom(scroll)

    async def build_message(self, message: dict) -> Gtk.Box:
        group_message = self.last_user != message["user"]

        # Base message box
        message_box = Gtk.Box(spacing=6)
        message_box.set_orientation(Gtk.Orientation.HORIZONTAL)

        # Message content
        message_content = Gtk.Label(label=message["content"])
        message_content.set_wrap(True)
        message_content.set_wrap_mode(Pango.WrapMode.WORD)
        message_content.set_halign(Gtk.Align.START)
        message_content.set_selectable(True)

        # Content box
        content_box = Gtk.Box()
        content_box.set_orientation(Gtk.Orientation.VERTICAL)

        if group_message:
            # Profile picture
            pfp = Gtk.Image.new_from_icon_name("pfp")
            pfp.set_pixel_size(32)
            pfp.set_valign(Gtk.Align.START)
            message_box.append(pfp)

            url = f"https://avatars.rotur.dev/{message["user"]}"
            asyncio.create_task(load_pfp(url, pfp))

            # Username label
            user_label = Gtk.Label(label=message["user"])
            user_label.set_halign(Gtk.Align.START)
            content_box.append(user_label)
        else:
            message_box.set_margin_bottom(0)
            message_content.set_margin_start(38)

        content_box.append(message_content)


        # Append to widget tree
        message_box.append(content_box)
        return message_box


async def load_pfp(url: str, image: Gtk.Image):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))

    def apply():
        image.set_from_paintable(texture)
        image.set_pixel_size(32)

    GLib.idle_add(apply)


async def load_server_icon(url: str, widget: Gtk.Button):
    """
    Downloads a single server icon and apply it to a widget's child

    :param url: URL to icon
    :type url: str
    :param widget: Widget to set child Gtk.Image on
    :type widget: Gtk.Button
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
    image = Gtk.Image.new_from_paintable(texture)
    image.set_pixel_size(34)

    GLib.idle_add(widget.set_child, image)


def load_css(path: str):
    """
    Load GTK CSS from given file path

    :param path: Path to CSS stylesheet
    :type path: str
    """
    css = Gtk.CssProvider()
    css.load_from_path(path)

    display = Gdk.Display.get_default()

    if not isinstance(display, Gdk.Display):
        raise RuntimeError("CSS could not load, something is seriously wrong")

    Gtk.StyleContext.add_provider_for_display(
        display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def set_system_theme():
    """
    Workaround to GTK 4 forcing Adwaita by default.

    Couple limitations to this method of forcing the system theme:
        * If user changes theme, they will have to restart the app to apply
        * May just break in the future
    """

    # Ignore if platform isn't Linux
    if platform.system() != "Linux":
        return

    # Search for default theme via GIO
    settings = Gio.Settings.new("org.gnome.desktop.interface")
    theme = settings.get_string("gtk-theme")
    icon_theme = settings.get_string("icon-theme")
    os.environ["GTK_THEME"] = theme

    default_settings = Gtk.Settings.get_default()
    assert default_settings
    default_settings.set_property("gtk-icon-theme-name", icon_theme)

    # Set font size to the system font size
    font = settings.get_string("font-name").split()[1]
    font_css = f"""
    * {{
	    font-family: system-ui;
        font-size: {font}pt;
    }}
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(font_css)
    display = Gdk.Display.get_default()

    if not isinstance(display, Gdk.Display):
        raise RuntimeError("CSS could not load, something is seriously wrong")

    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


if __name__ == "__main__":
    try:
        set_system_theme()
        config.create_config()
        app = Chlorine()
        app.run(sys.argv)
    except KeyboardInterrupt:
        sys.exit(0)
