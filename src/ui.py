import gi
import os
import platform
import sys
import threading
import webbrowser
import auth

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gdk, Gio  # type: ignore


AUTHENTICATED = False


class Chlorine(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.xhlowi.Chlorine")

    def do_activate(self):
        """
        UI initialization, consisting of building the UI via GtkBuilder,
        loading custom icon theme and CSS, then presents application to user.
        """

        # Build UI from auth.ui XML
        builder = Gtk.Builder()
        if AUTHENTICATED:
            builder.add_from_file("../ui/main.ui")
        else:
            builder.add_from_file("../ui/auth.ui")
        win = builder.get_object("ChlorineAuth")
        linking_button = builder.get_object("linking_button")

        assert linking_button is not None

        linking_button.connect("clicked", self.open_linking_page)

        # Checks if GtkBuilder UI isn't broken
        assert isinstance(win, Gtk.ApplicationWindow)

        # Initialize custom icon theme and CSS
        icon_theme = Gtk.IconTheme.get_for_display(Gtk.Window().get_display())
        icon_theme.add_search_path("../assets")
        load_css("../ui/style.css")

        # Auth thread
        thread = threading.Thread(target=self.auth_thread, args=(builder,))
        thread.start()

        # Starts application
        win.set_application(self)
        win.present()

    def auth_thread(self, builder: Gtk.Builder) -> None:
        """
        Handles account linking on authentication UI.
        Should be ran as a thread instead of a function.

        :param builder: GTK Builder instance
        :type builder: Gtk.Builder
        """
        code = auth.get_linking_code()
        code_label = builder.get_object("code_label")
        assert isinstance(code_label, Gtk.Label)

        code_label.set_markup(f"Code: <tt>{code}</tt>")

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
    set_system_theme()
    app = Chlorine()
    app.run(sys.argv)
