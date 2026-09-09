"""Validated display-only settings, never scientific or selection parameters."""
POINT_STYLES = ("Circular", "Square")


def point_appearance(style="Circular", size=0):
    if style not in POINT_STYLES:
        raise ValueError("Unknown point style.")
    if type(size) is not int or not 0 <= size <= 16:
        raise ValueError("Point size must be Automatic or 1-16 pixels.")
    return {"point_style": style, "point_size": size}
