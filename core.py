"""Local collection, conservative comparisons and rune arithmetic.

This module has no network, screen-capture or game-process access.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
import zipfile
import copy

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
QUALITIES = {'unique':'Унікальні', 'set':'Комплекти', 'rare':'Рідкісні',
             'crafted':'Крафтові', 'magic':'Магічні', 'normal':'Бази',
             'runeword':'Рунні слова', 'rune':'Руни', 'unknown':'Не визначено'}

# Direction comes from our rules, never from a language model's confidence.
DIRECTIONS = {key:1 for key in (
    'all_skills class_skills life mana vitality strength dexterity energy '
    'all_res fire_res cold_res lightning_res poison_res magic_find gold_find '
    'fcr ias fhr frw block_rate enhanced_damage enhanced_defense defense '
    'flat_damage min_damage max_damage attack_rating crushing_blow deadly_strike '
    'open_wounds life_leech mana_leech damage_reduced_percent magic_damage_reduced '
    'fire_skill_damage cold_skill_damage lightning_skill_damage poison_skill_damage'
).split()}
DIRECTIONS.update({k:-1 for k in (
    'required_level required_strength required_dexterity enemy_fire_res enemy_cold_res '
    'enemy_lightning_res enemy_poison_res physical_damage_received_percent'
).split()})

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def norm(value): return re.sub(r'[^a-zа-яіїєґ0-9]+','',str(value).casefold())
def uid(): return uuid.uuid4().hex

def data_directory():
    if os.environ.get('LOOT_COMPANION_DATA'):
        return Path(os.environ['LOOT_COMPANION_DATA'])
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'LootCompanion'

def blank_item():
    return dict(name='',canonical_name='',base='',quality='unknown',set_name='',
                ethereal=None,sockets=None,identified=None,stats=[],builds=[],
                explanation='',warnings=[],rune_counts={},confidence='unknown',
                verified=False,location='',notes='',prices={},advice={})

ADVICE_ACTIONS={'keep':'ЗАЛИШИТИ','trade':'ПРОДАТИ ГРАВЦЮ','vendor':'МОЖНА ПРОДАТИ ТОРГОВЦЮ','review':'ПЕРЕВІРИТИ ПЕРЕД РІШЕННЯМ'}

def validate_advice(advice):
    if not isinstance(advice,dict):raise ValueError('Порада має бути об’єктом.')
    if not advice:return {}
    if advice.get('action') not in ADVICE_ACTIONS:raise ValueError('Невідома рекомендація.')
    for key in ('reason','trade_note'):
        if not isinstance(advice.get(key),str):raise ValueError('Порада: потрібен текст '+key)
    for key in ('strengths','weaknesses','uses'):
        if not isinstance(advice.get(key),list) or not all(isinstance(s,str) for s in advice[key]):raise ValueError('Порада: потрібен список '+key)
    return {key:advice[key] for key in ('action','reason','trade_note','strengths','weaknesses','uses')}

def effective_advice(item):
    advice=item.get('advice') or {}
    if not advice:return dict(action='review',reason='Для цієї картки ще немає рекомендації. Натисніть «Оновити пораду».',strengths=[],weaknesses=[],uses=[],trade_note='')
    advice=copy.deepcopy(advice)
    uncertain=((item.get('confidence')!='high' and not item.get('verified')) or item.get('identified') is not True or
               any(needs_stat_review(s['key']) for s in item.get('stats',[])))
    if advice['action'] in ('vendor','trade') and uncertain:
        advice['action']='review';advice['reason']='Спочатку звірте назву й цифри зі знімком. '+advice['reason']
    if item.get('quality')=='rune' and advice['action']=='vendor':
        advice['action']='keep';advice['reason']='Збережіть руни для рецептів або обміну; продаж торговцю не рекомендовано.'
    return advice

def validate_stat(stat):
    if not isinstance(stat,dict) or not all(k in stat for k in ('key','label','value','unit','condition')):
        raise ValueError('Параметр: key, label, value, unit, condition.')
    if not all(isinstance(stat[k],str) for k in ('key','label','unit','condition')):
        raise ValueError('Назва й одиниці параметра мають бути текстом.')
    if stat['value'] is not None and (type(stat['value']) not in (int,float) or not math.isfinite(stat['value'])):
        raise ValueError('Значення параметра: скінченне число або null.')

def needs_stat_review(key):
    return bool(re.search(r'__review_\d+$',key))

def validate_item(value):
    if not isinstance(value,dict): raise ValueError('Картка має бути об’єктом JSON.')
    out=blank_item()
    for key in out:
        if key in value: out[key]=value[key]
    for key in ('name','canonical_name','base','set_name','explanation','location','notes','confidence'):
        if not isinstance(out[key],str): raise ValueError(f'{key}: потрібен текст.')
    if out['quality'] not in QUALITIES: raise ValueError('Невідома категорія предмета.')
    for key in ('ethereal','identified'):
        if out[key] is not None and type(out[key]) is not bool: raise ValueError(f'{key}: true/false/null.')
    if out['sockets'] is not None and (type(out['sockets']) is not int or not 0<=out['sockets']<=6):
        raise ValueError('Кількість гнізд: ціле число 0–6 або null.')
    if not isinstance(out['stats'],list): raise ValueError('stats: потрібен список.')
    seen=set()
    for stat in out['stats']:
        validate_stat(stat)
        identity=(stat['key'],stat['condition'])
        if identity in seen: raise ValueError('Повтор параметра: '+stat['key'])
        seen.add(identity)
    for key in ('builds','warnings'):
        if not isinstance(out[key],list) or not all(isinstance(x,str) for x in out[key]):
            raise ValueError(f'{key}: потрібен список рядків.')
    validate_runes(out['rune_counts'])
    out['verified']=bool(out['verified'])
    if not isinstance(out['prices'],dict): raise ValueError('prices: потрібен об’єкт.')
    out['advice']=validate_advice(out['advice'])
    if out['quality']=='set':
        title=norm(out['canonical_name'] or out['name'])
        for definition in CATALOG['sets']:
            if title in [norm(n) for n in definition['pieces']]:
                out['set_name']=definition['name'];break
    return out

def validate_runes(counts):
    if not isinstance(counts,dict): raise ValueError('Запас рун має бути словником.')
    for name,count in counts.items():
        if name not in CATALOG['runes']: raise ValueError('Невідома руна: '+name)
        if type(count) is not int or not 0<=count<=999999: raise ValueError('Кількість рун: невід’ємне ціле число.')
    return counts

def same_family(a,b):
    if a['quality'] != b['quality']: return False
    name=norm(a['canonical_name'] or a['name'])
    if a['quality'] in ('unique','set','runeword'):
        return bool(name) and name==norm(b['canonical_name'] or b['name'])
    return bool(norm(a['base'])) and norm(a['base'])==norm(b['base'])

def compare_items(new, old):
    """A per-stat Pareto comparison, not a build-independent power score."""
    rows=[]; directions=[]; caveats=[]
    if not same_family(new,old): caveats.append('Різні типи або назви предметів.')
    if not new.get('verified') or not old.get('verified'):
        caveats.append('Перевірте розпізнані цифри в обох картках.')
    if new.get('identified') is not True or old.get('identified') is not True:
        caveats.append('Ідентифікацію обох речей не підтверджено.')
    for key,label in [('ethereal','Ефірність'),('sockets','Гнізда'),('base','Базовий предмет')]:
        if new.get(key)!=old.get(key) or new.get(key) is None:
            caveats.append(label+': відмінність або невідоме значення.')
    a={(s['key'],s['condition']):s for s in new['stats']}
    b={(s['key'],s['condition']):s for s in old['stats']}
    for key in sorted(set(a)|set(b)):
        x,y=a.get(key),b.get(key)
        label=(x or y)['label']; nv=x['value'] if x else None; ov=y['value'] if y else None
        delta=None; verdict='Потрібен контекст'
        if needs_stat_review(key[0]):
            caveats.append('Повторні параметри ще не розділено за змістом. Звірте їх зі знімком і виправте ключі у картці.')
        elif x and y and x['unit']==y['unit'] and nv is not None and ov is not None:
            delta=nv-ov
            if delta==0: verdict='Без змін'
            elif key[1]=='intrinsic' and key[0] in DIRECTIONS:
                sign=1 if delta*DIRECTIONS[key[0]]>0 else -1
                directions.append(sign);verdict='Вище за цим параметром' if sign>0 else 'Нижче за цим параметром'
            else: caveats.append('Умовні або невідомі параметри потребують окремої оцінки.')
        else: caveats.append('Не всі параметри зіставлено; відсутність рядка не вважається нулем.')
        rows.append(dict(label=label,new=nv,old=ov,delta=delta,unit=(x or y)['unit'],verdict=verdict))
    if not rows: caveats.append('Немає числових параметрів для порівняння.')
    caveats=list(dict.fromkeys(caveats))
    if 1 in directions and -1 in directions: verdict='Компроміс: частина параметрів краща, частина гірша'
    elif caveats: verdict='Потрібна перевірка — остаточного висновку немає'
    elif 1 in directions: verdict='Кращі зіставлені числові параметри'
    elif -1 in directions: verdict='Гірші зіставлені числові параметри'
    else: verdict='Зіставлені числові параметри однакові'
    return dict(verdict=verdict,rows=rows,caveats=caveats)

def rune_options(inventory, mode='Non-Ladder', era='D2R LoD'):
    validate_runes(inventory)
    options=[]
    for word in CATALOG['runewords']:
        if word['release']=='RotW' and era!='Reign of the Warlock':continue
        need=Counter(word['runes'])
        missing={r:n-inventory.get(r,0) for r,n in need.items() if inventory.get(r,0)<n}
        check=word['availability']!='all'
        options.append(dict(**word,missing=missing,runes_ready=not missing,
                            mode_check=check,craftable=False))
    if era=='Reign of the Warlock':
        for word in options[:]:
            if word['name']=='Hustle':
                options.remove(word)
                for name,base in [('Mania','Weapons'),('Hysteria','Body Armor')]:
                    variant=copy.deepcopy(word);variant.update(name=name,bases=base,stats=[],mode_check=True,
                        source='https://news.blizzard.com/en-us/article/24296140/diablo-ii-resurrected-ladder-season-15-now-live')
                    options.append(variant)
            elif word['name'] in ['Metamorphosis','Ground','Temper','Hearth','Cure','Bulwark']:
                word['stats']=[];word['mode_check']=True
    return sorted(options,key=lambda w:(sum(w['missing'].values()),w['name']))

def set_progress(definition, items):
    owned=Counter(norm(i['canonical_name'] or i['name']) for i in items if i['quality']=='set')
    parts=[dict(name=n,count=owned[norm(n)]) for n in definition['pieces']]
    return dict(parts=parts,owned=sum(p['count']>0 for p in parts),total=len(parts))

def all_rune_options(inventory,mode='Non-Ladder',era='D2R LoD'):
    """All named recipes, including other editions, with explicit edition labels."""
    current={w['name']:w for w in rune_options(inventory,mode,era)}
    variants={}
    for edition in ('D2R LoD','Reign of the Warlock'):
        for word in rune_options(inventory,mode,edition):variants[word['name']]=word
    for name,word in current.items():variants[name]=word
    result=[]
    for name,word in variants.items():
        value=dict(word);value['edition_available']=name in current
        value['edition_note']='' if name in current else ('Назва LoD; у RotW див. Mania / Hysteria' if name=='Hustle' else 'Лише Reign of the Warlock')
        result.append(value)
    return sorted(result,key=lambda w:w['name'].casefold())

class Store:
    def __init__(self, directory=None):
        self.path=Path(directory or data_directory());self.path.mkdir(parents=True,exist_ok=True)
        (self.path/'screenshots').mkdir(exist_ok=True)
        self.db=sqlite3.connect(self.path/'collection.sqlite3');self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,name TEXT NOT NULL,created TEXT NOT NULL,profile TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS shots(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),profile TEXT NOT NULL,
            created TEXT NOT NULL,path TEXT NOT NULL,sha TEXT NOT NULL,status TEXT NOT NULL,error TEXT NOT NULL DEFAULT '');
          CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,shot_id TEXT REFERENCES shots(id),run_id TEXT NOT NULL REFERENCES runs(id),
            profile TEXT NOT NULL,created TEXT NOT NULL,payload TEXT NOT NULL,owned INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS runes(profile TEXT NOT NULL,name TEXT NOT NULL,count INTEGER NOT NULL CHECK(count>=0),
            PRIMARY KEY(profile,name));
          CREATE TABLE IF NOT EXISTS rune_imports(item_id TEXT PRIMARY KEY REFERENCES items(id),created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS rune_updates(shot_id TEXT PRIMARY KEY REFERENCES shots(id),
            profile TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,created TEXT NOT NULL);
        ''')
        columns={r['name'] for r in self.db.execute('PRAGMA table_info(shots)')}
        if 'destination' not in columns:
            self.db.execute("ALTER TABLE shots ADD COLUMN destination TEXT NOT NULL DEFAULT 'run'")
        if 'rune_baseline' not in columns:
            self.db.execute("ALTER TABLE shots ADD COLUMN rune_baseline TEXT NOT NULL DEFAULT '{}'")
        if 'source_path' not in columns:self.db.execute("ALTER TABLE shots ADD COLUMN source_path TEXT NOT NULL DEFAULT ''")
        if 'capture_note' not in columns:self.db.execute("ALTER TABLE shots ADD COLUMN capture_note TEXT NOT NULL DEFAULT ''")
        if 'deleted_at' not in columns:self.db.execute("ALTER TABLE shots ADD COLUMN deleted_at TEXT NOT NULL DEFAULT ''")
        columns={r['name'] for r in self.db.execute('PRAGMA table_info(items)')}
        if 'decision' not in columns:
            self.db.execute("ALTER TABLE items ADD COLUMN decision TEXT NOT NULL DEFAULT 'pending'")
        if 'origin' not in columns:
            self.db.execute("ALTER TABLE items ADD COLUMN origin TEXT NOT NULL DEFAULT 'run'")
        if 'deleted_at' not in columns:self.db.execute("ALTER TABLE items ADD COLUMN deleted_at TEXT NOT NULL DEFAULT ''")
        self.db.execute("UPDATE shots SET status='pending',error='Попередню обробку перервано. Можна повторити.' WHERE status='working'")
        self.db.commit()

    def get_setting(self,key,default=None):
        row=self.db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self,key,value):
        with self.db:self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))

    def new_run(self,profile,name=None):
        ident=uid();name=name or datetime.now().strftime('Забіг %d.%m · %H:%M:%S')
        with self.db:self.db.execute('INSERT INTO runs VALUES (?,?,?,?)',(ident,name,now(),profile))
        return ident

    def runs(self,profile):
        return [dict(r) for r in self.db.execute('SELECT * FROM runs WHERE profile=? ORDER BY created DESC,rowid DESC',(profile,))]

    def add_shot(self,png,run_id,profile,force=False,destination='run',source_png=None,capture_note=''):
        if destination not in ('run','owned','runes'): raise ValueError('Невідоме призначення знімка.')
        digest=hashlib.sha256(png).hexdigest()
        if not force:
            prev=self.db.execute("SELECT id FROM shots WHERE sha=? AND run_id=? AND destination=? AND deleted_at=''",(digest,run_id,destination)).fetchone()
            if prev:return prev[0],False
        ident=uid();filename='screenshots/'+ident+'.png';target=self.path/filename
        tmp=target.with_suffix('.tmp');tmp.write_bytes(png);tmp.replace(target)
        source_path=''
        if source_png is not None and source_png!=png:
            source_path='screenshots/'+ident+'-original.png'
            tmp=(self.path/source_path).with_suffix('.tmp');tmp.write_bytes(source_png);tmp.replace(self.path/source_path)
        baseline=json.dumps(self.inventory(profile)) if destination=='runes' else '{}'
        with self.db:self.db.execute('INSERT INTO shots(id,run_id,profile,created,path,sha,status,destination,rune_baseline,source_path,capture_note) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                    (ident,run_id,profile,now(),filename,digest,'pending',destination,baseline,source_path,capture_note))
        return ident,True

    def shots(self,profile,run_id=None):
        sql="SELECT * FROM shots WHERE profile=? AND deleted_at=''";args=[profile]
        if run_id:sql+=' AND run_id=?';args.append(run_id)
        return [dict(r) for r in self.db.execute(sql+' ORDER BY created,rowid',args)]

    def shot(self,ident):
        r=self.db.execute("SELECT * FROM shots WHERE id=? AND deleted_at=''",(ident,)).fetchone()
        return dict(r) if r else None

    def shot_status(self,ident,status,error=''):
        with self.db:self.db.execute('UPDATE shots SET status=?,error=? WHERE id=?',(status,error,ident))

    def crop_pending_shot(self,ident,png):
        """Keep capture identity, routing and full original when confirming a crop."""
        shot=self.shot(ident)
        if not shot:raise ValueError('Знімок не знайдено.')
        if shot['status']=='working' or self.db.execute('SELECT 1 FROM items WHERE shot_id=?',(ident,)).fetchone():
            raise ValueError('Знімок уже обробляється або має картки.')
        filename='screenshots/'+ident+'-crop-'+uid()+'.png';target=self.path/filename
        tmp=target.with_suffix('.tmp');tmp.write_bytes(png);tmp.replace(target)
        with self.db:self.db.execute("UPDATE shots SET path=?,source_path=?,status='pending',error='',capture_note=? WHERE id=?",
            (filename,shot['source_path'] or shot['path'],'Область вибрано вручну. Повний оригінал збережено.',ident))

    def finish_shot(self,shot_id,items):
        # Validate all candidates before writing any; retries never delete user edits.
        clean=[validate_item(x) for x in items];shot=self.shot(shot_id)
        if not shot:raise ValueError('Знімок не знайдено.')
        if self.db.execute('SELECT 1 FROM items WHERE shot_id=?',(shot_id,)).fetchone():
            raise ValueError('Знімок уже має картки. Відредагуйте їх або імпортуйте новий знімок.')
        with self.db:
            for item in clean:
                own=shot['destination'] in ('owned','runes')
                self.db.execute('INSERT INTO items(id,shot_id,run_id,profile,created,payload,owned,decision,origin) VALUES (?,?,?,?,?,?,?,?,?)',
                    (uid(),shot_id,shot['run_id'],shot['profile'],now(),json.dumps(item,ensure_ascii=False),int(own),'keep' if own else 'pending',shot['destination']))
            self.db.execute('UPDATE shots SET status=?,error=? WHERE id=?',
                            ('done' if clean else 'empty','' if clean else 'Немає читабельного опису предмета.',shot_id))

    def add_manual(self,run_id,profile,item,owned=False):
        item=validate_item(item);ident=uid()
        with self.db:self.db.execute('INSERT INTO items(id,shot_id,run_id,profile,created,payload,owned,decision,origin) VALUES (?,?,?,?,?,?,?,?,?)',
            (ident,None,run_id,profile,now(),json.dumps(item,ensure_ascii=False),int(owned),'keep' if owned else 'pending','owned' if owned else 'run'))
        return ident

    def items(self,profile,run_id=None,owned=False):
        sql="SELECT * FROM items WHERE profile=? AND deleted_at=''";args=[profile]
        if run_id:sql+=' AND run_id=?';args.append(run_id)
        if owned:sql+=' AND owned=1'
        result=[]
        for r in self.db.execute(sql+' ORDER BY created DESC,rowid DESC',args):
            row=dict(r);row['item']=json.loads(row.pop('payload'));result.append(row)
        return result

    def item(self,ident):
        r=self.db.execute("SELECT * FROM items WHERE id=? AND deleted_at=''",(ident,)).fetchone()
        if not r:return None
        row=dict(r);row['item']=json.loads(row.pop('payload'));return row

    def update_item(self,ident,item):
        clean=validate_item(item)
        with self.db:self.db.execute('UPDATE items SET payload=? WHERE id=?',(json.dumps(clean,ensure_ascii=False),ident))

    def own(self,ident,owned=True):
        with self.db:self.db.execute('UPDATE items SET owned=?,decision=? WHERE id=?',(int(owned),'keep' if owned else 'skip',ident))

    def decide(self,ident,decision):
        if decision not in ('keep','skip','pending'):raise ValueError('Невідоме рішення.')
        with self.db:self.db.execute('UPDATE items SET owned=?,decision=? WHERE id=?',(int(decision=='keep'),decision,ident))

    def trash_entry(self,kind,ident):
        """Reversible list deletion. Rune totals and screenshot files remain intact."""
        token={'items':[],'shots':[],'stamp':uid()}
        with self.db:
            if kind=='item':
                record=self.item(ident)
                if not record:return token
                token['items']=[ident];sid=record['shot_id']
                self.db.execute('UPDATE items SET deleted_at=? WHERE id=?',(token['stamp'],ident))
                if sid and not self.db.execute("SELECT 1 FROM items WHERE shot_id=? AND deleted_at=''",(sid,)).fetchone():token['shots']=[sid]
            elif kind=='shot':
                if not self.shot(ident):return token
                token['shots']=[ident]
                token['items']=[r['id'] for r in self.db.execute("SELECT id FROM items WHERE shot_id=? AND deleted_at=''",(ident,))]
                for item in token['items']:self.db.execute('UPDATE items SET deleted_at=? WHERE id=?',(token['stamp'],item))
            else:raise ValueError('Невідомий тип запису.')
            for sid in token['shots']:self.db.execute('UPDATE shots SET deleted_at=? WHERE id=?',(token['stamp'],sid))
        return token

    def restore_entries(self,token):
        with self.db:
            for table in ('shots','items'):
                for ident in token[table]:
                    self.db.execute(f"UPDATE {table} SET deleted_at='' WHERE id=? AND deleted_at=?",(ident,token['stamp']))

    def inventory(self,profile):
        return {r['name']:r['count'] for r in self.db.execute('SELECT * FROM runes WHERE profile=?',(profile,))}

    def set_runes(self,profile,counts,item_id=None):
        """Absolute quantities, not additions. Only supplied rune types are changed."""
        validate_runes(counts)
        if item_id:
            r=self.item(item_id)
            if not r or r['profile']!=profile:raise ValueError('Картка з іншого профілю.')
        with self.db:
            for name,count in counts.items():
                self.db.execute('INSERT OR REPLACE INTO runes VALUES (?,?,?)',(profile,name,count))
            if item_id:self.db.execute('INSERT OR REPLACE INTO rune_imports VALUES (?,?)',(item_id,now()))

    def apply_rune_snapshot(self,shot_id):
        """Idempotent partial replacement. Never erase unseen or concurrently edited runes."""
        shot=self.shot(shot_id)
        if not shot or shot['destination']!='runes':return 'not_runes'
        if self.db.execute('SELECT 1 FROM rune_updates WHERE shot_id=?',(shot_id,)).fetchone():return 'already_applied'
        records=[r for r in self.items(shot['profile']) if r['shot_id']==shot_id]
        if len(records)!=1:return 'review'
        if self.db.execute('SELECT 1 FROM rune_imports WHERE item_id=?',(records[0]['id'],)).fetchone():return 'already_applied'
        item=records[0]['item'];counts=item['rune_counts']
        if item['quality']!='rune' or not counts or item['confidence']!='high' or item['warnings']:
            return 'review'
        # A model must not erase a rune because it is absent from a partial screenshot.
        if any(n<=0 for n in counts.values()):return 'review'
        current=self.inventory(shot['profile']);baseline=json.loads(shot['rune_baseline'])
        if any(current.get(r,0)!=baseline.get(r,0) for r in counts):return 'conflict'
        with self.db:
            for rune,count in counts.items():
                self.db.execute('INSERT OR REPLACE INTO runes VALUES (?,?,?)',(shot['profile'],rune,count))
            self.db.execute('INSERT INTO rune_updates VALUES (?,?,?,?,?)',
                (shot_id,shot['profile'],json.dumps({r:current.get(r,0) for r in counts}),json.dumps(counts),now()))
            self.db.execute('INSERT OR REPLACE INTO rune_imports VALUES (?,?)',(records[0]['id'],now()))
        return 'applied'

    def backup(self,filename):
        target=Path(filename).resolve()
        # Back up a consistent SQLite snapshot, not a live WAL file.
        tmp=self.path/('backup-'+uid()+'.sqlite3')
        try:
            conn=sqlite3.connect(tmp);self.db.backup(conn);conn.close()
            with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                z.write(tmp,'collection.sqlite3')
                for p in (self.path/'screenshots').glob('*.png'):z.write(p,'screenshots/'+p.name)
                z.writestr('RESTORE.txt','Close Loot Companion. Replace collection.sqlite3 and screenshots in the application data directory with this backup. Keep a copy of the previous directory. API keys are never included.\n')
        finally:tmp.unlink(missing_ok=True)

    def close(self): self.db.close()
