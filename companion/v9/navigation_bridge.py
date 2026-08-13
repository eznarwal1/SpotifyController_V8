from __future__ import annotations

from dataclasses import dataclass

from v8_controller import V8Controller
from v9.view_controller import ViewController


def discover_v8_view_order(
    v8: V8Controller,
    *,
    max_views: int = 16,
) -> tuple[str, ...]:
    """Discover the existing V8 page cycle and restore the starting page."""
    original = v8.state.view
    order = [original]

    try:
        for _ in range(max_views):
            candidate = v8.next_view()

            if candidate == original:
                return tuple(order)

            if candidate in order:
                raise RuntimeError(
                    "V8 view cycle repeated before returning to its start."
                )

            order.append(candidate)

        raise RuntimeError(f"V8 view cycle exceeded {max_views} pages.")
    finally:
        for _ in range(max_views + 1):
            if v8.state.view == original:
                break
            v8.next_view()


@dataclass(slots=True)
class V8ViewNavigator:
    """Canonical page-navigation facade for the companion."""

    v8: V8Controller
    controller: ViewController

    @classmethod
    def create(cls, v8: V8Controller) -> V8ViewNavigator:
        order = discover_v8_view_order(v8)
        return cls(
            v8=v8,
            controller=ViewController(
                order=order,
                current=v8.state.view,
            ),
        )

    @property
    def current(self) -> str:
        self._adopt_external_view()
        return self.controller.current

    @property
    def order(self) -> tuple[str, ...]:
        return self.controller.order

    def next(self) -> str:
        self._adopt_external_view()
        return self._sync_to(self.controller.next())

    def previous(self) -> str:
        self._adopt_external_view()
        return self._sync_to(self.controller.previous())

    def home(self) -> str:
        self._adopt_external_view()
        return self._sync_to(self.controller.home())

    def set(self, view: str) -> str:
        self._adopt_external_view()
        return self._sync_to(self.controller.set(view))

    def _adopt_external_view(self) -> None:
        current = self.v8.state.view
        if (
            current in self.controller.order
            and current != self.controller.current
        ):
            self.controller.current = current

    def _sync_to(self, target: str) -> str:
        if self.v8.state.view == target:
            self.controller.current = target
            return target

        for _ in range(len(self.controller.order) + 1):
            candidate = self.v8.next_view()
            if candidate == target:
                self.controller.current = target
                return target

        raise RuntimeError(
            f"Unable to synchronize V8 view to {target!r}."
        )
