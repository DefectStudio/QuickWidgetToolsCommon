"""Add the Rendering Tool's V1/V2 selectors using the live editor APIs."""

import unreal


ASSET_PATH = "/QuickWidgetTools/EditorWidgets/WBP_03_RenderingTool"
INIT_SCRIPT = "import render_farm_version_selector\nrender_farm_version_selector.initialize(v1_checkbox, v2_checkbox)"
SUBMIT_SCRIPT = (
    "import importlib\n"
    "import publish_render_queue_to_farm\n"
    "import render_farm_version_selector\n"
    "importlib.reload(publish_render_queue_to_farm)\n"
    "result_summary = publish_render_queue_to_farm.run(\n"
    "    use_v2=render_farm_version_selector.use_v2(v1_checkbox, v2_checkbox))"
)


def connect(source, target):
    if not source.try_create_connection(target):
        raise RuntimeError("Could not connect Blueprint pins")


def apply():
    asset = unreal.load_asset(ASSET_PATH)
    asset.modify()
    tree = unreal.load_object(None, asset.get_path_name() + ":WidgetTree")
    tree.modify()
    prefix = tree.get_path_name() + "."

    def widget(name, cls):
        existing = unreal.find_object(None, prefix + name)
        return existing or unreal.new_object(cls, outer=tree, name=name)

    button = unreal.load_object(None, prefix + "SendRenderQueuetoFarmButton")
    grid = button.get_parent().get_parent()
    row = widget("FarmVersionSelector", unreal.HorizontalBox)
    if row.get_parent() is None:
        slot = grid.add_child_to_grid(row, 3, 1)
        slot.set_column_span(2)
        slot.set_padding(unreal.Margin(left=12.0))
        slot.set_horizontal_alignment(unreal.HorizontalAlignment.H_ALIGN_LEFT)
        slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)

    label_reference = unreal.load_object(None, prefix + "TextBlock_17")
    for version in ("V1", "V2"):
        checkbox = widget("FarmVersion" + version, unreal.CheckBox)
        checkbox.set_is_checked(version == "V1")
        checkbox.set_tool_tip_text("Send queued jobs to the " + version + " render farm.")
        if checkbox.get_parent() is None:
            slot = row.add_child_to_horizontal_box(checkbox)
            slot.set_padding(unreal.Margin(right=16.0))
            slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
        label = widget("FarmVersion" + version + "Label", unreal.TextBlock)
        label.set_text(version)
        label.set_font(label_reference.get_editor_property("font"))
        checkbox.set_content(label)

    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(asset, "EventGraph")
    nodes = graph.list_all_nodes()
    submit = next(n for n in nodes if n.get_name() == "K2Node_ExecutePythonScript_1")
    initializers = [
        n for n in nodes if n.get_class().get_name() == "K2Node_ExecutePythonScript"
        and "render_farm_version_selector.initialize" in n.find_input_pin("PythonScript").get_pin_value()
    ]
    if initializers:
        init = initializers[0]
    else:
        init = graph.create_node_from_name("Python|Execution|ExecutePythonScript", unreal.Vector2D(400, -400), [])
        construct = next(n for n in nodes if n.get_node_title() == "Event Construct")
        following = list(construct.find_then_pin().list_connected_pins())
        construct.find_then_pin().break_pin_links()
        connect(construct.find_then_pin(), init.find_execute_pin())
        for pin in following:
            connect(init.find_then_pin(), pin)

    for node, script in ((init, INIT_SCRIPT), (submit, SUBMIT_SCRIPT)):
        node.set_editor_property("inputs", ["v1_checkbox", "v2_checkbox"])
        if not node.find_input_pin("PythonScript").set_pin_value(script):
            raise RuntimeError("Could not set Python node script")
        for version in ("V1", "V2"):
            pin = node.find_input_pin(version.lower() + "_checkbox")
            if not pin.list_connected_pins():
                getter = graph.add_get_member_variable_node("FarmVersion" + version)
                connect(getter.find_output_pin("FarmVersion" + version), pin)

    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    errors = graph.list_nodes_with_errors()
    if errors:
        raise RuntimeError("Rendering Tool has Blueprint compilation errors: " + str(errors))
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Could not save Rendering Tool")
    unreal.log("[FarmVersionSelector] Added V1/V2 selectors and explicit submission routing.")


if __name__ == "__main__":
    apply()
