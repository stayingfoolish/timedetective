"""Render the story page's figures as PNG files for the README.

    uv run --with playwright python scripts/story/figures.py --chrome /usr/bin/google-chrome

Run build_page.py first. Playwright is not a project dependency, so it is pulled in for this one command, and a
Chrome or Chromium install is needed. Without network access the page's web fonts cannot load; pass --fonts with
a folder of fontsource packages (ibm-plex-sans, ibm-plex-mono) to use local copies instead.
"""

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "story" / "index.html"
OUT = ROOT / "docs" / "images" / "story"

# README image name -> the part of the page it shows
TARGETS = {
    "fields": "#q6 figure.plate",
    "q1_subtract": "#q1 > figure.plate",
    "q1_region": "#q1 > .two",
    "q2_annual": "#q2 figure.plate",
    "q3_changes": "#q3 figure.plate",
    "q4_gap": "#q4 figure.plate",
    "q5_rain": "#q5 figure.plate",
    "q8_district": "#q8 .two",
    "q9_compare": "#q9 .two",
    "playbook": "#playbook figure.plate",
    "procedure": "#procedures .anatomy",
}

# For a still image: no "show the numbers" toggles, and a see-through page so the cards sit on GitHub's own background.
STILL = """
details.tbl { display: none !important; }
html, body { background: transparent !important; }
#procedures .anatomy { background: var(--page); padding: 16px; border-radius: 12px; }
"""


def local_fonts(folder: Path) -> str:
    rules = []
    for family, package in (("IBM Plex Sans", "ibm-plex-sans"), ("IBM Plex Mono", "ibm-plex-mono")):
        for weight in (400, 500, 600):
            file = folder / "@fontsource" / package / "files" / f"{package}-latin-{weight}-normal.woff2"
            if file.exists():
                rules.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; src: url("{file.as_uri()}") format("woff2"); }}')
    return "\n".join(rules)


async def render(chrome: str | None, fonts: Path | None, scale: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox", "--allow-file-access-from-files"])
        context = await browser.new_context(viewport={"width": 940, "height": 1000}, color_scheme="light", device_scale_factor=scale)
        page = await context.new_page()
        await page.goto(PAGE.as_uri(), wait_until="load")
        await page.add_style_tag(content=STILL + (local_fonts(fonts) if fonts else ""))
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(500)
        for name, selector in TARGETS.items():
            target = page.locator(selector)
            assert await target.count() == 1, f"{selector} matched {await target.count()} elements"
            path = OUT / f"{name}.png"
            await target.screenshot(path=str(path), omit_background=True)
            print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chrome", help="path to a Chrome or Chromium binary (default: the one Playwright installed)")
    parser.add_argument("--fonts", type=Path, help="a node_modules folder holding @fontsource/ibm-plex-sans and -mono")
    parser.add_argument("--scale", type=float, default=2, help="device pixel ratio of the images (default 2)")
    args = parser.parse_args()
    asyncio.run(render(args.chrome, args.fonts, args.scale))
