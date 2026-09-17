"""Mutually exclusive V1/V2 checkboxes for the Rendering Tool farm publisher."""


def initialize(v1_checkbox, v2_checkbox):
    """Each Rendering Tool instance starts on V1, independent of session settings."""
    updating = False

    def select(active, other):
        nonlocal updating
        if updating:
            return
        updating = True
        try:
            active.set_is_checked(True)
            other.set_is_checked(False)
        finally:
            updating = False

    # These dedicated controls have no other handlers. Reconstructing the widget
    # replaces the bindings rather than accumulating callbacks on the same boxes.
    v1_checkbox.on_check_state_changed.clear()
    v2_checkbox.on_check_state_changed.clear()
    v1_checkbox.on_check_state_changed.add_callable(lambda _checked: select(v1_checkbox, v2_checkbox))
    v2_checkbox.on_check_state_changed.add_callable(lambda _checked: select(v2_checkbox, v1_checkbox))
    select(v1_checkbox, v2_checkbox)


def use_v2(v1_checkbox, v2_checkbox):
    """Reject ambiguous UI state rather than submit to an unintended queue."""
    v1 = v1_checkbox.is_checked()
    v2 = v2_checkbox.is_checked()
    if v1 == v2:
        raise RuntimeError("Select exactly one render farm version: V1 or V2.")
    return bool(v2)
