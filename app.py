"""Loot Companion — standalone desktop screenshot notebook, Ukrainian UI."""
from __future__ import annotations
import base64
import html
import json
import os
from pathlib import Path
import sys
import threading
import hashlib
import time
from datetime import datetime
import webbrowser

from PySide6.QtCore import Qt, QTimer, QObject, Signal, QByteArray, QBuffer, QIODevice, QSize, QRect
from PySide6.QtGui import QImage, QPixmap, QIcon, QColor, QPainter, QPen, QFont, QFontDatabase,QShortcut,QKeySequence
from PySide6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QPushButton,QComboBox,QCheckBox,QLineEdit,QTabWidget,QSplitter,QListWidget,
    QListWidgetItem,QTextBrowser,QFileDialog,QMessageBox,QDialog,QDialogButtonBox,
    QTableWidget,QTableWidgetItem,QSpinBox,QHeaderView,QGroupBox,QScrollArea,
    QAbstractItemView,QPlainTextEdit,QInputDialog,QSizePolicy,QGridLayout,QProgressBar
)
from core import (Store,CATALOG,QUALITIES,DIRECTIONS,blank_item,validate_item,
                  compare_items,same_family,rune_options,all_rune_options,norm,effective_advice,ADVICE_ACTIONS)
from vision import analyze, advise, test_connection, DEFAULT_MODEL, GeminiError, safe_text
from credentials import KeyStore
from artwork import Artwork,lookup
from localization import stat_uk
from hotkey import GlobalHotkey,DEFAULT_HOTKEY,HOTKEYS
from screen_capture import capture_active_monitor,foreground_window,return_to_window
from gallery import CollectionPanel,RuneTile,CardGrid,WordCard

def esc(x):return html.escape(str(x))
def png_bytes(image):
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly)
    image.save(buffer,'PNG');return bytes(data)
def button(text,callback):
    b=QPushButton(text);b.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Fixed);b.clicked.connect(callback);return b
def wrap(text):
    label=QLabel(text);label.setWordWrap(True);label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred);return label
def rich_browser():
    b=QTextBrowser();b.setOpenExternalLinks(True);b.document().setDefaultFont(QApplication.font())
    b.document().setDefaultStyleSheet('a {color:#8ec8ff;} p {line-height:135%;} li {line-height:130%;}')
    return b
def fill_table(table,rows):
    table.setRowCount(len(rows))
    for r,row in enumerate(rows):
        for c,value in enumerate(row):table.setItem(r,c,QTableWidgetItem(str(value)))
def make_table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.verticalHeader().setVisible(False);t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows);return t

STYLE='''
QWidget { background:#121820; color:#e2e8ef; }
QMainWindow, QDialog { background:#121820; }
QLabel#title { font-size:22pt; font-weight:700; color:#e5bc73; }
QLabel#subtitle { color:#95a6b7; font-size:10pt; }
QLabel#status { color:#8fd5be; padding:7px; background:#192c2b; border-radius:5px; }
QPushButton { background:#243343; border:1px solid #3b4d5e; padding:7px 10px; min-height:20px; border-radius:5px; }
QPushButton:hover { background:#30475c; border-color:#e5bc73; }
QPushButton:disabled { color:#65727f; }
QLineEdit,QComboBox,QSpinBox,QPlainTextEdit { background:#1a2430; border:1px solid #354456; padding:6px; border-radius:4px; min-height:20px; }
QTabWidget::pane { border:1px solid #2a3848; top:-1px; }
QTabBar::tab { background:#18212b; color:#97a8b9; padding:10px 16px; }
QTabBar::tab:selected { background:#24323f; color:#f1d099; border-bottom:2px solid #d6ae66; }
QListWidget,QTextBrowser,QTableWidget { background:#151f29; border:1px solid #2c3a49; border-radius:5px; }
QListWidget::item { padding:10px; border-bottom:1px solid #293543; }
QListWidget::item:selected { background:#2c4051; }
QListWidget#compactItems::item { padding:3px 6px; }
QListWidget#cardGallery { border:0; background:#121820; }
QListWidget#cardGallery::item { background:#1a2733; border:1px solid #33475b; border-radius:9px; padding:8px; }
QListWidget#cardGallery::item:hover { background:#263c4e; border-color:#e5bc73; }
QListWidget#cardGallery::item:selected { background:#30475c; border-color:#e5bc73; }
QPushButton#wordCard { background:#1a2733; border:1px solid #33475b; border-radius:9px; padding:0; }
QPushButton#wordCard:hover { background:#263c4e; border-color:#e5bc73; }
QToolButton { background:#30475c; border:0; border-radius:3px; color:#e5bc73; }
QHeaderView::section { background:#263442; color:#c6d5e3; border:0; padding:7px; }
QGroupBox { border:1px solid #334455; border-radius:5px; margin-top:13px; padding:15px; }
QGroupBox::title { subcontrol-origin:margin; left:12px; color:#d9b477; }
QCheckBox { spacing:8px; min-height:24px; }
QTextBrowser#apiInfo { background:#192c2b; border:1px solid #335749; padding:8px; }
QScrollArea { border:0; }
QLabel#runeNotice { color:#e5bc73; }
QProgressBar { border:0; background:#243343; border-radius:3px; }
QProgressBar::chunk { background:#e5bc73; border-radius:3px; }
QScrollBar:vertical { background:#17212c; width:12px; }
QScrollBar::handle:vertical { background:#415467; min-height:24px; border-radius:5px; }
'''

def configure_app(app):
    app.setStyle('Fusion')
    family='Segoe UI' if 'Segoe UI' in QFontDatabase.families() else 'DejaVu Sans'
    app.setFont(QFont(family,10));app.setStyleSheet(STYLE)


def fit_controls(widget):
    for cls in (QPushButton,QLineEdit,QComboBox,QSpinBox):
        for control in widget.findChildren(cls):
            if control.property('compact'):continue
            control.setMinimumHeight(max(control.sizeHint().height(),control.fontMetrics().height()+16))
            control.setSizePolicy(QSizePolicy.Expanding if cls==QLineEdit else QSizePolicy.Preferred,QSizePolicy.Fixed)

def activity_icon(state,frame=0):
    pix=QPixmap(32,36);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing)
    color='#e5bc73' if state not in ('error','empty') else '#ee998c'
    p.setPen(QPen(QColor(color),2))
    if state=='working':
        p.setPen(QPen(QColor('#354456'),3));p.drawEllipse(5,7,22,22)
        p.setPen(QPen(QColor(color),3));p.drawArc(5,7,22,22,-frame*30*16,230*16)
    elif state in ('needs_crop','cropping'):
        p.drawRect(7,9,18,18);p.drawLine(3,9,29,9);p.drawLine(7,4,7,32)
    elif state=='done':
        p.setPen(QPen(QColor('#8fd5be'),3));p.drawLine(6,18,13,25);p.drawLine(13,25,27,11)
    elif state in ('error','empty','waiting_api'):
        p.drawEllipse(5,7,22,22);p.drawLine(16,12,16,21);p.drawPoint(16,26)
    else:
        p.drawEllipse(5,7,22,22);p.drawLine(16,11,16,18);p.drawLine(16,18,22,21)
    p.end();return QIcon(pix)


