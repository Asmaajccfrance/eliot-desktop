"""Actions de comptes connectés (LinkedIn, etc.) via Composio.

Inactif sans composio.cle. Publier ou envoyer demande une confirmation vocale.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from core.config import reglage
from core.registre import outil

_BASE = "https://backend.composio.dev/api/v3.1"


def _cle():
    return str(reglage("composio.cle", "") or "").strip()


def _user():
    return str(reglage("composio.user_id", "jarvis") or "jarvis")


def _appeler(methode, chemin, corps=None):
    cle = _cle()
    if not cle:
        return None, "Composio n'est pas configuré. Ajoute composio.cle dans config.yaml."
    data = None if corps is None else json.dumps(corps).encode("utf-8")
    requete = urllib.request.Request(
        _BASE + chemin,
        data=data,
        headers={"x-api-key": cle, "Content-Type": "application/json"},
        method=methode,
    )
    try:
        with urllib.request.urlopen(requete, timeout=40) as reponse:
            return json.loads(reponse.read().decode("utf-8")), ""
    except urllib.error.HTTPError as e:
        return None, f"Composio a refusé l'action (code {e.code})."
    except Exception:
        return None, "Composio est injoignable."


def lister(application):
    recherche = urllib.parse.quote(str(application or "linkedin")[:40])
    data, erreur = _appeler("GET", f"/tools?search={recherche}&limit=8")
    if erreur:
        return erreur
    items = data.get("items") if isinstance(data, dict) else None
    if items is None and isinstance(data, list):
        items = data
    lignes = []
    for item in (items or [])[:8]:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug") or item.get("name") or "?"
        desc = str(item.get("description") or "")[:120]
        lignes.append(f"{slug} — {desc}" if desc else str(slug))
    if not lignes:
        return "Composio n'a listé aucune action. Connecte d'abord le compte sur composio.dev."
    return "Actions : " + " | ".join(lignes)


def executer_action(action, arguments):
    slug = str(action or "").strip()
    if not slug:
        return "Dis-moi quelle action Composio lancer, par exemple LINKEDIN_CREATE_LINKED_IN_POST."
    args = arguments if isinstance(arguments, dict) else {}
    data, erreur = _appeler(
        "POST",
        "/tools/execute/" + urllib.parse.quote(slug),
        {"user_id": _user(), "arguments": args},
    )
    if erreur:
        return erreur
    if not isinstance(data, dict):
        return "Composio n'a pas renvoyé de résultat."
    if data.get("successful") is False:
        return "Composio : " + str(data.get("error") or "l'action a échoué.")[:300]
    apercu = json.dumps(data.get("data"), ensure_ascii=False)[:500]
    return "Action terminée. " + apercu


@outil(
    nom="lister_composio",
    description="Liste les actions Composio disponibles pour un service "
                "(linkedin, gmail, slack). À appeler avant de publier.",
    parametres={
        "type": "object",
        "properties": {
            "application": {"type": "string", "description": "Nom du service, ex. linkedin."},
        },
        "required": ["application"],
    },
)
def lister_composio(application: str) -> str:
    return lister(application)


def _annonce(args):
    return f"Je lance l'action Composio {args.get('action', '')}."


@outil(
    nom="executer_composio",
    description="Exécute une action Composio seulement si l'utilisateur demande "
                "explicitement Composio. Pour un article LinkedIn, utiliser "
                "rediger_linkedin : ne jamais publier par ici.",
    parametres={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Slug de l'action, ex. LINKEDIN_CREATE_LINKED_IN_POST."},
            "arguments": {"type": "object", "description": "Champs demandés par l'action."},
        },
        "required": ["action"],
    },
    confirmation=True,
    annonce=_annonce,
    lent=True,
    phrase_attente="J'envoie ça.",
)
def executer_composio(action: str, arguments: dict = None) -> str:
    return executer_action(action, arguments or {})
