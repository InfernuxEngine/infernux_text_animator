"""Typed playback events backed by the native text layout."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol

from infernux.lib import TextCharacterInfo
from infernux.ui.ui_event import UIEvent1


class TimeScale(Enum):
    SCALED = 0
    UNSCALED = 1


class AnimationLoop(Enum):
    UPDATE = 0
    LATE_UPDATE = 1
    SCRIPT = 2


class WaitMode(Enum):
    APPEARANCE = 0
    DISAPPEARANCE = 1


class WaitInputMode(Enum):
    ANY_INPUT = 0
    SPECIFIC_ACTION = 1


class ActionStatus(Enum):
    RUNNING = "running"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class CharacterInfo:
    character: str
    native: TextCharacterInfo


class _VisibilityState:
    __slots__ = ("count", "first", "limit", "overrides")

    def __init__(self):
        self.count, self.first, self.limit = 0, 0, -1
        self.overrides = None

    def __call__(self, index):
        if index < self.first or self.limit >= 0 and index >= self.limit:
            return False
        if self.overrides is not None and self.overrides[index] != -1:
            return bool(self.overrides[index])
        return index < self.count


@dataclass(frozen=True, slots=True)
class CharacterData:
    index: int
    info: CharacterInfo
    _visibility: Callable[[int], bool] = field(default=lambda _: False, repr=False, compare=False)

    @property
    def is_visible(self) -> bool:
        return self._visibility(self.index)


@dataclass(frozen=True, slots=True)
class EventMarker:
    name: str
    parameters: list[str]

    def __post_init__(self):
        if not isinstance(self.name, str) or not isinstance(self.parameters, list) or not all(isinstance(value, str) for value in self.parameters):
            raise TypeError("Event markers require a string name and a list of strings")


@dataclass(frozen=True, slots=True)
class ActionMarker:
    name: str
    parameters: list[str]

    def __post_init__(self):
        if not isinstance(self.name, str) or not isinstance(self.parameters, list) or not all(isinstance(value, str) for value in self.parameters):
            raise TypeError("Action markers require a string name and a list of strings")


@dataclass(slots=True)
class TypingInfo:
    typewriter: object
    time_passed: float
    speed: float


class ActionState(Protocol):
    def progress(self, delta_time: float, typing_info: TypingInfo) -> ActionStatus: ...
    def cancel(self) -> None: ...


class TypewriterAction(Protocol):
    def create_action_from(self, marker: ActionMarker, typewriter: object) -> ActionState: ...


@dataclass(frozen=True, slots=True)
class TextRegion:
    start: int
    end: int
    effect: object


@dataclass(frozen=True, slots=True)
class TextStyle:
    opening: str
    closing: str = ""

    def __post_init__(self):
        if not isinstance(self.opening, str) or not isinstance(self.closing, str):
            raise TypeError("Style definitions must be strings")


class CharacterEvent(UIEvent1):
    __slots__ = ()

    def add_listener(self, callback: Callable[[CharacterData], None]) -> None:
        self._registry.add_listener(callback)

    def remove_listener(self, callback: Callable[[CharacterData], None]) -> None:
        self._registry.remove_listener(callback)

    def invoke(self, character: CharacterData) -> None:
        self._registry.invoke(character, propagate_exceptions=True)


class MessageEvent(UIEvent1):
    __slots__ = ()

    def add_listener(self, callback: Callable[[EventMarker], None]) -> None:
        self._registry.add_listener(callback)

    def remove_listener(self, callback: Callable[[EventMarker], None]) -> None:
        self._registry.remove_listener(callback)

    def invoke(self, marker: EventMarker) -> None:
        self._registry.invoke(marker, propagate_exceptions=True)


class CharacterWaitEvent(UIEvent1):
    __slots__ = ()
    def add_listener(self, callback: Callable[[CharacterData, WaitMode], None]) -> None:
        self._registry.add_listener(callback)

    def remove_listener(self, callback: Callable[[CharacterData, WaitMode], None]) -> None:
        self._registry.remove_listener(callback)

    def invoke(self, character: CharacterData, wait_mode: WaitMode) -> None:
        self._registry.invoke(character, wait_mode, propagate_exceptions=True)
