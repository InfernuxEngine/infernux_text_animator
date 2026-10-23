from infernux.lifecycle import InxPreload


class TextAnimatorPreload(InxPreload):
    def preload(self, context):
        from infernux.lib import TextCharacterBuffer

        if not hasattr(TextCharacterBuffer, "color_overrides"):
            raise RuntimeError("Text Animator requires Infernux 0.4.3 hotfix 4 or later")
        context.own_python_library("runtime/infernux_text_animator")
        from infernux.timing import Time
        from infernux_text_animator.playback import scheduler, late_scheduler

        def tick(delta):
            scheduler.update(delta, Time.unscaled_delta_time)

        registration = context.add_update(tick, enabled=False)
        scheduler.on_activity = lambda enabled: setattr(registration, "enabled", enabled)
        def late_tick(delta):
            late_scheduler.update(delta, Time.unscaled_delta_time)

        late_registration = context.add_update(late_tick, phase="late_update", enabled=False)
        late_scheduler.on_activity = lambda enabled: setattr(late_registration, "enabled", enabled)

        def cleanup():
            scheduler.clear()
            late_scheduler.clear()
            scheduler.on_activity = None
            late_scheduler.on_activity = None

        context.add_cleanup(cleanup)
