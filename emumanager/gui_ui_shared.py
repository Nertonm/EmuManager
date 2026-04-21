from __future__ import annotations

from typing import Any


class MainWindowUISharedMixin:
    """Shared widget factories to keep tab builders declarative."""

    def _make_button(
        self,
        qt: Any,
        text: str,
        *,
        attr_name: str | None = None,
        tooltip: str | None = None,
        icon_name: str | None = None,
        enabled: bool | None = None,
        minimum_height: int | None = None,
    ):
        button = qt.QPushButton(text)
        if attr_name:
            setattr(self, attr_name, button)
        if tooltip:
            button.setToolTip(tooltip)
        if icon_name:
            icon = self._get_icon(qt, icon_name)
            if icon:
                button.setIcon(icon)
        if enabled is not None:
            button.setEnabled(enabled)
        if minimum_height is not None:
            button.setMinimumHeight(minimum_height)
        return button

    def _create_action_tab(
        self,
        qt: Any,
        *,
        tab_attr: str,
        tab_title: str,
        group_title: str,
        actions: list[dict[str, str]],
    ):
        tab = qt.QWidget()
        setattr(self, tab_attr, tab)
        layout = qt.QVBoxLayout(tab)
        group = qt.QGroupBox(group_title)
        group_layout = qt.QVBoxLayout()

        for action in actions:
            button = self._make_button(
                qt,
                action["text"],
                attr_name=action["attr_name"],
                tooltip=action.get("tooltip"),
                icon_name=action.get("icon_name"),
            )
            group_layout.addWidget(button)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        self.tools_tabs.addTab(tab, tab_title)
        return tab
