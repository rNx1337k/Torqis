"""Widgets próprios: logo, mostrador de painel, indicador de pulso, toast, mosaicos, banner animado
e mapa do veículo."""
import math
import os
from collections import deque

from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QPoint, QPointF, QPropertyAnimation, QRectF, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QAbstractSpinBox, QDialog, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QTableView, QTreeView,
                               QVBoxLayout, QWidget)

from .style import (BLUE_SOFT, CYAN, DIM, LINE, MUTED, OK, RED, TEXT, WARN)
from ..i18n import decimal, tr, tr_data

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class SpinBoxTextMargin(QObject):
    """Acertos que o QSS não consegue fazer, aplicados a cada widget quando é criado (instalado na aplicação):
    - caixas numéricas (QSpinBox): o Qt ignora o padding do QSS no texto e o número ficava colado à margem;
    - tabelas: sem a grelha de linhas verticais (só a separação entre linhas, no QSS) e com os títulos das colunas
      alinhados à esquerda como o conteúdo."""

    LEFT = 8

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish:
            if isinstance(obj, QAbstractSpinBox):
                edit = obj.findChild(QLineEdit)
                if edit is not None:
                    edit.setTextMargins(self.LEFT, 0, 0, 0)
            elif isinstance(obj, QTableView):
                obj.setShowGrid(False)
                obj.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            elif isinstance(obj, QTreeView):
                obj.header().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return False


def install_spinbox_margin(app):
    """Uma vez por aplicação (guardado na própria aplicação para não ser libertado)."""
    if getattr(app, "_rad_spin_margin", None) is None:
        app._rad_spin_margin = SpinBoxTextMargin(app)
        app.installEventFilter(app._rad_spin_margin)
    return app._rad_spin_margin


def asset_path(name):
    return os.path.join(ASSETS, name)


