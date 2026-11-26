"""Her model's expressions (poses, chibi, outfits), toggled VTube Studio style."""


class Expressions:
    def __init__(self, model):
        self.model = model
        self.active = set()

    def toggle(self, exp):
        """ToggleExpression; None clears them all. Shared by the hotkeys and the mini buttons."""
        if exp is None:
            self.model.ResetExpressions()
            self.active.clear()
        elif exp in self.active:
            self.model.RemoveExpression(exp)
            self.active.discard(exp)
        else:
            self.model.AddExpression(exp)
            self.active.add(exp)
