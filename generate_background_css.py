from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
import random
import re
import sys

REPO_OWNER = "NagatoAmegakure"
REPO_NAME = "CyclingBackgroundTheme"
BRANCH = "main"

ROOT_DIR = Path(__file__).resolve().parent
BACKGROUND_DIR = ROOT_DIR / "images"
OUTPUT_FILE = ROOT_DIR / "generated-backgrounds.css"

RAW_BASE = (
    f"https://raw.githubusercontent.com/"
    f"{REPO_OWNER}/{REPO_NAME}/{BRANCH}"
)

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".avif",
    ".bmp",
}


def natural_sort_key(path: Path) -> list[object]:
    relative_name = path.relative_to(BACKGROUND_DIR).as_posix()
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", relative_name)
    ]


def pct(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return f"{text}%"


def file_version(path: Path) -> str:
    digest = sha256(path.read_bytes()).hexdigest()
    return digest[:12]


def image_url(path: Path) -> str:
    relative_path = path.relative_to(ROOT_DIR).as_posix()
    encoded_path = quote(relative_path, safe="/")
    version = file_version(path)
    return f"{RAW_BASE}/{encoded_path}?v={version}"


def generate_root_variables(images: list[Path]) -> list[str]:
    count = len(images)

    lines = [
        ":root {",
        f"  --background-count: {count};",
        f"  --cycle-time: calc(var(--image-time, 30s) * {count});",
    ]

    for index, image in enumerate(images, start=1):
        lines.append(
            f'  --background-image-{index}: url("{image_url(image)}");'
        )

    lines.append(
        "  --theme-background-image: var(--background-image-1);"
    )
    lines.append("}")

    return lines


def generate_shared_layers() -> list[str]:
    return [
        "",
        ".appMount__51fd7 {",
        "  background: transparent !important;",
        "  position: relative;",
        "  isolation: isolate;",
        "}",
        "",
        ".appMount__51fd7::before,",
        ".appMount__51fd7::after {",
        '  content: "";',
        "  position: fixed;",
        "  inset: 0;",
        "  width: 100vw;",
        "  height: 100vh;",
        "  background-position: center center;",
        "  background-repeat: no-repeat;",
        "  background-size: cover;",
        "  pointer-events: none;",
        "  will-change: opacity;",
        "}",
    ]


def generate_single_image_css() -> list[str]:
    return [
        "",
        ".appMount__51fd7::before {",
        "  z-index: -2;",
        "  background-image: var(--background-image-1);",
        "  opacity: 1;",
        "}",
        "",
        ".appMount__51fd7::after {",
        "  display: none;",
        "}",
    ]


def generate_bottom_keyframes(count: int, slot: float, epsilon: float) -> list[str]:
    odd_indices = list(range(1, count + 1, 2))
    lines = ["", "@keyframes background-bottom-images {"]

    for position, image_index in enumerate(odd_indices):
        if image_index == 1:
            start = 0.0
        else:
            start = (image_index - 2) * slot + epsilon

        end = min(image_index * slot, 100.0)

        lines.extend(
            [
                f"  {pct(start)},",
                f"  {pct(end)} {{",
                f"    background-image: var(--background-image-{image_index});",
                "  }",
            ]
        )

    # For an even number of images, switch the hidden bottom layer back to
    # image 1 during the final top-layer image so the cycle loops seamlessly.
    if count % 2 == 0:
        reset_start = (count - 1) * slot + epsilon
        lines.extend(
            [
                f"  {pct(reset_start)},",
                "  100% {",
                "    background-image: var(--background-image-1);",
                "  }",
            ]
        )

    lines.append("}")
    return lines


def generate_top_keyframes(count: int, slot: float, epsilon: float) -> list[str]:
    even_indices = list(range(2, count + 1, 2))
    lines = ["", "@keyframes background-top-images {"]

    for image_index in even_indices:
        if image_index == 2:
            start = 0.0
        else:
            start = (image_index - 2) * slot + epsilon

        end = min(image_index * slot, 100.0)

        lines.extend(
            [
                f"  {pct(start)},",
                f"  {pct(end)} {{",
                f"    background-image: var(--background-image-{image_index});",
                "  }",
            ]
        )

    lines.append("}")
    return lines


def generate_opacity_keyframes(count: int, slot: float) -> list[str]:
    fade = slot * 0.10
    points: list[tuple[float, int]] = [(0.0, 0)]

    # Each even-numbered image lives on the top layer.
    # Fade in at the end of the preceding bottom-image slot,
    # then fade back out at the end of its own slot.
    transition_slots = count if count % 2 == 0 else count - 1

    for slot_index in range(transition_slots):
        boundary = (slot_index + 1) * slot

        if slot_index % 2 == 0:
            points.append((max(0.0, boundary - fade), 0))
            points.append((boundary, 1))
        else:
            points.append((max(0.0, boundary - fade), 1))
            points.append((boundary, 0))

    if count % 2 == 1:
        points.append((100.0, 0))

    # Merge duplicate percentages, keeping the last value at each point.
    merged: dict[float, int] = {}
    for position, opacity in points:
        merged[round(position, 8)] = opacity

    lines = ["", "@keyframes background-top-opacity {"]
    for position in sorted(merged):
        lines.extend(
            [
                f"  {pct(position)} {{",
                f"    opacity: {merged[position]};",
                "  }",
            ]
        )
    lines.append("}")

    return lines


def generate_slideshow_css(images: list[Path]) -> str:
    count = len(images)

    header = [
        "/*",
        " * AUTO-GENERATED FILE.",
        " * Do not edit this file by hand.",
        " * generate_background_css.py rewrites it.",
        " */",
        "",
    ]

    if count == 0:
        return "\n".join(
            header
            + [
                "/* No supported images were found in the images folder. */",
                "",
            ]
        )

    lines = header
    lines.extend(generate_root_variables(images))
    lines.extend(generate_shared_layers())

    if count == 1:
        lines.extend(generate_single_image_css())
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            ".appMount__51fd7::before {",
            "  z-index: -2;",
            "  background-image: var(--background-image-1);",
            "  animation:",
            "    background-bottom-images",
            "    var(--cycle-time)",
            "    step-end",
            "    infinite;",
            "  opacity: 1;",
            "}",
            "",
            ".appMount__51fd7::after {",
            "  z-index: -1;",
            "  background-image: var(--background-image-2);",
            "  animation:",
            "    background-top-images",
            "    var(--cycle-time)",
            "    step-end",
            "    infinite,",
            "    background-top-opacity",
            "    var(--cycle-time)",
            "    linear",
            "    infinite;",
            "}",
        ]
    )

    slot = 100.0 / count
    epsilon = min(0.001, slot / 1000.0)

    lines.extend(generate_bottom_keyframes(count, slot, epsilon))
    lines.extend(generate_top_keyframes(count, slot, epsilon))
    lines.extend(generate_opacity_keyframes(count, slot))

    if count % 2 == 1:
        lines.extend(
            [
                "",
                "/*",
                " * Note: with an odd number of images, the final image-to-first-image",
                " * loop is an instant layer reset. Use an even image count for a fully",
                " * seamless crossfade around the entire loop.",
                " */",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    if not BACKGROUND_DIR.exists():
        print(
            f"Background folder does not exist: {BACKGROUND_DIR}",
            file=sys.stderr,
        )
        return 1

    images = sorted(
        [
            path
            for path in BACKGROUND_DIR.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=natural_sort_key,
    )

    random.SystemRandom().shuffle(images)

    OUTPUT_FILE.write_text(
        generate_slideshow_css(images),
        encoding="utf-8",
    )

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Found {len(images)} background image(s).")

    for index, image in enumerate(images, start=1):
        print(
            f"  {index}: "
            f"{image.relative_to(BACKGROUND_DIR).as_posix()}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
