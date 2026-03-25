"""
Authentication UI logic for Chlorine.
"""

import threading
import time
import webbrowser

import gi

import auth
import config

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # type: ignore


def load_auth_ui(app):
    builder = Gtk.Builder()
    builder.add_from_file("../ui/auth.ui")
    app.builder = builder

    win = builder.get_object("ChlorineAuth")
    assert isinstance(win, Gtk.ApplicationWindow)
    linking_button = builder.get_object("linking_button")

    assert linking_button is not None
    linking_button.connect("clicked", open_linking_page)

    threading.Thread(
        target=auth_thread,
        args=(app, builder),
        daemon=True,
    ).start()

    win.set_application(app)
    win.present()


def auth_thread(app, builder: Gtk.Builder) -> None:
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
            GLib.idle_add(app.load_main_ui)
            break
        time.sleep(2.5)


def open_linking_page(*_):
    """Opens linking page in web browser"""
    webbrowser.open("https://rotur.dev/link")
