#!/usr/bin/env python3
"""Capture the documentation screenshots for the JuiceLab Coach + teacher dashboard.

Drives the running stack (PwnzzAI coach on :8095, teacher dashboard on :5050)
with Playwright and writes PNGs into docs/img/. Reusable: re-run after a UI
change to refresh every capture in one shot.

Env overrides:
  PWNZZAI_URL    coach-injected shop base   (default http://localhost:8095)
  DASHBOARD_URL  teacher dashboard base     (default http://localhost:5050)
  TEACHER_TOKEN  dashboard auth token       (default read from juicelab-dashboard env)
"""
import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

PWNZZAI = os.environ.get("PWNZZAI_URL", "http://localhost:8095")
DASHBOARD = os.environ.get("DASHBOARD_URL", "http://localhost:5050")
LAB_PATH = "/direct-prompt-injection"
OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
VIEWPORT = {"width": 1480, "height": 950}
DPR = 2


def teacher_token() -> str:
    token = os.environ.get("TEACHER_TOKEN", "")
    if token:
        return token
    # fall back to the value baked into the running dashboard container
    res = subprocess.run(
        ["docker", "exec", "juicelab-dashboard", "sh", "-c", "echo $DASHBOARD_TEACHER_TOKEN"],
        capture_output=True, text=True, check=False,
    )
    return res.stdout.strip()


def open_panel(page):
    """Reveal the coach sidebar on a lab page and wait for it to render."""
    page.wait_for_selector(".coach-launcher", timeout=15000)
    if "coach-hidden" in (page.locator(".coach-panel").get_attribute("class") or ""):
        page.click(".coach-launcher")
    page.wait_for_selector(".coach-panel:not(.coach-hidden)", timeout=10000)


def click_tab(page, label):
    page.click(f".coach-tabs .coach-tab >> text='{label}'")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    token = teacher_token()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")

        # ---- coach captures (lang FR, default) ----
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=DPR)
        page = ctx.new_page()

        page.goto(PWNZZAI + "/basics", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "coach-home.png"))

        page.goto(PWNZZAI + LAB_PATH, wait_until="networkidle")
        page.wait_for_selector(".coach-launcher", timeout=15000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "coach-closed.png"))

        open_panel(page)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "coach-panel.png"))

        click_tab(page, "Indices")
        page.wait_for_selector(".coach-hint-row", timeout=10000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "coach-hints.png"))

        click_tab(page, "Progression")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "coach-progress.png"))
        ctx.close()

        # ---- teacher dashboard (full page, both themes) ----
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=DPR)
            ctx.add_cookies([{"name": "teacher_token", "value": token,
                              "url": DASHBOARD}])
            ctx.add_init_script(
                "try{localStorage.setItem('juicelab-theme','%s')}catch(e){}" % theme
            )
            page = ctx.new_page()
            page.goto(DASHBOARD + "/dashboard", wait_until="networkidle")
            page.wait_for_timeout(900)
            page.screenshot(path=str(OUT / f"prof-dashboard-{theme}.png"), full_page=True)
            ctx.close()

        browser.close()
    print("screenshots written to", OUT)


if __name__ == "__main__":
    main()
