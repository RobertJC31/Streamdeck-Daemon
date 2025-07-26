#!/usr/bin/env python3
import sys
import ctypes
import ctypes.wintypes
import win32con
import win32gui
import win32api
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Transport.Transport import TransportError

# --- define GUID & structures for GUID_CONSOLE_DISPLAY_STATE ---
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.wintypes.DWORD),
        ("Data2", ctypes.wintypes.WORD),
        ("Data3", ctypes.wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8)
    ]

class POWERBROADCAST_SETTING(ctypes.Structure):
    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", ctypes.wintypes.DWORD),
        ("Data", ctypes.wintypes.DWORD)
    ]

GUID_CONSOLE_DISPLAY_STATE = GUID(
    0x6FE69556, 0x704A, 0x47A0,
    (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47)
)

WM_POWERBROADCAST      = win32con.WM_POWERBROADCAST
PBT_POWERSETTINGCHANGE = 0x8013

def init_decks():
    """Enumerate and open all Stream Decks once at startup."""
    decks = list(DeviceManager().enumerate())
    if not decks:
        print("[ERROR] No Stream Decks found. Exiting.")
        sys.exit(1)
    for deck in decks:
        deck.open()
        print(f"[INFO] Opened StreamDeck {deck.id()}")
    return decks

# Keep a global, persistent list of opened decks:
DECKS = init_decks()

def set_deck_brightness(level: int):
    """Set brightness on every open deck; if the handle has died, reopen and retry."""
    for deck in DECKS:
        try:
            deck.set_brightness(level)
        except TransportError:
            print(f"[WARN] Lost HID handle on deck {deck.id()}, reopening…")
            try:
                deck.open()
                deck.set_brightness(level)
            except Exception as e2:
                print(f"[ERROR] Still can’t set brightness: {e2}")
        except Exception as e:
            print(f"[ERROR] Unexpected error on deck {deck.id()}: {e}")

def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_POWERBROADCAST and wparam == PBT_POWERSETTINGCHANGE:
        pbs = POWERBROADCAST_SETTING.from_address(lparam)
        if (
            pbs.PowerSetting.Data1 == GUID_CONSOLE_DISPLAY_STATE.Data1 and
            pbs.PowerSetting.Data2 == GUID_CONSOLE_DISPLAY_STATE.Data2 and
            pbs.PowerSetting.Data3 == GUID_CONSOLE_DISPLAY_STATE.Data3 and
            bytes(pbs.PowerSetting.Data4) == bytes(GUID_CONSOLE_DISPLAY_STATE.Data4)
        ):
            if pbs.Data == 0:  # display off
                print("[DEBUG] DISPLAY OFF event received")
                set_deck_brightness(0)
            elif pbs.Data == 1:  # display on (wake)
                print("[DEBUG] DISPLAY ON event received")
                set_deck_brightness(40)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def main():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc   = wnd_proc
    wc.lpszClassName = "StreamDeckPowerMonitor"
    wc.hInstance     = win32api.GetModuleHandle(None)
    classAtom = win32gui.RegisterClass(wc)

    hwnd = win32gui.CreateWindowEx(
        0, classAtom, "SDPowerMon", 0, 0,0,0,0,
        win32con.HWND_MESSAGE, 0, wc.hInstance, None
    )

    ctypes.windll.user32.RegisterPowerSettingNotification(
        hwnd,
        ctypes.byref(GUID_CONSOLE_DISPLAY_STATE),
        0
    )

    print("[INFO] Entering message loop, waiting for display off/on events…")
    win32gui.PumpMessages()

if __name__ == "__main__":
    main()
