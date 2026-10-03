"""UZ: FSM holatlari va holat guruhlari.
RU: Состояния FSM и группы состояний.
EN: FSM states and state groups.

UZ: Misol / RU: Пример / EN: Example::

    class Form(StatesGroup):
        name = State()
        age = State()

    await state.set_state(Form.name)      # "Form:name"
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

#: UZ: Istalgan (bo'sh bo'lmagan) holat. RU: Любое (непустое) состояние.
#: EN: Any non-empty state.
ANY_STATE = "*"


class State:
    """UZ: Bitta holat; `StatesGroup` ichida e'lon qilinadi.
    RU: Одно состояние; объявляется внутри `StatesGroup`.
    EN: A single state; declared inside a `StatesGroup`.
    """

    __slots__ = ("_group", "_name")

    def __init__(self, name: str | None = None) -> None:
        self._name = name
        self._group: str | None = None

    @property
    def state(self) -> str:
        name = self._name or "state"
        return f"{self._group}:{name}" if self._group else name

    @property
    def group(self) -> str | None:
        return self._group

    def __set_name__(self, owner: type, name: str) -> None:
        if self._name is None:
            self._name = name

    def _attach(self, group: str, attribute: str) -> None:
        self._group = group
        if self._name is None:
            self._name = attribute

    def __eq__(self, other: object) -> bool:
        if isinstance(other, State):
            return self.state == other.state
        if isinstance(other, str):
            return self.state == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.state)

    def __str__(self) -> str:
        return self.state

    def __repr__(self) -> str:
        return f"<State {self.state}>"


class StatesGroupMeta(type):
    """UZ: Guruhdagi holatlarga guruh nomini biriktiradi.
    RU: Присваивает состояниям группы имя группы.
    EN: Attaches the group name to the states of a group.
    """

    __states__: tuple[State, ...]

    def __new__(
        mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> StatesGroupMeta:
        cls = super().__new__(mcs, name, bases, namespace)
        states = []
        for attribute, value in namespace.items():
            if isinstance(value, State):
                value._attach(name, attribute)
                states.append(value)
        cls.__states__ = tuple(states)
        return cls

    def __iter__(cls) -> Iterator[State]:
        return iter(cls.__states__)

    def __contains__(cls, item: object) -> bool:
        return any(state == item for state in cls.__states__)


class StatesGroup(metaclass=StatesGroupMeta):
    """UZ: Holatlar guruhi. RU: Группа состояний. EN: A group of states."""

    @classmethod
    def all(cls) -> tuple[State, ...]:
        return cls.__states__


__all__ = ["ANY_STATE", "State", "StatesGroup", "StatesGroupMeta"]
