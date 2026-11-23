"""Recherche web sourcée via Perplexity. Inactif sans perplexity.cle."""
import json
import urllib.error
import urllib.request

from core.config import reglage
from core.registre import outil


def _cle():
    return str(reglage("perplexity.cle", "") or "").strip()


def interroger(question):
    cle = _cle()
    if not cle:
        return "Perplexity n'est pas configuré. Ajoute perplexity.cle dans config.yaml."
    corps = json.dumps({
        "model": reglage("perplexity.modele", "sonar"),
        "messages": [{"role": "user", "content": question[:2000]}],
    }).encode("utf-8")
    requete = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=corps,
        headers={
            "Authorization": f"Bearer {cle}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            data = json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"Perplexity a refusé la recherche (code {e.code})."
    except Exception:
        return "Perplexity est injoignable."
    choix = (data.get("choices") or [{}])[0]
    texte = ((choix.get("message") or {}).get("content") or "").strip()
    sources = [s for s in (data.get("citations") or []) if isinstance(s, str)][:3]
    if sources:
        texte += "\nSources : " + " ; ".join(sources)
    return (texte or "Perplexity n'a rien répondu.")[:1800]


@outil(
    nom="chercher_perplexity",
    description="Cherche une information récente sur le web avec des sources "
                "(météo, actualité, fait). À préférer à une réponse inventée.",
    parametres={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "La question à chercher."},
        },
        "required": ["question"],
    },
    lent=True,
    phrase_attente="Je cherche.",
)
def chercher_perplexity(question: str) -> str:
    return interroger(str(question or "").strip() or "Dis-moi quoi chercher.")