class CropCanvas(QLabel):
    selectionChanged=Signal()
    def __init__(self,image):
        super().__init__();self.image=image;self.start=None;self.end=None
        self.setMinimumSize(320,200);self.setMouseTracking(True);self.setCursor(Qt.CrossCursor)
    def display_rect(self):
        size=self.image.size();size.scale(self.size(),Qt.KeepAspectRatio)
        return QRect((self.width()-size.width())//2,(self.height()-size.height())//2,size.width(),size.height())
    def paintEvent(self,event):
        p=QPainter(self);rect=self.display_rect();p.drawImage(rect,self.image)
        if self.start is not None and self.end is not None:
            p.setPen(QPen(QColor('#e5bc73'),2));p.drawRect(QRect(self.start,self.end).normalized().intersected(rect))
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.start=event.position().toPoint();self.end=self.start;self.update();self.selectionChanged.emit()
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.LeftButton:self.end=event.position().toPoint();self.update();self.selectionChanged.emit()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.start is not None:
            self.end=event.position().toPoint();self.update();self.selectionChanged.emit()
    def select_all(self):
        rect=self.display_rect();self.start=rect.topLeft();self.end=rect.bottomRight();self.update();self.selectionChanged.emit()
    def selection(self):
        if self.start is None or self.end is None:return None
        display=self.display_rect();selection=QRect(self.start,self.end).normalized().intersected(display)
        if selection.width()<10 or selection.height()<10:return None
        x=int((selection.x()-display.x())*self.image.width()/display.width())
        y=int((selection.y()-display.y())*self.image.height()/display.height())
        w=int(selection.width()*self.image.width()/display.width());h=int(selection.height()*self.image.height()/display.height())
        return [x,y,w,h]

class CropDialog(QDialog):
    def __init__(self,image,parent,capture_mode=False):
        super().__init__(parent);self.capture_next=False;self.setWindowTitle('Обріжте знімок → розпізнавання')
        if capture_mode:self.setWindowFlag(Qt.WindowStaysOnTopHint,True)
        screen=parent.screen().availableGeometry();self.resize(min(1050,screen.width()-40),min(700,screen.height()-60))
        layout=QVBoxLayout(self);layout.addWidget(wrap('Виділіть мишкою предмет разом з усім його описом або область із рунами. Після підтвердження область піде на розпізнавання; оригінал залишиться збереженим.'))
        self.canvas=CropCanvas(image);layout.addWidget(self.canvas,1)
        self.preset=QCheckBox('Застосовувати цю область до наступних імпортів файлів');layout.addWidget(self.preset);self.preset.setVisible(not capture_mode)
        row=QHBoxLayout();row.addWidget(button('Весь знімок',self.canvas.select_all));row.addStretch()
        bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.submit=bb.button(QDialogButtonBox.Ok);self.submit.setText('Вирізати й розпізнати');self.submit.setEnabled(False)
        bb.button(QDialogButtonBox.Cancel).setText('Не надсилати')
        self.next_button=button('У чергу й наступний',self.accept_next);self.next_button.setEnabled(False)
        self.next_button.setToolTip('Розпізнавати вибрану область у фоні й повернутися до гри для наступного предмета.')
        row.addWidget(self.next_button)
        self.canvas.selectionChanged.connect(self.selection_changed)
        bb.accepted.connect(self.accept);bb.rejected.connect(self.reject);layout.addLayout(row);layout.addWidget(bb)
    def accept(self):
        if self.canvas.selection():super().accept()
    def selection_changed(self):
        valid=bool(self.canvas.selection());self.submit.setEnabled(valid);self.next_button.setEnabled(valid)
    def accept_next(self):
        if self.canvas.selection():self.capture_next=True;self.accept()

class ItemEditor(QDialog):
    def __init__(self,item,parent):
        super().__init__(parent);self.value=dict(item);self.setWindowTitle('Перевірка картки предмета');self.resize(1050,750)
        layout=QVBoxLayout(self);form=QFormLayout();self.fields={}
        for key,label in [('name','Назва на екрані'),('canonical_name','Англійська назва'),('base','Базовий предмет'),
                          ('set_name','Назва комплекту'),('location','Де зберігається'),('notes','Мої нотатки')]:
            edit=QLineEdit(item.get(key,''));self.fields[key]=edit;form.addRow(label,edit)
        self.quality=QComboBox()
        for key,label in QUALITIES.items():self.quality.addItem(label,key)
        self.quality.setCurrentIndex(self.quality.findData(item['quality']));form.addRow('Категорія',self.quality)
        self.identified=QComboBox();self.ethereal=QComboBox()
        for box,key in [(self.identified,'identified'),(self.ethereal,'ethereal')]:
            box.addItem('Невідомо',None);box.addItem('Так',True);box.addItem('Ні',False)
            box.setCurrentIndex(0 if item.get(key) is None else (1 if item[key] else 2))
        form.addRow('Предмет ідентифікований',self.identified);form.addRow('Ефірний',self.ethereal)
        self.sockets=QSpinBox();self.sockets.setRange(-1,6);self.sockets.setSpecialValueText('Невідомо');self.sockets.setValue(item.get('sockets') if item.get('sockets') is not None else -1)
        form.addRow('Гнізда',self.sockets);layout.addLayout(form)
        layout.addWidget(wrap('Параметри: key — назва для зіставлення, intrinsic — звичайний параметр; set_bonus / level_scaled — умовний. Значення можна виправити подвійним кліком.'))
        self.stats=make_table(['Ключ','Назва','Значення','Одиниці','Умова'])
        self.stats.setEditTriggers(QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed)
        fill_table(self.stats,[[s['key'],s['label'],'' if s['value'] is None else s['value'],s['unit'],s['condition']] for s in item['stats']]);layout.addWidget(self.stats,1)
        row=QHBoxLayout();row.addWidget(button('+ Параметр',self.add_stat));row.addWidget(button('Прибрати рядок',lambda:self.stats.removeRow(self.stats.currentRow())));row.addStretch();layout.addLayout(row)
        self.verified=QCheckBox('Я перевірив назву та всі розпізнані параметри за скриншотом');self.verified.setChecked(item.get('verified',False));layout.addWidget(self.verified)
        bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);bb.accepted.connect(self.save);bb.rejected.connect(self.reject);layout.addWidget(bb)
    def add_stat(self):
        r=self.stats.rowCount();self.stats.insertRow(r)
        for c,x in enumerate(['','', '', '', 'intrinsic']):self.stats.setItem(r,c,QTableWidgetItem(x))
    def save(self):
        try:
            value=dict(self.value);value.update({k:w.text().strip() for k,w in self.fields.items()})
            value.update(quality=self.quality.currentData(),ethereal=self.ethereal.currentData(),identified=self.identified.currentData(),
                         sockets=None if self.sockets.value()<0 else self.sockets.value(),verified=self.verified.isChecked())
            stats=[]
            for r in range(self.stats.rowCount()):
                cells=[self.stats.item(r,c).text().strip() if self.stats.item(r,c) else '' for c in range(5)]
                if not cells[0]:raise ValueError('Укажіть ключ кожного параметра.')
                stats.append(dict(key=cells[0],label=cells[1] or cells[0],value=float(cells[2].replace(',','.')) if cells[2] else None,unit=cells[3],condition=cells[4] or 'intrinsic'))
            value['stats']=stats
            if not value['name']:raise ValueError('Укажіть назву предмета.')
            self.value=validate_item(value);self.accept()
        except ValueError as e:QMessageBox.warning(self,'Перевірте дані',str(e))

class Signals(QObject):
    result=Signal(str,object,object)
    api_result=Signal(object)
    advice_result=Signal(str,object,object)

