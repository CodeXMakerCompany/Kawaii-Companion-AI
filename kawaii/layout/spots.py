"""Where things float around her (window coords): her head, the agent app icons, the
GitHub badge. They follow her outline and step aside for an open card."""

from kawaii.render.painter import NOTES_H


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
        x = max(self.layout.left + 34, min(x + side * 118, self.win.width - 34))
        if self.overlay.card_top is not None:
            return x, min(self.win.height - 40, max(y + 30, self.overlay.card_bottom + 40))
        return x, max(70, y - 40)

    def github(self):
        """The GitHub badge: above her head (beside it, under Claude's icon, when a card is open)."""
        x, y = self.head()
        if self.overlay.card_top is not None:
            return max(self.layout.left + 34, x - 118), min(self.win.height - 40, self.agent(-1)[1] + 66)
        return x, max(70, y - 78)
