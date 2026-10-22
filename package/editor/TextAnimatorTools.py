from infernux import editor
from infernux.editor import EditorPanel, PanelInteractionDescriptor, editor_panel, translate
from infernux.engine.interaction import SelectionService
from infernux.lib import SceneManager
from infernux.lifecycle import InxPreload


_context = None


class TextAnimatorTools(InxPreload):
    def preload(self, context):
        global _context
        _context = context


@editor_panel("Text Animator", type_id="infernux.text_animator.tools", title_key="text_animator.panel",
              menu_path="Animation", interaction=PanelInteractionDescriptor())
class TextAnimatorPanel(EditorPanel):
    def __init__(self):
        super().__init__(translate("text_animator.panel"))
        self._component = None
        self._scope = None

    def on_enable(self):
        SelectionService.instance().add_listener(self._selection_changed)
        self.services.play_mode_manager.add_state_change_listener(self._selection_changed)
        self._bind_selection()

    def on_disable(self):
        SelectionService.instance().remove_listener(self._selection_changed)
        self.services.play_mode_manager.remove_state_change_listener(self._selection_changed)
        self._stop()

    def _selection_changed(self, _change):
        self._stop()
        self._bind_selection()

    def _bind_selection(self):
        identifier = SelectionService.instance().primary_scene_object_id()
        obj = SceneManager.instance().find_runtime_object_by_id(identifier) if identifier else None
        self._component = obj.get_component("TextAnimator") if obj is not None else None

    def _stop(self):
        if self._scope is not None:
            self._scope.close()
            self._scope = None

    def _start(self):
        self._stop()
        scope = _context.create_preview()
        try:
            self._component.BeginPreview(scope)
        except BaseException:
            scope.close()
            raise
        self._scope = scope

    def on_render_content(self, ctx):
        if self._component is not None and not self._component.is_valid:
            self._bind_selection()
        if self._component is None:
            ctx.label(translate("text_animator.select_hint"))
            return
        ctx.label(self._component.game_object.name)
        if self.services.play_mode_manager.is_playing:
            ctx.label(translate("text_animator.edit_hint"))
            return
        if ctx.button(translate("text_animator.preview")):
            editor.defer(self._start, description=translate("text_animator.preview"))
        ctx.same_line()
        if ctx.button(translate("text_animator.stop_restore")):
            editor.defer(self._stop, description=translate("text_animator.stop_restore"))
        if self._scope is not None and not self._scope.closed:
            if ctx.button(translate("text_animator.pause")):
                self._component.Pause()
            ctx.same_line()
            if ctx.button(translate("text_animator.play")):
                self._component.Play()
