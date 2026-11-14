"""Maps procedure names (as written in knowledge/procedures/) to skill functions.

The engine never names a skill directly: it reads a procedure name from a
playbook and looks it up here.
"""

from collections.abc import Callable

_REGISTRY: dict[str, Callable] = {}


def register(name: str) -> Callable[[Callable], Callable]:
    """Decorator: register a skill under the name of its procedure YAML."""

    def wrap(fn: Callable) -> Callable:
        if name in _REGISTRY:
            raise ValueError(f"skill already registered: {name}")
        _REGISTRY[name] = fn
        return fn

    return wrap


def get(name: str) -> Callable:
    """Return the skill for a procedure name; KeyError if none is registered."""
    return _REGISTRY[name]


def names() -> list[str]:
    """All registered procedure names, sorted."""
    return sorted(_REGISTRY)
