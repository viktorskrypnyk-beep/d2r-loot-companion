"""Overlapping collection categories; one item remains one database record."""
from core import norm

CATEGORIES=[
 ('all','Усі речі','all'),('unique','Унікальні · легендарні','unique'),
 ('set','Зелені предмети','set'),('magic','Магічні','magic'),('rare','Рідкісні','rare'),
 ('crafted','Крафтові','crafted'),('runeword','Речі з рунними словами','runeword'),
 ('normal','Бази й гнізда','normal'),('rings','Кільця','rings'),('amulets','Амулети','amulets'),
 ('charms','Чарми','charms'),('rune','Руни','rune'),('unknown','Не визначено','unknown'),
 ('pending','Знімки в роботі','pending')]

RINGS={'angelichalo','cathansseal','nagelring','manaldheal','stoneofjordan','thestoneofjordan',
       'dwarfstar','ravenfrost','bulkathosweddingband','carrionwind','naturespeace','wispprojector'}
CHARMS={'annihilus':'small','hellfiretorch':'large','gheedsfortune':'grand',
        'bonebreak':'grand','coldrupture':'grand','crackoftheheavens':'grand','flamerift':'grand',
        'rottingfissure':'grand','theblackcleft':'grand'}

def item_type(item):
    base=norm(item.get('base',''));names=[norm(item.get(k,'')) for k in ('name','canonical_name')]
    if base in ('ring','кільце','перстень','кольцо') or any(n in RINGS for n in names):return 'rings'
    if base in ('amulet','амулет') or any(n in {'angelicwings','talrashasadjudication','therisingsun','maras kaleidoscope'.replace(' ','')} for n in names):return 'amulets'
    if any(s in base for s in ('charm','чарм','талисман','талісман','оберіг','оберег')):return 'charms'
    if any(n in CHARMS or n.removeprefix('renewed') in CHARMS for n in names):return 'charms'
    return ''

def charm_size(item):
    base=norm(item.get('base',''))
    for size,words in [('small',('small','малий','малый')),('grand',('grand','гранд','велетен','великийталисман')),('large',('large','великий','большой','середній'))]:
        if any(w in base for w in words):return size
    for key in ('canonical_name','name'):
        value=norm(item.get(key,'')).removeprefix('renewed')
        if value in CHARMS:return CHARMS[value]
    return ''

def in_category(item,key,subtype=''):
    if key=='all':return True
    if key in ('rings','amulets','charms'):
        return item_type(item)==key and (not subtype or charm_size(item)==subtype)
    return item.get('quality')==key
