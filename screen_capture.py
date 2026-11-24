"""Capture the active window's monitor before showing any app UI (Windows GDI).

Physical pixels preserve mixed-DPI and negative monitor coordinates. No clipboard
or simulated Print Screen. GDI handles are released on success and every failure.
Reference: https://learn.microsoft.com/windows/win32/api/wingdi/nf-wingdi-getdibits
"""
import ctypes
from ctypes import wintypes as W
import os
from PySide6.QtGui import QImage

def foreground_window():
    if os.name!='nt':return None
    user=ctypes.WinDLL('user32',use_last_error=True)
    bind(user,'GetForegroundWindow',[],W.HWND)
    return user.GetForegroundWindow()

def return_to_window(hwnd):
    if os.name!='nt' or not hwnd:return False
    user=ctypes.WinDLL('user32',use_last_error=True)
    bind(user,'IsWindow',[W.HWND],W.BOOL);bind(user,'SetForegroundWindow',[W.HWND],W.BOOL)
    return bool(user.IsWindow(hwnd) and user.SetForegroundWindow(hwnd))

class MonitorInfo(ctypes.Structure):
    _fields_=[('cbSize',W.DWORD),('rcMonitor',W.RECT),('rcWork',W.RECT),('dwFlags',W.DWORD)]

class BitmapHeader(ctypes.Structure):
    _fields_=[('biSize',W.DWORD),('biWidth',W.LONG),('biHeight',W.LONG),('biPlanes',W.WORD),
              ('biBitCount',W.WORD),('biCompression',W.DWORD),('biSizeImage',W.DWORD),
              ('biXPelsPerMeter',W.LONG),('biYPelsPerMeter',W.LONG),('biClrUsed',W.DWORD),('biClrImportant',W.DWORD)]

class BitmapInfo(ctypes.Structure):
    _fields_=[('header',BitmapHeader),('colors',W.DWORD*3)]

def bind(api,name,args,result):
    fn=getattr(api,name);fn.argtypes=args;fn.restype=result;return fn

def capture_active_monitor():
    if os.name!='nt':raise RuntimeError('Прямий знімок екрана доступний у Windows.')
    user=ctypes.WinDLL('user32',use_last_error=True);gdi=ctypes.WinDLL('gdi32',use_last_error=True)
    bind(user,'GetForegroundWindow',[],W.HWND)
    bind(user,'MonitorFromWindow',[W.HWND,W.DWORD],W.HANDLE)
    bind(user,'GetMonitorInfoW',[W.HANDLE,ctypes.POINTER(MonitorInfo)],W.BOOL)
    bind(user,'GetDC',[W.HWND],W.HDC);bind(user,'ReleaseDC',[W.HWND,W.HDC],ctypes.c_int)
    bind(gdi,'CreateCompatibleDC',[W.HDC],W.HDC)
    bind(gdi,'CreateCompatibleBitmap',[W.HDC,ctypes.c_int,ctypes.c_int],W.HBITMAP)
    bind(gdi,'SelectObject',[W.HDC,W.HANDLE],W.HANDLE)
    bind(gdi,'BitBlt',[W.HDC,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HDC,ctypes.c_int,ctypes.c_int,W.DWORD],W.BOOL)
    bind(gdi,'GetDIBits',[W.HDC,W.HBITMAP,W.UINT,W.UINT,ctypes.c_void_p,ctypes.POINTER(BitmapInfo),W.UINT],ctypes.c_int)
    bind(gdi,'DeleteObject',[W.HANDLE],W.BOOL);bind(gdi,'DeleteDC',[W.HDC],W.BOOL)
    awareness=getattr(user,'SetThreadDpiAwarenessContext',None);previous=None
    screen=memory=bitmap=old=None
    if awareness:
        awareness.argtypes=[ctypes.c_void_p];awareness.restype=ctypes.c_void_p
        previous=awareness(ctypes.c_void_p(-4))
    try:
        monitor=user.MonitorFromWindow(user.GetForegroundWindow(),2)
        info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
        if not monitor or not user.GetMonitorInfoW(monitor,ctypes.byref(info)):raise OSError('Не вдалося визначити монітор активного вікна.')
        rect=info.rcMonitor;w=rect.right-rect.left;h=rect.bottom-rect.top
        if w<=0 or h<=0 or w*h>60000000:raise OSError('Непідтримуваний розмір екрана.')
        screen=user.GetDC(None)
        if not screen:raise OSError('Windows не надала доступ до зображення екрана.')
        memory=gdi.CreateCompatibleDC(screen);bitmap=gdi.CreateCompatibleBitmap(screen,w,h)
        if not memory or not bitmap:raise OSError('Не вдалося підготувати знімок екрана.')
        old=gdi.SelectObject(memory,bitmap)
        if not old or old==ctypes.c_void_p(-1).value:
            old=None;raise OSError('Не вдалося підготувати знімок екрана.')
        if not gdi.BitBlt(memory,0,0,w,h,screen,rect.left,rect.top,0x40CC0020):raise OSError('Windows не змогла захопити зображення гри.')
        gdi.SelectObject(memory,old);old=None  # GetDIBits requires a deselected bitmap.
        info=BitmapInfo();info.header.biSize=ctypes.sizeof(BitmapHeader)
        info.header.biWidth=w;info.header.biHeight=-h;info.header.biPlanes=1;info.header.biBitCount=32
        raw=ctypes.create_string_buffer(w*h*4)
        if gdi.GetDIBits(screen,bitmap,0,h,raw,ctypes.byref(info),0)!=h:raise OSError('Не вдалося прочитати знімок екрана.')
        # Own the storage before ctypes releases its temporary buffer.
        result=QImage(raw.raw,w,h,w*4,QImage.Format_RGB32).copy()
        if result.isNull():raise OSError('Отримано порожній знімок.')
        return result
    finally:
        if old and memory:gdi.SelectObject(memory,old)
        if bitmap:gdi.DeleteObject(bitmap)
        if memory:gdi.DeleteDC(memory)
        if screen:user.ReleaseDC(None,screen)
        if previous:awareness(previous)
