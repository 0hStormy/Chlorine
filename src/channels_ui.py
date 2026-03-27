"""
Channel panel UI logic for Chlorine.
"""

import asyncio
import json
import gi
import ws

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # type: ignore


def set_server_name(app, data: dict):
    """
    Sets name of server in channel list

    Only useful when ran via `GLib.idle_add()`

    :param data: Description
    :type data: dict
    """
    assert app.builder is not None

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

    container = app.builder.get_object("channel_list")
    assert isinstance(container, Gtk.Box)

    child = container.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        container.remove(child)
        child = next_child

    app.channel_buttons = {}
    app.button_handlers = {}

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

                handler_id = button.connect(
                    "toggled", on_channel_toggled, app, channel["name"]
                )
                app.channel_buttons[channel["name"]] = button
                app.button_handlers[channel["name"]] = handler_id

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


def on_channel_toggled(button: Gtk.ToggleButton, app, channel_name: str) -> None:
    """
    Handle selecting a text channel and request messages for it.
    """
    assert isinstance(app.server, ws.Server)

    if not button.get_active():
        if app.server.channel == channel_name:
            handler_id = app.button_handlers[channel_name]
            button.handler_block(handler_id)
            button.set_active(True)
            button.handler_unblock(handler_id)
        return

    if app.server.channel == channel_name:
        return

    for name, channel_button in app.channel_buttons.items():
        if name == channel_name:
            continue
        if not channel_button.get_active():
            continue

        handler_id = app.button_handlers[name]
        channel_button.handler_block(handler_id)
        channel_button.set_active(False)
        channel_button.handler_unblock(handler_id)

    app.cancel_message_loading()

    app.server.channel = channel_name

    assert app.server.loop is not None
    assert app.server.websocket is not None
    payload = {"cmd": "messages_get", "channel": app.server.channel}
    asyncio.run_coroutine_threadsafe(
        app.server.websocket.send(json.dumps(payload)),
        app.server.loop,
    )
