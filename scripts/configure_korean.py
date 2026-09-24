"""Configure the current GNOME user's Hangul input without restarting IBus."""

from gi.repository import Gio, GLib


def configure_korean():
    """Preserve existing input sources and make Hangul start in Korean mode."""
    settings = Gio.Settings.new("org.gnome.desktop.input-sources")
    sources = list(settings.get_value("sources").unpack())
    if ("ibus", "hangul") not in sources:
        sources.append(("ibus", "hangul"))
        if not settings.set_value("sources", GLib.Variant("a(ss)", sources)):
            raise RuntimeError("Unable to save the Hangul input source")

    hangul = Gio.Settings.new("org.freedesktop.ibus.engine.hangul")
    if not hangul.set_string("initial-input-mode", "hangul"):
        raise RuntimeError("Unable to set the initial Hangul mode")
    if not hangul.set_boolean("disable-latin-mode", True):
        raise RuntimeError("Unable to enable direct Hangul typing")
    Gio.Settings.sync()


if __name__ == "__main__":
    configure_korean()
