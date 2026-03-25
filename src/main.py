"""
Entry point file for Chlorine.
Initializes the GTK application and handles UI loading and websocket events.
"""

import aiohttp
import gi
import asyncio
import sys
import threading
import auth
import config
import ws
import auth_ui
import main_ui
import ui_utils

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # type: ignore


class Chlorine(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="xyz.xhlowi.Chlorine")
        self.stop_event = threading.Event()
        self.auth_thread_obj = None
        self.builder: Gtk.Builder | None = None
        self.server: ws.Server | None = None
        self.session: aiohttp.ClientSession | None = None
        self.last_user = ""

    def do_activate(self):
        icon_theme = Gtk.IconTheme.get_for_display(Gtk.Window().get_display())
        icon_theme.add_search_path("../assets")
        ui_utils.load_css("../ui/style.css")

        if auth.is_authenticated():
            self.load_main_ui()
        else:
            self.load_auth_ui()

    def load_main_ui(self):
        main_ui.load_main_ui(self)

    def load_auth_ui(self):
        auth_ui.load_auth_ui(self)

    def auth_thread(self, builder: Gtk.Builder) -> None:
        auth_ui.auth_thread(self, builder)

    def open_linking_page(self, *_):
        auth_ui.open_linking_page(*_)

    async def load_server_buttons(self, builder: Gtk.Builder):
        await main_ui.load_server_buttons(self, builder)

    async def process_server(self, server, server_box: Gtk.Box):
        session = aiohttp.ClientSession()
        try:
            await main_ui.process_server(server, server_box, session)
        finally:
            await session.close()

    def server_buttons_async(self, builder: Gtk.Builder):
        main_ui.server_buttons_async(self, builder)

    async def handle_ws_event(self, event_type: str, data) -> None:
        await main_ui.handle_ws_event(self, event_type, data)

    def handle_ws_event_async(self, event_type: str, data) -> None:
        main_ui.handle_ws_event_async(self, event_type, data)

    def scroll_to_bottom(self, scrollable: Gtk.ScrolledWindow):
        main_ui.scroll_to_bottom(scrollable)

    def set_server_name(self, data: dict):
        main_ui.set_server_name(self, data)

    def build_channel_list(self, channels: list) -> None:
        main_ui.build_channel_list(self, channels)

    async def build_single_message(self, message: dict) -> None:
        await main_ui.build_single_message(self, message)

    async def build_messages_list(self, messages: list) -> None:
        await main_ui.build_messages_list(self, messages)

    async def build_message(self, message: dict) -> Gtk.Box:
        return await main_ui.build_message(self, message)


if __name__ == "__main__":
    try:
        ui_utils.set_system_theme()
        config.create_config()
        app = Chlorine()
        app.run(sys.argv)
    except KeyboardInterrupt:
        sys.exit(0)
