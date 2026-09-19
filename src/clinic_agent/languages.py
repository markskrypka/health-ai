"""Which language is this? Enough to pick a voice for a reply and a listening model for a caller.

Measured on an 8 kHz line (2026-09-19): the English voice is understood best in English (96% of words
against 86-88% for Deepgram's bilingual Spanish voices, and it speaks a third faster), so each language
gets its own voice. Deepgram's multilingual model has no Catalan and turns "dijous que ve al matí" into
"Villosca de Almaty"; its Nova-2 Catalan model gets the same audio word for word.
"""

import re

from .tools import fold

VOICES = {"en": "aura-2-thalia-en", "es": "aura-2-carina-es"}
HOLDING = {"en": "One moment, please.", "es": "Un momento, por favor."}
NUDGE = {"en": "Are you still there?", "es": "¿Sigue ahí?"}

_ES = set("el la los las de del que para con su una un es esta cita por favor gracias buenos dias buenas tardes tiene "
          "puede le en al lo hay momento claro perfecto hola si usted manana doctora lunes martes miercoles jueves "
          "viernes sabado domingo nombre apellidos fecha nacimiento seguro disponible primera como cual quiere desea "
          "adios hasta luego y tengo queda reservada las septiembre octubre sigue ahi digame puedo ayudarle quien "
          "senor senora lamento siento necesito".split())
_EN = set("the you your is are i have can could please with at on for would appointment thank thanks good morning "
          "afternoon what which that it of and to this there how help may do does will be like name date birth "
          "earliest available booked monday tuesday wednesday thursday friday saturday september october goodbye "
          "still one moment sorry need".split())
# Words a Catalan speaker says that a Spanish or English speaker does not — spelled the way Deepgram's
# multilingual model tends to write them down.
_CA = ["bon dia", "bona tarda", "bones tardes", "voldria", "parlar", "catala", "si us plau", "sisplau", "gracies",
       "moltes", "merci", "adeu", "em dic", "truco", "trucava", "meva", "meu", "lliure", "tinc", "vull", "metge",
       "metgessa", "dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge", "dema", "mati",
       "tarda", "vaig", "neixer", "amb", "aixo", "doncs", "puc", "pugui", "cognoms", "demanar"]
_CA_RE = [re.compile(rf"\b{re.escape(w)}\b") for w in _CA]


def reply_language(text: str, current: str) -> str:
    """'en' or 'es' for something the agent is about to say; `current` when the words do not settle it."""
    if "¿" in text or "¡" in text:
        return "es"
    words = re.findall(r"[a-z]+", fold(text))
    es, en = sum(w in _ES for w in words), sum(w in _EN for w in words)
    return "es" if es > en else "en" if en > es else current


def sounds_catalan(heard: list[str], tags: list[str]) -> bool:
    """Two Catalan words, or one plus a language tag that is neither Spanish nor English (the multilingual
    model hears Catalan as a blend of Spanish, Portuguese, French and Italian)."""
    said = " ".join(fold(t) for t in heard)
    markers = sum(1 for rx in _CA_RE if rx.search(said))
    foreign = any(t and t[:2] not in ("es", "en") for t in tags)
    return markers >= 2 or (markers >= 1 and foreign)
