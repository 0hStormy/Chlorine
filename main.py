"""
Chlorine, a native client for the originChats protocol written in Python.
"""

import gi
import requests.exceptions
import threading
import asyncio
import auth
import config
import ws

gi.require_version("Gtk", "3.0")
# Sorry for the inline comments, Ruff wanted to explode if they weren't there
from gi.repository import GLib, Gtk, Gdk  # type: ignore # noqa: E402


class ChlorineAuth(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(320, 480)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        self.add(box)

        # Rotur logo
        rotur_logo = load_icon("rotur-symbolic", 64)
        box.pack_start(rotur_logo, False, False, 0)

        # Welcome header
        welcome = Gtk.Label(label="Welcome back!")
        welcome.get_style_context().add_class("title-2")
        box.pack_start(welcome, False, False, 0)

        # Login info label
        login_info = Gtk.Label(label="Please login via Rotur's device link")
        box.pack_start(login_info, False, False, 0)

        # Login code label
        self.code_label = Gtk.Label()
        self.code_label.set_selectable(True)
        self.code_label.set_can_focus(False)
        self.code_label.set_markup("Code: <tt>...</tt>")
        box.pack_start(self.code_label, False, False, 0)

        # Open linking site button
        linking_site = Gtk.Button(label="Open Linking Page")
        linking_site.connect("clicked", lambda _: auth.open_linking_page())
        box.pack_start(linking_site, False, False, 0)

        self.show_all()


class ChlorineChat(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(800, 600)
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        root_box.set_hexpand(True)
        root_box.set_vexpand(True)
        self.add(root_box)

        server_list = asyncio.run(add_server_buttons())

        root_box.pack_start(server_list, False, False, 0)

        servers_separtator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        server_list.set_vexpand(True)
        root_box.pack_start(servers_separtator, False, False, 0)

        self.show_all()


class ChlorineApplication(Gtk.Application):
    """Main application class for Chlorine."""

    def __init__(self):
        super().__init__(application_id="xyz.ostormy.Chlorine")
        GLib.set_application_name("Chlorine")

    def do_activate(self) -> None:
        """Activate the application, routing to auth or main window."""
        token = config.get_value(config.CONFIG_PATH, "token")
        is_authenticated = token is not None

        title = "Chlorine" if is_authenticated else "Auth - Chlorine"
        if is_authenticated:
            window = ChlorineChat(application=self, title=title)
        else:
            window = ChlorineAuth(application=self, title=title)
        window.present()

        if not is_authenticated:
            self._load_auth_styles()
            self._start_auth_flow(window)
        else:
            threading.Thread(target=self._handle_ws_server, daemon=True).start()
            
    def _handle_ws_server(self) -> None:
        handle = ws.Handle()
        asyncio.run(ws.Handle.start(handle))

    def _load_auth_styles(self):
        """Load and apply the authentication screen CSS"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path("assets/auth.css")
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _start_auth_flow(self, window):
        """Spawn a background thread to handle the auth code flow"""

        def get_auth_code():
            """Fetch auth code and update the UI label"""
            try:
                auth_code = auth.generate_auth_code()
                window.code_label.set_markup(f"Code: <tt>{auth_code}</tt>")
            except requests.exceptions.ConnectionError:
                window.code_label.set_markup("Error fetching code")
                return

            auth.token_from_link(auth_code)

        threading.Thread(target=get_auth_code, daemon=True).start()


def load_icon(icon: str = "rotur-symbolic", size: int = 16):
    """
    Loads symbolic icon from built-in icon pack

    :param icon: Icon to load
    :type icon: str
    :param size: Size of icon
    :type size: int
    :return: Widget object
    :rtype: object
    """
    icon_theme = Gtk.IconTheme.get_default()
    icon_theme.append_search_path("assets")
    image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DIALOG)
    image.set_pixel_size(size)
    return image


async def add_server_buttons(path: str = config.CONFIG_PATH):
    # Server list box
    server_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    server_list.set_margin_top(6)
    server_list.set_margin_start(6)
    server_list.set_margin_end(6)
    server_list.set_vexpand(True)

    user_servers = config.get_value(path, "servers")
    selected_server = config.get_value(path, "selected_server")

    if not isinstance(user_servers, list):
        return server_list

    server_index = 0

    for server in user_servers:
        server_info = (await ws.get_server_info(server))["val"]
        server_button = Gtk.ToggleButton()
        icon = Gtk.Image.new_from_icon_name("dontknow", Gtk.IconSize.BUTTON)
        icon.set_pixel_size(24)
        server_button.set_image(icon)
        server_button.set_size_request(48, 48)
        server_button.set_tooltip_text(server_info["server"]["name"])
        if server_index == selected_server:
            server_button.set_active(True)
        server_list.pack_start(server_button, False, False, 0)

        server_index += 1

    # Add server button
    add_server = Gtk.Button.new_from_icon_name(
        "list-add", Gtk.IconSize.LARGE_TOOLBAR
    )
    add_server.set_size_request(48, 48)
    server_list.pack_start(add_server, False, False, 0)

    return server_list


if __name__ == "__main__":
    config.create_config(config.CONFIG_PATH)
    app = ChlorineApplication()
    app.run()
