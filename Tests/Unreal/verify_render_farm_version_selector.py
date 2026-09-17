"""Verify live selector events and submission wiring without publishing a job."""

import importlib
from unittest.mock import patch

import unreal
import publish_render_queue_to_farm as publisher
import render_farm_version_selector as selector


def verify():
    asset = unreal.load_asset("/QuickWidgetTools/EditorWidgets/WBP_03_RenderingTool")
    tree_path = asset.get_path_name() + ":WidgetTree."
    assert unreal.load_object(None, tree_path + "FarmVersionV1").is_checked()
    assert not unreal.load_object(None, tree_path + "FarmVersionV2").is_checked()
    widget = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).spawn_and_register_tab(asset)
    v1 = widget.get_editor_property("FarmVersionV1")
    v2 = widget.get_editor_property("FarmVersionV2")
    assert v1.on_check_state_changed.is_bound() and v2.on_check_state_changed.is_bound()
    assert v1.is_checked() and not v2.is_checked()
    button = widget.get_editor_property("SendRenderQueuetoFarmButton")
    calls = []
    original_reload = importlib.reload
    with patch.object(publisher, "run", side_effect=lambda **kwargs: calls.append(kwargs) or "test only"), patch.object(
        importlib, "reload", side_effect=lambda module: module if module is publisher else original_reload(module)
    ):
        button.on_clicked.broadcast()
        v2.set_is_checked(True)
        v2.on_check_state_changed.broadcast(True)
        assert not v1.is_checked() and v2.is_checked()
        button.on_clicked.broadcast()
        v2.set_is_checked(False)
        v2.on_check_state_changed.broadcast(False)
        assert not v1.is_checked() and v2.is_checked()
        v1.set_is_checked(True)
        v1.on_check_state_changed.broadcast(True)
        assert v1.is_checked() and not v2.is_checked()
        button.on_clicked.broadcast()
    assert calls == [{"use_v2": False}, {"use_v2": True}, {"use_v2": False}], calls
    unreal.log("[FarmVersionSelectorTest] PASS: defaults, exclusive selection and actual submission button routing. No jobs published.")


if __name__ == "__main__":
    verify()
