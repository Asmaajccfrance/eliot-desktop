"""Mesure d'usage optionnelle (PostHog).

N'envoie rien tant que posthog.actif n'est pas true et qu'une clé n'est pas
posée. Le contenu des demandes, les arguments et les clés ne partent pas :
seulement le nom de l'outil, sa réussite et sa durée.
"""
import json
import logging
import threading
import urllib.request

from core.config import reglage

LOG = logging.getLogger("jarvis.usage")


def signaler(nom, ok, duree):
    if not reglage("posthog.actif", False):
        return
    cle = str(reglage("posthog.cle", "") or "").strip()
    if not cle:
        return
    hote = str(reglage("posthog.hote", "https://eu.i.posthog.com") or "").rstrip("/")
    corps = json.dumps({
        "api_key": cle,
        "event": "outil_jarvis",
        "distinct_id": "jarvis-local",
        "properties": {
            "outil": str(nom or "")[:80],
            "ok": bool(ok),
            "duree_s": round(float(duree or 0), 3),
        },
    }).encode("utf-8")

    def envoyer():
        try:
            requete = urllib.request.Request(
                hote + "/capture/",
                data=corps,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(requete, timeout=3) as reponse:
                reponse.read()
        except Exception:
            LOG.debug("posthog indisponible", exc_info=True)

    threading.Thread(target=envoyer, daemon=True).start()
