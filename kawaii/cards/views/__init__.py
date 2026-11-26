"""Each card's drawing, by card name. A view is a module with draw(painter, d, payload),
painting with the primitives of kawaii.render.painter, and FOOTER, the Esc hint while open."""

from kawaii.cards.views import calendar, decoder, observe, pendings, picker, prs, rules, settings

VIEWS = {"pendings": pendings, "calendar": calendar, "prs": prs, "decoder": decoder, "picker": picker,
         "settings": settings, "observe": observe, "rules": rules}