def logo_pixmap(size, dpr=1.0):
    pm = QPixmap(asset_path("logo.png"))
    if pm.isNull():
        return pm
    px = int(size * dpr)
    pm = pm.scaled(px, px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm.setDevicePixelRatio(dpr)
    return pm


def display_font(pt, bold=True):
    f = QFont("Bahnschrift")
    f.setPointSizeF(pt)
    f.setBold(bold)
    return f


def alpha(color, a):
    c = QColor(color)
    c.setAlpha(a)
    return c


def glow(widget, color=CYAN, radius=32, strength=110):
    """Brilho suave à volta de um widget (sombra sem deslocamento)."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setOffset(0, 0)
    eff.setBlurRadius(radius)
    eff.setColor(alpha(color, strength))
    widget.setGraphicsEffect(eff)
    return eff


class LogoLabel(QLabel):
    def __init__(self, size):
        super().__init__()
        self.setFixedSize(size, size)
        self.setPixmap(logo_pixmap(size, self.devicePixelRatioF() or 1.0))


# ------------------------------------------------------------- mostrador
UNIT_RANGES = {
    "/min": (0, 5000), "°C": (-40, 140), "V": (0, 16), "mbar": (0, 2600), "km/h": (0, 240),
    "%": (0, 100), "mg/H": (0, 60), "g/s": (0, 160), "bar": (0, 3), "ms": (0, 20),
    "° KW": (-10, 30), "° APMS": (0, 30), "° AAPMS": (0, 30), "A": (0, 150), "l/h": (0, 20),
    "kW": (0, 200), "Nm": (0, 400), "°": (-30, 30), "km": (0, 300000), "Ω": (0, 5000),
}


def unit_range(unit):
    """Gama do mostrador para a unidade (as unidades podem vir traduzidas, ex.: "° APMS" → "° BTDC")."""
    if unit in UNIT_RANGES:
        return UNIT_RANGES[unit]
    for key, rng in UNIT_RANGES.items():
        if tr_data(key) == unit:
            return rng
    return (0.0, 0.0)


def nice_ceil(x):
    if x <= 0:
        return 1
    mag = 10 ** math.floor(math.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if x <= m * mag:
            return m * mag
    return 10 * mag


def short_num(v):
    av = abs(v)
    if av >= 10000:
        return f"{v / 1000:.0f}k"
    if av >= 1000 and v == int(v) and int(v) % 1000 == 0:
        return f"{int(v / 1000)}k"
    if v == int(v):
        return str(int(v))
    return decimal(f"{v:.1f}")


def _arc_gradient(cx, cy):
    """Gradiente da escala: azul no início, ciano no topo, ciano claro no fim (arco de 210° a -30°)."""
    g = QConicalGradient(cx, cy, -30)
    g.setColorAt(0.0, QColor("#B4D2FF"))
    g.setColorAt(0.333, QColor(CYAN))
    g.setColorAt(0.667, QColor("#3B66FF"))
    g.setColorAt(1.0, QColor("#3B66FF"))
    return g


class GaugeCell(QWidget):
    """Mostrador circular estilo painel VAG: escala azul→ciano com brilho, ponteiro vermelho animado,
    histórico em baixo. Guarda o valor máximo (marca vermelha). Duplo clique abre o gráfico grande."""
    opened = Signal(int)

    def __init__(self, n):
        super().__init__()
        self.n = n
        self.label = None
        self.field = None
        self.key = None
        self.lo, self.hi = 0.0, 100.0
        self.hist = deque(maxlen=90)
        self.peak = None
        self.fixed_range = None
        self.target = 0.0
        self.shown = 0.0
        self.anim = QTimer(self)
        self.anim.setInterval(16)
        self.anim.timeout.connect(self._step)
        self.setMinimumSize(170, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("Duplo clique para abrir o gráfico"))

    def mouseDoubleClickEvent(self, _ev):
        if self.field is not None:
            self.opened.emit(self.n)

    def reset_peak(self):
        self.peak = None
        self.update()

    def set_fixed_range(self, rng):
        """Escala fixa (mín, máx) — p.ex. desvios dos injectores à volta de 0. None volta à automática."""
        self.fixed_range = tuple(rng) if rng else None
        self.key = None

    def set_label(self, text):
        if text != self.label:
            self.label = text
            self.update()

    def _frac(self, v):
        if v is None or self.hi <= self.lo:
            return 0.0
        return max(0.0, min(1.0, (v - self.lo) / (self.hi - self.lo)))

    def set(self, field):
        if field is None:
            self.field = None
            self.key = None
            self.hist.clear()
            self.setToolTip("")
            self.target = 0.0
            self._kick()
            return
        key = (field["formula"], field["unit"])
        if key != self.key:
            self.key = key
            self.hist.clear()
            self.peak = None
            self.lo, self.hi = self.fixed_range or unit_range(field["unit"])
        self.field = field
        v = field.get("numeric")
        if v is not None:
            self.hist.append(v)
            self.peak = v if self.peak is None else max(self.peak, v)
            if self.hi <= self.lo:
                self.lo, self.hi = (min(0.0, v), nice_ceil(abs(v) * 1.25) if v else 1.0)
            if v > self.hi:
                self.hi = nice_ceil(v * 1.2)
            if v < self.lo:
                self.lo = -nice_ceil(-v * 1.2)
        self.target = self._frac(v)
        self.setToolTip(tr("fórmula {formula}   a={a}   b={b}\nDuplo clique para abrir o gráfico",
                           formula=field['formula'], a=field['a'], b=field['b']))
        self._kick()

    def _kick(self):
        if abs(self.target - self.shown) > 0.001 and self.isVisible():
            if not self.anim.isActive():
                self.anim.start()
        else:
            self.shown = self.target
        self.update()

    def _step(self):
        d = self.target - self.shown
        if abs(d) < 0.002:
            self.shown = self.target
            self.anim.stop()
        else:
            self.shown += d * 0.25
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        box = QRectF(0.5, 0.5, w - 1, h - 1)
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#1A1D24"))
        bg.setColorAt(1, QColor("#0F1014"))
        f = self.field
        live = f is not None
        p.setPen(QPen(alpha(CYAN, 70) if live else QColor(LINE), 1))
        p.setBrush(bg)
        p.drawRoundedRect(box, 14, 14)
        if live:                                            # brilho no topo do cartão
            tg = QLinearGradient(0, 0, w, 0)
            tg.setColorAt(0, alpha(CYAN, 0))
            tg.setColorAt(0.5, alpha(CYAN, 170))
            tg.setColorAt(1, alpha(CYAN, 0))
            p.setPen(QPen(QBrush(tg), 1.6))
            p.drawLine(QPointF(18, 1), QPointF(w - 18, 1))

        p.setFont(display_font(9, False))
        title = self.label or tr("Campo {n}", n=self.n)
        title = p.fontMetrics().elidedText(title, Qt.ElideRight, int(w - 24))
        p.setPen(QColor(TEXT if self.label else MUTED))
        p.drawText(QRectF(12, 6, w - 24, 20), int(Qt.AlignLeft | Qt.AlignVCenter), title)

        spark_h = 30
        size = max(60.0, min(w - 28.0, h - 34.0 - spark_h - 8))
        cx, cy = w / 2, 28 + size / 2
        rad = size / 2
        dial = QRectF(cx - rad + 6, cy - rad + 6, size - 12, size - 12)
        v = f.get("numeric") if f else None
        frac = self.shown if (f is not None and v is not None) else 0.0

        # pista da escala
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#21242D"), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(dial, 210 * 16, -240 * 16)
        # traços (acendem até ao valor)
        for i in range(21):
            t = i / 20
            ang = math.radians(210 - t * 240)
            major = i % 2 == 0
            r1 = rad - 16
            r2 = r1 - (8 if major else 4)
            lit = f is not None and v is not None and t <= frac + 1e-6
            col = alpha(CYAN, 230) if lit else alpha(DIM, 200 if major else 120)
            p.setPen(QPen(col, 2.0 if major else 1.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx + r1 * math.cos(ang), cy - r1 * math.sin(ang)),
                       QPointF(cx + r2 * math.cos(ang), cy - r2 * math.sin(ang)))

        if f is not None and v is not None and self.hi > self.lo:
            span = int(-240 * 16 * frac)
            if frac > 0.002:
                p.setPen(QPen(alpha(CYAN, 45), 16, Qt.SolidLine, Qt.RoundCap))      # brilho
                p.drawArc(dial, 210 * 16, span)
                p.setPen(QPen(QBrush(_arc_gradient(cx, cy)), 7, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(dial, 210 * 16, span)
            if self.peak is not None and v is not None and self.peak > v:
                pf = self._frac(self.peak)
                pa = math.radians(210 - 240 * pf)
                p.setPen(QPen(QColor(RED), 3, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(cx + (rad - 1) * math.cos(pa), cy - (rad - 1) * math.sin(pa)),
                           QPointF(cx + (rad - 11) * math.cos(pa), cy - (rad - 11) * math.sin(pa)))
            # ponteiro afunilado com brilho
            ang = math.radians(210 - 240 * frac)
            rn = rad - 20
            ux, uy = math.cos(ang), -math.sin(ang)
            nx, ny = -uy, ux
            tip = QPointF(cx + rn * ux, cy + rn * uy)
            tail = QPointF(cx - 12 * ux, cy - 12 * uy)
            needle = QPolygonF([tip, QPointF(cx + 3.2 * nx, cy + 3.2 * ny), tail,
                                QPointF(cx - 3.2 * nx, cy - 3.2 * ny)])
            p.setPen(QPen(alpha(RED, 60), 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawLine(tail, tip)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(RED))
            p.drawPolygon(needle)
            hub = QRadialGradient(cx, cy, 8)
            hub.setColorAt(0, QColor("#FF8A95"))
            hub.setColorAt(1, QColor("#B81D2E"))
            p.setBrush(hub)
            p.drawEllipse(QPointF(cx, cy), 6.5, 6.5)
            p.setBrush(QColor("#0F1014"))
            p.drawEllipse(QPointF(cx, cy), 2.4, 2.4)
            # limites da escala: por fora das pontas do arco, para nunca tocarem no valor nem na unidade (que ficam
            # dentro do mostrador). Num cartão estreito, sem espaço ao lado do mostrador, não se desenham.
            p.setPen(QColor(MUTED))
            p.setFont(display_font(7.5, False))
            reach = (rad - 6) * math.cos(math.radians(30))     # distância horizontal do centro à ponta do arco
            room = cx - reach - 6                               # espaço livre entre a ponta e a borda do cartão
            if room >= 22:
                y = cy + (rad - 6) * 0.5
                p.drawText(QRectF(cx - reach - 6 - room, y - 8, room, 16), int(Qt.AlignRight | Qt.AlignVCenter),
                           short_num(self.lo))
                p.drawText(QRectF(cx + reach + 6, y - 8, room, 16), int(Qt.AlignLeft | Qt.AlignVCenter),
                           short_num(self.hi))

        # valor e unidade
        text_top = cy + rad * 0.22
        if f is None:
            p.setPen(QColor(DIM))
            p.setFont(display_font(16))
            p.drawText(QRectF(0, text_top, w, 30), int(Qt.AlignCenter), "—")
        else:
            big = v is None
            p.setPen(QColor("white"))
            p.setFont(display_font(15 if big else 18))
            vy = cy - 14 if big else text_top
            p.drawText(QRectF(4, vy, w - 8, 30), int(Qt.AlignCenter), decimal(f["value"]))
            p.setPen(QColor(CYAN))
            p.setFont(display_font(9, False))
            unit = f["unit"]
            if not big and self.peak is not None:
                from ..vag_data import display_number
                unit = tr("{unit}   ·   máx {v}", unit=unit, v=display_number(self.peak))
            unit = p.fontMetrics().elidedText(unit, Qt.ElideRight, int(w - 16))
            p.drawText(QRectF(4, vy + 27, w - 8, 18), int(Qt.AlignCenter), unit)

        # histórico (sparkline com preenchimento)
        area = QRectF(12, h - spark_h - 8, w - 24, spark_h)
        p.setPen(QPen(QColor(LINE), 1))
        p.drawLine(QPointF(area.left(), area.bottom()), QPointF(area.right(), area.bottom()))
        if len(self.hist) > 1 and self.hi > self.lo:
            path = QPainterPath()
            n = self.hist.maxlen
            first_x = last_x = 0.0
            for i, val in enumerate(self.hist):
                x = area.left() + area.width() * (i + n - len(self.hist)) / (n - 1)
                y = area.bottom() - area.height() * self._frac(val)
                if i == 0:
                    path.moveTo(x, y)
                    first_x = x
                else:
                    path.lineTo(x, y)
                last_x = x
            fill = QPainterPath(path)
            fill.lineTo(last_x, area.bottom())
            fill.lineTo(first_x, area.bottom())
            fill.closeSubpath()
            fg = QLinearGradient(0, area.top(), 0, area.bottom())
            fg.setColorAt(0, alpha(CYAN, 70))
            fg.setColorAt(1, alpha(CYAN, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(fg)
            p.drawPath(fill)
            p.setPen(QPen(QColor(CYAN), 1.6))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.end()


# ------------------------------------------------------- indicador de pulso
class PulseIndicator(QWidget):
    """Linha de ECG: plana quando desligado, a bater (com brilho) quando há ligação ao controlador."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(34)
        self.mode = "off"            # off | connecting | on
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def set_mode(self, mode):
        self.mode = mode
        if mode == "off":
            self.timer.stop()
        elif not self.timer.isActive():
            self.timer.start()
        self.update()

    def _tick(self):
        self.phase = (self.phase + (4.0 if self.mode == "connecting" else 1.6)) % 90
        self.update()

    @staticmethod
    def _beat(x):
        """Forma de onda de um batimento, x em [0, 90)."""
        pts = [(0, 0), (30, 0), (36, -0.15), (42, 0), (46, 0.25), (52, -1.0), (58, 0.45), (62, 0), (90, 0)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if x1 <= x <= x2:
                return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
        return 0

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mid = h / 2
        if self.mode == "off":
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0, alpha(BLUE_SOFT, 0))
            g.setColorAt(0.5, QColor(BLUE_SOFT))
            g.setColorAt(1, alpha(BLUE_SOFT, 0))
            p.setPen(QPen(QBrush(g), 2))
            p.drawLine(QPointF(4, mid), QPointF(w - 4, mid))
            p.end()
            return
        color = QColor(WARN if self.mode == "connecting" else RED)
        path = QPainterPath()
        for i in range(int(w) - 7):
            x = i + 4
            y = mid + self._beat((i + self.phase) % 90) * (h / 2 - 5)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        fade = QLinearGradient(0, 0, w, 0)
        fade.setColorAt(0, alpha(color, 0))
        fade.setColorAt(0.25, alpha(color, 255))
        fade.setColorAt(1, alpha(color, 255))
        glow_fade = QLinearGradient(0, 0, w, 0)
        glow_fade.setColorAt(0, alpha(color, 0))
        glow_fade.setColorAt(1, alpha(color, 70))
        p.setPen(QPen(QBrush(glow_fade), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QBrush(fade), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.end()


# ------------------------------------------------------------------ toast
class Toast(QLabel):
    ICONS = {"ok": "✔", "warn": "⚠", "bad": "✖", "info": "ℹ"}

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setTextFormat(Qt.RichText)
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade.finished.connect(self.hide)       # stop() não emite finished: mostrar de novo é seguro
        self.slide = QPropertyAnimation(self, b"pos", self)
        self.slide.setEasingCurve(QEasingCurve.OutCubic)
        self.last = ("", "")

    def target_pos(self):
        par = self.parentWidget()
        return QPoint(par.width() - self.width() - 24, par.height() - self.height() - 24)

    def show_msg(self, text, kind="ok"):
        import html
        color = {"ok": OK, "warn": WARN, "bad": RED}.get(kind, CYAN)
        self.last = (text, kind)
        self.setStyleSheet(f"QLabel#toast {{ border-color: {color}; border-left: 4px solid {color}; }}")
        self.setText(f"<span style='color:{color}; font-size:12pt'>{self.ICONS.get(kind, 'ℹ')}</span>"
                     f"&nbsp;&nbsp;{html.escape(text)}")
        self.adjustSize()
        end = self.target_pos()
        self.fade.stop()
        self.slide.stop()
        self.opacity.setOpacity(1.0)
        if not self.isVisible():
            self.move(end + QPoint(0, 26))
            self.slide.setDuration(260)
            self.slide.setStartValue(self.pos())
            self.slide.setEndValue(end)
            self.slide.start()
        else:
            self.move(end)
        self.show()
        self.raise_()
        self.timer.start(3000)

    def _fade_out(self):
        self.fade.setDuration(320)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.start()


# ----------------------------------------------------------- gráfico grande
class LiveChart(QWidget):
    """Gráfico de linha de um valor ao longo do tempo, com grelha, brilho e escala automática."""

    def __init__(self, maxlen=900):
        super().__init__()
        self.values = deque(maxlen=maxlen)
        self.times = deque(maxlen=maxlen)
        self.unit = ""
        self.setMinimumSize(560, 300)

    def add(self, t, v):
        self.times.append(t)
        self.values.append(v)
        self.update()

    def clear(self):
        self.values.clear()
        self.times.clear()
        self.update()

    def stats(self):
        if not self.values:
            return None
        vals = list(self.values)
        return min(vals), max(vals), sum(vals) / len(vals)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#181A21"))
        bg.setColorAt(1, QColor("#0E0F13"))
        p.setPen(QPen(QColor(LINE), 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)
        left, right, top, bottom = 64, w - 18, 18, h - 34
        plot = QRectF(left, top, right - left, bottom - top)
        st = self.stats()
        if st is None:
            p.setPen(QColor(MUTED))
            p.setFont(display_font(11, False))
            p.drawText(plot, int(Qt.AlignCenter), tr("À espera de dados — inicie a leitura"))
            p.end()
            return
        lo, hi, _avg = st
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.12
        lo, hi = lo - pad, hi + pad
        p.setFont(display_font(8, False))
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            val = lo + (hi - lo) * i / 4
            p.setPen(QPen(QColor("#21232B"), 1, Qt.DashLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(4, y - 9, left - 10, 18), int(Qt.AlignRight | Qt.AlignVCenter), short_num(val))
        t0, t1 = self.times[0], self.times[-1]
        span = max(t1 - t0, 1e-6)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(left, bottom + 6, 120, 18), int(Qt.AlignLeft | Qt.AlignVCenter), f"-{span:.0f} s")
        p.drawText(QRectF(right - 120, bottom + 6, 120, 18), int(Qt.AlignRight | Qt.AlignVCenter), tr("agora"))
        path = QPainterPath()
        last = None
        for i, (t, v) in enumerate(zip(self.times, self.values)):
            x = plot.left() + plot.width() * (t - t0) / span
            y = plot.bottom() - plot.height() * (v - lo) / (hi - lo)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
            last = QPointF(x, y)
        fill = QPainterPath(path)
        fill.lineTo(plot.right(), plot.bottom())
        fill.lineTo(plot.left(), plot.bottom())
        fill.closeSubpath()
        fg = QLinearGradient(0, plot.top(), 0, plot.bottom())
        fg.setColorAt(0, alpha(CYAN, 60))
        fg.setColorAt(1, alpha(CYAN, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(fg)
        p.drawPath(fill)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(alpha(CYAN, 50), 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QColor(CYAN), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        if last is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(CYAN, 70))
            p.drawEllipse(last, 8, 8)
            p.setBrush(QColor("white"))
            p.drawEllipse(last, 3.5, 3.5)
        p.end()


class ChartDialog(QDialog):
    """Janela com o gráfico grande de um campo de um grupo de medição."""

    def __init__(self, parent, group, index, title):
        super().__init__(parent)
        self.group, self.index = group, index
        self.setWindowTitle(tr("Grupo {group:03d} · campo {index} — {title}", group=group, index=index, title=title))
        self.resize(820, 460)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        self.title = QLabel(title)
        self.title.setObjectName("h1")
        v.addWidget(self.title)
        self.stats_lbl = QLabel("")
        self.stats_lbl.setObjectName("h2")
        v.addWidget(self.stats_lbl)
        self.chart = LiveChart()
        v.addWidget(self.chart, 1)
        row = QHBoxLayout()
        clear = QPushButton(tr("Limpar"))
        clear.clicked.connect(self.chart.clear)
        close = QPushButton(tr("Fechar"))
        close.clicked.connect(self.close)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)

    def feed(self, t, field):
        v = field.get("numeric")
        if v is None:
            self.stats_lbl.setText(tr("Valor actual: {value} {unit} (não numérico)",
                                      value=decimal(field['value']), unit=field['unit']))
            return
        self.chart.unit = field["unit"]
        self.chart.add(t, v)
        from ..vag_data import display_number
        mn, mx, avg = self.chart.stats()
        u = field["unit"]
        self.stats_lbl.setText(tr("Actual {value} {u}     mín {v}     máx {v2}     média {v3}",
                                  value=decimal(field['value']), u=u, v=display_number(mn), v2=display_number(mx),
                                  v3=display_number(avg)))


# ---------------------------------------------------------------- ícones
def nav_icon(kind, color="#8191B6", size=20):
    """Ícones de linha desenhados à mão (sem ficheiros nem fontes externas)."""
    from PySide6.QtGui import QIcon
    return QIcon(icon_pixmap(kind, color, size))


def icon_pixmap(kind, color="#8191B6", size=20):
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * 2 / 24, size * 2 / 24)
    p.setPen(QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if kind == "home":
        path = QPainterPath()
        path.moveTo(4, 11); path.lineTo(12, 4); path.lineTo(20, 11)
        path.moveTo(6, 9.5); path.lineTo(6, 20); path.lineTo(18, 20); path.lineTo(18, 9.5)
        p.drawPath(path)
        p.drawRect(QRectF(10, 14, 4, 6))
    elif kind == "modules":                       # ficha OBD
        p.drawRoundedRect(QRectF(3, 7, 18, 10), 3, 3)
        for x in (7, 10.5, 14, 17):
            p.drawPoint(QPointF(x, 10.5))
            p.drawPoint(QPointF(x, 13.5))
    elif kind == "module":                        # chip / centralina
        p.drawRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
        for t in (9, 12, 15):
            p.drawLine(QPointF(t, 3), QPointF(t, 6)); p.drawLine(QPointF(t, 18), QPointF(t, 21))
            p.drawLine(QPointF(3, t), QPointF(6, t)); p.drawLine(QPointF(18, t), QPointF(21, t))
    elif kind == "autoscan":                      # radar
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        p.drawEllipse(QPointF(12, 12), 4.5, 4.5)
        p.drawLine(QPointF(12, 12), QPointF(18, 6))
    elif kind == "history":                       # relógio
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        p.drawLine(QPointF(12, 12), QPointF(12, 7))
        p.drawLine(QPointF(12, 12), QPointF(15.5, 14))
    elif kind == "options":                       # engrenagem
        p.drawEllipse(QPointF(12, 12), 3.2, 3.2)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(12 + 6 * math.cos(a), 12 + 6 * math.sin(a)),
                       QPointF(12 + 8.8 * math.cos(a), 12 + 8.8 * math.sin(a)))
        p.drawEllipse(QPointF(12, 12), 6, 6)
    elif kind == "search":                        # lupa
        p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
        p.drawLine(QPointF(15, 15), QPointF(20, 20))
    elif kind == "report":                        # documento
        path = QPainterPath()
        path.moveTo(6, 3); path.lineTo(14, 3); path.lineTo(18, 7); path.lineTo(18, 21); path.lineTo(6, 21)
        path.closeSubpath()
        p.drawPath(path)
        for y in (11, 14, 17):
            p.drawLine(QPointF(9, y), QPointF(15, y))
    elif kind == "sim":                           # play
        p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        tri = QPolygonF([QPointF(10, 8.5), QPointF(16, 12), QPointF(10, 15.5)])
        p.drawPolygon(tri)
    elif kind == "fault":                         # triângulo de aviso
        tri = QPolygonF([QPointF(12, 3.5), QPointF(21, 19.5), QPointF(3, 19.5)])
        p.drawPolygon(tri)
        p.drawLine(QPointF(12, 9.5), QPointF(12, 14))
        p.drawPoint(QPointF(12, 17))
    elif kind == "bolt":                          # relâmpago
        poly = QPolygonF([QPointF(13, 3), QPointF(6, 13), QPointF(11.5, 13), QPointF(10.5, 21),
                          QPointF(18, 10.5), QPointF(12.5, 10.5)])
        p.drawPolygon(poly)
    elif kind == "log":                           # terminal
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2.5, 2.5)
        p.drawLine(QPointF(7, 10), QPointF(10, 12.5)); p.drawLine(QPointF(10, 12.5), QPointF(7, 15))
        p.drawLine(QPointF(12, 15), QPointF(17, 15))
    elif kind == "obd":                           # conta-rotações (OBD-II multimarca)
        path = QPainterPath()
        path.arcMoveTo(QRectF(3.5, 5, 17, 17), 200)
        path.arcTo(QRectF(3.5, 5, 17, 17), 200, -220)
        p.drawPath(path)
        p.drawLine(QPointF(12, 13.5), QPointF(16.5, 9))
        p.drawEllipse(QPointF(12, 13.5), 1.2, 1.2)
        p.drawLine(QPointF(8, 20), QPointF(16, 20))
    elif kind == "link":                          # elos (ligação / interfaces)
        p.drawRoundedRect(QRectF(3, 9, 10, 6), 3, 3)
        p.drawRoundedRect(QRectF(11, 9, 10, 6), 3, 3)
    elif kind == "grid":                          # matriz (compatibilidade)
        for x in (4, 10.5, 17):
            for y in (4, 10.5, 17):
                p.drawRoundedRect(QRectF(x, y, 3.5, 3.5), 1, 1)
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


class IconBadge(QWidget):
    """Ícone dentro de um quadrado arredondado com gradiente (usado nos mosaicos e estatísticas)."""

    def __init__(self, kind, color=CYAN, size=40):
        super().__init__()
        self.kind, self.color = kind, color
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        g = QLinearGradient(0, 0, s, s)
        g.setColorAt(0, alpha(self.color, 70))
        g.setColorAt(1, alpha(self.color, 18))
        p.setPen(QPen(alpha(self.color, 110), 1))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0.5, 0.5, s - 1, s - 1), s * 0.3, s * 0.3)
        ic = int(s * 0.55)
        p.drawPixmap(int((s - ic) / 2), int((s - ic) / 2), ic, ic, icon_pixmap(self.kind, self.color, ic))
        p.end()
