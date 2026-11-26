"""Build a lightweight copy of a VTube Studio Live2D model for the overlay viewer.

- Downscales the texture atlas (8192px -> 2048px by default: ~16x less VRAM).
- Rewrites model3.json so the Cubism framework knows about things VTube Studio
  normally wires up itself: idle motion, expressions, eye blink and lip sync.
- Never touches the source folder.

Usage: python -I tools/build_model.py <source_model_dir> [--out model] [--tex 2048]
"""

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "model")
    ap.add_argument("--tex", type=int, default=2048, help="max texture edge in px")
    args = ap.parse_args()

    src = args.source.resolve()
    out = args.out.resolve()
    model_json = next(src.glob("*.model3.json"))
    vtube_json = next(src.glob("*.vtube.json"), None)
    settings = load_json(model_json)
    vtube = load_json(vtube_json) if vtube_json else {}
    refs = settings["FileReferences"]

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # Plain copies under ASCII names so paths never depend on locale.
    shutil.copy2(src / refs["Moc"], out / "model.moc3")
    refs["Moc"] = "model.moc3"
    for key, name in (("Physics", "model.physics3.json"), ("DisplayInfo", "model.cdi3.json")):
        if key in refs:
            shutil.copy2(src / refs[key], out / name)
            refs[key] = name

    # Textures: resize with Lanczos, keep premultiplication-friendly RGBA PNG.
    textures = []
    for i, rel in enumerate(refs["Textures"]):
        img = Image.open(src / rel).convert("RGBA")
        if max(img.size) > args.tex:
            img = img.resize((args.tex, args.tex * img.height // img.width), Image.LANCZOS)
        name = f"texture_{i:02d}.png"
        img.save(out / name, optimize=True)
        textures.append(name)
        print(f"texture {rel} -> {name} {img.size[0]}x{img.size[1]}")
    refs["Textures"] = textures

    # Expressions: VTube Studio loads these from hotkeys, Cubism needs them listed.
    exp_dir = out / "expressions"
    exp_dir.mkdir()
    expressions = []
    for f in sorted(src.glob("*.exp3.json"), key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0)):
        shutil.copy2(f, exp_dir / f.name)
        expressions.append({"Name": f.name.removesuffix(".exp3.json"), "File": f"expressions/{f.name}"})
    if expressions:
        refs["Expressions"] = expressions

    # Idle motion from the VTube Studio config.
    idle = vtube.get("FileReferences", {}).get("IdleAnimation")
    if idle and (src / idle).exists():
        (out / "motions").mkdir()
        shutil.copy2(src / idle, out / "motions" / "idle.motion3.json")
        refs["Motions"] = {"Idle": [{"File": "motions/idle.motion3.json"}]}

    # Eye blink / lip sync parameters, taken from VTube Studio's tracking map.
    mapped = {p.get("Input"): p.get("OutputLive2D") for p in vtube.get("ParameterSettings", [])}
    blink = [mapped[k] for k in ("EyeOpenLeft", "EyeOpenRight") if mapped.get(k)]
    lips = [mapped[k] for k in ("MouthOpen",) if mapped.get(k)]
    groups = {g["Name"]: g for g in settings.get("Groups", [])}
    groups.setdefault("EyeBlink", {"Target": "Parameter", "Name": "EyeBlink", "Ids": []})["Ids"] = blink
    groups.setdefault("LipSync", {"Target": "Parameter", "Name": "LipSync", "Ids": []})["Ids"] = lips
    settings["Groups"] = list(groups.values())

    # Cubism's JSON parser wants indented JSON.
    (out / "model.model3.json").write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    # Hotkeys for the viewer, same keys as in VTube Studio.
    hotkeys = {}
    for h in vtube.get("Hotkeys", []):
        if h.get("Action") == "ToggleExpression" and h.get("File"):
            key = h.get("Triggers", {}).get("Trigger1")
            if key:
                hotkeys[key] = h["File"].removesuffix(".exp3.json")
    (out / "hotkeys.json").write_text(json.dumps(hotkeys, indent=2), encoding="utf-8")

    print(f"blink={blink} lipsync={lips} expressions={len(expressions)} hotkeys={len(hotkeys)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
