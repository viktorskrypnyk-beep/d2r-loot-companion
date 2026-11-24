"""Windows global shortcut via RegisterHotKey; no keyboard injection or hooks.

References: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-registerhotkey
https://doc.qt.io/qtforpython-6.10/PySide6/QtCore/QAbstractNativeEventFilter.html
"""
import ctypes
from ctypes import wintypes as W
import os
import time
from PySide6.QtCore import QAbstractNativeEventFilter,QTimer

DEFAULT_HOTKEY='Ctrl+Shift+F8'
HOTKEYS=[DEFAULT_HOTKEY]+[f'Ctrl+Shift+F{n}' for n in (9,10,7,6,11)]+[f'Ctrl+Alt+F{n}' for n in (8,9,10)]
WM_HOTKEY=0x0312
MOD_NOREPEAT=0x4000

def key_codes(sequence):
    if sequence not in HOTKEYS:raise ValueError('Оберіть одну із запропонованих комбінацій.')
    parts=sequence.split('+');mods=sum({'Ctrl':2,'Shift':4,'Alt':1}[p] for p in parts[:-1])
    return mods,0x70+int(parts[-1][1:])-1

class WindowsBackend:
    def __init__(self):
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.RegisterHotKey.argtypes=[W.HWND,ctypes.c_int,W.UINT,W.UINT];self.user.RegisterHotKey.restype=W.BOOL
        self.user.UnregisterHotKey.argtypes=[W.HWND,ctypes.c_int];self.user.UnregisterHotKey.restype=W.BOOL
    def register(self,ident,mods,vk):return bool(self.user.RegisterHotKey(None,ident,mods|MOD_NOREPEAT,vk))
    def unregister(self,ident):self.user.UnregisterHotKey(None,ident)

class GlobalHotkey(QAbstractNativeEventFilter):
    def __init__(self,app,callback,backend=None):
        super().__init__();self.app=app;self.callback=callback;self.backend=backend
        self.ident=None;self.sequence=None;self.closed=False;self.last_trigger=-float('inf')
        if backend is None and os.name=='nt':
            try:self.backend=WindowsBackend()
            except OSError:pass
        if self.backend:self.app.installNativeEventFilter(self)
    def configure(self,sequence,enabled=True):
        if not enabled:
            if self.ident is not None:self.backend.unregister(self.ident)
            self.ident=None;self.sequence=None;return True,'Глобальну комбінацію вимкнено.'
        if self.closed:return False,'Обробник комбінації вже закрито.'
        if not self.backend:return False,'Глобальна комбінація доступна у Windows.'
        mods,vk=key_codes(sequence)
        if sequence==self.sequence:return True,f'{sequence} — увімкнено.'
        candidate=0x4C02 if self.ident==0x4C01 else 0x4C01
        if not self.backend.register(candidate,mods,vk):
            suffix=f' Попередня {self.sequence} продовжує працювати.' if self.sequence else ''
            return False,'Windows не зареєструвала комбінацію. Можливо, її зайняла інша програма. Виберіть іншу.'+suffix
        old=self.ident;self.ident=candidate;self.sequence=sequence
        if old is not None:self.backend.unregister(old)
        return True,f'{sequence} — увімкнено. Працює, поки Loot Companion запущено.'
    def dispatch(self,message,ident):
        if self.closed or self.ident is None or message!=WM_HOTKEY or ident!=self.ident:return False
        now=time.monotonic()
        if now-self.last_trigger>=.4:
            self.last_trigger=now
            current=self.ident
            QTimer.singleShot(0,lambda:self.callback() if not self.closed and self.ident==current else None)
        return True
    def nativeEventFilter(self,event_type,message):
        if bytes(event_type) in (b'windows_generic_MSG',b'windows_dispatcher_MSG'):
            msg=W.MSG.from_address(int(message))
            return self.dispatch(msg.message,msg.wParam),0
        return False,0
    def close(self):
        if self.closed:return
        self.closed=True
        if self.ident is not None:self.backend.unregister(self.ident)
        self.ident=None;self.sequence=None
        if self.backend:self.app.removeNativeEventFilter(self)
