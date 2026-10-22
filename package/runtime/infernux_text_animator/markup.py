"""Compile animation tags once while retaining native color and size markup."""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from math import isfinite
import re
import shlex

from .effects import Effect, EffectKind


_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9_]*)([^<>]*)>")
_PARAMETERS = {"amplitude": float, "speed": float, "phase": float,
               "phase_offset": float, "seed": int,
               "color": lambda value: tuple(float(item) for item in value.split(","))}


@dataclass(frozen=True)
class Cue:
    character: int
    kind: str
    value: str | float


@dataclass(frozen=True)
class ParsedText:
    source: str
    text: str
    ranges: tuple
    cues: tuple

    def bind(self, layout):
        starts = [character.source_start for character in layout.characters]
        ends = [character.source_end for character in layout.characters]
        effects = [replace(effect, start=bisect_right(ends, first), end=bisect_left(starts, last))
                   for first, last, effect in self.ranges if first != last]
        cues = [Cue(bisect_left(starts, offset), kind, value) for offset, kind, value in self.cues]
        return effects, cues


def parse_markup(source, presets=None):
    if {"color", "size", "br"}.intersection(presets or {}):
        raise ValueError("Native text tags cannot be used as effect preset names")
    definitions = {kind.value: Effect(kind) for kind in EffectKind}
    definitions.update(presets or {})
    output, stack, ranges, cues = [], [], [], []
    offset = cursor = 0
    for match in _TAG.finditer(source):
        literal = source[cursor:match.start()]
        output.append(literal)
        offset += len(literal.encode("utf-8"))
        closing, name, arguments = match.groups()
        if name in definitions:
            if closing:
                if not stack or stack[-1][0] != name:
                    raise ValueError(f"Unbalanced text effect: {name}")
                _, first, effect = stack.pop()
                ranges.append((first, offset, effect))
            else:
                values = {}
                for argument in shlex.split(arguments):
                    key, separator, value = argument.partition("=")
                    if not separator or key not in _PARAMETERS:
                        raise ValueError(f"Unknown {name} parameter: {argument}")
                    values[key] = _PARAMETERS[key](value)
                stack.append((name, offset, replace(definitions[name], **values)))
        elif not closing and name in ("event", "wait"):
            value = arguments.strip().removesuffix("/").strip().removeprefix("=").strip().strip("\"'")
            if not value:
                raise ValueError(f"Text {name} requires a value")
            if name == "wait":
                value = float(value)
                if not isfinite(value) or value < 0:
                    raise ValueError("Text wait must be finite and nonnegative")
            cues.append((offset, name, value))
        else:
            literal = match.group()
            output.append(literal)
            offset += len(literal.encode("utf-8"))
        cursor = match.end()
    output.append(source[cursor:])
    if stack:
        raise ValueError(f"Unclosed text effect: {stack[-1][0]}")
    return ParsedText(source, "".join(output), tuple(ranges), tuple(cues))
