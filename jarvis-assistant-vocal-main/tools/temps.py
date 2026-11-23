"""Heure/date, minuteur et rappels vocaux.

Un rappel dit une phrase a l'heure choisie (« vendredi 12 a 10h, rendez-vous »)
ou apres un delai (« dans 10 minutes, vous avez rendez-vous avec... »).
La liste est dans reminders.json : un redemarrage avant l'heure ne l'efface pas.
Il faut que Jarvis tourne au moment voulu pour qu'il parle.
"""
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from core import voix
from core.registre import outil
from core.util import sans_accents

LOG = logging.getLogger("jarvis")
_FICHIER = Path(__file__).resolve().parent.parent / "reminders.json"
_VERROU = threading.Lock()
_DEMARRE = False

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_JOURS_DITS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre")
_MOIS_NORM = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
              "aout", "septembre", "octobre", "novembre", "decembre")


@outil(
    nom="heure_et_date",
    mcp_expose=True,
    description="Donne l'heure et la date actuelles",
)
def heure_et_date() -> str:
    """Donne l'heure et la date actuelles."""
    maintenant = datetime.now()
    jours = ["lundi", "mardi", "mercredi", "jeudi",
             "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
            "aout", "septembre", "octobre", "novembre", "decembre"]
    return (
        f"Il est {maintenant.hour} heures {maintenant.minute}, "
        f"le {jours[maintenant.weekday()]} {maintenant.day} "
        f"{mois[maintenant.month - 1]} {maintenant.year}."
    )


@outil(
    nom="lancer_minuteur",
    mcp_expose=True,
    description="Lance un minuteur qui previendra a voix haute",
    parametres={
        "type": "object",
        "properties": {
            "secondes": {"type": "integer", "description": "Duree en secondes"},
            "libelle": {"type": "string", "description": "Nom du minuteur"},
        },
        "required": ["secondes"],
    },
)
def lancer_minuteur(secondes: int, libelle: str = "") -> str:
    """Lance un minuteur qui previent a voix haute."""
    secondes = max(1, int(secondes))

    def sonner():
        texte = f"Le minuteur {libelle} est termine." if libelle \
            else "Le minuteur est termine."
        voix.parler(texte)

    threading.Timer(secondes, sonner).start()

    if secondes >= 60:
        duree = f"{secondes // 60} minutes"
    else:
        duree = f"{secondes} secondes"
    return f"Minuteur de {duree} lance."


def _maintenant():
    return datetime.now()


