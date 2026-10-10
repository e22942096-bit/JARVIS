import re
import sys
import time
import threading

import pyttsx3

try:
    import pythoncom  # kommt mit pywin32, wird fuer Threads unter Windows gebraucht
except ImportError:
    pythoncom = None

# Es darf immer nur eine Sprachausgabe gleichzeitig laufen
_lock = threading.Lock()

# Woerter, an denen Jarvis erkennt, dass ein Text deutsch ist
_GERMAN_WORDS = {
    "ich", "und", "nicht", "ist", "das", "der", "ein", "eine", "du", "wir",
    "bin", "kann", "habe", "heute", "wetter", "mit", "für", "auf", "zu",
    "nein", "bitte", "danke", "hallo", "gerade", "keine", "antwort",
}


def _looks_german(text: str) -> bool:
    low = text.lower()
    if any(c in low for c in "äöüß"):
        return True
    words = set(re.findall(r"[a-zäöüß]+", low))
    return len(words & _GERMAN_WORDS) >= 1


def _pick_voice(engine, text: str) -> None:
    """Waehlt eine deutsche oder englische Windows-Stimme passend zum Text."""
    if _looks_german(text):
        keys = ("german", "deutsch", "de-de", "de_de", "hedda", "katja", "stefan")
    else:
        keys = ("english", "en-us", "en-gb", "david", "zira", "mark", "hazel")
    try:
        for v in engine.getProperty("voices"):
            blob = f"{v.id} {v.name} {getattr(v, 'languages', '')}".lower()
            if any(k in blob for k in keys):
                engine.setProperty("voice", v.id)
                return
    except Exception:
        pass  # dann bleibt die Standardstimme


def print_animated_message(message):
    for char in message:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.050)  # Geschwindigkeit der Textanimation
    print()


def Co_speak(message: str, voice: str = "", folder: str = "", extension: str = ".mp3"):
    """Spricht den Text mit der Windows-Sprachausgabe (offline)."""
    with _lock:
        try:
            if pythoncom is not None:
                pythoncom.CoInitialize()
            engine = pyttsx3.init()
            _pick_voice(engine, message)
            engine.setProperty("rate", 175)
            engine.say(message)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print("Sprachausgabe Fehler:", e)
    return None


def speak(text):
    t1 = threading.Thread(target=Co_speak, args=(text,))
    t2 = threading.Thread(target=print_animated_message, args=(text,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
