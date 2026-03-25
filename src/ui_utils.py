"""
UI utility helpers shared across views.
"""

import os
import platform

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # type: ignore


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
