"""Full-width collection galleries and reusable rune cards."""
from collections import Counter
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QPixmap,QPainter,QColor,QIcon,QShortcut,QKeySequence
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,
    QListWidget,QListWidgetItem,QAbstractItemView,QLineEdit,QComboBox,QScrollArea,QGridLayout,
    QSpinBox,QToolButton,QAbstractSpinBox,QSizePolicy)
from core import QUALITIES
from collection import CATEGORIES,in_category

def label(text,parent=None):
    l=QLabel(text,parent);l.setWordWrap(True);l.setAttribute(Qt.WA_TransparentForMouseEvents);return l

def cards_list():
    view=QListWidget();view.setObjectName('cardGallery');view.setViewMode(QListWidget.IconMode)
    view.setResizeMode(QListWidget.Adjust);view.setMovement(QListWidget.Static);view.setWrapping(True)
    view.setWordWrap(True);view.setGridSize(QSize(210,180));view.setIconSize(QSize(80,92));view.setSpacing(8)
    view.setSelectionMode(QAbstractItemView.SingleSelection);view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return view

class CollectionPanel(QWidget):
    def __init__(self,window,detail_panel,progress_icon):
        super().__init__();self.window=window;self.detail_panel=detail_panel;self.progress_icon=progress_icon
        self.category_key='all';self.selected=None;self.current_profile=None
        layout=QVBoxLayout(self);bar=QHBoxLayout()
        self.back=QPushButton('← Категорії');self.back.clicked.connect(self.go_back);bar.addWidget(self.back)
        self.heading=QLabel('Моя колекція');self.heading.setStyleSheet('font-size:14pt; font-weight:600;');bar.addWidget(self.heading,1)
        self.import_button=QPushButton('Імпорт скриншотів');self.import_button.clicked.connect(lambda:self.window.import_files(destination='owned'));bar.addWidget(self.import_button)
        self.manual_button=QPushButton('+ Річ вручну');self.manual_button.clicked.connect(lambda:self.window.manual_item(owned=True));bar.addWidget(self.manual_button)
        self.delete_button=QPushButton('Видалити · Delete');self.delete_button.clicked.connect(self.delete_current);bar.addWidget(self.delete_button)
        layout.addLayout(bar);self.stack=QStackedWidget();layout.addWidget(self.stack,1)
        self.home=cards_list();self.home.itemClicked.connect(lambda item:self.open_category(item.data(Qt.UserRole)));self.home.itemActivated.connect(lambda item:self.open_category(item.data(Qt.UserRole)));self.stack.addWidget(self.home)
        page=QWidget();pl=QVBoxLayout(page);pl.setContentsMargins(0,0,0,0);row=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText('Пошук у цій категорії…');self.search.textChanged.connect(self.refresh_grid);row.addWidget(self.search,1)
        self.charm_filter=QComboBox()
        for name,value in [('Усі чарми',''),('Малі · Small','small'),('Великі · Large','large'),('Гранд · Grand','grand')]:self.charm_filter.addItem(name,value)
        self.charm_filter.currentIndexChanged.connect(self.refresh_grid);row.addWidget(self.charm_filter);pl.addLayout(row)
        self.list=cards_list();self.list.itemClicked.connect(lambda item:self.show_entry(item.data(Qt.UserRole)));self.list.itemActivated.connect(lambda item:self.show_entry(item.data(Qt.UserRole)))
        self.list.currentItemChanged.connect(lambda item,prev:self.select_current(item));pl.addWidget(self.list,1)
        self.empty=label('У цій категорії поки немає речей. Додайте скриншот або створіть картку вручну.');pl.addWidget(self.empty)
        self.stack.addWidget(page);self.stack.addWidget(detail_panel)
        self.hint=QLabel('Категорії перетинаються: зелений перстень є і в «Зелених», і в «Кільцях».');self.hint.setObjectName('subtitle');self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.shortcuts=[]
        for target in (self.list,detail_panel.detail):
            shortcut=QShortcut(QKeySequence(Qt.Key_Delete),target);shortcut.setContext(Qt.WidgetShortcut);shortcut.setAutoRepeat(False);shortcut.activated.connect(self.delete_current);self.shortcuts.append(shortcut)
        for target in (self.home,self.list,detail_panel.detail):
            shortcut=QShortcut(QKeySequence('Ctrl+Z'),target);shortcut.setContext(Qt.WidgetShortcut);shortcut.activated.connect(window.undo_delete);self.shortcuts.append(shortcut)
        self.show_home()
    def select_current(self,item):
        if item:self.selected=item.data(Qt.UserRole);self.delete_button.setEnabled(True)
    def show_home(self):
        self.stack.setCurrentIndex(0);self.back.hide();self.heading.setText('Моя колекція');self.delete_button.hide();self.hint.setText('Категорії перетинаються: зелений перстень є і в «Зелених», і в «Кільцях».');self.hint.show();self.selected=None
    def open_category(self,key):
        if key=='rune':self.window.mine_tabs.setCurrentWidget(self.window.runes_panel);return
        self.category_key=key;self.selected=None;self.search.clear();self.charm_filter.setCurrentIndex(0)
        self.stack.setCurrentIndex(1);self.back.show();self.back.setText('← Категорії');self.delete_button.show();self.hint.setText('Картка → опис · Delete — видалити · Ctrl+Z — повернути')
        self.refresh_grid();self.list.setFocus()
    def go_back(self):
        if self.stack.currentIndex()==2:
            self.stack.setCurrentIndex(1);self.back.setText('← Категорії');self.refresh_grid();self.list.setFocus()
        else:self.show_home()
    def title(self):return next((title for key,title,_ in CATEGORIES if key==self.category_key),'Колекція')
    def records(self):return self.window.store.items(self.window.profile(),owned=True)
    def pending_shots(self):
        return [s for s in self.window.store.shots(self.window.profile()) if s['destination']=='owned' and s['status'] not in ('done','cropped')]
    def refresh(self):
        profile=self.window.profile()
        if self.current_profile!=profile:self.current_profile=profile;self.show_home()
        records=self.records();shots=self.pending_shots();self.home.clear()
        for key,title,art in CATEGORIES:
            count=len(shots) if key=='pending' else sum(self.window.store.inventory(profile).values()) if key=='rune' else sum(in_category(r['item'],key) for r in records)
            item=QListWidgetItem(f'{title}\n{count} '+('шт.' if key=='rune' else 'записів'));item.setData(Qt.UserRole,key);item.setIcon(self.window.art.card_icon(self.window.art.category_icon(art)));item.setSizeHint(QSize(194,168));self.home.addItem(item)
        if self.stack.currentIndex()==2 and not self.selected:self.stack.setCurrentIndex(1);self.list.setFocus()
        if self.stack.currentIndex()==2 and self.selected:
            kind,ident=self.selected
            if kind=='shot':
                matches=[r for r in records if r['shot_id']==ident]
                if matches:self.selected=('item',matches[0]['id'])
            found=self.window.store.item(self.selected[1]) if self.selected[0]=='item' else self.window.store.shot(self.selected[1])
            if not found or (self.selected[0]=='item' and not found['owned']):self.stack.setCurrentIndex(1);self.back.setText('← Категорії');self.list.setFocus();self.selected=None
        self.refresh_grid()
        self.detail_panel.selected=self.selected;self.detail_panel.refresh()
        if self.stack.currentIndex()==2:self.heading.setText(self.title()+' / опис')
    def refresh_grid(self,*args):
        selected=self.selected;self.list.blockSignals(True);self.list.clear();text=self.search.text().casefold()
        self.charm_filter.setVisible(self.category_key=='charms')
        if self.category_key=='pending':
            for shot in self.pending_shots():
                title,state=self.window.shot_progress(shot);entry=QListWidgetItem(title);entry.setData(Qt.UserRole,('shot',shot['id']));entry.setData(Qt.UserRole+1,shot);entry.setIcon(self.progress_icon(state,self.window.progress_frame));entry.setSizeHint(QSize(194,168));self.list.addItem(entry)
        else:
            for r in self.records():
                i=r['item']
                if not in_category(i,self.category_key,self.charm_filter.currentData() if self.category_key=='charms' else ''):continue
                if text and text not in ' '.join(i.get(k,'') for k in ('name','canonical_name','base','location','notes')).casefold():continue
                entry=QListWidgetItem(i['name'] or i['canonical_name'] or 'Без назви');entry.setData(Qt.UserRole,('item',r['id']));entry.setIcon(self.window.art.card_icon(self.window.art.icon(i)));entry.setSizeHint(QSize(194,168));entry.setToolTip(QUALITIES[i['quality']]+' · '+i.get('base','')+'\n'+i.get('location',''));self.list.addItem(entry)
        self.list.blockSignals(False)
        for n in range(self.list.count()):
            if self.list.item(n).data(Qt.UserRole)==selected:self.list.setCurrentRow(n);break
        self.empty.setVisible(self.list.count()==0);self.delete_button.setEnabled(bool(self.selected))
        if self.stack.currentIndex()==1:self.heading.setText(self.title()+f' · {self.list.count()}')
    def show_entry(self,selection):
        if not selection:return
        self.selected=selection;self.detail_panel.selected=selection;self.detail_panel.refresh();self.stack.setCurrentIndex(2)
        self.back.show();self.back.setText('← '+self.title());self.delete_button.show();self.delete_button.setEnabled(True);self.heading.setText(self.title()+' / опис');self.detail_panel.detail.setFocus()
    def delete_current(self):
        if self.selected and self.stack.currentIndex()!=0:self.window.delete_entry(self.selected,self)
    def refresh_icons(self):
        for n in range(self.list.count()):
            entry=self.list.item(n);kind,ident=entry.data(Qt.UserRole)
            if kind=='item':
                record=self.window.store.item(ident)
                if record:entry.setIcon(self.window.art.card_icon(self.window.art.icon(record['item'])))
    def update_progress(self):
        for n in range(self.list.count()):
            entry=self.list.item(n);shot=entry.data(Qt.UserRole+1)
            if shot:
                title,state=self.window.shot_progress(shot);entry.setText(title);entry.setIcon(self.progress_icon(state,self.window.progress_frame))

