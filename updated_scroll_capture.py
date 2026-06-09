#!/usr/bin/env python3
"""
updated_scroll_capture — точка входа для EXE.

Обёртка над scroll_long_screenshot.py (склейка scroll-скриншотов с overlap).
"""

from __future__ import annotations

import sys


def _pause_if_windows() -> None:
    if sys.platform != "win32":
        return
    try:
        input("\nNazhmite Enter dlya vyhoda...")
    except EOFError:
        pass


def run() -> int:
    from scroll_long_screenshot import VERSION, main

    if sys.platform == "win32" and len(sys.argv) == 1:
        print(f"updated_scroll_capture v{VERSION}")
        print()
        print("Sklejka:")
        print("  updated_scroll_capture.exe stitch captures\\ -o page.png")
        print("Otladka overlap:")
        print("  updated_scroll_capture.exe overlap prev.png curr.png")
        print("Zahvat stranicy (nuzhen Playwright v sisteme):")
        print("  updated_scroll_capture.exe capture https://example.com -o page.png")
        print()
        _pause_if_windows()
        return 0

    code = main()
    if sys.platform == "win32" and "--help" not in sys.argv and "-h" not in sys.argv:
        _pause_if_windows()
    return code


if __name__ == "__main__":
    raise SystemExit(run())
