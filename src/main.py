"""
Frontend/UI for Chlorine, handles user actions and displays content to user.
Made with <3 by Stormy
"""

import gi
import os
import platform
import sys
import threading
import time
import webbrowser
import auth
import config

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk, Gio  # type: ignore


class Chlorine(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.xhlowi.Chlorine")
        self.stop_event = threading.Event()
        self.auth_thread_obj = None

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

        win = builder.get_object("ChlorineMain")
        assert isinstance(win, Gtk.ApplicationWindow)

        win.set_application(self)
        win.present()

    def load_auth_ui(self):
        builder = Gtk.Builder()
        builder.add_from_file("../ui/auth.ui")

        win = builder.get_object("ChlorineAuth")
        assert isinstance(win, Gtk.ApplicationWindow)
        linking_button = builder.get_object("linking_button")

        assert linking_button is not None
        linking_button.connect("clicked", self.open_linking_page)

        self.auth_thread_obj = threading.Thread(
            target=self.auth_thread, args=(builder,), daemon=True
        )
        self.auth_thread_obj.start()

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
                GLib.idle_add(self.load_main_ui)
                break
            time.sleep(2.5)

    def open_linking_page(self, *_):
        """Opens linking page in web browser"""
        webbrowser.open("https://rotur.dev/link")

def load_css(path: str):
    """
    Load GTK CSS from given file patth

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
    os.environ["GTK_ICON_THEME"] = icon_theme

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