def rune_slots(runes,inventory):
    used=Counter();result=[]
    for rune in runes:
        used[rune]+=1;result.append(inventory.get(rune,0)>=used[rune])
    return result

def rune_pixmap(art,rune,available=True,size=32):
    icon=art.rune_icon(rune).pixmap(size,size)
    if available:return icon
    pix=QPixmap(size,size);pix.fill(Qt.transparent);p=QPainter(pix);p.setOpacity(.22);p.drawPixmap(0,0,icon);p.end();return pix

class RuneTile(QWidget):
    def __init__(self,art,name,changed):
        super().__init__();self.art=art;self.name=name;self.setFixedWidth(38)
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(2)
        row=QHBoxLayout();row.setSpacing(0);self.icon=QLabel();self.icon.setFixedSize(24,28);row.addWidget(self.icon)
        self.plus=QToolButton();self.plus.setText('+');self.plus.setFixedSize(14,20);self.plus.setToolTip('Додати одну '+name);row.addWidget(self.plus);layout.addLayout(row)
        self.name_label=QLabel(name);self.name_label.setAlignment(Qt.AlignCenter);layout.addWidget(self.name_label)
        self.count=QSpinBox();self.count.setProperty('compact',True);self.count.setRange(0,999999);self.count.setButtonSymbols(QAbstractSpinBox.NoButtons);self.count.setAlignment(Qt.AlignCenter);self.count.setFixedSize(38,23);self.count.setStyleSheet('padding:0px; min-height:20px;');self.count.setToolTip('Загальна кількість '+name+' — можна вписати вручну');layout.addWidget(self.count)
        self.plus.clicked.connect(lambda:self.count.setValue(self.count.value()+1));self.count.valueChanged.connect(lambda value:changed(name,value));self.set_count(0)
    def set_count(self,value):
        self.count.blockSignals(True);self.count.setValue(value);self.count.blockSignals(False)
        self.icon.setPixmap(rune_pixmap(self.art,self.name,value>0,24));self.name_label.setStyleSheet('color:'+('#e5bc73' if value else '#586777'))

