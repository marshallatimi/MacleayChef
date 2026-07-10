"""
generate_icon.py - creates icon.ico from the MacleayChef logo (icon.png).
Run manually or automatically by CI before PyInstaller:
  python generate_icon.py

Loads icon.png (transparent background) and emits a multi-resolution icon.ico
that preserves the alpha channel, for the exe, installer, and shortcuts.
"""
import os, sys


def generate(dest="icon.ico", src="icon.png"):
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed - skipping icon generation.")
        return False

    here     = os.path.dirname(os.path.abspath(__file__))
    src_path = src if os.path.isabs(src) else os.path.join(here, src)
    if not os.path.isfile(src_path):
        print(f"Source logo not found: {src_path}")
        return False

    master = Image.open(src_path).convert("RGBA")

    sizes  = [16, 24, 32, 48, 64, 128, 256]
    frames = [master.resize((sz, sz), Image.LANCZOS) for sz in sizes]

    out = os.path.abspath(dest)
    frames[0].save(
        out,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f"Icon saved -> {out}")
    return True


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "icon.ico"
    ok = generate(dest)
    sys.exit(0 if ok else 1)
