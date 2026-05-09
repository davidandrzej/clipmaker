# clipmaker

Generate looping dither-effect animations from headshot images.

Takes a photo, applies Floyd-Steinberg dithering to 1-bit black & white, then produces a looping animation with vertical melt and horizontal shear effects that play forward and reverse.

## Dependencies

- Python 3.12+
- NumPy
- Pillow
- ffmpeg (optional, for MP4 output)

With Nix:

```bash
nix-shell -p python312 python312Packages.numpy python312Packages.pillow --run "python3 dither-loop.py ..."
```

## Usage

```bash
# Basic: produce a looping GIF
python3 dither-loop.py headshot.png

# With MP4 conversion
python3 dither-loop.py headshot.png --mp4

# All options
python3 dither-loop.py headshot.png \
  --width 400 \
  --fps 15 \
  --speed 6 \
  --frames 60 \
  --pause 2.0 \
  --style dark \
  --mp4 \
  -o output.gif
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--width` | 400 | Output width in pixels |
| `--fps` | 15 | Frames per second |
| `--speed` | 6 | Animation speed factor |
| `--frames` | 60 | Frames per animation direction |
| `--pause` | 2.0 | Pause duration in seconds |
| `--style` | dark | `dark` = black bg / white fg, `light` = white bg / black fg |
| `--mp4` | off | Also produce MP4 via ffmpeg (CRF 45, good for dithered content) |
| `-o` | `<input>-loop.gif` | Output filename |

## How it works

1. Load image, composite onto black background (handles transparency)
2. Scale to target width
3. Floyd-Steinberg dither to 1-bit
4. Optionally invert to match requested style
5. Generate melt frames (per-column vertical displacement)
6. Generate shear frames (per-row horizontal displacement, alternating directions)
7. Assemble: pause -> melt fwd -> melt rev -> pause -> shear fwd -> shear rev -> loop
8. Save as GIF, optionally convert to MP4
