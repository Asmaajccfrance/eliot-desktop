"""Lecture du texte d'une page web via Firecrawl. Inactif sans firecrawl.cle."""
import json
import urllib.error
import urllib.request

from core.config import reglage
from core.registre import outil


def _cle():
    return str(reglage("firecrawl.cle", "") or "").strip()


def lire(url):
    cle = _cle()
    if not cle:
        return "Firecrawl n'est pas configuré. Ajoute firecrawl.cle dans config.yaml."
    adresse = str(url or "").strip()
    if not adresse.startswith(("http://", "https://")):
        return "Donne-moi une adresse qui commence par https://."
    corps = json.dumps({"url": adresse, "formats": ["markdown"]}).encode("utf-8")
    requete = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=corps,
        headers={
            "Authorization": f"Bearer {cle}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=40) as reponse:
            data = json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"Firecrawl n'a pas pu lire la page (code {e.code})."
    except Exception:
        return "Firecrawl est injoignable."
    markdown = ((data.get("data") or {}).get("markdown") or "").strip()
    if not markdown:
        return "La page n'a pas de texte lisible."
    return markdown[:2000]


@outil(
    nom="lire_page",
    description="Lit le texte d'une page web déjà connue (article, documentation) "
                "pour le résumer. Il faut une adresse https.",
    parametres={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Adresse https de la page."},
        },
        "required": ["url"],
    },
    lent=True,
    phrase_attente="Je lis la page.",
)
def lire_page(url: str) -> str:
    return lire(url)
