#!/usr/bin/env python3
"""
Generate a looping dither-effect animation from a headshot image.

Sequence: inverted dither (pause) → melt → reverse melt → (pause) → shear → reverse shear → loop

Usage:
    python3 dither-loop.py test-headshot.png
    python3 dither-loop.py test-headshot.png --width 400 --fps 15 --speed 6 --frames 60 --pause 2.0
    python3 dither-loop.py test-headshot.png --mp4   # also produce MP4 via ffmpeg
"""

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load_and_scale(path: str, max_width: int) -> np.ndarray:
    """Load image, composite onto black if alpha, convert to grayscale, scale."""
    img = Image.open(path)
    # Composite onto black background if there's an alpha channel
    if img.mode in ("RGBA", "LA", "PA"):
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    img = img.convert("L")
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, round(img.height * ratio)), Image.LANCZOS)
    return np.array(img, dtype=np.float64)


def floyd_steinberg_dither(gray: np.ndarray) -> np.ndarray:
    """Floyd-Steinberg dither to 1-bit. Returns uint8 array of 0 and 255."""
    h, w = gray.shape
    img = gray.copy()
    for y in range(h):
        for x in range(w):
            old = img[y, x]
            new = 255.0 if old >= 128 else 0.0
            img[y, x] = new
            err = old - new
            if x + 1 < w:
                img[y, x + 1] += err * 7 / 16
            if y + 1 < h and x > 0:
                img[y + 1, x - 1] += err * 3 / 16
            if y + 1 < h:
                img[y + 1, x] += err * 5 / 16
            if y + 1 < h and x + 1 < w:
                img[y + 1, x + 1] += err * 1 / 16
    return np.clip(img, 0, 255).astype(np.uint8)


def invert(img: np.ndarray) -> np.ndarray:
    return 255 - img


def compute_melt_frames(src: np.ndarray, num_frames: int, speed: float, rng: np.random.Generator) -> list:
    """Compute vertical melt frames. Returns list of uint8 arrays."""
    h, w = src.shape
    bg = int(src[0, 0])
    velocities = 0.3 + rng.random(w) * 0.7
    offsets = np.zeros(w, dtype=np.float64)
    frames = []
    for _ in range(num_frames):
        offsets += velocities * speed
        out = np.full((h, w), bg, dtype=np.uint8)
        for x in range(w):
            off = int(offsets[x])
            if off < h:
                visible = h - off
                out[off : off + visible, x] = src[:visible, x]
        frames.append(out)
    return frames


def compute_shear_frames(src: np.ndarray, num_frames: int, speed: float, rng: np.random.Generator) -> list:
    """Compute horizontal shear/rip frames. Returns list of uint8 arrays."""
    h, w = src.shape
    bg = int(src[0, 0])
    directions = np.where(np.arange(h) % 2 == 0, 1, -1)
    velocities = directions * (0.3 + rng.random(h) * 1.2)
    offsets = np.zeros(h, dtype=np.float64)
    frames = []
    for _ in range(num_frames):
        offsets += velocities * speed
        out = np.full((h, w), bg, dtype=np.uint8)
        for y in range(h):
            shift = int(offsets[y])
            if shift >= 0:
                src_start = 0
                dst_start = shift
            else:
                src_start = -shift
                dst_start = 0
            count = w - abs(shift)
            if count > 0:
                out[y, dst_start : dst_start + count] = src[y, src_start : src_start + count]
        frames.append(out)
    return frames


def frames_to_pil(frames: list) -> list:
    return [Image.fromarray(f, mode="L") for f in frames]


