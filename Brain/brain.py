import os
import requests

# Gespraechsverlauf, damit Jarvis den Zusammenhang behaelt
_history = []

SYSTEM_PROMPT = (
    "Du bist J.A.R.V.I.S, ein hilfreicher Sprachassistent. "
    "Antworte kurz und klar in hoechstens zwei bis drei Saetzen, "
    "weil deine Antwort laut vorgelesen wird. "
    "Antworte in der Sprache, in der der Nutzer mit dir spricht. "
    "Verwende keine Sonderzeichen, Listen oder Markdown."
)

# Modelle, die der Reihe nach probiert werden
MODELS = ["gemini-flash-latest", "gemini-2.5-flash"]


def _load_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_file = os.path.join(here, "api_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def _call(model, key, payload):
    """Probiert erst die normale Gemini API, dann den Vertex Express Zugang."""
    urls = [
        (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": key, "Content-Type": "application/json"},
            {},
        ),
        (
            f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent",
            {"Content-Type": "application/json"},
            {"key": key},
        ),
    ]
    last_error = None
    for url, headers, params in urls:
        try:
            r = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()
            last_error = f"{r.status_code}: {r.text[:300]}"
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(last_error)


def Main_Brain(text):
    key = _load_api_key()
    if not key:
        return "Sir, mir fehlt der API Schluessel. Lege ihn in die Datei api_key.txt."

    _history.append({"role": "user", "parts": [{"text": text}]})
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": _history[-20:],
        "generationConfig": {"maxOutputTokens": 300},
    }

    last_error = None
    for model in MODELS:
        try:
            data = _call(model, key, payload)
            parts = data["candidates"][0]["content"]["parts"]
            answer = "".join(p.get("text", "") for p in parts).strip()
            _history.append({"role": "model", "parts": [{"text": answer}]})
            return answer
        except Exception as e:
            last_error = e

    print("Brain Fehler:", last_error)
    if _history and _history[-1]["role"] == "user":
        _history.pop()
    return "Sir, ich konnte gerade keine Antwort erzeugen."
