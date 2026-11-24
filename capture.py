"""Read-only Windows window geometry; no game memory access or keyboard hooks."""
import ctypes
from ctypes import wintypes as W
from dataclasses import dataclass
import os
from pathlib import PureWindowsPath

@dataclass(frozen=True)
class WindowBounds:
    client:tuple
    frame:tuple
    desktop:tuple
    title:str='Diablo II'

def rect_size(rect):return rect[2]-rect[0],rect[3]-rect[1]

def crop_for_image(size,bounds):
    """Map physical screenshot pixels only when its source geometry is unambiguous."""
    client,frame,desktop=bounds.client,bounds.frame,bounds.desktop
    if size==rect_size(client):return (0,0,*size)
    if size==rect_size(desktop):origin=desktop
    elif size==rect_size(frame):origin=frame
    else:return None  # Snipping Tool selection / resized image: do not guess its origin.
    left=max(client[0],origin[0]);top=max(client[1],origin[1])
    right=min(client[2],origin[2]);bottom=min(client[3],origin[3])
    if right-left<100 or bottom-top<100:return None
    return left-origin[0],top-origin[1],right-left,bottom-top

def game_window():
    if os.name!='nt':return None
    user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.GetForegroundWindow.restype=W.HWND
    user.IsWindowVisible.argtypes=[W.HWND];user.IsIconic.argtypes=[W.HWND]
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    user.GetClientRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    user.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    user.ClientToScreen.argtypes=[W.HWND,ctypes.POINTER(W.POINT)]
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)]
    kernel.CloseHandle.argtypes=[W.HANDLE]
    # Keep all geometry in physical pixels, including mixed-DPI / negative-origin monitors.
    awareness=getattr(user,'SetThreadDpiAwarenessContext',None);previous=None
    if awareness:
        awareness.argtypes=[ctypes.c_void_p];awareness.restype=ctypes.c_void_p
        previous=awareness(ctypes.c_void_p(-4))
    try:
        candidates=[];foreground=user.GetForegroundWindow()
        callback_type=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        @callback_type
        def visit(hwnd,_):
            if not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):return True
            title=ctypes.create_unicode_buffer(512);user.GetWindowTextW(hwnd,title,512)
            if not title.value.casefold().startswith(('diablo ii','diablo 2')):return True
            pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            process=kernel.OpenProcess(0x1000,False,pid.value)
            if not process:return True
            try:
                path=ctypes.create_unicode_buffer(32768);length=W.DWORD(len(path))
                if not kernel.QueryFullProcessImageNameW(process,0,path,ctypes.byref(length)):return True
                if PureWindowsPath(path.value).name.casefold() not in ('d2r.exe','game.exe','diablo ii.exe'):return True
            finally:kernel.CloseHandle(process)
            client=W.RECT();frame=W.RECT();point=W.POINT(0,0)
            if not user.GetClientRect(hwnd,ctypes.byref(client)) or not user.ClientToScreen(hwnd,ctypes.byref(point)):return True
            if not user.GetWindowRect(hwnd,ctypes.byref(frame)):return True
            try:
                dwm=ctypes.WinDLL('dwmapi');fn=dwm.DwmGetWindowAttribute
                fn.argtypes=[W.HWND,W.DWORD,ctypes.c_void_p,W.DWORD];fn.restype=ctypes.c_long
                visible=W.RECT()
                if fn(hwnd,9,ctypes.byref(visible),ctypes.sizeof(visible))==0:frame=visible
            except (OSError,AttributeError):pass
            if client.right<100 or client.bottom<100:return True
            desktop=(user.GetSystemMetrics(76),user.GetSystemMetrics(77))
            desktop=(*desktop,desktop[0]+user.GetSystemMetrics(78),desktop[1]+user.GetSystemMetrics(79))
            bound=WindowBounds((point.x,point.y,point.x+client.right,point.y+client.bottom),
                               (frame.left,frame.top,frame.right,frame.bottom),desktop,title.value)
            candidates.append((hwnd==foreground,bound));return True
        user.EnumWindows.argtypes=[callback_type,W.LPARAM];user.EnumWindows(visit,0)
        active=[b for foreground,b in candidates if foreground]
        return active[0] if active else candidates[0][1] if len(candidates)==1 else None
    finally:
        if previous:awareness(previous)

def auto_crop(image):
    try:bounds=game_window()
    except (OSError,AttributeError):bounds=None
    if not bounds:return image,'Вікно Diablo II не знайдено; знімок залишено цілим.',False
    rect=crop_for_image((image.width(),image.height()),bounds)
    if rect is None:return image,'Розмір знімка не збігається з вікном або робочим столом; перевірте обрізання.',False
    return image.copy(*rect),'Автоматично виділено вікно Diablo II.',True
