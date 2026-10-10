"""
J.A.R.V.I.S HUD  -  Iron-Man-Oberflaeche fuer das Jarvis-Projekt

Start:  py -3.12 ui.py
Bedienung:  ESC = beenden,  F11 = Vollbild,  Fenster mit der Maus verschieben
"""
import math
import os
import random
import sys
import threading
import time
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, QPointF, QRectF, QRect
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
                         QLinearGradient, QFontMetrics)
from PyQt5.QtWidgets import QApplication, QWidget

try:
    import psutil
except ImportError:  # HUD laeuft auch ohne Systemanzeigen
    psutil = None

HERE = os.path.dirname(os.path.abspath(__file__))

CYAN = QColor(0, 229, 255)
ORANGE = QColor(255, 170, 0)
YELLOW = QColor(255, 214, 80)
TEXT = QColor(205, 245, 255)
DIM = QColor(110, 160, 175)

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def rgba(color, alpha):
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def mono(size, bold=False):
    f = QFont("Consolas", size)
    f.setStyleHint(QFont.Monospace)
    f.setBold(bold)
    return f


class Bridge(QObject):
    """Verbindet die Jarvis-Threads sicher mit dem Fenster."""
    jarvis_said = pyqtSignal(str)
    speech_done = pyqtSignal()


