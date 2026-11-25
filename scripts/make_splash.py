"""Render assets/splash.png, the start-up image shown while the one-file EXE unpacks itself.

Run once on Windows with the project's Python:  python scripts/make_splash.py
The image is committed, so building the EXE never needs this script or a display.
The unpack takes several seconds before any Python runs, so the text is part of the image.
"""
from __future__ import annotations

import ctypes
import struct
import sys
import tkinter as tk
import zlib
from ctypes import wintypes
from pathlib import Path

WIDTH, HEIGHT = 560, 180
NAVY, STRIPE, TEXT, MUTED = "#124C72", "#E0A100", "#FFFFFF", "#BFD3E3"
OUT = Path(__file__).resolve().parents[1] / "assets" / "splash.png"


def _capture(left: int, top: int, width: int, height: int) -> bytes:
    """Copy a screen rectangle as raw RGB rows."""
    user32, gdi32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    user32.GetDC.argtypes, user32.GetDC.restype = [wintypes.HWND], wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.CreateCompatibleDC.argtypes, gdi32.CreateCompatibleDC.restype = [wintypes.HDC], wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes, gdi32.SelectObject.restype = [wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ
    gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(memory, bitmap)
    gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, 0x00CC0020)  # SRCCOPY
    header = ctypes.create_string_buffer(struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0) + bytes(8))
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory, bitmap, 0, height, pixels, header, 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(None, screen)
    raw = bytearray()
    for row in range(height):
        bgra = pixels.raw[row * width * 4:(row + 1) * width * 4]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
        raw.append(0)  # PNG filter type: none
        raw += rgb
    return bytes(raw)


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{WIDTH}x{HEIGHT}+80+80")
    root.attributes("-topmost", True)
    canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=NAVY, highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(0, 0, 10, HEIGHT, fill=STRIPE, width=0)
    canvas.create_text(44, 62, anchor="w", text="Manifest Cleaner", fill=TEXT, font=("Segoe UI", 30, "bold"))
    canvas.create_text(46, 108, anchor="w", text="Đang khởi động… vui lòng chờ vài giây.", fill=TEXT, font=("Segoe UI", 13))
    canvas.create_text(46, 150, anchor="w", text="Tien - Tan Thuan Port @2026", fill=MUTED, font=("Segoe UI", 10))
    result: dict[str, bytes] = {}

    def grab() -> None:
        root.update()
        result["raw"] = _capture(root.winfo_rootx(), root.winfo_rooty(), WIDTH, HEIGHT)
        root.destroy()

    root.after(700, grab)
    root.mainloop()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(_png(WIDTH, HEIGHT, result["raw"]))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("make_splash.py needs Windows: it captures a Tk window with GDI.")
    main()
