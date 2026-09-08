"""Display-only class visibility; unobserved classes retain their prior state."""


def visible_classes_after_changes(current, changes):
    visible = set(range(256) if current is None else current)
    for code, shown in changes.items():
        if type(code) is not int or not 0 <= code <= 255:
            raise ValueError("Class values must be integers from 0 to 255.")
        if shown:
            visible.add(code)
        else:
            visible.discard(code)
    return sorted(visible)
