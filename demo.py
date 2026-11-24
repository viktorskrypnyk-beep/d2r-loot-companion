"""Offline demo with explicit synthetic examples in a temporary collection."""
from pathlib import Path
import sys
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor,QFont
from app import MainWindow,STYLE,png_bytes,configure_app
from core import Store,blank_item,CATALOG

def sample(name,quality,stats=None):
    i=blank_item();i.update(name=name,canonical_name=name,quality=quality,base='Demo',
        identified=True,ethereal=False,sockets=0,verified=True,stats=stats or [],
        notes='Демонстраційний запис. Не імпортовано з гри.',location='ДЕМО · спільна скриня')
    return i

def seed(store,profile,run):
    def stat(key,label,value,unit=''):
        return dict(key=key,label=label,value=value,unit=unit,condition='intrinsic')
    old=sample('Демо-кільце','rare',[stat('all_res','Усі опори',15,'%'),stat('life','Життя',25)]);old['base']='Ring'
    store.add_manual(run,profile,old,owned=True)
    s=next(s for s in CATALOG['sets'] if s['name']=='Immortal King')
    for name in s['pieces'][:3]:
        i=sample(name,'set');i['set_name']=s['name'];store.add_manual(run,profile,i,owned=True)
    for name,quality,base in [('Angelic Halo','set','Ring'),('Raven Frost','unique','Ring'),('Annihilus','unique','Small Charm'),('Hellfire Torch','unique','Large Charm'),("Gheed’s Fortune",'unique','Grand Charm')]:
        item=sample(name,quality);item['base']=base;store.add_manual(run,profile,item,owned=True)
    store.set_runes(profile,{'Tal':2,'Thul':1,'Ort':1,'Amn':1,'Ral':2,'Tir':2,'Sol':1,'Shael':1,'Io':1,'Ber':1,'Mal':1,'Ist':1})
    new=sample('Демо-кільце','unique',[stat('all_res','Усі опори',20,'%'),stat('life','Життя',20)])
    new['base']='Ring'
    new['explanation']='Навчальний приклад компромісу: більше опорів, менше життя. Не реальна ігрова річ.'
    items=[new,sample(s['pieces'][3],'set'),sample('Демо-амулет','crafted'),sample('Демо-зброя','rare')]
    items[1]['set_name']=s['name']
    for n,i in enumerate(items):
        image=QImage(680,380,QImage.Format_RGB32);image.fill(QColor('#10151c'))
        p=QPainter(image);p.setPen(QColor('#e5bc73'));p.setFont(QFont('Sans',21));p.drawText(35,70,'ДЕМОНСТРАЦІЙНИЙ ЗНІМОК')
        p.setPen(QColor('#9cddaf' if i['quality']=='set' else '#d6e0e9'));p.setFont(QFont('Sans',17));p.drawText(35,135,i['name'])
        for j,st in enumerate(i['stats']):p.drawText(35,190+j*40,f'{st["label"]}: {st["value"]}{st["unit"]}')
        p.setFont(QFont('Sans',11));p.setPen(QColor('#95a6b7'));p.drawText(35,340,'Приклад інтерфейсу · це не результат AI-розпізнавання');p.end()
        sid,_=store.add_shot(png_bytes(image),run,profile);store.finish_shot(sid,[i])

def main():
    app=QApplication(sys.argv);configure_app(app)
    with tempfile.TemporaryDirectory(prefix='LootCompanion-demo-') as tmp:
        store=Store(tmp);win=MainWindow(store);seed(store,win.profile(),win.run_id);win.refresh_all()
        win.setWindowTitle('Loot Companion · ДЕМОНСТРАЦІЯ · окрема тимчасова колекція')
        win.message('ДЕМОНСТРАЦІЯ: вигадані приклади. Ваша основна колекція не використовується.');win.show()
        app.exec()

if __name__=='__main__':main()
