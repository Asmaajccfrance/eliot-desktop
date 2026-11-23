C = {
    "bg": "#041018",
    "panel": "#081C28",
    "surface": "#0E2C3A",
    "surface2": "#143848",
    "border": "#1E5464",
    "text": "#E7F6FB",
    "muted": "#8AAFBC",
    "cyan": "#3EE0D2",
    "teal": "#2EC4B6",
    "blue": "#0E4A58",
    "danger": "#F43F5E",
    "warn": "#FBBF24",
    "ok": "#34D399",
}

QSS = f"""
* {{ font-size: 14px; color: {C['text']}; }}
QMainWindow {{ background: {C['bg']}; }}
#center, #homePage, QStackedWidget, QScrollArea {{ background: transparent; }}
QToolTip {{ background: {C['surface2']}; color: {C['text']}; border: 1px solid {C['border']}; padding: 6px; }}
#shell {{ background: rgba(8, 28, 40, 235); border: 1px solid #2A7A88; border-radius: 18px; }}
#sidebar {{ background: rgba(5, 20, 30, 210); border-right: 1px solid {C['border']};
           border-top-left-radius: 16px; border-bottom-left-radius: 16px; }}
#taskPanel {{ background: rgba(5, 20, 30, 210); border-left: 1px solid {C['border']};
             border-top-right-radius: 16px; border-bottom-right-radius: 16px; }}
#kicker {{ color: {C['teal']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
#cardTitle {{ font-size: 16px; font-weight: 600; }}
#featureCard {{ background: rgba(10, 40, 54, 220); border: 1px solid {C['border']}; border-radius: 14px; }}
#featureCard:hover {{ border-color: {C['cyan']}; }}
#brand {{ font-size: 22px; font-weight: 700; letter-spacing: 6px; color: {C['text']}; }}
#version {{ color: {C['cyan']}; font-size: 11px; letter-spacing: 2px; }}
#section {{ color: {C['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 2px; }}
#pageTitle {{ font-size: 20px; font-weight: 600; }}
#statusPill {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 12px; padding: 4px 12px;
              color: {C['teal']}; font-size: 12px; }}
#greeting {{ font-size: 26px; font-weight: 400; }}
#subtitle {{ color: {C['muted']}; font-size: 15px; }}
#hint {{ color: {C['muted']}; font-size: 12px; letter-spacing: 1px; }}
#footer {{ color: {C['muted']}; font-size: 11px; }}
QPushButton {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 9px 14px; }}
QPushButton:hover {{ background: {C['surface2']}; border-color: {C['cyan']}; }}
QPushButton:pressed {{ background: {C['blue']}; }}
QPushButton:disabled {{ color: #3B4866; border-color: #141E33; background: #0B1324; }}
QPushButton#primary {{ background: {C['cyan']}; color: #04121A; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {C['teal']}; }}
QPushButton#danger {{ background: transparent; color: {C['danger']}; border: 1px solid {C['danger']}; font-weight: 700; }}
QPushButton#danger:hover {{ background: {C['danger']}; color: white; }}
QPushButton#nav {{ background: transparent; border: 1px solid transparent; border-radius: 10px;
                   text-align: left; padding: 10px 12px; color: {C['muted']}; }}
QPushButton#nav:hover {{ background: rgba(20, 70, 86, 180); color: {C['text']}; }}
QPushButton#nav:checked {{ background: rgba(16, 78, 90, 230); color: {C['cyan']}; border-color: #2A8F96; }}
QPushButton#cardButton {{ background: transparent; color: {C['cyan']}; border: 1px solid #2A8F96;
                         border-radius: 10px; padding: 8px 14px; font-weight: 600; }}
QPushButton#cardButton:hover {{ background: rgba(62, 224, 210, 40); }}
QPushButton#chip {{ border-radius: 16px; padding: 8px 16px; color: {C['muted']}; background: {C['panel']}; }}
QPushButton#chip:hover {{ color: {C['cyan']}; }}
QPushButton#mic {{ border-radius: 20px; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; padding: 0; }}
QPushButton#mic:checked {{ background: {C['danger']}; border-color: {C['danger']}; }}
#inputBar {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 16px; }}
#inputBar QLineEdit {{ background: transparent; border: none; font-size: 15px; padding: 8px; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{ background: {C['surface']}; border: 1px solid {C['border']};
    border-radius: 8px; padding: 6px 8px; selection-background-color: {C['cyan']}; selection-color: #04121A; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {C['cyan']}; }}
QComboBox QAbstractItemView {{ background: {C['surface']}; border: 1px solid {C['border']}; selection-background-color: {C['surface2']}; }}
QListWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; color: {C['muted']}; }}
QListWidget::item:hover {{ background: {C['surface']}; color: {C['text']}; }}
QListWidget::item:selected {{ background: {C['surface2']}; color: {C['cyan']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {C['border']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
#bubbleUser {{ background: {C['blue']}; border-radius: 14px; }}
#bubbleAssistant {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 14px; }}
#bubbleError {{ background: #2A0F1A; border: 1px solid {C['danger']}; border-radius: 14px; }}
#confirmBox {{ background: #1F1A0A; border: 1px solid {C['warn']}; border-radius: 12px; }}
#taskGoal {{ font-size: 15px; font-weight: 600; }}
QTabWidget::pane {{ border: 1px solid {C['border']}; border-radius: 10px; top: -1px; background: {C['panel']}; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {C['muted']}; }}
QTabBar::tab:selected {{ color: {C['cyan']}; border-bottom: 2px solid {C['cyan']}; }}
QDialog {{ background: {C['bg']}; }}
QTableWidget {{ background: {C['panel']}; border: 1px solid {C['border']}; gridline-color: {C['border']}; border-radius: 8px; }}
QHeaderView::section {{ background: {C['surface']}; color: {C['muted']}; border: none; padding: 6px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['border']}; border-radius: 4px; background: {C['surface']}; }}
QCheckBox::indicator:checked {{ background: {C['cyan']}; border-color: {C['cyan']}; }}
"""
