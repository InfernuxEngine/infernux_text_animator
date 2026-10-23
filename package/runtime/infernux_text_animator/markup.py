"""Compile effect categories and typing actions without replacing native markup."""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from math import isfinite
from collections.abc import Mapping
import re
import shlex

from .effects import CustomEffect, Effect, EffectKind
from .appearance import AppearanceKind, AppearanceTag
from .events import ActionMarker, EventMarker, TextStyle, TypewriterAction


_TOKEN = re.compile(r"<([^<>]*)>|\{([^{}]*)\}")
_HEAD = re.compile(r"([/?]?)(#?)([^\s/=,?]*)(.*)", re.DOTALL)
_MODIFIER = re.compile(r"([^=*]+)([=*])(.+)")
_PARAMETERS = {"a": ("amplitude", float), "s": ("speed", float),
               "amplitude": ("amplitude", float), "speed": ("speed", float),
               "phase": ("phase", float), "phase_offset": ("phase_offset", float), "seed": ("seed", int),
               "color": ("color", lambda value: tuple(float(item) for item in value.split(",")))}


@dataclass(frozen=True)
class Cue:
    character: int
    kind: str
    value: ActionMarker | EventMarker | float | str


@dataclass(frozen=True)
class ParsedText:
    source: str
    text: str
    ranges: tuple
    cues: tuple
    appearance_ranges: tuple = ()

    def bind(self, layout):
        starts = [character.source_start for character in layout.characters]
        ends = [character.source_end for character in layout.characters]
        effects = [replace(effect, start=bisect_right(ends, first), end=bisect_left(starts, last))
                   for first, last, effect in self.ranges if first != last]
        cues = [Cue(bisect_left(starts, offset), kind, value) for offset, kind, value in self.cues]
        return effects, cues

    def bind_appearance_tags(self, layout):
        starts = [character.source_start for character in layout.characters]
        ends = [character.source_end for character in layout.characters]
        phases = ([], [])
        for disappearing, first, last, tag in self.appearance_ranges:
            if first != last:
                phases[disappearing].append(replace(tag, start=bisect_right(ends, first), end=bisect_left(starts, last)))
        return phases


def _expand_styles(source, styles):
    definitions = {name.lower(): value for name, value in styles.items()}
    raw = False

    def expand(text, chain):
        nonlocal raw
        output, cursor = [], 0
        for match in _TOKEN.finditer(text):
            output.append(text[cursor:match.start()])
            angle = match[1]
            key = angle.strip().lstrip('/').lower() if angle is not None else ''
            if raw:
                output.append(match.group())
                if angle == '/noparse':
                    raw = False
            elif angle == 'noparse':
                raw = True
                output.append(match.group())
            elif key in definitions:
                if key in chain:
                    raise ValueError("Recursive text style: "+' -> '.join((*chain, key)))
                style = definitions[key]
                output.append(expand(style.closing if angle.strip().startswith('/') else style.opening, (*chain, key)))
            else:
                output.append(match.group())
            cursor = match.end()
        output.append(text[cursor:])
        return ''.join(output)

    return expand(source, ())


def parse_markup(source: str, presets: Mapping[str, Effect | CustomEffect | AppearanceTag] | None = None, *,
                 actions: Mapping[str, TypewriterAction] | None = None, style_sheet: Mapping[str, TextStyle] | None = None) -> ParsedText:
    if {"color", "size", "br", "noparse"}.intersection(presets or {}):
        raise ValueError("Native text tags cannot be used as effect preset names")
    definitions = {kind.value: Effect(kind) for kind in EffectKind}
    definitions.update({kind.value: AppearanceTag(kind) for kind in AppearanceKind})
    definitions.update(presets or {})
    action_names = {name.lower(): name for name in actions or ()}
    original_source = source
    if style_sheet:
        source = _expand_styles(source, style_sheet)
    output, ranges, cues, appearance_ranges = [], [], [], []
    stacks = {"persistent": [], "appearance": [], "disappearance": []}
    offset = cursor = 0
    raw = False

    def literal(value):
        nonlocal offset
        output.append(value)
        offset += len(value.encode("utf-8"))

    def close(category):
        name, first, effect = stacks[category].pop()
        if category == "persistent":
            ranges.append((first, offset, effect))
        else:
            appearance_ranges.append((category == "disappearance", first, offset, effect))

    for match in _TOKEN.finditer(source):
        literal(source[cursor:match.start()])
        angle, brace = match.groups()
        body = angle if angle is not None else brace
        if raw:
            literal(match.group())
            if angle == "/noparse":
                raw = False
        elif angle == "noparse":
            raw = True
            literal(match.group())
        else:
            closing, hiding, name, arguments = _HEAD.fullmatch(body).groups()
            category = "persistent" if angle is not None else "disappearance" if hiding else "appearance"
            definitions_for_category = definitions
            stack = stacks[category]
            if angle is not None and closing == "?":
                arguments = arguments.strip()
                if arguments and not arguments.startswith("="):
                    raise ValueError("Event parameters must follow '='")
                cues.append((offset, "event", EventMarker(name, arguments[1:].split(",") if arguments else [])))
            elif closing == "/" and not name and not arguments.strip():
                while stack:
                    close(category)
            elif name in definitions_for_category:
                if closing:
                    if not stack or stack[-1][0] != name:
                        raise ValueError(f"Unbalanced text effect: {name}")
                    close(category)
                else:
                    values = {}
                    for argument in shlex.split(arguments):
                        if argument == "once":
                            values["once"] = True
                            continue
                        modifier = _MODIFIER.fullmatch(argument)
                        if modifier is None or modifier[1] not in _PARAMETERS:
                            raise ValueError(f"Unknown {name} parameter: {argument}")
                        key, operation, value = modifier.groups()
                        field, parser = _PARAMETERS[key]
                        if not hasattr(definitions_for_category[name], field):
                            raise ValueError(f"Unknown {name} modifier: {key}")
                        value = parser(value)
                        if operation == "*":
                            if not isinstance(value, (int, float)):
                                raise ValueError("Only numeric effect modifiers can be multiplied")
                            value *= getattr(definitions_for_category[name], field)
                        values[field] = value
                    stack.append((name, offset, replace(definitions_for_category[name], **values)))
            elif angle is not None and not closing and name.lower() in ("waitfor", "speed", "waitinput"):
                value = arguments.strip().removesuffix("/").strip().removeprefix("=").strip().strip("\"'")
                action = name.lower()
                if action == "waitinput":
                    if "," in value:
                        raise ValueError("waitinput accepts one action key")
                    cues.append((offset, "input", value))
                else:
                    if not value:
                        raise ValueError(f"Text {action} requires a value")
                    value = float(value)
                    if not isfinite(value) or value < (0.001 if action == "speed" else 0):
                        raise ValueError(f"Invalid {action} value")
                    cues.append((offset, "speed" if action == "speed" else "wait", value))
            elif angle is not None and not closing and name.lower() in action_names:
                arguments = arguments.strip().removesuffix('/').strip()
                if arguments and not arguments.startswith('='):
                    raise ValueError("Action parameters must follow '='")
                cues.append((offset, "action", ActionMarker(action_names[name.lower()], arguments[1:].split(',') if arguments else [])))
            else:
                literal(match.group())
        cursor = match.end()
    literal(source[cursor:])
    for category, stack in stacks.items():
        while stack:
            close(category)
    return ParsedText(original_source, "".join(output), tuple(ranges), tuple(cues), tuple(appearance_ranges))
