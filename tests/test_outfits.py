"""Outfits per client: assets/<client>/shirt.png is fitted onto her torso (sleeves cut off),
her jacket, its sleeve and the tie come off, and a variant of the model wears it."""

import json

import numpy as np
from PIL import Image

from kawaii import outfits
from kawaii.outfits import Outfit, build, client_folder, dress, ensure_folder, folder_name, sleeveless

FABRIC, SKIN_TONE = (40, 60, 200, 255), (240, 220, 210, 255)


def test_folders_are_named_like_the_one_you_made():
    assert folder_name("Assistance Connect") == "assistance_connect"
    assert folder_name("Café Ñandú S.A.") == "cafe_nandu_s_a"


def test_every_client_gets_a_folder(tmp_path):
    path = ensure_folder("Acme Corp", assets=tmp_path)
    assert path == tmp_path / "acme_corp" and path.is_dir()
    assert client_folder("Acme Corp", assets=tmp_path) == path


def test_no_shirt_no_outfit(tmp_path):
    assert not Outfit(tmp_path).active


def test_a_shirt_takes_off_the_jacket_and_the_tie(tmp_path):
    Image.new("RGBA", (10, 10)).save(tmp_path / "shirt.png")
    outfit = Outfit(tmp_path)
    assert outfit.active and not outfit.jacket and not outfit.tie and not outfit.sleeve


def test_outfit_json_can_keep_them(tmp_path):
    Image.new("RGBA", (10, 10)).save(tmp_path / "shirt.png")
    (tmp_path / "outfit.json").write_text(json.dumps({"tie": True}))
    assert Outfit(tmp_path).tie and not Outfit(tmp_path).jacket


def tshirt():
    """A t-shirt: a 40 px wide body, sleeves sticking out 20 px each side near the top."""
    img = Image.new("RGBA", (100, 120), (0, 0, 0, 0))
    a = np.asarray(img).copy()
    a[10:110, 30:70] = (255, 255, 255, 255)  # body
    a[10:40, 10:90] = (255, 255, 255, 255)  # sleeves
    return Image.fromarray(a)


def test_sleeveless_cuts_the_sleeves_off():
    body = sleeveless(tshirt())
    assert body.size == (40, 100)
    assert np.asarray(body)[..., 3].all()


def texture():
    """A 64 px texture: a torso piece (fabric on top, skin below) and a separate sleeve piece."""
    a = np.zeros((64, 64, 4), np.uint8)
    a[10:40, 10:30] = FABRIC
    a[25:40, 10:30] = SKIN_TONE
    a[50:60, 40:60] = FABRIC  # the sleeve
    a[2:8, 40:44] = (255, 255, 255, 255)  # the tie
    a[2:8, 46:48] = (120, 120, 120, 255)  # its grey shadow (a separate drawing)
    a[2:8, 50:60] = (10, 10, 10, 255)  # the collar it hangs from (a separate drawing)
    return Image.fromarray(a)


GEOMETRY = dict(torso=(10, 10, 30, 40), torso_seed=(20, 20), sleeve_seed=(50, 55), tie_seeds=((41, 4), (46, 4)))


def test_dress_paints_the_shirt_inside_her_torso_only():
    shirt = Image.new("RGBA", (40, 80), (250, 100, 20, 255))
    out = np.asarray(dress(texture(), shirt, **GEOMETRY))
    assert tuple(out[20, 20]) == (250, 100, 20, 255)
    assert tuple(out[5, 5]) == (0, 0, 0, 0)  # outside: untouched
    assert out[10:40, 10:30, 3].min() == 255  # her outline is kept


def test_where_the_shirt_is_open_the_old_top_turns_to_skin():
    shirt = np.zeros((60, 20, 4), np.uint8)
    shirt[20:, :] = (250, 250, 250, 255)  # a neckline: nothing in the top third
    out = np.asarray(dress(texture(), Image.fromarray(shirt), **GEOMETRY))
    assert tuple(out[11, 20][:3]) == outfits.SKIN
    assert tuple(out[30, 20][:3]) == (250, 250, 250)


def test_the_old_sleeve_goes():
    out = np.asarray(dress(texture(), Image.new("RGBA", (20, 30), (255, 255, 255, 255)), **GEOMETRY))
    assert out[50:60, 40:60, 3].max() == 0
    kept = np.asarray(dress(texture(), Image.new("RGBA", (20, 30), (255, 255, 255, 255)), keep_sleeve=True,
                            **GEOMETRY))
    assert kept[55, 50, 3] == 255


def test_build_writes_a_model_variant_once(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    texture().save(model_dir / "texture_00.png")
    (model_dir / "model.model3.json").write_text(json.dumps({"FileReferences": {"Textures": ["texture_00.png"]}}))
    folder = tmp_path / "assistance_connect"
    folder.mkdir()
    Image.new("RGBA", (20, 30), (255, 255, 255, 255)).save(folder / "shirt.png")
    monkeypatch.setattr(outfits, "GEOMETRY", GEOMETRY)
    variant = build(model_dir / "model.model3.json", Outfit(folder))
    refs = json.loads(variant.read_text())["FileReferences"]
    assert variant.parent == model_dir and (model_dir / refs["Textures"][0]).exists()
    stamp = (model_dir / refs["Textures"][0]).stat().st_mtime_ns
    assert build(model_dir / "model.model3.json", Outfit(folder)) == variant
    assert (model_dir / refs["Textures"][0]).stat().st_mtime_ns == stamp  # cached


def test_only_the_tie_goes_her_collar_stays():
    shirt = Image.new("RGBA", (20, 30), (255, 255, 255, 255))
    out = np.asarray(dress(texture(), shirt, **GEOMETRY))
    assert out[2:8, 40:44, 3].max() == 0
    assert out[2:8, 46:48, 3].max() == 0  # and its shadow on the shirt
    assert tuple(out[4, 55]) == (10, 10, 10, 255)
    kept = np.asarray(dress(texture(), shirt, keep_tie=True, **GEOMETRY))
    assert kept[4, 41, 3] == 255
