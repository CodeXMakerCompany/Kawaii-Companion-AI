"""Outfits per client. Every client has a folder in assets/ named after it
(assets/assistance_connect/ for "Assistance Connect"). A shirt.png there is what she wears
while you work for that client:

  - its sleeves are cut off (the body of the shirt is what fits her),
  - it is painted onto her torso in a copy of the model's texture, trimmed to her outline so
    it hugs her shape; where it is open (the neckline) her old top turns to skin,
  - her jacket comes off (the model's jacket switch), and the old top's sleeve and the tie
    are erased from the texture, so the shirt shows whole (her collar and choker stay).

An outfit.json next to it can keep any of those: {"jacket": true, "tie": true, "sleeve": true}.
The dressed texture and a model3.json pointing at it are written next to the model once, and
rebuilt only when the shirt or outfit.json changes.
"""

import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

from kawaii.features.clients import slug
from kawaii.paths import ASSETS

VERSION = 3  # bump to rebuild every dressed texture
SKIN = (246, 234, 230)  # her skin, sampled from the belly
JACKET_PARAM = "Param53"  # 外套: 1 takes the jacket (and its big sleeves) off
# Where things are in the model's 2048 px texture (texture_00.png from tools/build_model.py).
GEOMETRY = dict(torso=(1005, 372, 1188, 686),  # her torso piece: the top and the belly, one drawing
                torso_seed=(1100, 520),  # a pixel inside it
                sleeve_seed=(195, 1933),  # a pixel inside the old top's sleeve (her left arm)
                tie_seeds=((1897, 1763),  # the tie (its model part also holds her collar: that stays)
                           (1927, 1492)))  # the tie's grey shadow, drawn over her chest


def folder_name(client):
    return slug(client).replace("-", "_")


def client_folder(client, assets=ASSETS):
    return Path(assets) / folder_name(client)


def ensure_folder(client, assets=ASSETS):
    path = client_folder(client, assets)
    path.mkdir(parents=True, exist_ok=True)
    return path


class Outfit:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.shirt = self.folder / "shirt.png"
        try:
            config = json.loads((self.folder / "outfit.json").read_text())
        except (OSError, ValueError):
            config = {}
        self.config = config if isinstance(config, dict) else {}
        self.active = self.shirt.exists()
        self.jacket = bool(self.config.get("jacket", not self.active))
        self.tie = bool(self.config.get("tie", not self.active))
        self.sleeve = bool(self.config.get("sleeve", not self.active))


def island(alpha, seed):
    """The drawing a pixel belongs to: every non-transparent pixel connected to it."""
    h, w = alpha.shape
    mask = np.zeros((h, w), bool)
    x, y = seed
    if not alpha[y, x]:
        return mask
    mask[y, x] = True
    queue = deque([(y, x)])
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and alpha[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                queue.append((ny, nx))
    return mask


def sleeveless(shirt):
    """The shirt's body: cropped to the width of its lower half, which the sleeves never reach."""
    a = np.asarray(shirt.convert("RGBA"))[..., 3] > 20
    rows = np.flatnonzero(a.any(axis=1))
    top, bottom = rows[0], rows[-1] + 1
    edges = [np.flatnonzero(a[y]) for y in range(int(top + (bottom - top) * 0.55), bottom)]
    edges = [e for e in edges if e.size]
    left = int(np.median([e[0] for e in edges]))
    right = int(np.median([e[-1] for e in edges])) + 1
    return shirt.crop((left, top, right, bottom))


def dress(texture, shirt, torso, torso_seed, sleeve_seed, tie_seeds, keep_sleeve=False, keep_tie=False):
    """A copy of the texture with `shirt` painted over her torso: scaled to its width, collar at
    the top, trimmed to her outline; her old top turns to skin where the shirt is open."""
    arr = np.asarray(texture.convert("RGBA")).copy()
    alpha = arr[..., 3] > 0
    body = island(alpha, torso_seed)
    r, b = arr[..., 0].astype(int), arr[..., 2].astype(int)
    arr[body & (b > r + 12), :3] = SKIN  # the old top (it is the blue in her torso piece)
    x0, y0, x1, y1 = torso
    w, h = x1 - x0, y1 - y0
    fitted = np.zeros((h, w, 4), np.float32)
    scaled = np.asarray(shirt.convert("RGBA").resize((w, max(1, round(shirt.height * w / shirt.width))),
                                                     Image.LANCZOS)).astype(np.float32)
    rows = min(h, scaled.shape[0])
    fitted[:rows] = scaled[:rows]  # longer than her torso: the hem tucks into her shorts
    region = arr[y0:y1, x0:x1].astype(np.float32)
    k = fitted[..., 3:4] / 255 * body[y0:y1, x0:x1, None]
    region[..., :3] = fitted[..., :3] * k + region[..., :3] * (1 - k)
    arr[y0:y1, x0:x1] = region.round().clip(0, 255).astype(np.uint8)
    gone = ([] if keep_sleeve else [sleeve_seed]) + ([] if keep_tie else list(tie_seeds))
    for seed in gone:
        arr[island(alpha, seed)] = 0
    return Image.fromarray(arr)


def build(model_json, outfit):
    """The model3.json of `model_json` wearing `outfit` (written next to it, cached)."""
    model_json = Path(model_json)
    model_dir = model_json.parent
    settings = json.loads(model_json.read_text(encoding="utf-8"))
    textures = settings["FileReferences"]["Textures"]
    name = outfit.folder.name
    out_dir = model_dir / "outfits" / name
    texture = out_dir / "texture_00.png"
    variant = model_dir / f"model.{name}.model3.json"
    key = hashlib.sha1(b"%d" % VERSION + outfit.shirt.read_bytes() + json.dumps(outfit.config, sort_keys=True).encode()
                       + json.dumps(GEOMETRY, sort_keys=True).encode()).hexdigest()
    stamp = out_dir / "built"
    if texture.exists() and variant.exists() and stamp.exists() and stamp.read_text() == key:
        return variant
    out_dir.mkdir(parents=True, exist_ok=True)
    shirt = sleeveless(Image.open(outfit.shirt))
    dress(Image.open(model_dir / textures[0]), shirt, keep_sleeve=outfit.sleeve, keep_tie=outfit.tie,
          **GEOMETRY).save(texture)
    settings["FileReferences"]["Textures"] = [texture.relative_to(model_dir).as_posix()] + textures[1:]
    variant.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    stamp.write_text(key)
    return variant
