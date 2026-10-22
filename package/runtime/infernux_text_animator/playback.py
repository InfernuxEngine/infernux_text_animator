"""One owned engine callback for the text components currently animating."""


class PlaybackScheduler:
    def __init__(self):
        self._active = {}
        self.on_activity = None

    def add(self, controller):
        was_empty = not self._active
        self._active[controller] = None
        if was_empty and self.on_activity is not None:
            self.on_activity(True)

    def remove(self, controller):
        if controller in self._active:
            del self._active[controller]
            if not self._active and self.on_activity is not None:
                self.on_activity(False)

    def Update(self, delta, unscaled_delta):
        for controller in tuple(self._active):
            if controller in self._active:
                controller._tick(delta, unscaled_delta)

    def Clear(self):
        for controller in tuple(self._active):
            controller.on_disable()


scheduler = PlaybackScheduler()
