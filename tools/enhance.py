"""Make sliced photos crisp: Real-ESRGAN x4 upscale, blended with a plain Lanczos
upscale so skin keeps natural texture, a light unsharp mask, then a tone lock that
restores the original low-frequency colour so the slice blends with its surroundings. Writes @2x
(and @1x re-sampled from the enhanced image) JPEGs.

usage: enhance.py <in.jpg|png> <out-prefix> [--blend 0.65]
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ESRGAN = os.path.join(HERE, "esrgan", "realesrgan-ncnn-vulkan")

def enhance(src, prefix, blend=0.65):
    img = Image.open(src).convert("RGB")
    with tempfile.TemporaryDirectory() as tmp:
        up = os.path.join(tmp, "x4.png")
        subprocess.run([ESRGAN, "-i", src, "-o", up, "-n", "realesrgan-x4plus", "-m", os.path.join(HERE, "esrgan", "models")],
                       check=True, capture_output=True)
        ai = Image.open(up).convert("RGB")
    w, h = img.size
    x2 = (w * 2, h * 2)
    mixed = Image.blend(img.resize(x2, Image.LANCZOS), ai.resize(x2, Image.LANCZOS), blend)
    mixed = mixed.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    # tone lock: keep the enhanced fine detail but the original's low-frequency tone/colour,
    # so the slice still blends seamlessly with the flat colours around it
    import numpy as np
    base = img.resize(x2, Image.LANCZOS)
    blur = lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(6)), dtype=np.float32)
    fixed = np.asarray(mixed, dtype=np.float32) + blur(base) - blur(mixed)
    mixed = Image.fromarray(np.clip(fixed, 0, 255).astype(np.uint8))
    mixed.save(f"{prefix}-2x.jpg", quality=88, optimize=True, progressive=True)
    mixed.resize((w, h), Image.LANCZOS).save(f"{prefix}.jpg", quality=90, optimize=True, progressive=True)
    print(prefix, "->", x2)

if __name__ == "__main__":
    blend = float(sys.argv[sys.argv.index("--blend") + 1]) if "--blend" in sys.argv else 0.65
    enhance(sys.argv[1], sys.argv[2], blend)