class ItemPanel(QWidget):
    def __init__(self,window,kind,detail_only=False):
        super().__init__();self.window=window;self.kind=kind;self.selected=None
        layout=QVBoxLayout(self);filters=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Знайти назву, тип або місце зберігання…');self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search,1)
        self.category=QComboBox();self.category.addItem('Усі категорії','')
        for key,label in QUALITIES.items():self.category.addItem(label,key)
        self.category.currentIndexChanged.connect(self.refresh);filters.addWidget(self.category)
        if kind=='history':
            self.runs=QComboBox();self.runs.currentIndexChanged.connect(self.refresh);filters.addWidget(self.runs)
        layout.addLayout(filters)
        split=QSplitter();layout.addWidget(split,1)
        left=QWidget();ll=QVBoxLayout(left);ll.setContentsMargins(0,0,0,0)
        self.list=QListWidget();self.list.setObjectName('compactItems');self.list.setIconSize(QSize(32,36));self.list.setUniformItemSizes(True);self.list.setWordWrap(False);self.list.currentItemChanged.connect(self.selection_changed);ll.addWidget(self.list,1)
        hint=QLabel('Delete — видалити · Ctrl+Z — повернути');hint.setObjectName('subtitle');ll.addWidget(hint);split.addWidget(left)
        self.delete_shortcut=QShortcut(QKeySequence(Qt.Key_Delete),self.list);self.delete_shortcut.setContext(Qt.WidgetShortcut);self.delete_shortcut.setAutoRepeat(False);self.delete_shortcut.activated.connect(self.delete_selected)
        self.undo_shortcut=QShortcut(QKeySequence('Ctrl+Z'),self.list);self.undo_shortcut.setContext(Qt.WidgetShortcut);self.undo_shortcut.setAutoRepeat(False);self.undo_shortcut.activated.connect(self.window.undo_delete)
        right=QWidget();rl=QVBoxLayout(right);hero=QHBoxLayout()
        self.preview=QLabel();self.preview.setAlignment(Qt.AlignCenter);self.preview.setFixedSize(110,120);hero.addWidget(self.preview)
        self.art_caption=wrap('Наведіть на предмет у грі й зробіть знімок');self.art_caption.setOpenExternalLinks(True);hero.addWidget(self.art_caption,1)
        self.source_button=button('Скриншот / оригінал',self.show_source);hero.addWidget(self.source_button);rl.addLayout(hero)
        self.detail=rich_browser();rl.addWidget(self.detail,1)
        actions=QHBoxLayout();self.edit=button('Перевірити',self.edit_item);self.keep=button('До моїх речей',self.toggle_owned)
        self.compare=button('Порівняти',self.compare_item);self.scan=button('Розпізнати',self.scan_item);self.skip=button('Не залишати',self.skip_item)
        for b in [self.edit,self.keep,self.skip,self.compare,self.scan]:actions.addWidget(b)
        rl.addLayout(actions)
        row=QHBoxLayout();self.crop=button('Обрізати знімок',self.crop_shot);self.rune=button('Перенести руни',self.import_runes);self.copy=button('Окремий екземпляр',self.copy_item)
        for b in [self.crop,self.rune,self.copy]:row.addWidget(b)
        if kind=='run':
            self.new_run_button=button('Новий забіг',window.new_run);row.addWidget(self.new_run_button)
        rl.addLayout(row);split.addWidget(right);split.setSizes([300,850]);self.set_empty()
        if detail_only:
            left.hide();self.search.hide();self.category.hide();layout.setContentsMargins(0,0,0,0)
    def set_empty(self):
        self.detail.setHtml('<h2>Тут збиратимуться всі знахідки</h2><p>Кожен скриншот — окрема картка. Новий знімок не замінює попередні.</p><p>Зображення зберігається відразу. Для автоматичного розпізнавання підключіть API у налаштуваннях; також можна заповнювати картки вручну.</p>')
        for b in [self.edit,self.keep,self.skip,self.compare,self.scan,self.crop,self.rune,self.copy]:b.setEnabled(False)
    def refresh_runs(self):
        if self.kind!='history':return
        chosen=self.runs.currentData();self.runs.blockSignals(True);self.runs.clear();self.runs.addItem('Уся історія',None)
        for r in self.window.store.runs(self.window.profile()):self.runs.addItem(r['name'],r['id'])
        idx=self.runs.findData(chosen);self.runs.setCurrentIndex(max(0,idx));self.runs.blockSignals(False)
    def refresh(self,*args):
        if not hasattr(self,'list'):return
        selected=self.selected;self.list.blockSignals(True);self.list.clear()
        win=self.window;profile=win.profile();run_id=win.run_id if self.kind=='run' else (self.runs.currentData() if self.kind=='history' else None)
        items=win.store.items(profile,run_id,owned=self.kind=='owned');shots={s['id']:s for s in win.store.shots(profile,run_id)}
        text=self.search.text().casefold();quality=self.category.currentData();used=set();selected_row=None
        for record in items:
            i=record['item'];used.add(record['shot_id'])
            if self.kind=='run' and record['origin']!='run':continue
            if quality and i['quality']!=quality:continue
            if text and text not in ' '.join(str(i.get(k,'')) for k in ['name','canonical_name','base','location','notes']).casefold():continue
            title=i['name'] or i['canonical_name'] or 'Без назви'
            badge='✓ У колекції' if record['owned'] else ('Не залишено · в історії' if record['decision']=='skip' else 'Залишити цю річ?')
            verified='перевірено' if i['verified'] else 'перевірте цифри'
            entry=QListWidgetItem(('✓ ' if record['shot_id'] else '')+title);entry.setSizeHint(QSize(0,44))
            entry.setToolTip(f'{title}\n{QUALITIES[i["quality"]]} · {badge}\n{verified}')
            entry.setData(Qt.UserRole,('item',record['id']))
            colors={'set':'#76cf91','unique':'#e4bd74','crafted':'#f2a36b','rare':'#e4d86f','magic':'#8faef1','rune':'#cdb6f1'}
            entry.setForeground(QColor(colors.get(i['quality'],'#d4e0e9')))
            entry.setIcon(win.art.icon(i))
            self.list.addItem(entry)
            if entry.data(Qt.UserRole)==selected:selected_row=entry
        if not text and not quality:
            for sid,s in shots.items():
                if sid in used:continue
                if self.kind=='owned' and s['destination'] not in ('owned','runes'):continue
                if self.kind=='run' and s['destination']!='run':continue
                if self.window.store.db.execute('SELECT 1 FROM items WHERE shot_id=?',(sid,)).fetchone():continue
                label,state=win.shot_progress(s)
                entry=QListWidgetItem(label);entry.setSizeHint(QSize(0,44))
                entry.setToolTip(s.get('error','') or s.get('capture_note',''))
                entry.setData(Qt.UserRole,('shot',sid));entry.setData(Qt.UserRole+1,s);entry.setIcon(activity_icon(state,win.progress_frame));self.list.addItem(entry)
                if entry.data(Qt.UserRole)==selected:selected_row=entry
        self.list.blockSignals(False)
        if selected_row:self.list.setCurrentItem(selected_row)
        elif self.list.count():self.list.setCurrentRow(0)
        else:self.selected=None;self.preview.clear();self.art_caption.setText('Зробіть скриншот предмета');self.source_button.setEnabled(False);self.set_empty()
    def record(self):
        return self.window.store.item(self.selected[1]) if self.selected and self.selected[0]=='item' else None
    def delete_selected(self):
        entry=self.list.currentItem()
        if entry:self.window.delete_entry(entry.data(Qt.UserRole),self)
    def current_shot(self):
        if not self.selected:return None
        if self.selected[0]=='shot':return self.window.store.shot(self.selected[1])
        r=self.record();return self.window.store.shot(r['shot_id']) if r and r['shot_id'] else None
    def selection_changed(self,current,previous=None):
        if not current:return
        self.selected=current.data(Qt.UserRole);record=self.record();shot=self.current_shot()
        self.preview.clear();self.source_button.setEnabled(bool(shot));self.show_art(record)
        busy=bool(shot and (shot['id']==self.window.active or shot['id'] in self.window.queue))
        self.crop.setEnabled(bool(shot) and not busy)
        self.scan.setText('Оновити пораду' if record else ('Обрізати й розпізнати' if shot and shot['status']=='needs_crop' else 'Розпізнати'))
        self.scan.setEnabled(not self.window.advice_active if record else bool(shot) and not busy and shot['status']!='cropped')
        self.edit.setEnabled(not busy);self.keep.setEnabled(bool(record));self.skip.setEnabled(bool(record and not record['owned'] and record['decision']!='skip'));self.compare.setEnabled(bool(record));self.copy.setEnabled(bool(record));self.rune.setEnabled(bool(record and record['item']['rune_counts']))
        if not record:
            self._progress_detail=None;self.update_progress();return
        i=record['item'];self.keep.setText('Прибрати з колекції' if record['owned'] else 'Залишити ✓')
        stats=''.join(f'<tr><td>{esc(s["label"])}</td><td><b>{esc(s["value"] if s["value"] is not None else "?")}{esc(s["unit"])}</b></td><td>{esc(s["condition"])}</td></tr>' for s in i['stats'])
        builds=''.join('<li>'+esc(s)+'</li>' for s in i['builds']) or '<li>Поки не визначено.</li>'
        warnings=''.join('<li>'+esc(s)+'</li>' for s in i['warnings'])
        same=[r for r in self.window.store.items(self.window.profile(),owned=True) if r['id']!=record['id'] and same_family(i,r['item'])]
        content=f'<h2>{esc(i["name"])}</h2><p>{esc(i["canonical_name"])} · {esc(i["base"])}</p><p><b>{"Перевірено користувачем" if i["verified"] else "Розпізнане: перевірте цифри"}</b> · Схожих у колекції: {len(same)}</p>'
        advice=effective_advice(i);color={'keep':'#8fd5be','trade':'#e5bc73','vendor':'#e7ad89','review':'#f0d288'}[advice['action']]
        content+='<h2 style="color:'+color+'">'+ADVICE_ACTIONS[advice['action']]+'</h2><p>'+esc(advice['reason'])+'</p><p><i>Рекомендація AI за прочитаними властивостями. Дії в грі виконуєте ви.</i></p>'
        for key,title in [('strengths','Сильні сторони'),('weaknesses','Недоліки й обмеження'),('uses','Кому та для чого підійде')]:
            if advice[key]:content+='<h3>'+title+'</h3><ul>'+''.join('<li>'+esc(s)+'</li>' for s in advice[key])+'</ul>'
        if advice['trade_note']:content+='<h3>Перед продажем</h3><p>'+esc(advice['trade_note'])+'</p>'
        if record['decision']=='pending':content+='<p style="color:#e5bc73"><b>Залишиш цю річ?</b> Натисни «Залишити ✓» — вона автоматично з’явиться у відповідній категорії колекції.</p>'
        if same:
            content+='<h3>Автопорівняння з колекцією</h3>'
            for existing in same[:3]:
                result=compare_items(i,existing['item'])
                content+='<p><b>'+esc(existing['item']['location'] or existing['id'][:6])+': '+esc(result['verdict'])+'</b><br>'
                changes=[f'{x["label"]}: {x["old"]} → {x["new"]}{x["unit"]}' for x in result['rows'] if x['delta'] is not None and x['delta']!=0]
                content+=esc('; '.join(changes[:6]) or 'Немає зіставлених змін.')+'</p>'
            content+='<p>Повна таблиця та застереження — кнопка «Порівняти».</p>'
        if i['set_name']:
            content+='<p>Комплект: <b>'+esc(i['set_name'])+'</b>.</p>'
        if i['rune_counts']:content+='<p>Видимі руни: '+esc(', '.join(f'{k} × {v}' for k,v in i['rune_counts'].items()))+'</p>'
        content+='<table cellspacing="8">'+stats+'</table><h3>Можливе використання</h3><p>Підказки AI; потребують перевірки для вашої версії гри.</p><ul>'+builds+'</ul><h3>Оцінка предмета</h3><p>'+esc(i['explanation']).replace('\n','<br>')+'</p><ul>'+warnings+'</ul>'
        content+='<h3>Ринок</h3><p>Ladder: немає перевіреної ціни<br>Non-Ladder: немає перевіреної ціни</p><p>Автоматичне джерело цін ще не підключене. Перевіряйте той самий режим і близькі параметри.</p><p><a href="https://diablo2.io/pricecheck.php">Перевірити на diablo2.io</a> · <a href="https://traderie.com/diablo2resurrected">Traderie</a></p>'
        content+='<p>Місце: '+esc(i['location'] or 'не вказано')+'</p><p>'+esc(i['notes'])+'</p>'
        self.detail.setHtml(content)
    def show_art(self,record):
        if not record:
            self.preview.setPixmap(self.window.art.icon({}).pixmap(48,48));self.art_caption.setText('Зображення предмета з’явиться після розпізнавання назви.');return
        item=record['item'];entry=lookup(item);path=self.window.art.path(entry)
        if path:self.preview.setPixmap(QPixmap(str(path)).scaled(100,112,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:self.preview.setPixmap(self.window.art.icon(item).pixmap(40,40))
        if entry:
            caption='Зображення базового предмета; вигляд вашого екземпляра може відрізнятися.' if entry['kind']=='base' else 'Ілюстрація предмета з довідника.'
            if not path:caption+=' Зображення ще не завантажено.'
            self.art_caption.setText('<b>'+esc(entry['name'])+'</b><br>'+caption+'<br><a style="color:#8ec8ff" href="'+esc(entry['source'])+'">Blizzard · класична графіка Diablo II</a>')
        else:self.art_caption.setText('Точного зображення у довіднику не знайдено. Переглянути свій предмет можна на збереженому скриншоті.')
    def show_source(self):
        shot=self.current_shot()
        if not shot:return
        dialog=QDialog(self);dialog.setWindowTitle('Збережений скриншот · перевірка предмета');dialog.resize(1050,760)
        layout=QVBoxLayout(dialog);tabs=QTabWidget();layout.addWidget(tabs,1)
        for title,path in [('Розпізнаний знімок',shot['path']),('Повний оригінал',shot.get('source_path',''))]:
            if not path:continue
            scroll=QScrollArea();label=QLabel();label.setPixmap(QPixmap(str(self.window.store.path/path)));scroll.setWidget(label);tabs.addTab(scroll,title)
        layout.addWidget(button('Закрити',dialog.accept));dialog.exec()
    def edit_item(self):
        record=self.record();dialog=ItemEditor(record['item'] if record else blank_item(),self)
        if dialog.exec():
            if record:self.window.store.update_item(record['id'],dialog.value)
            else:
                shot=self.current_shot()
                if shot:self.window.store.finish_shot(shot['id'],[dialog.value])
            self.window.refresh_all()
    def toggle_owned(self):
        r=self.record()
        if r:self.window.store.own(r['id'],not r['owned']);self.window.refresh_all()
    def skip_item(self):
        r=self.record()
        if r:self.window.store.decide(r['id'],'skip');self.window.refresh_all()
    def copy_item(self):
        r=self.record()
        if not r:return
        if QMessageBox.question(self,'Окремий фізичний предмет','Створити ще один екземпляр із такими самими даними? Використовуйте це лише для іншої речі, а не повторного скриншота.')==QMessageBox.Yes:
            self.window.store.add_manual(self.window.run_id,self.window.profile(),r['item'],owned=True);self.window.refresh_all()
    def compare_item(self):
        r=self.record()
        candidates=[x for x in self.window.store.items(self.window.profile(),owned=True) if x['id']!=r['id'] and same_family(r['item'],x['item'])]
        if not candidates:QMessageBox.information(self,'Порівняння','У цьому профілі ще немає схожої речі в колекції. Додайте й перевірте попередній екземпляр.');return
        labels=[f'{x["item"]["name"]} · {x["item"]["location"] or "без місця"} · {x["id"][:6]}' for x in candidates]
        choice,ok=QInputDialog.getItem(self,'Порівняння','З яким власним екземпляром порівняти?',labels,0,False)
        if not ok:return
        result=compare_items(r['item'],candidates[labels.index(choice)]['item'])
        d=QDialog(self);d.setWindowTitle('Знайдена річ і власний екземпляр');d.resize(1000,600);l=QVBoxLayout(d);l.addWidget(wrap(result['verdict']))
        t=make_table(['Параметр','Моя річ','Знахідка','Різниця','Висновок']);fill_table(t,[[s['label'],s['old'] if s['old'] is not None else '?',s['new'] if s['new'] is not None else '?',f'{s["delta"]:+g}{s["unit"]}' if s['delta'] is not None else '—',s['verdict']] for s in result['rows']]);l.addWidget(t)
        l.addWidget(wrap('\n'.join(result['caveats'])+'\nЦе зіставлення параметрів, а не гарантований приріст сили білда чи ринкової ціни.'));l.addWidget(button('Закрити',d.accept));d.exec()
    def scan_item(self):
        if self.record():self.window.refresh_advice(self.record());return
        s=self.current_shot()
        if s:self.window.enqueue(s['id'],explicit=True)
    def update_progress(self):
        for n in range(self.list.count()):
            entry=self.list.item(n);shot=entry.data(Qt.UserRole+1)
            if not shot:continue
            label,state=self.window.shot_progress(shot);entry.setText(label);icon=activity_icon(state,self.window.progress_frame);entry.setIcon(icon)
            if entry.data(Qt.UserRole)==self.selected:
                self.preview.setPixmap(icon.pixmap(56,64));self.art_caption.setText(label)
                detail=(label,shot.get('error',''),shot.get('capture_note',''))
                if detail!=getattr(self,'_progress_detail',None):
                    self._progress_detail=detail
                    hint='Google аналізує вибрану область. Можна зробити наступний знімок; результат з’явиться тут.' if state=='working' else ('Натисніть «Обрізати й розпізнати», щоб продовжити. До підтвердження знімок не надсилається.' if state in ('needs_crop','cropping') else 'Оригінал збережено. Після завершення тут з’являться назва, зображення й рекомендація.')
                    self.detail.setHtml('<h2>'+esc(label)+'</h2><p>'+esc(shot.get('error',''))+'</p><p>'+esc(hint)+'</p><p>'+esc(shot.get('capture_note',''))+'</p>')
    def crop_shot(self):
        s=self.current_shot()
        if not s:return
        if not self.record():self.window.request_crop(s['id']);return
        image=QImage(str(self.window.store.path/(s.get('source_path') or s['path'])));d=CropDialog(image,self)
        if d.exec():
            rect=d.canvas.selection()
            if not rect:QMessageBox.warning(self,'Область','Виділіть прямокутник.');return
            if d.preset.isChecked():self.window.store.set_setting('rune_crop' if s['destination']=='runes' else 'crop',dict(size=[image.width(),image.height()],rect=rect))
            ident,created=self.window.store.add_shot(png_bytes(image.copy(*rect)),s['run_id'],s['profile'],destination=s['destination'])
            if not self.record():self.window.store.shot_status(s['id'],'cropped')
            self.window.refresh_all()
            if created:self.window.enqueue(ident,explicit=True)
            if d.capture_next:QTimer.singleShot(100,self.window,lambda:self.window.wait_for_next_capture(None))
    def import_runes(self):
        r=self.record()
        if not r:return
        counts=r['item']['rune_counts'];d=QDialog(self);d.setWindowTitle('Перевірте запас рун');d.resize(600,650);l=QVBoxLayout(d)
        l.addWidget(wrap('Це нова ЗАГАЛЬНА кількість перелічених рун у цьому профілі. Вона замінить попередні значення, а не додасться до них. Якщо на скриншоті лише частина запасу, виправте кількість з урахуванням решти. Інші типи рун не зміняться.'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);inside=QWidget();form=QFormLayout(inside);boxes={}
        for name,count in counts.items():
            box=QSpinBox();box.setRange(0,999999);box.setValue(count);boxes[name]=box;form.addRow(name,box)
        scroll.setWidget(inside);l.addWidget(scroll,1);bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);bb.accepted.connect(d.accept);bb.rejected.connect(d.reject);l.addWidget(bb);fit_controls(d)
        if d.exec():
            self.window.store.set_runes(r['profile'],{n:b.value() for n,b in boxes.items()},r['id']);self.window.refresh_all()

class RunesPanel(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.boxes={};self.tiles={};self.words=[];self.word_dialog=None
        layout=QVBoxLayout(self)
        strip=QScrollArea();strip.setObjectName('runeStrip');strip.setWidgetResizable(True);strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);strip.setFixedHeight(116)
        inside=QWidget();rr=QHBoxLayout(inside);rr.setContentsMargins(4,2,4,2);rr.setSpacing(2)
        for rune in CATALOG['runes']:
            tile=RuneTile(window.art,rune,self.save_rune);self.tiles[rune]=tile;self.boxes[rune]=tile.count;rr.addWidget(tile)
        rr.addStretch();strip.setWidget(inside);layout.addWidget(strip)
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Знайти рунне слово…');self.search.textChanged.connect(self.refresh_words);row.addWidget(self.search,1)
        self.only_ready=QCheckBox('Рун вистачає');self.only_ready.toggled.connect(self.refresh_words);row.addWidget(self.only_ready)
        self.only_edition=QCheckBox('Лише моя версія гри');self.only_edition.toggled.connect(self.refresh_words);row.addWidget(self.only_edition)
        self.counter=QLabel('');row.addWidget(self.counter);layout.addLayout(row)
        self.word_grid=CardGrid();layout.addWidget(self.word_grid,1)
        row=QHBoxLayout();self.import_button=button('Імпорт рун',lambda:self.window.import_files(destination='runes'));row.addWidget(self.import_button)
        self.shots=QComboBox();self.shots.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.shots.setMinimumContentsLength(14);self.shots.currentIndexChanged.connect(self.show_snapshot);row.addWidget(self.shots,1)
        self.scan_button=button('Розпізнати',self.scan_selected);self.crop_button=button('Обрізати',self.crop_selected);self.review_button=button('Перевірити кількість',self.review_runes)
        for b in (self.scan_button,self.crop_button,self.review_button):row.addWidget(b)
        layout.addLayout(row);self.notice=wrap('');self.notice.setObjectName('runeNotice');layout.addWidget(self.notice)
        self.detail=rich_browser()
    def refresh(self):
        inv=self.window.store.inventory(self.window.profile())
        for rune,box in self.boxes.items():
            self.tiles[rune].set_count(inv.get(rune,0))
        selected=self.shots.currentData();self.shots.blockSignals(True);self.shots.clear()
        for shot in reversed(self.window.store.shots(self.window.profile())):
            if shot['destination']!='runes':continue
            label,state=self.window.shot_progress(shot)
            self.shots.addItem(activity_icon(state),label,shot['id']);self.shots.setItemData(self.shots.count()-1,shot,Qt.UserRole+1)
        self.shots.setCurrentIndex(max(0,self.shots.findData(selected)));self.shots.blockSignals(False)
        self.show_snapshot();self.refresh_words()
    def show_snapshot(self,*args):
        sid=self.shots.currentData();shot=self.window.store.shot(sid) if sid else None
        busy=sid==self.window.active or sid in self.window.queue
        self.scan_button.setEnabled(bool(shot and not busy and shot['status'] in ('needs_crop','waiting_api','pending','error','empty')))
        self.scan_button.setText('Обрізати й розпізнати' if shot and shot['status']=='needs_crop' else 'Розпізнати')
        self.crop_button.setEnabled(bool(shot and not busy and shot['status']!='done'))
        records=[r for r in self.window.store.items(self.window.profile()) if r['shot_id']==sid] if sid else []
        self.review_button.setEnabled(bool(records and records[0]['item']['rune_counts']))
        if not shot:
            self.notice.setText('Знімок → обрізання → запас рун. «+» додає вручну; відсутні на знімку руни не обнуляються.');return
        applied=self.window.store.db.execute('SELECT 1 FROM rune_updates WHERE shot_id=?',(sid,)).fetchone()
        if not applied and records:
            applied=self.window.store.db.execute('SELECT 1 FROM rune_imports WHERE item_id=?',(records[0]['id'],)).fetchone()
        if applied:self.notice.setText('✓ Цей знімок уже застосовано. Повторне розпізнавання не додасть руни вдруге. Перевірте загальну кількість, якщо знято лише частину запасу.')
        elif shot['error']:self.notice.setText(shot['error'])
        elif records and records[0]['item']['rune_counts']:self.notice.setText('Кількості прочитано, але потрібна перевірка. Натисніть «Перевірити кількість зі знімка». Попередній запас збережено.')
        elif records:self.notice.setText('Назви або кількість рун не вдалося прочитати. Обріжте знімок або імпортуйте чіткіший. Попередній запас збережено.')
        else:self.notice.setText('Знімок збережено. Після впевненого розпізнавання кількість оновиться автоматично; нечіткі назви й числа потребують перевірки.')
    def update_progress(self):
        if not hasattr(self,'shots'):return
        for n in range(self.shots.count()):
            shot=self.shots.itemData(n,Qt.UserRole+1)
            if not shot:continue
            label,state=self.window.shot_progress(shot)
            self.shots.setItemText(n,label);self.shots.setItemIcon(n,activity_icon(state,self.window.progress_frame))
            if n==self.shots.currentIndex() and state in ('working','pending','needs_crop','cropping','waiting_api'):
                self.notice.setText(label+(' · '+shot['error'] if shot['error'] else ''))
    def scan_selected(self):
        if self.shots.currentData():self.window.enqueue(self.shots.currentData(),explicit=True)
    def crop_selected(self):
        if self.shots.currentData():
            panel=self.window.history_panel;panel.selected=('shot',self.shots.currentData());panel.crop_shot()
    def review_runes(self):
        sid=self.shots.currentData()
        records=[r for r in self.window.store.items(self.window.profile()) if r['shot_id']==sid]
        if records:
            panel=self.window.history_panel;panel.selected=('item',records[0]['id']);panel.import_runes()
    def save_rune(self,rune,count):
        self.window.store.set_runes(self.window.profile(),{rune:count});self.tiles[rune].set_count(count);self.refresh_words()
        self.window.collection_panel.refresh()
        self.window.message('Кількість рун збережено автоматично.')
    def save(self):
        self.window.store.set_runes(self.window.profile(),{r:b.value() for r,b in self.boxes.items()});self.refresh_words();self.window.message('Запас рун збережено.')
    def refresh_words(self,*args):
        if not hasattr(self,'word_grid'):return
        inventory=self.window.store.inventory(self.window.profile());text=self.search.text().casefold()
        signature=(tuple(sorted(inventory.items())),self.window.mode.currentText(),self.window.era.currentText(),text,self.only_ready.isChecked(),self.only_edition.isChecked())
        if signature==getattr(self,'_words_signature',None):return
        self._words_signature=signature
        words=all_rune_options(inventory,self.window.mode.currentText(),self.window.era.currentText())
        self.words=[w for w in words if (not text or text in w['name'].casefold()) and (not self.only_ready.isChecked() or w['runes_ready']) and (not self.only_edition.isChecked() or w['edition_available'])]
        pos=self.word_grid.verticalScrollBar().value()
        self.word_grid.set_cards([WordCard(word,self.window.art,inventory,lambda checked=False,n=n:self.show_word(n)) for n,word in enumerate(self.words)])
        self.counter.setText(f'{len(self.words)} / {len(words)} слів')
        QTimer.singleShot(0,self.word_grid,lambda:self.word_grid.verticalScrollBar().setValue(pos))
    def show_word(self,index):
        if not 0<=index<len(self.words):return
        w=self.words[index]
        content=f'<h2>{esc(w["name"])}</h2><p><b>{esc(" → ".join(w["runes"]))}</b></p><p>Потрібно гнізд: {w["sockets"]}<br>База: {esc(w["bases"])}</p>'
        content+='<p>'+('Рун вистачає. Перевірте базу перед створенням.' if w['runes_ready'] else 'Не вистачає: '+esc(', '.join(f'{r} × {n}' for r,n in w['missing'].items())))+'</p>'
        if w['mode_check']:content+='<p><b>Доступність створення у поточному режимі ще не перевірена.</b> Наявність готового слова на Non-Ladder не доводить можливість його створити.</p>'
        if not w['stats']:content+='<p>Характеристики змінювались у RotW. Звірте потрібну версію за джерелом; старі значення тут не підставляються.</p>'
        if w.get('summary_only'):content+='<p>Нижче — основні властивості; повний список у джерелі.</p>'
        content+='<ul>'+''.join('<li>'+esc(stat_uk(x))+'</li>' for x in w['stats'])+'</ul><p><a href="'+esc(w['source'])+'">Джерело рецепта</a></p>'
        if w.get('edition_note'):content+='<p><b>'+esc(w['edition_note'])+'</b></p>'
        self.detail.setHtml(content)
        if self.word_dialog is None:
            self.word_dialog=QDialog(self);self.word_dialog.setWindowTitle('Рунне слово · рецепт і властивості');self.word_dialog.resize(760,650)
            dl=QVBoxLayout(self.word_dialog);dl.addWidget(self.detail,1);dl.addWidget(button('Закрити',self.word_dialog.accept))
        self.word_dialog.open()

class MainWindow(QMainWindow):
    def __init__(self,store=None):
        super().__init__();self.store=store or Store();self.run_id=None;self.queue=[];self.active=None
        self.closed=False;self.api_testing=False;self.queue_paused=False;self.advice_active=None
        self.crop_queue=[];self.crop_dialog=None;self.crop_sid=None;self.progress_frame=0;self.activity_started=time.monotonic()
        self.deleted_stack=[];self.discarded_shots=set();self.discarded_advice=set()
        self.hotkey=GlobalHotkey(QApplication.instance(),self.capture_hotkey);self.capturing=False;self.capture_return_windows={}
        self.art=Artwork(self.store.path,self,enabled=self.store.get_setting('art_online',True) and not os.environ.get('LOOT_COMPANION_NO_ART_NETWORK'))
        self.art.ready.connect(self.art_ready)
        self.keys=KeyStore(self.store.path);self.last_saved_key=None
        self.signals=Signals();self.signals.result.connect(self.analysis_done);self.signals.api_result.connect(self.api_test_done);self.signals.advice_result.connect(self.advice_done)
        self.setWindowTitle('Loot Companion 0.6 · Google Gemini · Колекція Diablo II');self.resize(1400,900)
        central=QWidget();self.setCentralWidget(central);layout=QVBoxLayout(central)
        header=QHBoxLayout();title=QLabel('LOOT COMPANION');title.setObjectName('title');header.addWidget(title)
        self.capture=QCheckBox('Приймати нові зображення з буфера');header.addWidget(self.capture);header.addStretch();layout.addLayout(header)
        profile_bar=QHBoxLayout();self.capture_target=wrap('');self.capture_target.setObjectName('subtitle');profile_bar.addWidget(self.capture_target,1)
        self.era=QComboBox();self.era.addItems(['D2R LoD','Reign of the Warlock']);self.mode=QComboBox();self.mode.addItems(['Non-Ladder','Ladder']);self.hardcore=QComboBox();self.hardcore.addItems(['Softcore','Hardcore'])
        for box in [self.era,self.mode,self.hardcore]:profile_bar.addWidget(box)
        layout.addLayout(profile_bar)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.run_panel=ItemPanel(self,'run');self.history_panel=ItemPanel(self,'history');self.owned_panel=ItemPanel(self,'owned',detail_only=True)
        self.collection_panel=CollectionPanel(self,self.owned_panel,activity_icon);self.runes_panel=RunesPanel(self)
        self.tabs.addTab(self.run_panel,'Забіг');self.tabs.addTab(self.history_panel,'Історія');mine=QTabWidget();self.mine_tabs=mine;mine.addTab(self.collection_panel,'Колекція');mine.addTab(self.runes_panel,'Рунні слова');self.tabs.addTab(mine,'Мої речі')
        self.activity=QWidget();al=QHBoxLayout(self.activity);al.setContentsMargins(2,0,2,0)
        self.progress_bar=QProgressBar();self.progress_bar.setRange(0,0);self.progress_bar.setTextVisible(False);self.progress_bar.setFixedSize(110,6)
        self.progress_label=wrap('');al.addWidget(self.progress_bar);al.addWidget(self.progress_label,1);layout.addWidget(self.activity);self.activity.hide()
        self.status=wrap('');self.status.setObjectName('status');layout.addWidget(self.status)
        self.create_settings();self.tabs.addTab(self.settings_widget,'Налаштування')
        self.tabs.currentChanged.connect(self.target_changed);self.mine_tabs.currentChanged.connect(self.target_changed);self.target_changed()
        previous=self.store.get_setting('profile',{});
        for box,key in [(self.era,'era'),(self.mode,'mode'),(self.hardcore,'hardcore')]:
            if previous.get(key):box.setCurrentText(previous[key])
            box.currentTextChanged.connect(self.change_profile)
        self.change_profile()
        self.capture.setChecked(self.store.get_setting('capture_enabled',False))
        self.capture.toggled.connect(lambda checked:self.store.set_setting('capture_enabled',checked))
        self.tabs.setCurrentIndex(self.store.get_setting('tab',0));self.mine_tabs.setCurrentIndex(self.store.get_setting('mine_tab_v06',1 if self.store.get_setting('mine_tab',0)==2 else 0))
        self.target_changed()
        QApplication.clipboard().dataChanged.connect(self.clipboard_changed)
        geometry=self.store.get_setting('geometry')
        if geometry:
            try:self.restoreGeometry(QByteArray(base64.b64decode(geometry)))
            except Exception:pass
        fit_controls(self)
        self.apply_hotkey()
        self.progress_timer=QTimer(self);self.progress_timer.setInterval(160);self.progress_timer.timeout.connect(self.update_progress);self.progress_timer.start()
    def profile(self):return ' | '.join([self.era.currentText(),self.mode.currentText(),self.hardcore.currentText(),'PC'])
    def message(self,text):self.status.setText(text)
    def apply_hotkey(self):
        sequence=self.hotkey_choice.currentText();enabled=self.hotkey_enabled.isChecked()
        ok,message=self.hotkey.configure(sequence,enabled)
        if ok:
            self.store.set_setting('capture_hotkey',sequence);self.store.set_setting('hotkey_enabled',enabled)
        elif self.hotkey.sequence:
            self.hotkey_choice.setCurrentText(self.hotkey.sequence)
        self.hotkey_status.setText(message);self.message(message);self.target_changed()
    def capture_hotkey(self):
        if self.closed or self.capturing:return
        if self.crop_dialog:
            self.crop_dialog.raise_();self.crop_dialog.activateWindow();return
        if QApplication.activeModalWidget():
            self.message('Закрийте відкрите діалогове вікно перед новим знімком.');return
        self.capturing=True
        try:
            # Capture before activating our window: the game's hovered tooltip stays visible.
            return_window=foreground_window();image=capture_active_monitor()
            destination=self.capture_destination()
            if self.tabs.currentIndex() in (1,3):self.tabs.setCurrentIndex(0)
            self.ingest(image,destination=destination,from_clipboard=True,return_window=return_window)
        except Exception as exc:
            self.message('Не вдалося зробити знімок: '+str(exc)+' Якщо гра дає чорний кадр, спробуйте віконний режим без рамки.')
            QApplication.alert(self)
        finally:self.capturing=False
    def delete_entry(self,selection,panel):
        if self.closed or not selection:return
        kind,ident=selection;token=self.store.trash_entry(kind,ident)
        if not token['shots'] and not token['items']:return
        self.deleted_stack.append((token,panel,selection))
        removed=set(token['shots']);self.queue=[sid for sid in self.queue if sid not in removed];self.crop_queue=[sid for sid in self.crop_queue if sid not in removed]
        if self.active in removed:
            self.discarded_shots.add(self.active);self.store.shot_status(self.active,'pending','Обробку скасовано при видаленні. Можна розпізнати повторно.')
        if self.advice_active in token['items']:self.discarded_advice.add(self.advice_active)
        if self.crop_sid in removed and self.crop_dialog:self.crop_dialog.reject()
        row=panel.list.currentRow();panel.selected=None;self.refresh_all()
        if panel.list.count():panel.list.setCurrentRow(min(row,panel.list.count()-1))
        self.message('Запис видалено зі списків. Ctrl+Z у списку або галереї — повернути.');self.start_next()
    def undo_delete(self):
        if not self.deleted_stack:return
        token,panel,selection=self.deleted_stack.pop();self.store.restore_entries(token);panel.selected=selection;self.refresh_all()
        self.message('Видалення скасовано. Запис повернуто; автоматичний аналіз не запускався.')
    def art_ready(self,url):
        if self.closed:return
        for panel in (self.run_panel,self.history_panel,self.owned_panel):
            for n in range(panel.list.count()):
                entry=panel.list.item(n);kind,ident=entry.data(Qt.UserRole)
                if kind=='item':
                    record=self.store.item(ident)
                    if record:entry.setIcon(self.art.icon(record['item']))
            if panel.record():panel.show_art(panel.record())
        self.collection_panel.refresh_icons()
    def capture_destination(self):
        if self.tabs.currentIndex()==2:
            return 'runes' if self.mine_tabs.currentWidget()==self.runes_panel else 'owned'
        return 'run'
    def target_changed(self,*args):
        idx=self.tabs.currentIndex();dest=self.capture_destination()
        route=('→ Руни · заповнити запас' if dest=='runes' else '→ Мої речі') if idx==2 else '→ Забіг'
        self.capture_target.setText((self.hotkey.sequence+' '+route) if self.hotkey.sequence else ('Буфер '+route if idx in (0,2) else 'Приймання з буфера призупинене'))
    def change_profile(self,*args):
        self.store.set_setting('profile',dict(era=self.era.currentText(),mode=self.mode.currentText(),hardcore=self.hardcore.currentText()))
        runs=self.store.runs(self.profile());self.run_id=runs[0]['id'] if runs else self.store.new_run(self.profile());self.refresh_all()
    def new_run(self):
        self.run_id=self.store.new_run(self.profile());self.refresh_all();self.tabs.setCurrentIndex(0);self.message('Новий забіг. Попередні знахідки залишились в історії.')
    def refresh_all(self):
        self.history_panel.refresh_runs()
        for panel in [self.run_panel,self.history_panel,self.collection_panel,self.runes_panel]:panel.refresh()
        self.update_progress()
    def shot_progress(self,shot):
        sid=shot['id'];state=shot['status']
        if sid==self.active:
            state='working';label=f'Розпізнається… · {int(time.monotonic()-self.activity_started)} с'
        elif sid in self.queue:
            state='pending';label=('Пауза черги' if self.queue_paused else 'У черзі')+f' · №{self.queue.index(sid)+1}'
        elif sid==self.crop_sid:state='cropping';label='Обрізання…'
        elif sid in self.crop_queue:state='needs_crop';label='Чекає обрізання'
        else:
            label={'needs_crop':'Обрізати й розпізнати','pending':'Очікує запуску','waiting_api':'Потрібне підключення API',
                   'working':'Обробка перервана — повторіть','error':'Помилка — повторити','empty':'Нічого не розпізнано',
                   'cropped':'Оригінал · є обрізана копія','done':'Готово'}.get(state,state)
        stamp=datetime.fromisoformat(shot['created']).astimezone().strftime('%H:%M:%S')
        return f'{label} · {stamp}',state
    def update_progress(self):
        if self.closed:return
        self.progress_frame=(self.progress_frame+1)%12
        for panel in (self.run_panel,self.history_panel,self.owned_panel):panel.update_progress()
        self.runes_panel.update_progress();self.collection_panel.update_progress()
        seconds=int(time.monotonic()-self.activity_started)
        busy=bool(self.active or self.advice_active or self.api_testing)
        if busy:
            label=('Gemini розпізнає знімок' if self.active else ('Gemini оновлює пораду' if self.advice_active else 'Тестування API'))
            if self.active in self.discarded_shots or self.advice_active in self.discarded_advice:label='Завершується скасований запит · результат буде пропущено'
            label+=f' · {seconds} с · у черзі: {len(self.queue)}'
        elif self.queue:label=('Черга призупинена — повторіть після усунення помилки' if self.queue_paused else 'Черга чекає підключення API')+f' · знімків: {len(self.queue)}'
        elif self.crop_dialog or self.crop_queue:label='Виберіть область у вікні обрізання й натисніть «Вирізати й розпізнати»'
        else:label=''
        self.activity.setVisible(bool(label));self.progress_bar.setVisible(busy);self.progress_label.setText(label)
    def select_shot(self,sid):
        shot=self.store.shot(sid)
        if not shot or shot['profile']!=self.profile():return
        if shot['destination']=='runes':
            self.runes_panel.shots.setCurrentIndex(self.runes_panel.shots.findData(sid));return
        if shot['destination']=='owned':
            self.collection_panel.category_key='pending';self.collection_panel.show_entry(('shot',sid));return
        panel=self.run_panel if shot['destination']=='run' and shot['run_id']==self.run_id else self.owned_panel if shot['destination']!='run' else self.history_panel
        panel.search.blockSignals(True);panel.search.clear();panel.search.blockSignals(False)
        panel.category.blockSignals(True);panel.category.setCurrentIndex(0);panel.category.blockSignals(False)
        panel.selected=('shot',sid);panel.refresh()
        if panel.list.currentItem():panel.list.scrollToItem(panel.list.currentItem())
        if shot['destination']=='runes':
            self.runes_panel.shots.setCurrentIndex(self.runes_panel.shots.findData(sid))
    def request_crop(self,sid):
        if self.closed:return
        if sid==self.crop_sid:
            self.crop_dialog.raise_();self.crop_dialog.activateWindow();return
        shot=self.store.shot(sid)
        if not shot or sid==self.active or sid in self.queue or shot['status']=='done':return
        if sid not in self.crop_queue:self.crop_queue.append(sid)
        self.open_next_crop()
    def open_next_crop(self):
        if self.closed or self.crop_dialog or not self.crop_queue:return
        if self.isMinimized():self.showNormal()
        sid=self.crop_queue.pop(0);shot=self.store.shot(sid)
        image=QImage(str(self.store.path/(shot.get('source_path') or shot['path']))) if shot else QImage()
        if image.isNull():
            if shot:self.store.shot_status(sid,'error','Не вдалося відкрити зображення для обрізання.')
            self.refresh_all();QTimer.singleShot(0,self.open_next_crop);return
        dialog=CropDialog(image,self,capture_mode=True);self.crop_dialog=dialog;self.crop_sid=sid
        dialog.finished.connect(lambda result:self.crop_finished(dialog,sid,result))
        self.select_shot(sid);self.update_progress();dialog.open();dialog.raise_();dialog.activateWindow();QApplication.alert(dialog)
    def crop_finished(self,dialog,sid,result):
        self.crop_dialog=None;self.crop_sid=None
        if self.closed:dialog.deleteLater();return
        if not self.store.shot(sid):
            dialog.deleteLater();QTimer.singleShot(0,self.open_next_crop);return
        rect=dialog.canvas.selection();capture_next=False
        if result==QDialog.Accepted and rect:
            try:
                self.store.crop_pending_shot(sid,png_bytes(dialog.canvas.image.copy(*rect)))
                self.refresh_all();self.select_shot(sid);self.enqueue(sid,explicit=True);capture_next=dialog.capture_next
            except Exception as exc:
                self.store.shot_status(sid,'error',str(exc));self.refresh_all();self.message('Не вдалося підготувати область: '+str(exc))
        else:
            self.message('Обрізання скасовано. Знімок збережено; до Google його не надіслано.');self.refresh_all()
        handle=self.capture_return_windows.pop(sid,None)
        dialog.deleteLater();QTimer.singleShot(0,self.open_next_crop)
        if capture_next:QTimer.singleShot(100,self,lambda:self.wait_for_next_capture(handle))
    def wait_for_next_capture(self,handle):
        if self.closed or self.crop_dialog or self.crop_queue:return
        # Windows may refuse foreground transfer. Minimize only when no game window was restored.
        if not return_to_window(handle):self.showMinimized()
    def import_files(self,checked=False,destination=None):
        destination=destination or self.capture_destination()
        paths,_=QFileDialog.getOpenFileNames(self,'Скриншоти рун' if destination=='runes' else 'Скриншоти предметів','','Images (*.png *.jpg *.jpeg *.bmp *.webp)')
        for path in paths:self.ingest(QImage(path),destination=destination)
    def clipboard_changed(self):
        if self.closed:return
        if self.capture.isChecked() and self.tabs.currentIndex() in (0,2):
            image=QApplication.clipboard().image()
            if not image.isNull():self.ingest(image.copy(),from_clipboard=True)
    def ingest(self,image,destination=None,from_clipboard=False,return_window=None):
        if image.isNull():self.message('Не вдалося прочитати зображення.');return
        if image.width()*image.height()>60000000:self.message('Зображення завелике. Зробіть знімок лише вікна гри.');return
        destination=destination or self.capture_destination();original=png_bytes(image);capture_note='';auto_allowed=True
        if from_clipboard:
            sid,created=self.store.add_shot(original,self.run_id,self.profile(),destination=destination)
            if created:self.store.shot_status(sid,'needs_crop')
            self.capture_return_windows.setdefault(sid,return_window if return_window is not None else foreground_window())
            self.refresh_all();self.select_shot(sid)
            if self.store.shot(sid)['status']=='needs_crop':
                self.message('Знімок отримано. Виберіть область для розпізнавання.');self.request_crop(sid)
            elif not created:self.message('Цей знімок уже збережено. Його стан видно в списку.')
            return
        crop=self.store.get_setting('rune_crop' if destination=='runes' else 'crop')
        if crop:
            if crop['size']==[image.width(),image.height()]:image=image.copy(*crop['rect']);auto_allowed=True
            else:auto_allowed=False
        sid,created=self.store.add_shot(png_bytes(image),self.run_id,self.profile(),destination=destination,source_png=original,capture_note=capture_note)
        self.refresh_all();self.message((capture_note or 'Знімок додано; попередні картки збережено.') if created else 'Такий знімок уже є в цьому забігу.')
        if not auto_allowed:self.message((capture_note or 'Розмір знімка змінився.')+' Автоаналіз цього знімка призупинено; перевірте область або натисніть «Розпізнати».')
        if created and (self.cloud_auto.isChecked() or destination=='runes') and auto_allowed:self.enqueue(sid)
    def manual_item(self,owned=None):
        d=ItemEditor(blank_item(),self)
        if d.exec():
            owned=self.tabs.currentIndex()==2 if owned is None else owned
            ident=self.store.add_manual(self.run_id,self.profile(),d.value,owned=owned);self.refresh_all()
            if owned:self.collection_panel.category_key='all';self.collection_panel.show_entry(('item',ident))
    def create_settings(self):
        self.settings_widget=QScrollArea();self.settings_widget.setWidgetResizable(True)
        inside=QWidget();self.settings_widget.setWidget(inside);layout=QVBoxLayout(inside)
        layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        shortcut_group=QGroupBox('Власна комбінація для знімка');sl=QVBoxLayout(shortcut_group)
        self.hotkey_enabled=QCheckBox('Увімкнути глобальну комбінацію у Windows');self.hotkey_enabled.setChecked(self.store.get_setting('hotkey_enabled',True));sl.addWidget(self.hotkey_enabled)
        sr=QHBoxLayout();self.hotkey_choice=QComboBox();self.hotkey_choice.addItems(HOTKEYS)
        saved=self.store.get_setting('capture_hotkey',DEFAULT_HOTKEY);self.hotkey_choice.setCurrentText(saved if saved in HOTKEYS else DEFAULT_HOTKEY)
        sr.addWidget(self.hotkey_choice,1);sr.addWidget(button('Застосувати комбінацію',self.apply_hotkey));sl.addLayout(sr)
        self.hotkey_status=wrap('');sl.addWidget(self.hotkey_status)
        sl.addWidget(wrap('За замовчуванням Ctrl+Shift+F8. Знімає монітор активного вікна й відкриває обрізання, навіть коли гра має фокус, а програма згорнута. Print Screen і буфер не потрібні. Якщо комбінація зайнята, виберіть іншу й натисніть «Застосувати».'))
        sl.addWidget(wrap('У «Рунах» знімок заповнює запас; у «Моїх речах» додає предмети до колекції; в інших вкладках — до забігу. Спочатку відкрийте потрібну вкладку, поверніться у гру й натисніть комбінацію. Якщо кадр чорний, увімкніть у грі віконний режим без рамки.'))
        layout.addWidget(shortcut_group)
        capture=QGroupBox('Скриншоти на трьох екранах');cl=QVBoxLayout(capture)
        cl.addWidget(wrap('Print Screen → вікно обрізання → «Вирізати й розпізнати». Кожен новий знімок з буфера відкриває вибір області. До підтвердження він не надсилається. Скасований знімок можна відкрити знову кнопкою «Обрізати й розпізнати».'))
        cl.addWidget(wrap('Приймання з буфера залишається додатковим способом і вмикається окремою позначкою вгорі. Глобальна комбінація працює без цієї позначки. На вкладках «Історія» та «Налаштування» автоматичне приймання буфера призупинене.'))
        cl.addWidget(wrap('Біля знімка видно обрізання, чергу, рухомий індикатор аналізу й час очікування. «У чергу й наступний» закриває обрізання та повертає до гри. Кілька знімків обробляються по черзі у фоні; можна одразу додавати наступні. Помилка не приховується, а оригінали зберігаються. Збережені раніше області застосовуються лише до імпорту файлів.'))
        cl.addWidget(button('Скинути область обрізання предметів',lambda:self.store.set_setting('crop',None)))
        cl.addWidget(button('Скинути область обрізання рун',lambda:self.store.set_setting('rune_crop',None)));layout.addWidget(capture)
        group=QGroupBox('Google Gemini · розпізнавання й опис предметів');form=QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow);form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setVerticalSpacing(12)
        initial='';key_error=''
        try:initial=self.keys.load()
        except RuntimeError as exc:key_error=str(exc)
        self.last_saved_key=initial
        initial=initial or os.environ.get('GEMINI_API_KEY','')
        self.api_key=QLineEdit(initial);self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText('Вставте ключ із Google AI Studio — збережеться автоматично')
        form.addRow('Google API-ключ',self.api_key)
        self.key_status=wrap(key_error or ('Збережений ключ завантажено.' if self.last_saved_key else 'Ключ зберігається захищено у вашому профілі Windows.'))
        form.addRow(self.key_status)
        self.key_timer=QTimer(self);self.key_timer.setSingleShot(True);self.key_timer.setInterval(700)
        self.key_timer.timeout.connect(self.save_api_key)
        self.api_key.textChanged.connect(lambda:self.key_timer.start())
        self.api_key.editingFinished.connect(self.save_api_key)
        model_name=self.store.get_setting('gemini_model',DEFAULT_MODEL)
        self.model=QComboBox();self.model.setEditable(True);self.model.addItems(list(dict.fromkeys([model_name,DEFAULT_MODEL,'gemini-3.1-flash-lite'])))
        self.model.setCurrentText(model_name);self.model.currentTextChanged.connect(lambda text:self.store.set_setting('gemini_model',text))
        form.addRow('Модель',self.model)
        self.player_build=QLineEdit(self.store.get_setting('player_build',''));self.player_build.setPlaceholderText('Наприклад: Варвар · Whirlwind · два Grief')
        self.player_build.textChanged.connect(lambda text:self.store.set_setting('player_build',text));form.addRow('Мій персонаж / білд',self.player_build)
        actions=QHBoxLayout();actions.addWidget(button('Зберегти ключ',self.save_api_key))
        self.test_button=button('Тест API',self.test_api);actions.addWidget(self.test_button)
        actions.addWidget(button('Створити ключ Google',lambda:webbrowser.open('https://aistudio.google.com/apikey')))
        form.addRow(actions)
        self.consent=QCheckBox('Дозволяю надсилати скриншоти до Google для аналізу')
        self.consent.setChecked(self.store.get_setting('google_consent',False))
        self.consent.toggled.connect(self.consent_changed);form.addRow(self.consent)
        self.cloud_auto=QCheckBox('Автоматично розпізнавати імпортовані файли речей')
        self.cloud_auto.setChecked(bool(self.consent.isChecked() and self.store.get_setting('google_auto',True)))
        self.cloud_auto.toggled.connect(self.auto_toggled);form.addRow(self.cloud_auto)
        form.addRow(wrap('Після підтвердження обрізання Print Screen розпізнавання запускається незалежно від прапорця імпорту. Потрібні ключ і дозвіл. «Тест API» надсилає лише контрольне зображення. Для безкоштовної роботи використовуйте проєкт Free Tier; якщо підключено оплату, запити можуть тарифікуватися.'))
        form.addRow(button('Обробити / повторити очікувані знімки забігу',self.analyze_pending));layout.addWidget(group)
        info_group=QGroupBox('Інформація про API');il=QVBoxLayout(info_group)
        self.api_info=rich_browser();self.api_info.setObjectName('apiInfo');self.api_info.setMinimumHeight(240)
        il.addWidget(self.api_info);layout.addWidget(info_group)
        self.render_api_info(self.store.get_setting('api_report',{}))
        data=QGroupBox('Моя колекція');dl=QVBoxLayout(data)
        dl.addWidget(wrap('Речі, історія, знімки, кількість рун і налаштування зберігаються автоматично. Папка даних: '+str(self.store.path)))
        dl.addWidget(wrap('Ключ зберігається окремо під захистом Windows. У резервну копію він не входить. На іншому комп’ютері введіть ключ знову.'))
        dl.addWidget(button('Зберегти резервну копію зі скриншотами',self.backup));layout.addWidget(data)
        self.art_online=QCheckBox('Завантажувати ілюстрації предметів із довідника Blizzard')
        self.art_online.setChecked(self.store.get_setting('art_online',True));self.art_online.toggled.connect(self.art_toggled);dl.addWidget(self.art_online)
        dl.addWidget(wrap('Ілюстрації — класична графіка Diablo II. У мережу для них надсилаються лише адреси зображень; ваші скриншоти та ключ не використовуються. Завантажені зображення кешуються.'))
        layout.addWidget(wrap('Версія 0.6 · Google Gemini. Програма працює зі скриншотами й не керує грою. Актуальні торгові ціни поки не підключені.'))
        layout.addStretch()
    def save_api_key(self):
        if self.closed:return
        self.key_timer.stop();key=self.api_key.text().strip()
        if key==self.last_saved_key:return
        try:
            self.keys.save(key);self.last_saved_key=key
            self.key_status.setText('✓ Ключ збережено під захистом Windows.' if key else 'Ключ видалено з цього комп’ютера.')
        except (RuntimeError,OSError) as exc:
            self.key_status.setText(safe_text(exc,key))
    def art_toggled(self,checked):
        self.store.set_setting('art_online',checked);self.art.enabled=checked
        if checked:self.art.failed.clear()
        self.refresh_all()
    def consent_changed(self,checked):
        self.store.set_setting('google_consent',checked)
        if not checked and hasattr(self,'cloud_auto'):self.cloud_auto.setChecked(False)
    def auto_toggled(self,checked):
        if checked and not self.consent.isChecked():
            self.cloud_auto.setChecked(False);self.message('Спочатку дозвольте надсилання скриншотів у налаштуваннях.');return
        self.store.set_setting('google_auto',checked)
    def render_api_info(self,info):
        content='<h3>Google Gemini</h3>'
        if info:
            content+='<p><b>'+('✓ ' if info.get('ok') else '● ')+esc(info.get('message',''))+'</b></p>'
            content+='<p>Перевірено: '+esc(info.get('time',''))+'<br>Модель: '+esc(info.get('model',''))+'<br>Час відповіді: '+esc(info.get('seconds','—'))+' с</p>'
            if info.get('model_version'):content+='<p>Версія відповіді: '+esc(info['model_version'])+'</p>'
            if info.get('response_id'):content+='<p>ID відповіді: '+esc(info['response_id'])+'</p>'
            if info.get('usage'):content+='<p>Токени тесту: '+esc(json.dumps(info['usage'],ensure_ascii=False))+'</p>'
            if info.get('error'):content+='<p><b>Подробиці помилки</b><br>'+esc(json.dumps(info['error'],ensure_ascii=False,indent=2)).replace('\n','<br>')+'</p>'
            meta=info.get('model_info',{})
            if meta:
                content+='<p><b>'+esc(meta.get('displayName',''))+'</b><br>'+esc(meta.get('description',''))+'</p><p>Версія моделі: '+esc(meta.get('version','не вказано'))+'<br>Максимум вхідних токенів: '+esc(meta.get('inputTokenLimit','не вказано'))+'<br>Максимум вихідних токенів: '+esc(meta.get('outputTokenLimit','не вказано'))+'<br>Підтримка thinking: '+esc(meta.get('thinking','не вказано'))+'<br>Методи: '+esc(', '.join(meta.get('supportedGenerationMethods',[])))+'</p>'
            models=info.get('models',[])
            if models:
                content+='<p><b>Моделей у відповіді Google: '+str(len(models))+'</b>. Наявність у списку не гарантує доступну квоту або безкоштовність.</p><ul>'
                for m in models:content+='<li>'+esc(m.get('name',''))+' · вхід '+esc(m.get('inputTokenLimit','?'))+' / вихід '+esc(m.get('outputTokenLimit','?'))+' · '+esc(', '.join(m.get('supportedGenerationMethods',[])))+'</li>'
                content+='</ul>'
        else:content+='<p>Вставте ключ і натисніть «Тест API». Перевіримо підключення, вибрану модель, читання зображень і формат карток.</p>'
        content+='<p>Тариф, баланс і залишок добової квоти Google не повертає через звичайний API-ключ. Результат тесту стосується часу перевірки; він не підтверджує безкоштовний тариф.</p>'
        content+='<p><a href="https://aistudio.google.com/rate-limit">Квоти мого проєкту</a> · <a href="https://aistudio.google.com/usage">Використання</a> · <a href="https://ai.google.dev/gemini-api/docs/pricing">Тарифи</a> · <a href="https://aistudio.google.com/apikey">Ключі й проєкти</a></p>'
        content+='<p>Безкоштовний тариф Google може використовувати надіслані матеріали для покращення продуктів. Обрізайте інші екрани перед аналізом.</p>'
        self.api_info.setHtml(content)
    def test_api(self):
        if self.api_testing:return
        if self.active or self.advice_active:self.message('Дочекайтеся завершення поточного запиту, потім запустіть тест.');return
        key=self.api_key.text().strip();model=self.model.currentText().strip()
        if not key:self.message('Спочатку вставте Google Gemini API-ключ.');return
        if key.startswith('sk-'):self.message('Це схоже на ключ OpenAI. Потрібен ключ із Google AI Studio.');return
        self.save_api_key();self.api_testing=True;self.test_button.setEnabled(False)
        self.activity_started=time.monotonic();self.update_progress()
        self.test_identity=(hashlib.sha256(key.encode()).hexdigest(),model)
        self.message('Тест Google API: список моделей і контрольне зображення…')
        self.api_info.setHtml('<h3>Перевіряємо Google…</h3><p>Надсилається лише контрольне зображення програми. Ваші скриншоти не використовуються.</p>')
        img=QImage(420,120,QImage.Format_RGB32);img.fill(QColor('white'))
        painter=QPainter(img);painter.setPen(QColor('black'));painter.setFont(QFont('Sans Serif',32));painter.drawText(img.rect(),Qt.AlignCenter,'LOOT 123');painter.end()
        png=png_bytes(img);signals=self.signals
        def work():
            try:info=test_connection(key,model,png)
            except Exception as exc:info={'ok':False,'message':safe_text(exc,key),'model':model,'time':datetime.now().astimezone().isoformat(timespec='seconds')}
            try:signals.api_result.emit(info)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def api_test_done(self,info):
        if self.closed:return
        self.api_testing=False;self.test_button.setEnabled(True)
        current=(hashlib.sha256(self.api_key.text().strip().encode()).hexdigest(),self.model.currentText().strip())
        if current!=self.test_identity:
            info=dict(info);info['ok']=False;info['message']='Ключ або модель змінені під час тесту. Нижче — результат попереднього підключення; запустіть тест знову.'
        self.store.set_setting('api_report',info);self.render_api_info(info)
        # Preserve explicit selection; no automatic model or paid-provider fallback.
        chosen=self.model.currentText();self.model.blockSignals(True)
        for entry in info.get('models',[]):
            name=entry.get('name','').removeprefix('models/')
            if 'generateContent' in entry.get('supportedGenerationMethods',[]) and name and self.model.findText(name)<0:self.model.addItem(name)
        self.model.setCurrentText(chosen);self.model.blockSignals(False)
        self.message(info['message']);self.start_next()
    def analyze_pending(self):
        if not self.ready_api():return
        self.queue_paused=False
        for shot in self.store.shots(self.profile(),self.run_id):
            if shot['status'] in ('pending','waiting_api','error','empty'):self.enqueue(shot['id'])
        self.start_next()
    def ready_api(self):
        if not self.consent.isChecked() or not self.api_key.text().strip() or not self.model.currentText().strip():
            self.message('Для аналізу потрібні Google API-ключ, модель і дозвіл у налаштуваннях. Знімки вже збережено.');return False
        if self.api_key.text().strip().startswith('sk-'):
            self.message('Введено ключ OpenAI. Для цієї версії потрібен Google Gemini API-ключ.');return False
        return True
    def enqueue(self,sid,explicit=False):
        shot=self.store.shot(sid)
        if not shot or shot['status'] in ('done','cropped'):return
        if shot['status']=='needs_crop':
            if explicit:self.request_crop(sid)
            return
        if not self.ready_api():
            if sid!=self.active:self.store.shot_status(sid,'waiting_api',self.status.text());self.refresh_all()
            return
        if explicit:self.queue_paused=False
        if sid==self.active or sid in self.queue:
            if explicit:self.start_next()
            return
        self.store.shot_status(sid,'pending');self.queue.append(sid);self.refresh_all();self.start_next()
    def start_next(self):
        if self.closed or self.active or self.advice_active or self.api_testing or self.queue_paused or not self.queue:return
        if not self.ready_api():return
        sid=self.queue.pop(0);self.active=sid;self.activity_started=time.monotonic();shot=self.store.shot(sid);self.store.shot_status(sid,'working');self.refresh_all()
        key=self.api_key.text().strip();model=self.model.currentText().strip()
        path=self.store.path/shot['path'];signals=self.signals;profile=shot['profile'];purpose='runes' if shot['destination']=='runes' else 'items'
        if self.player_build.text().strip():profile+='\nPlayer build: '+self.player_build.text().strip()
        self.message(f'Розпізнавання Gemini… У черзі: {len(self.queue)}. Можна робити наступні знімки.')
        def work():
            try:result=analyze(path.read_bytes(),key,model,profile,purpose=purpose);error=None
            except Exception as exc:
                result=[];error={'message':safe_text(exc,key),'details':getattr(exc,'details',{}),'code':getattr(exc,'code',None),'model':model}
            try:signals.result.emit(sid,result,error)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def refresh_advice(self,record):
        if self.active or self.advice_active or self.api_testing:self.message('Дочекайтеся завершення поточного запиту.');return
        if not self.ready_api():return
        self.advice_active=record['id'];self.activity_started=time.monotonic();self.advice_snapshot=json.dumps(record['item'],sort_keys=True,ensure_ascii=False)
        key=self.api_key.text().strip();model=self.model.currentText().strip();player=self.player_build.text().strip();signals=self.signals
        self.refresh_all();self.message('Gemini готує рекомендацію за збереженими характеристиками…')
        def work():
            try:result=advise(record['item'],key,model,record['profile'],player);error=None
            except Exception as exc:result=None;error={'message':safe_text(exc,key),'details':getattr(exc,'details',{}),'model':model}
            try:signals.advice_result.emit(record['id'],result,error)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def advice_done(self,ident,result,error):
        if self.closed:return
        if ident in self.discarded_advice:
            self.discarded_advice.discard(ident);self.advice_active=None;self.refresh_all();self.start_next();return
        record=self.store.item(ident);self.advice_active=None
        if error:
            self.queue_paused=True;self.message(error['message'])
            report={'ok':False,'message':error['message'],'error':error['details'],'model':error['model'],'time':datetime.now().astimezone().isoformat(timespec='seconds')}
            self.store.set_setting('api_report',report);self.render_api_info(report)
        elif not record:self.message('Картку вже видалено.')
        elif json.dumps(record['item'],sort_keys=True,ensure_ascii=False)!=self.advice_snapshot:self.message('Картку змінено під час запиту. Оновіть пораду ще раз — ваші зміни збережено.')
        else:
            item=dict(record['item']);item['advice']=result;self.store.update_item(ident,item);self.message('Рекомендацію оновлено й збережено.')
        self.refresh_all();self.start_next()
    def analysis_done(self,sid,result,error):
        if self.closed:return
        if sid in self.discarded_shots or not self.store.shot(sid):
            self.discarded_shots.discard(sid)
            if self.active==sid:self.active=None
            self.refresh_all();self.start_next();return
        message=error.get('message','') if isinstance(error,dict) else str(error or '')
        rune_status=None
        if message:
            self.store.shot_status(sid,'error',message);self.queue_paused=True
            report={'time':datetime.now().astimezone().isoformat(timespec='seconds'),'ok':False,'message':message,
                    'model':error.get('model','') if isinstance(error,dict) else self.model.currentText(),
                    'error':error.get('details',{}) if isinstance(error,dict) else {}}
            self.store.set_setting('api_report',report);self.render_api_info(report)
        else:
            try:
                self.store.finish_shot(sid,result);rune_status=self.store.apply_rune_snapshot(sid)
            except Exception as exc:message=safe_text(exc,self.api_key.text());self.store.shot_status(sid,'error',message)
        self.active=None
        shot=self.store.shot(sid)
        records=[r for r in self.store.items(shot['profile'],shot['run_id']) if r['shot_id']==sid] if shot and shot['status']=='done' else []
        if records:
            for panel in (self.run_panel,self.history_panel,self.owned_panel):
                if panel.selected==('shot',sid):panel.selected=('item',records[0]['id'])
        self.refresh_all()
        if rune_status=='applied':message='✓ Руни розпізнано. Кількість оновлено й збережено; відсутні на знімку типи не змінено.'
        elif rune_status=='conflict':message='Запас змінено після знімка. Перевірте розпізнані руни — ручні зміни збережено.'
        elif rune_status=='review':message='Знімок рун збережено. Перевірте прочитані кількості; якщо їх немає — обріжте знімок або імпортуйте чіткіший.'
        self.message(message or f'Розпізнано карток: {len(result)}. Перевірте цифри перед порівнянням.')
        self.start_next()
    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,'Резервна копія','LootCompanion_backup.zip','ZIP (*.zip)')
        if path:
            try:self.store.backup(path);self.message('Резервну копію зі скриншотами збережено.')
            except Exception as e:QMessageBox.warning(self,'Помилка копіювання',str(e))
    def closeEvent(self,event):
        self.save_api_key();self.key_timer.stop()
        self.store.set_setting('geometry',base64.b64encode(bytes(self.saveGeometry())).decode())
        self.store.set_setting('tab',self.tabs.currentIndex());self.store.set_setting('mine_tab_v06',self.mine_tabs.currentIndex())
        self.store.set_setting('capture_enabled',self.capture.isChecked())
        self.closed=True
        self.hotkey.close()
        self.progress_timer.stop();self.crop_queue.clear()
        if self.crop_dialog:self.crop_dialog.reject()
        self.art.close()
        try:QApplication.clipboard().dataChanged.disconnect(self.clipboard_changed)
        except RuntimeError:pass
        self.store.close();event.accept()

def main():
    app=QApplication(sys.argv);configure_app(app)
    app.setApplicationName('LootCompanion');app.setOrganizationName('ViktorTools')
    win=MainWindow();win.show();sys.exit(app.exec())

if __name__=='__main__':main()
