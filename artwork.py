"""Exact-name lookup and disk cache for Blizzard's public item illustrations."""
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen,HTTPRedirectHandler,build_opener
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,threading
from PySide6.QtCore import QObject,Signal,Qt,QSize
from PySide6.QtGui import QImage,QPixmap,QIcon,QPainter,QColor,QFont
from core import ROOT,norm

def load_index():
    try:return json.loads((ROOT/'data/item_art.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {'items':{},'bases':{},'runes':{}}

INDEX=load_index()
try:BUNDLED=json.loads((ROOT/'data/collection_art.json').read_text(encoding='utf-8'))
except (OSError,ValueError):BUNDLED={'urls':{},'categories':{}}

def lookup(item):
    if item.get('quality')=='rune':
        counts=item.get('rune_counts',{})
        names=list(counts) if counts else [item.get('canonical_name','').removesuffix(' Rune')]
        if len(names)==1 and norm(names[0]) in INDEX['runes']:return dict(INDEX['runes'][norm(names[0])],kind='rune')
        return None
    if item.get('quality') in ('unique','set'):
        for name in (item.get('canonical_name',''),item.get('name','')):
            if norm(name) in INDEX['items']:return dict(INDEX['items'][norm(name)],kind='exact')
            if name.casefold().startswith('the ') and norm(name[4:]) in INDEX['items']:return dict(INDEX['items'][norm(name[4:])],kind='exact')
    base=INDEX['bases'].get(norm(item.get('base','')))
    if not base:
        from collection import item_type,charm_size
        kind=item_type(item)
        generic='Ring' if kind=='rings' else 'Amulet' if kind=='amulets' else {'small':'Small Charm','large':'Large Charm','grand':'Grand Charm'}.get(charm_size(item),'Grand Charm') if kind=='charms' else ''
        base=INDEX['bases'].get(norm(generic))
    if base:return dict(base,kind='base')
    return None

def trusted_url(url):
    parts=urlsplit(url)
    return parts.scheme=='https' and parts.hostname=='classic.battle.net' and parts.port in (None,443) and not parts.username and parts.path.startswith(('/images/battle/diablo2exp/images/','/diablo2exp/images/items/'))

class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not trusted_url(newurl):raise ValueError('Недозволена адреса зображення')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_image(url,target):
    if not trusted_url(url):raise ValueError('Недозволена адреса зображення')
    with build_opener(SafeRedirect()).open(Request(url,headers={'User-Agent':'LootCompanion/0.3'}),timeout=15) as response:
        data=response.read(2*1024*1024+1)
    if len(data)>2*1024*1024:raise ValueError('Завелике зображення')
    image=QImage.fromData(data)
    if image.isNull() or image.width()>2048 or image.height()>2048:raise ValueError('Невідомий формат зображення')
    temp=target.with_suffix('.tmp')
    try:
        if not image.save(str(temp),'PNG'):raise OSError('Не вдалося зберегти зображення')
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)

class Artwork(QObject):
    ready=Signal(str)
    def __init__(self,directory,parent=None,enabled=True):
        super().__init__(parent);self.directory=Path(directory)/'art_cache';self.directory.mkdir(exist_ok=True)
        self.enabled=enabled;self.pending=set();self.failed=set();self.pool=ThreadPoolExecutor(max_workers=3)
        self.closed=False;self._lock=threading.Lock();self._placeholder=None
    def path(self,entry,request=True):
        if not entry:return None
        if entry['kind']=='rune':
            bundled=ROOT/'data/runes'/(entry['name']+'.gif')
            if bundled.exists():return bundled
        url=entry['url'];target=self.directory/(hashlib.sha256(url.encode()).hexdigest()+'.png')
        bundled=ROOT/'data/art'/BUNDLED.get('urls',{}).get(url,'_missing')
        if bundled.is_file():return bundled
        if target.exists():return target
        if request and self.enabled and not self.closed and url not in self.pending and url not in self.failed:
            self.pending.add(url);self.pool.submit(self._fetch,url,target)
        return None
    def _fetch(self,url,target):
        try:fetch_image(url,target)
        except Exception:
            with self._lock:self.failed.add(url)
        finally:
            with self._lock:self.pending.discard(url)
            if not self.closed:
                try:self.ready.emit(url)
                except RuntimeError:pass
    def icon(self,item):
        path=self.path(lookup(item))
        if path:return QIcon(str(path))
        if self._placeholder is None:
            pix=QPixmap(32,32);pix.fill(Qt.transparent);p=QPainter(pix)
            p.setPen(QColor('#65798b'));p.drawRoundedRect(3,3,26,26,4,4)
            p.setFont(QFont('Sans Serif',14));p.drawText(pix.rect(),Qt.AlignCenter,'?');p.end();self._placeholder=QIcon(pix)
        return self._placeholder
    def card_icon(self,icon):
        canvas=QPixmap(80,92);canvas.fill(Qt.transparent)
        source=icon.pixmap(80,92)
        if not source.isNull():
            size=source.size();size.scale(64,84,Qt.KeepAspectRatio)
            p=QPainter(canvas);p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawPixmap((80-size.width())//2,(92-size.height())//2,source.scaled(size,Qt.KeepAspectRatio,Qt.SmoothTransformation));p.end()
        return QIcon(canvas)
    def rune_icon(self,name):return self.icon({'quality':'rune','rune_counts':{name:1}})
    def category_icon(self,key):
        path=ROOT/'data/art'/BUNDLED.get('categories',{}).get(key,'_missing')
        return QIcon(str(path)) if path.is_file() else self.rune_icon('Ist') if key=='rune' else self.icon({})
    def rune_strip(self,names):
        pix=QPixmap(max(1,len(names))*30,30);pix.fill(Qt.transparent);p=QPainter(pix)
        for n,name in enumerate(names):self.rune_icon(name).paint(p,n*30,0,28,28)
        p.end();return pix
    def close(self):
        self.closed=True;self.pool.shutdown(wait=False,cancel_futures=True)