def main():
    parser = argparse.ArgumentParser(description="Generate dither-effect loop animation")
    parser.add_argument("image", help="Input image path")
    parser.add_argument("--width", type=int, default=400, help="Output width in pixels (default: 400)")
    parser.add_argument("--fps", type=int, default=15, help="Frames per second (default: 15)")
    parser.add_argument("--speed", type=float, default=6, help="Animation speed factor (default: 6)")
    parser.add_argument("--frames", type=int, default=60, help="Frames per animation direction (default: 60)")
    parser.add_argument("--pause", type=float, default=2.0, help="Pause duration in seconds (default: 2.0)")
    parser.add_argument("--style", choices=["dark", "light"], default="dark",
                        help="dark = black bg / white fg, light = white bg / black fg (default: dark)")
    parser.add_argument("--invert-source", action="store_true",
                        help="Invert grayscale before dithering (negative dither effect)")
    parser.add_argument("--mp4", action="store_true", help="Also produce MP4 via ffmpeg")
    parser.add_argument("-o", "--output", default=None, help="Output filename (default: <input>-loop.gif)")
    args = parser.parse_args()

    input_path = Path(args.image)
    if args.output:
        out_gif = Path(args.output)
    else:
        out_gif = input_path.with_name(input_path.stem + "-loop.gif")

    frame_delay_ms = round(1000 / args.fps)
    pause_ms = round(args.pause * 1000)

    print(f"Loading {input_path} ...")
    gray = load_and_scale(str(input_path), args.width)
    h, w = gray.shape
    print(f"  Scaled to {w}x{h}")

    if args.invert_source:
        print("Inverting source (negative) ...")
        gray = 255.0 - gray

    print("Dithering ...")
    dithered = floyd_steinberg_dither(gray)

    # Enforce the requested background color (style)
    dithered_bg = int(dithered[0, 0])
    want_bg = 0 if args.style == "dark" else 255
    if dithered_bg != want_bg:
        print("Inverting to match style ...")
        base = invert(dithered)
    else:
        base = dithered
    bg_color = int(base[0, 0])
    print(f"  Style: {args.style}, background color: {bg_color}")

    rng = np.random.default_rng(42)

    print(f"Computing melt ({args.frames} frames, speed={args.speed}) ...")
    melt = compute_melt_frames(base, args.frames, args.speed, rng)

    rng2 = np.random.default_rng(99)
    print(f"Computing shear ({args.frames} frames, speed={args.speed}) ...")
    shear = compute_shear_frames(base, args.frames, args.speed, rng2)

    # Assemble sequence
    print("Assembling frames ...")
    base_pil = Image.fromarray(base, mode="L")
    all_frames = []
    all_durations = []

    # 1. Pause on inverted dither
    all_frames.append(base_pil)
    all_durations.append(pause_ms)

    # 2. Melt forward
    for f in frames_to_pil(melt):
        all_frames.append(f)
        all_durations.append(frame_delay_ms)

    # 3. Melt reverse (skip last to avoid duplicate)
    for f in frames_to_pil(melt[-2::-1]):
        all_frames.append(f)
        all_durations.append(frame_delay_ms)

    # 4. Pause on inverted dither
    all_frames.append(base_pil)
    all_durations.append(pause_ms)

    # 5. Shear forward
    for f in frames_to_pil(shear):
        all_frames.append(f)
        all_durations.append(frame_delay_ms)

    # 6. Shear reverse
    for f in frames_to_pil(shear[-2::-1]):
        all_frames.append(f)
        all_durations.append(frame_delay_ms)

    total_frames = len(all_frames)
    total_duration = sum(all_durations) / 1000
    print(f"  {total_frames} frames, ~{total_duration:.1f}s total")

    print(f"Saving {out_gif} ...")
    all_frames[0].save(
        out_gif,
        save_all=True,
        append_images=all_frames[1:],
        duration=all_durations,
        loop=0,
    )
    gif_size = out_gif.stat().st_size
    print(f"  {gif_size / (1024*1024):.1f} MB")

    if args.mp4:
        out_mp4 = out_gif.with_suffix(".mp4")
        print(f"Converting to {out_mp4} ...")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(out_gif),
                "-c:v", "libx264", "-crf", "45",
                "-preset", "veryslow", "-tune", "grain",
                "-pix_fmt", "yuv420p",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-movflags", "faststart",
                str(out_mp4),
            ],
            check=True,
            capture_output=True,
        )
        mp4_size = out_mp4.stat().st_size
        print(f"  {mp4_size / (1024*1024):.1f} MB")

    print("Done!")


if __name__ == "__main__":
    main()
