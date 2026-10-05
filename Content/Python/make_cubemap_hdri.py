"""One-shot, scene-linear HDR cubemap capture for the Lite Tools widget.

The default is six 8192-square faces. The capture starts at the editor viewport,
or reuses the selected capture actor previously made by this tool. Only the new
TextureCube is saved; the level remains available for the user to save or undo.
"""

import datetime
import re

import unreal


OUTPUT_DIRECTORY = "/Game/Materials/Textures/HDRI"
CAPTURE_TAG = "QuickWidgetToolsHDRICapture"
DEFAULT_FACE_SIZE = 8192
WARMUP_FRAMES = 24
_job = None
last_result = None
last_error = None


def _configure_capture(component):
    component.set_editor_property("capture_every_frame", False)
    component.set_editor_property("capture_on_movement", False)
    component.set_editor_property("always_persist_rendering_state", True)
    component.set_editor_property("capture_rotation", False)
    component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR_NO_ALPHA)

    # Cube captures default to disabling GI/reflections, even in a Lumen project.
    # Explicitly opt into the project's renderer, while retaining volume settings.
    settings = component.get_editor_property("post_process_settings")
    if unreal.SystemLibrary.get_console_variable_int_value("r.DynamicGlobalIlluminationMethod") == 1:
        settings.set_editor_property("override_dynamic_global_illumination_method", True)
        settings.set_editor_property("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN)
    if unreal.SystemLibrary.get_console_variable_int_value("r.ReflectionMethod") == 1:
        settings.set_editor_property("override_reflection_method", True)
        settings.set_editor_property("reflection_method", unreal.ReflectionMethod.LUMEN)
    component.set_editor_property("post_process_settings", settings)
    component.set_editor_property("post_process_blend_weight", 1.0)


def _capture_actor(actor_subsystem, editor_subsystem):
    selected = actor_subsystem.get_selected_level_actors()
    if len(selected) == 1 and isinstance(selected[0], unreal.SceneCaptureCube) and selected[0].actor_has_tag(CAPTURE_TAG):
        return selected[0]
    camera_info = editor_subsystem.get_level_viewport_camera_info()
    if not camera_info:
        raise RuntimeError("Open a perspective level viewport before making an HDRI.")
    location, _rotation = camera_info
    with unreal.ScopedEditorTransaction("Create HDRI 360 capture camera"):
        actor = actor_subsystem.spawn_actor_from_class(unreal.SceneCaptureCube, location, unreal.Rotator())
        if not actor:
            raise RuntimeError("Could not create the 360 capture camera in the editor world.")
        actor.set_actor_label("HDRI_360_Capture")
        actor.set_editor_property("tags", [unreal.Name(CAPTURE_TAG)])
        actor.set_folder_path("HDRI Captures")
    return actor


class _CaptureJob:
    def __init__(self, actor, world, face_size):
        self.actor = actor
        self.actor_path = actor.get_path_name()
        self.world = world
        self.face_size = face_size
        self.component = actor.get_component_by_class(unreal.SceneCaptureComponentCube)
        if not self.component:
            raise RuntimeError("The 360 camera has no cube capture component.")
        self.target = None
        self.callback = None
        self.frames = 0
        self.phase = "warmup"
        self.original_cube_single_pass = None

    def start(self):
        # The default 3-by-2 face atlas would be 24576px wide at 8K, beyond
        # DX12's 2D texture limit. Render the faces separately for this job.
        self.original_cube_single_pass = unreal.SystemLibrary.get_console_variable_int_value("r.SceneCapture.CubeSinglePass")
        unreal.SystemLibrary.execute_console_command(self.world, "r.SceneCapture.CubeSinglePass 0")
        _configure_capture(self.component)
        self.target = unreal.QuickWidgetToolsHDRILibrary.create_hdr_cube_render_target(min(512, self.face_size))
        if not self.target:
            raise RuntimeError("Could not allocate the HDR cube render target.")
        self.component.set_editor_property("texture_target", self.target)
        self.callback = unreal.register_slate_post_tick_callback(self.tick)
        unreal.log("[MakeCubeMapHDRI] Warming up 360 capture; final size: {} x {} per face.".format(self.face_size, self.face_size))

    def tick(self, _delta_seconds):
        if _job is not self or self.phase == "saving":
            return
        try:
            editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            if editor_world != self.world or not unreal.SystemLibrary.is_valid(self.actor):
                raise RuntimeError("HDRI capture cancelled because the level or capture camera changed.")
            if self.phase == "warmup":
                self.component.capture_scene()
                self.frames += 1
                if self.frames >= WARMUP_FRAMES:
                    # Re-registering the component here would discard its warmed
                    # Lumen view states. Only replace the target reference.
                    self.component.set_editor_property("texture_target", None, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                    unreal.QuickWidgetToolsHDRILibrary.release_hdr_cube_render_target(self.target)
                    self.target = unreal.QuickWidgetToolsHDRILibrary.create_hdr_cube_render_target(self.face_size)
                    if not self.target:
                        raise RuntimeError("Could not allocate the final HDR cube render target.")
                    self.component.set_editor_property("texture_target", self.target, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                    self.phase = "capture"
                    unreal.log("[MakeCubeMapHDRI] Taking final HDR snapshot...")
            elif self.phase == "capture":
                self.component.capture_scene()
                unreal.QuickWidgetToolsHDRILibrary.flush_hdri_capture_rendering()
                self.phase = "save"
            elif self.phase == "save":
                self.phase = "saving"
                self.save()
        except Exception as error:
            self.fail(error)

    def save(self):
        global last_result
        # Asset compilation/saving can pump Slate ticks. Stop this callback
        # before entering either operation, while keeping the job's busy guard.
        self.stop_callback()
        level_name = re.sub(r"[^A-Za-z0-9_]", "_", self.world.get_name())
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        name = "T_HDRI_{}_{}K_{}".format(level_name, self.face_size // 1024, stamp)
        if not unreal.EditorAssetLibrary.does_directory_exist(OUTPUT_DIRECTORY):
            if not unreal.EditorAssetLibrary.make_directory(OUTPUT_DIRECTORY):
                raise RuntimeError("Could not create " + OUTPUT_DIRECTORY)
        texture = unreal.QuickWidgetToolsHDRILibrary.create_hdr_texture_cube(self.target, OUTPUT_DIRECTORY + "/" + name)
        if not texture:
            raise RuntimeError("Unreal could not convert the captured HDR pixels into a TextureCube.")
        actual_size = unreal.QuickWidgetToolsHDRILibrary.get_hdr_cube_source_size(texture)
        face_count = unreal.QuickWidgetToolsHDRILibrary.get_hdr_cube_source_slice_count(texture)
        if actual_size != self.face_size or face_count != 6:
            raise RuntimeError("Unexpected captured face size: {} (requested {}).".format(actual_size, self.face_size))
        # Pixels now belong to the TextureCube source. Release the large capture
        # target and Lumen histories before waiting for compression and saving.
        self.release_capture_resources()
        if not unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False):
            raise RuntimeError("Could not save HDRI texture " + texture.get_path_name())
        last_result = {"asset_path": texture.get_path_name(), "face_size": actual_size, "capture_actor": self.actor_path}
        self.cleanup()
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if unreal.SystemLibrary.is_valid(self.actor):
            actors.set_selected_level_actors([self.actor])
        unreal.EditorAssetLibrary.sync_browser_to_objects([texture.get_path_name()])
        unreal.log("[MakeCubeMapHDRI] SAVED: {} (six {} x {} HDR faces).".format(texture.get_path_name(), actual_size, actual_size))

    def stop_callback(self):
        if self.callback is not None:
            callback, self.callback = self.callback, None
            try:
                unreal.unregister_slate_post_tick_callback(callback)
            except Exception as error:
                unreal.log_warning("[MakeCubeMapHDRI] Could not unregister capture callback: " + str(error))

    def release_capture_resources(self):
        try:
            if unreal.SystemLibrary.is_valid(self.component):
                try:
                    self.component.set_editor_property("texture_target", None)
                    self.component.set_editor_property("always_persist_rendering_state", False)
                except Exception as error:
                    unreal.log_warning("[MakeCubeMapHDRI] Could not reset capture component: " + str(error))
        finally:
            try:
                if self.target is not None:
                    target, self.target = self.target, None
                    unreal.QuickWidgetToolsHDRILibrary.release_hdr_cube_render_target(target)
            finally:
                try:
                    if self.original_cube_single_pass is not None:
                        value, self.original_cube_single_pass = self.original_cube_single_pass, None
                        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
                        unreal.SystemLibrary.execute_console_command(world, "r.SceneCapture.CubeSinglePass " + str(value))
                except Exception as error:
                    unreal.log_warning("[MakeCubeMapHDRI] Could not restore cube capture renderer setting: " + str(error))

    def cleanup(self):
        global _job
        try:
            self.stop_callback()
            self.release_capture_resources()
        finally:
            if _job is self:
                _job = None

    def fail(self, error):
        global last_error
        last_error = str(error)
        self.cleanup()
        unreal.log_error("[MakeCubeMapHDRI] " + last_error)


def run(face_size=DEFAULT_FACE_SIZE):
    """Begin one capture. A second click while capturing leaves the job running."""
    global _job, last_result, last_error
    if _job is not None:
        unreal.log_warning("[MakeCubeMapHDRI] A capture is already running. Please wait for it to finish.")
        return False
    if not isinstance(face_size, int) or face_size < 16 or face_size > 8192 or face_size & (face_size - 1):
        raise ValueError("HDRI face size must be a power of two from 16 to 8192.")
    if not hasattr(unreal, "QuickWidgetToolsHDRILibrary"):
        raise RuntimeError("Restart Unreal to load the updated Quick Widget Tools HDRI helper.")
    last_result = None
    last_error = None
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world:
        raise RuntimeError("Open a level before making an HDRI.")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = _capture_actor(actors, editor)
    _job = _CaptureJob(actor, world, face_size)
    try:
        _job.start()
    except Exception as error:
        _job.fail(error)
        raise
    return True


def cancel():
    """Release an unfinished capture's GPU resources without saving a texture."""
    if _job is not None:
        if _job.phase == "saving":
            unreal.log_warning("[MakeCubeMapHDRI] The texture is being saved; wait for the save to finish.")
            return False
        _job.cleanup()
    return True

