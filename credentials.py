"""Per-Windows-user DPAPI key storage, separate from collection and backups."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Захищене збереження ключа доступне у Windows. Тут ключ діє до закриття програми.')

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    target = Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    fn = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p if decrypt else wintypes.LPCWSTR,
                   ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    # CRYPTPROTECT_UI_FORBIDDEN; deliberately do not use LOCAL_MACHINE scope.
    if not fn(ctypes.byref(source), None if decrypt else 'Loot Companion Gemini',
              None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError('Windows не зміг '+('відкрити' if decrypt else 'зберегти')+' захищений ключ.')
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))


class KeyStore:
    def __init__(self, directory):
        self.path = Path(directory) / 'gemini-key.dpapi'

    def load(self):
        if not self.path.exists(): return ''
        try: return _crypt(self.path.read_bytes(), decrypt=True).decode('utf-8')
        except Exception:
            raise RuntimeError('Не вдалося відкрити збережений ключ у цьому профілі Windows. Введіть його знову.') from None

    def save(self, key):
        key = key.strip()
        if not key:
            self.path.unlink(missing_ok=True)
            return
        encrypted = _crypt(key.encode('utf-8'))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        try:
            with open(tmp, 'wb') as handle:
                handle.write(encrypted);handle.flush();os.fsync(handle.fileno())
            tmp.replace(self.path)
        finally:
            tmp.unlink(missing_ok=True)