class CardGrid(QScrollArea):
    def __init__(self):
        super().__init__();self.setWidgetResizable(True);self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inside=QWidget();self.grid=QGridLayout(inside);self.grid.setSizeConstraint(QGridLayout.SetMinimumSize);self.grid.setAlignment(Qt.AlignTop);self.grid.setSpacing(12);self.setWidget(inside);self.cards=[];self.columns=0
    def set_cards(self,cards):
        for old in self.cards:self.grid.removeWidget(old);old.hide();old.deleteLater()
        self.cards=cards;self.columns=0;self.arrange()
    def arrange(self):
        cols=max(1,(self.viewport().width()-20)//310)
        if cols==self.columns:return
        for old in range(self.columns):self.grid.setColumnStretch(old,0)
        self.columns=cols
        for card in self.cards:self.grid.removeWidget(card)
        for n,card in enumerate(self.cards):self.grid.addWidget(card,n//cols,n%cols)
        for n in range(cols):self.grid.setColumnStretch(n,1)
    def resizeEvent(self,event):super().resizeEvent(event);self.arrange()

class WordCard(QPushButton):
    def __init__(self,word,art,inventory,clicked):
        super().__init__();self.word=word;self.setProperty('compact',True);self.setObjectName('wordCard');self.setMinimumWidth(290);self.setFixedHeight(204);self.setStyleSheet('QPushButton#wordCard { min-height:204px; max-height:204px; } QPushButton#wordCard QWidget { background:transparent; }')
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);layout=QVBoxLayout(self);layout.setContentsMargins(12,10,12,10);layout.setSpacing(5)
        title=label(word['name']);title.setStyleSheet('font-size:13pt; font-weight:600; color:#e5bc73;');layout.addWidget(title)
        base=label(f'{word["sockets"]} гнізд · '+word['bases']);base.setFixedHeight(36);base.setToolTip(word['bases']);layout.addWidget(base)
        row=QHBoxLayout();row.setSpacing(4);row.addStretch();self.slots=rune_slots(word['runes'],inventory)
        for rune,available in zip(word['runes'],self.slots):
            tile=QWidget();tile.setAttribute(Qt.WA_TransparentForMouseEvents);vl=QVBoxLayout(tile);vl.setContentsMargins(0,0,0,0);vl.setSpacing(1)
            icon=QLabel();icon.setAlignment(Qt.AlignCenter);icon.setPixmap(rune_pixmap(art,rune,available,30));vl.addWidget(icon)
            name=label(rune);name.setAlignment(Qt.AlignCenter);name.setStyleSheet('color:'+('#e2e8ef' if available else '#586777'));vl.addWidget(name);row.addWidget(tile)
        row.addStretch();layout.addLayout(row)
        status=word.get('edition_note') or ('✓ Руни є · перевірте базу' if word['runes_ready'] else 'Бракує: '+', '.join(f'{r} ×{n}' for r,n in word['missing'].items()))
        state=label(status);state.setFixedHeight(36);state.setStyleSheet('color:'+('#8fd5be' if word['runes_ready'] and word['edition_available'] else '#95a6b7'));layout.addWidget(state)
        self.setToolTip(' → '.join(word['runes'])+'\n'+status);self.clicked.connect(clicked)