def _lire():
    if not _FICHIER.exists():
        return []
    try:
        donnees = json.loads(_FICHIER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return donnees if isinstance(donnees, list) else []


def _ecrire(rappels):
    _FICHIER.write_text(json.dumps(rappels, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def _heure(texte):
    """(heure, minute) ou None si le texte n'en contient pas."""
    normalise = sans_accents(texte or "").lower()
    if re.search(r"\bmidi\b", normalise):
        return 12, 0
    if re.search(r"\bminuit\b", normalise):
        return 0, 0
    trouve = re.search(r"\b(\d{1,2})\s*(?:h|heure|heures)\s*(\d{1,2})?\b", normalise)
    if not trouve:
        trouve = re.search(r"\b(\d{1,2}):(\d{2})\b", normalise)
    if not trouve:
        return None
    heure = int(trouve.group(1))
    minute = int(trouve.group(2) or 0)
    if heure > 23 or minute > 59:
        return None
    return heure, minute


def _sans_heure(texte):
    normalise = sans_accents(texte or "").lower()
    normalise = re.sub(r"\b\d{1,2}\s*(?:h|heure|heures)\s*\d{0,2}\b", " ", normalise)
    normalise = re.sub(r"\b\d{1,2}:\d{2}\b", " ", normalise)
    return normalise


def _delai(texte, maintenant):
    normalise = sans_accents(texte or "").lower()
    if re.search(r"\bdans\s+une\s+heure\b", normalise):
        return maintenant + timedelta(hours=1)
    if re.search(r"\bdans\s+une\s+minute\b", normalise):
        return maintenant + timedelta(minutes=1)
    trouve = re.search(r"\bdans\s+(\d+)\s*(min|minute|minutes|h|heure|heures)\b", normalise)
    if not trouve:
        return None
    nombre = int(trouve.group(1))
    if nombre < 1:
        return None
    if trouve.group(2).startswith("h"):
        return maintenant + timedelta(hours=nombre)
    return maintenant + timedelta(minutes=nombre)


def _jour_calendrier(texte, maintenant):
    """Date visee, sans l'heure. None si aucune date n'est reconnaissable."""
    normalise = _sans_heure(texte)
    semaine = next((i for i, nom in enumerate(_JOURS) if re.search(rf"\b{nom}\b", normalise)), None)
    mois = next((i + 1 for i, nom in enumerate(_MOIS_NORM) if nom in normalise), None)
    numeros = [int(n) for n in re.findall(r"\b(\d{1,2})\b", normalise) if 1 <= int(n) <= 31]
    quantieme = numeros[0] if numeros else None
    if "apres demain" in normalise or "apres-demain" in normalise:
        return maintenant.date() + timedelta(days=2)
    if "demain" in normalise:
        return maintenant.date() + timedelta(days=1)
    if "aujourd" in normalise:
        return maintenant.date()
    if mois and quantieme:
        annee = maintenant.year
        try:
            candidat = datetime(annee, mois, quantieme).date()
        except ValueError:
            return None
        if candidat < maintenant.date():
            try:
                candidat = datetime(annee + 1, mois, quantieme).date()
            except ValueError:
                return None
        if semaine is None or candidat.weekday() == semaine:
            return candidat
        return None
    if quantieme and semaine is not None:
        jour = maintenant.date() - timedelta(days=1)
        for _ in range(431):
            jour += timedelta(days=1)
            if jour.day == quantieme and jour.weekday() == semaine:
                return jour
        return None
    if quantieme:
        jour = maintenant.date()
        for _ in range(62):
            jour += timedelta(days=1)
            if jour.day == quantieme:
                return jour
        return None
    if semaine is not None:
        delta = (semaine - maintenant.weekday()) % 7
        return maintenant.date() + timedelta(days=delta)
    return None


def resoudre_rappel(quand="", dans_minutes=0, maintenant=None):
    """(datetime, "") ou (None, raison courte) pour l'utilisateur."""
    maintenant = maintenant or _maintenant()
    if dans_minutes:
        try:
            minutes = int(dans_minutes)
        except (TypeError, ValueError):
            minutes = 0
        if minutes > 0:
            return maintenant + timedelta(minutes=minutes), ""
    texte = str(quand or "").strip()
    if not texte:
        return None, "quand"
    delai = _delai(texte, maintenant)
    if delai is not None:
        return delai, ""
    jour = _jour_calendrier(texte, maintenant)
    heure = _heure(texte)
    if jour is None:
        return None, "quand"
    if heure is None:
        return None, "heure"
    moment = datetime(jour.year, jour.month, jour.day, heure[0], heure[1])
    sans = _sans_heure(texte)
    jour_nomme = any(re.search(rf"\b{nom}\b", sans) for nom in _JOURS)
    quantieme = re.search(r"\b\d{1,2}\b", sans)
    if moment <= maintenant and jour_nomme and not quantieme:
        moment += timedelta(days=7)
    if moment <= maintenant:
        return None, "passe"
    return moment, ""


def _phrase_moment(moment, maintenant):
    ecart = moment - maintenant
    if timedelta(0) < ecart <= timedelta(hours=2):
        minutes = max(1, int(round(ecart.total_seconds() / 60)))
        if minutes < 60:
            unite = "minute" if minutes == 1 else "minutes"
            return f"Dans {minutes} {unite}"
        return "Dans une heure" if minutes < 90 else f"Dans {minutes // 60} heures"
    heure = f"{moment.hour} heures" if moment.minute == 0 else f"{moment.hour} heures {moment.minute}"
    return (f"{_JOURS_DITS[moment.weekday()].capitalize()} {moment.day} "
            f"{_MOIS[moment.month - 1]} à {heure}")


def _annonce(message):
    message = " ".join(str(message or "").split())
    if not message:
        return ""
    if sans_accents(message).lower().startswith("rappel"):
        return message
    return "Rappel. " + message[0].upper() + message[1:]


@outil(
    nom="poser_rappel",
    description="Programme un rappel dit a voix haute. Pour 'vendredi 12 a 10h, "
                "rendez-vous' ou 'dans 10 minutes, vous avez rendez-vous avec Paul'. "
                "quand = le moment ('vendredi 12 a 10h', 'demain 9h', 'dans 10 minutes'). "
                "dans_minutes = delai en minutes si c'est un delai court. "
                "message = la phrase exacte a prononcer au moment voulu. "
                "Ne cree pas d'evenement d'agenda pour un simple rappel.",
    parametres={
        "type": "object",
        "properties": {
            "message": {"type": "string",
                        "description": "Phrase a dire, par exemple 'Vous avez rendez-vous avec Paul'."},
            "quand": {"type": "string",
                      "description": "Moment : 'vendredi 12 a 10h', 'demain 9h30', 'dans 10 minutes'."},
            "dans_minutes": {"type": "integer",
                             "description": "Delai en minutes. 0 si la date est dans quand."},
        },
        "required": ["message"],
    },
)
def poser_rappel(message: str, quand: str = "", dans_minutes: int = 0) -> str:
    """Enregistre un rappel et le dira a voix haute a l'heure choisie."""
    message = " ".join(str(message or "").split())
    if not message:
        return "Il me faut la phrase du rappel."
    maintenant = _maintenant()
    moment, raison = resoudre_rappel(quand, dans_minutes, maintenant)
    if raison == "heure":
        return "A quelle heure je te le rappelle ?"
    if raison == "passe":
        return "Cette heure est deja passee."
    if moment is None:
        return ("Dis-moi le moment : vendredi 12 a 10 heures, "
                "ou dans 10 minutes.")
    annonce = _annonce(message)
    with _VERROU:
        rappels = _lire()
        rappels.append({
            "echeance": moment.isoformat(timespec="minutes"),
            "message": annonce,
        })
        _ecrire(rappels)
    return f"C'est noté. {_phrase_moment(moment, maintenant)}, je dirai : {message}."


def demarrer_rappels():
    """Surveille reminders.json et parle quand l'heure est la."""
    global _DEMARRE
    with _VERROU:
        if _DEMARRE:
            return
        _DEMARRE = True

    def surveiller():
        while True:
            try:
                _sonner_ceux_qui_sont_dus()
            except Exception:
                LOG.exception("rappels")
            time.sleep(5)

    threading.Thread(target=surveiller, name="rappels", daemon=True).start()


def _sonner_ceux_qui_sont_dus():
    maintenant = _maintenant()
    dus = []
    with _VERROU:
        reste = []
        for rappel in _lire():
            try:
                echeance = datetime.fromisoformat(rappel.get("echeance", ""))
            except ValueError:
                continue
            if echeance <= maintenant:
                dus.append(rappel)
            else:
                reste.append(rappel)
        if dus:
            _ecrire(reste)
    for rappel in dus:
        voix.parler(rappel.get("message") or "Rappel.")
