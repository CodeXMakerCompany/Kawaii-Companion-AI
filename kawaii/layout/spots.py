"""Where things float around her (window coords): her head, the agent app icons, the
other app icons, the GitHub badge. They follow her outline and step aside for an open card."""

from kawaii.render.painter import NOTES_H, PANEL_W

STACK = ("monitor_toggle", "monitor_panel", "focus_toggle", "focus_open", "focus_panel", "clocks")  # top right
ICON_R = 30  # an icon's reach from its centre, frame and bob included
CLEAR_OF_BUTTONS = PANEL_W + 26  # icons never cover the side buttons (they float at the left edge on portrait screens)


class Spots:
    def __init__(self, layout, overlay, win):
        self.layout, self.overlay, self.win = layout, overlay, win

    def head(self):
        """Top centre of her, for effects on her."""
        box, (mw, _) = self.layout.body_box, self.layout.size
        x = self.layout.left + ((box[0] + box[1]) / 2 if box else mw / 2)
        return x, self.overlay.head_y if self.overlay.head_y is not None else NOTES_H + 16

    def agent(self, side):
        """An agent app's icon: up and to one side of her head (beside it instead, under the
        card, when a card fills the space above)."""
        x, y = self.head()
        x = max(self.layout.left + 34, CLEAR_OF_BUTTONS, min(x + side * 118, self.win.width - 34))
        if self.overlay.card_top is not None:
            y = max(y + 30, self.overlay.card_bottom + 40)
        else:
            y = max(70, y - 40)
        return x, min(self.win.height - 40, self._below_stack(x, y))

    def _below_stack(self, x, y):
        """y moved under the top-right stack (system pill, Focus, clocks) when the icon would
        cover it."""
        rects = [r for r in (self.overlay.rect_of(kind) for kind in STACK) if r]
        if not rects or x + ICON_R <= min(r[0] for r in rects):
            return y
        bottom = max(r[3] for r in rects)
        return max(y, bottom + ICON_R + 6) if y - ICON_R < bottom else y

    def app(self, index):
        """The other open apps' icons (Warp, the browsers...): in pairs under the agents' icons,
        right then left, stacking down; index counts the open ones."""
        side = 1 if index % 2 == 0 else -1
        x, y = self.agent(side)
        return x, min(self.win.height - 40, y + 54 * (index // 2 + 1))

    def github(self):
        """The GitHub badge: above her head (beside it, under Claude's icon, when a card is open)."""
        x, y = self.head()
        if self.overlay.card_top is not None:
            return max(self.layout.left + 34, x - 118), min(self.win.height - 40, self.agent(-1)[1] + 66)
        return x, max(70, y - 78)
