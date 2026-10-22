from infernux.lifecycle import InxPreload


class TextAnimatorPreload(InxPreload):
    def preload(self, context):
        from infernux.ui import UIText

        if not hasattr(UIText, "create_character_buffer"):
            raise RuntimeError("Text Animator requires the Infernux 0.4.3 build 2 hotfix or later")
        context.own_python_library("runtime/infernux_text_animator")
        import infernux_text_animator
