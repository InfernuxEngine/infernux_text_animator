from infernux.lifecycle import InxPreload


class TextAnimatorPreload(InxPreload):
    def preload(self, context):
        from infernux.ui import UIText

        if not hasattr(UIText, "create_character_buffer"):
            raise RuntimeError("Text Animator requires the Infernux 0.4.3 build 2 hotfix or later")
        context.own_python_library("runtime/infernux_text_animator")
        from infernux.timing import Time
        from infernux_text_animator.playback import scheduler

        def tick(delta):
            scheduler.Update(delta, Time.unscaled_delta_time)

        registration = context.add_update(tick, enabled=False)
        scheduler.on_activity = lambda enabled: setattr(registration, "enabled", enabled)

        def cleanup():
            scheduler.Clear()
            scheduler.on_activity = None

        context.add_cleanup(cleanup)