class HUD(QWidget):
    def __init__(self, bridge=None):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S")
        self.resize(1180, 700)
        self.setMinimumSize(980, 620)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFocusPolicy(Qt.StrongFocus)

        self.t0 = time.time()
        self.status = "STARTING"
        self.status_since = time.time()
        self.speak_count = 0
        self.log = []                 # (wer, text, uhrzeit)
        self.user_line = ""
        self.pending = ""
        self.pending_t = 0.0
        self.logged = ""
        self.spikes = [0.0] * 96
        self.cpu = 0.0
        self.ram = 0.0
        self.bat = None
        self.charging = False
        self.close_rect = QRectF(0, 0, 0, 0)
        self._drag = None

        if bridge is not None:
            bridge.jarvis_said.connect(self.on_jarvis_said)
            bridge.speech_done.connect(self.on_speech_done)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_input)
        self.poll_timer.start(250)

        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self.update_system)
        self.sys_timer.start(2000)
        self.update_system()

    # ------------------------------------------------------------------ Logik
    @property
    def speaking(self):
        return self.speak_count > 0

    def set_status(self, s):
        self.status = s
        self.status_since = time.time()

    def add_log(self, who, text):
        text = " ".join(str(text).split())
        if not text:
            return
        self.log.append((who, text, datetime.now().strftime("%H:%M:%S")))
        self.log = self.log[-60:]

    def on_jarvis_said(self, text):
        self.speak_count += 1
        self.set_status("SPEAKING")
        self.add_log("JARVIS", text)

    def on_speech_done(self):
        self.speak_count = max(0, self.speak_count - 1)
        if self.speak_count == 0:
            self.set_status("LISTENING")

    def poll_input(self):
        """Liest, was die Spracherkennung in input.txt geschrieben hat."""
        path = os.path.join(os.getcwd(), "input.txt")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
        except OSError:
            return
        if text:
            if text != self.pending:
                self.pending = text
                self.pending_t = time.time()
            self.user_line = text
        else:
            self.commit_pending()
            self.pending = ""
            self.logged = ""

    def commit_pending(self):
        if self.pending and self.pending != self.logged:
            self.add_log("DU", self.pending)
            self.logged = self.pending
            if not self.speaking:
                self.set_status("PROCESSING")

    def update_system(self):
        if psutil is None:
            return
        try:
            self.cpu = psutil.cpu_percent(None)
            self.ram = psutil.virtual_memory().percent
            b = psutil.sensors_battery()
            if b is not None:
                self.bat = b.percent
                self.charging = bool(b.power_plugged)
        except Exception:
            pass

    def tick(self):
        now = time.time()
        t = now - self.t0
        for i in range(len(self.spikes)):
            if self.speaking:
                target = random.uniform(0.15, 1.0)
            else:
                target = 0.08 + 0.06 * math.sin(t * 1.4 + i * 0.35)
            self.spikes[i] += (target - self.spikes[i]) * 0.35

        if self.pending and now - self.pending_t > 1.2:
            self.commit_pending()
        if self.status == "PROCESSING" and now - self.status_since > 10:
            self.set_status("LISTENING")
        if self.status == "STARTING" and now - self.status_since > 25:
            self.set_status("LISTENING")
        self.update()

    # ----------------------------------------------------------------- Eingabe
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        elif e.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.close_rect.contains(QPointF(e.pos())):
                self.close()
                return
            if not self.isFullScreen():
                self._drag = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def closeEvent(self, e):
        # Chrome der Spracherkennung und alle Jarvis-Threads sauber beenden
        try:
            if psutil is not None:
                for child in psutil.Process().children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass
        except Exception:
            pass
        e.accept()
        os._exit(0)

    # ----------------------------------------------------------------- Zeichnen
    def paintEvent(self, _):
        t = time.time() - self.t0
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        self.draw_background(p, w, h, t)

        top, bottom = 110, 100
        cx = w / 2
        cy = top + (h - top - bottom) / 2
        avail = (w - 2 * 340) / 2
        R = max(60, min(avail / 1.42, (h - top - bottom) / 2.84))

        self.draw_reactor(p, cx, cy, R, t)
        self.draw_header(p, w, t)
        self.draw_left(p, 44, 120)
        self.draw_log(p, QRectF(w - 44 - 280, 120, 280, h - 120 - 100))
        self.draw_footer(p, w, h, t)
        self.draw_corners(p, w, h)
        p.end()

    def accent(self):
        return ORANGE if self.speaking else CYAN

    def draw_background(self, p, w, h, t):
        p.fillRect(0, 0, w, h, QColor(2, 8, 12))
        g = QRadialGradient(w / 2, h / 2, max(w, h) * 0.65)
        g.setColorAt(0.0, rgba(CYAN, 38))
        g.setColorAt(1.0, rgba(CYAN, 0))
        p.fillRect(0, 0, w, h, QBrush(g))

        p.setPen(QPen(rgba(CYAN, 12), 1))
        for x in range(0, w, 48):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 48):
            p.drawLine(0, y, w, y)

        # wandernde Scan-Linie
        y = ((t % 7.0) / 7.0) * (h + 160) - 80
        sg = QLinearGradient(0, y - 60, 0, y + 60)
        sg.setColorAt(0.0, rgba(CYAN, 0))
        sg.setColorAt(0.5, rgba(CYAN, 22))
        sg.setColorAt(1.0, rgba(CYAN, 0))
        p.fillRect(0, int(y - 60), w, 120, QBrush(sg))

    def draw_reactor(self, p, cx, cy, R, t):
        sp = 2.2 if self.speaking else 1.0
        pulse = 0.5 + 0.5 * math.sin(t * (8.0 if self.speaking else 2.2))
        acc = self.accent()
        center = QPointF(cx, cy)

        # Leuchten
        g = QRadialGradient(center, R * 1.5)
        g.setColorAt(0.0, rgba(acc, 80 + 60 * pulse))
        g.setColorAt(0.55, rgba(CYAN, 20))
        g.setColorAt(1.0, rgba(CYAN, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(center, R * 1.5, R * 1.5)
        p.setBrush(Qt.NoBrush)

        # Audio-Zacken
        p.save()
        p.translate(cx, cy)
        n = len(self.spikes)
        for i in range(n):
            length = 3 + self.spikes[i] * R * 0.22
            p.setPen(QPen(rgba(acc, 90 + 140 * self.spikes[i]), 2))
            p.drawLine(QPointF(R * 1.18, 0), QPointF(R * 1.18 + length, 0))
            p.rotate(360.0 / n)
        p.restore()

        # Skalenring mit Strichen
        p.save()
        p.translate(cx, cy)
        p.rotate(t * 6 * sp)
        for i in range(72):
            long_tick = (i % 6 == 0)
            r1 = R * 1.08
            r2 = r1 + (R * 0.06 if long_tick else R * 0.03)
            p.setPen(QPen(rgba(CYAN, 210 if long_tick else 110), 2 if long_tick else 1))
            p.drawLine(QPointF(r1, 0), QPointF(r2, 0))
            p.rotate(5)
        p.restore()

        # Ring A: drei dicke Boegen
        self.glow_arcs(p, cx, cy, R * 1.0, [(0, 70), (120, 70), (240, 70)],
                       t * 35 * sp, acc, 5)
        # Ring B: viele kurze Segmente, gegenlaeufig
        segs = [(i * 15, 9) for i in range(24)]
        self.glow_arcs(p, cx, cy, R * 0.84, segs, -t * 50 * sp, CYAN, 3, alpha=170)
        # Ring C: zwei breite Boegen
        self.glow_arcs(p, cx, cy, R * 0.66, [(0, 100), (180, 100)],
                       -t * 70 * sp, acc, 9, alpha=200)

        # duenner Kreis
        p.setPen(QPen(rgba(CYAN, 130), 1))
        p.drawEllipse(center, R * 0.50, R * 0.50)

        # zwei gegenlaeufige Dreiecke
        for direction, ang in ((1, t * 40 * sp), (-1, 60 - t * 40 * sp)):
            pts = []
            for k in range(3):
                a = math.radians(ang + k * 120)
                pts.append(QPointF(cx + R * 0.46 * math.cos(a), cy + R * 0.46 * math.sin(a)))
            p.setPen(QPen(rgba(CYAN if direction == 1 else acc, 200), 2))
            for k in range(3):
                p.drawLine(pts[k], pts[(k + 1) % 3])

        # Kern
        core_r = R * 0.30 * (0.92 + 0.12 * pulse)
        cg = QRadialGradient(center, core_r * 1.6)
        cg.setColorAt(0.0, QColor(255, 255, 255, 255))
        cg.setColorAt(0.35, rgba(acc, 255))
        cg.setColorAt(0.75, rgba(acc, 110))
        cg.setColorAt(1.0, rgba(acc, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(cg))
        p.drawEllipse(center, core_r * 1.6, core_r * 1.6)
        p.setBrush(Qt.NoBrush)

    def glow_arcs(self, p, cx, cy, r, arcs, rotation, color, width, alpha=255):
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        for start, span in arcs:
            s = int(((start + rotation) % 360) * 16)
            for wmul, a in ((4, 0.10), (2, 0.25), (1, 1.0)):
                pen = QPen(rgba(color, alpha * a), width * wmul)
                pen.setCapStyle(Qt.FlatCap)
                p.setPen(pen)
                p.drawArc(rect, s, int(span * 16))

    def draw_header(self, p, w, t):
        f = QFont("Segoe UI", 24)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 12)
        p.setFont(f)
        p.setPen(QPen(rgba(CYAN, 255)))
        p.drawText(QRectF(0, 18, w, 46), Qt.AlignCenter, "J.A.R.V.I.S")

        labels = {
            "STARTING": ("STARTET", DIM),
            "LISTENING": ("HOERT ZU", CYAN),
            "PROCESSING": ("VERARBEITET", YELLOW),
            "SPEAKING": ("SPRICHT", ORANGE),
        }
        text, color = labels.get(self.status, (self.status, CYAN))
        blink = 0.55 + 0.45 * math.sin(t * 5)
        p.setFont(mono(11, True))
        fm = QFontMetrics(p.font())
        tw = fm.horizontalAdvance(text)
        y = 84
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(color, 255 * blink))
        p.drawEllipse(QPointF(w / 2 - tw / 2 - 14, y - 5), 4, 4)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color))
        p.drawText(QRectF(0, y - 14, w, 22), Qt.AlignCenter, text)

        # Schliessen-Knopf
        self.close_rect = QRectF(w - 46, 14, 30, 30)
        p.setPen(QPen(rgba(CYAN, 150), 1))
        p.drawRect(self.close_rect)
        p.setPen(QPen(rgba(CYAN, 220), 2))
        r = self.close_rect
        p.drawLine(QPointF(r.left() + 9, r.top() + 9), QPointF(r.right() - 9, r.bottom() - 9))
        p.drawLine(QPointF(r.right() - 9, r.top() + 9), QPointF(r.left() + 9, r.bottom() - 9))

    def panel_title(self, p, x, y, text, width):
        p.setFont(mono(10, True))
        p.setPen(QPen(ORANGE))
        p.drawText(QPointF(x, y), text)
        p.setPen(QPen(rgba(CYAN, 120), 1))
        p.drawLine(QPointF(x, y + 6), QPointF(x + width, y + 6))
        p.setPen(QPen(rgba(ORANGE, 255), 2))
        p.drawLine(QPointF(x, y + 6), QPointF(x + 28, y + 6))

    def bar(self, p, x, y, width, label, value, suffix="%"):
        p.setFont(mono(10))
        p.setPen(QPen(DIM))
        p.drawText(QPointF(x, y), label)
        txt = "--" if value is None else "%d%s" % (value, suffix)
        p.setPen(QPen(TEXT))
        p.drawText(QRectF(x, y - 14, width, 18), Qt.AlignRight, txt)
        track = QRectF(x, y + 6, width, 7)
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(CYAN, 28))
        p.drawRect(track)
        if value is not None:
            fill = QRectF(x, y + 6, width * max(0.0, min(100.0, value)) / 100.0, 7)
            g = QLinearGradient(fill.left(), 0, fill.right(), 0)
            g.setColorAt(0, rgba(CYAN, 150))
            g.setColorAt(1, rgba(CYAN, 255))
            p.setBrush(QBrush(g))
            p.drawRect(fill)
        p.setBrush(Qt.NoBrush)

    def draw_left(self, p, x, y):
        width = 220
        now = datetime.now()
        self.panel_title(p, x, y, "ZEIT", width)
        p.setFont(mono(30, True))
        p.setPen(QPen(CYAN))
        p.drawText(QPointF(x, y + 52), now.strftime("%H:%M:%S"))
        p.setFont(mono(11))
        p.setPen(QPen(TEXT))
        p.drawText(QPointF(x, y + 78), WEEKDAYS[now.weekday()])
        p.setPen(QPen(DIM))
        p.drawText(QPointF(x, y + 98), now.strftime("%d.%m.%Y"))

        y2 = y + 140
        self.panel_title(p, x, y2, "SYSTEM", width)
        self.bar(p, x, y2 + 36, width, "CPU", self.cpu)
        self.bar(p, x, y2 + 78, width, "RAM", self.ram)
        bat_label = "AKKU (LAEDT)" if self.charging else "AKKU"
        self.bar(p, x, y2 + 120, width, bat_label, self.bat)

    def draw_log(self, p, rect):
        self.panel_title(p, rect.x(), rect.y(), "KOMMUNIKATION", rect.width())
        inner = QRectF(rect.x(), rect.y() + 18, rect.width(), rect.height() - 18)
        p.setPen(QPen(rgba(CYAN, 55), 1))
        p.setBrush(rgba(CYAN, 10))
        p.drawRect(inner)
        p.setBrush(Qt.NoBrush)

        p.save()
        p.setClipRect(inner)
        font = mono(10)
        p.setFont(font)
        fm = QFontMetrics(font)
        pad = 12
        body_w = int(inner.width() - 2 * pad)

        if not self.log:
            p.setPen(QPen(DIM))
            p.drawText(QRectF(inner.x() + pad, inner.y() + pad, body_w, 60),
                       Qt.TextWordWrap, "Warte auf Sprachbefehl ...")
        y = inner.bottom() - 10
        for who, txt, ts in reversed(self.log):
            br = fm.boundingRect(QRect(0, 0, body_w, 2000), Qt.TextWordWrap, txt)
            y -= br.height() + 18
            if y + br.height() + 18 < inner.top():
                break
            color = ORANGE if who == "JARVIS" else CYAN
            p.setPen(QPen(rgba(color, 255)))
            p.drawText(QPointF(inner.x() + pad, y + 11), "%s  %s" % (who, ts))
            p.setPen(QPen(TEXT))
            p.drawText(QRectF(inner.x() + pad, y + 16, body_w, br.height() + 4),
                       Qt.TextWordWrap, txt)
            y -= 10
        p.restore()

    def draw_footer(self, p, w, h, t):
        p.setFont(mono(15))
        fm = QFontMetrics(p.font())
        if self.user_line:
            caret = "_" if int(t * 2) % 2 == 0 else " "
            txt = fm.elidedText(self.user_line, Qt.ElideLeft, int(w * 0.5))
            p.setPen(QPen(TEXT))
            p.drawText(QRectF(0, h - 86, w, 30), Qt.AlignCenter, "> " + txt + caret)
        else:
            p.setPen(QPen(DIM))
            p.drawText(QRectF(0, h - 86, w, 30), Qt.AlignCenter,
                       "Sprich jetzt ... (Befehle auf Englisch)")
        p.setFont(mono(9))
        p.setPen(QPen(rgba(DIM, 170)))
        p.drawText(QRectF(0, h - 40, w, 20), Qt.AlignCenter,
                   "ESC beenden   |   F11 Vollbild   |   Fenster mit der Maus verschieben")

    def draw_corners(self, p, w, h):
        p.setPen(QPen(rgba(self.accent(), 170), 2))
        m, L = 14, 30
        for (x, y, dx, dy) in ((m, m, 1, 1), (w - m, m, -1, 1),
                               (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * L, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * L))


# --------------------------------------------------------------- Jarvis anbinden
def install_speak_hook(bridge):
    """Meldet jeden gesprochenen Satz an das Fenster, bevor die anderen Module speak importieren."""
    import TextToSpeech.Fast_DF_TTS as tts
    original = tts.speak

    def hooked(text):
        try:
            bridge.jarvis_said.emit(str(text))
        except Exception:
            pass
        try:
            return original(text)
        finally:
            try:
                bridge.speech_done.emit()
            except Exception:
                pass

    tts.speak = hooked


def run_jarvis():
    """Startet jarvis.py wie 'python jarvis.py', aber im Hintergrund."""
    import runpy
    import traceback
    try:
        runpy.run_path(os.path.join(HERE, "jarvis.py"), run_name="__main__")
    except Exception:
        traceback.print_exc()


def main():
    os.chdir(HERE)
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    bridge = Bridge()
    hud = HUD(bridge)

    try:
        install_speak_hook(bridge)
    except Exception as e:
        print("Hinweis: Sprachausgabe konnte nicht angebunden werden:", e)

    hud.show()
    threading.Thread(target=run_jarvis, daemon=True).start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
