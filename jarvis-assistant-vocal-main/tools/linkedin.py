"""Brouillon LinkedIn dans le navigateur, sans le publier.

Ouvre le composeur deja rempli. Le clic sur Publier reste a l'utilisateur.
Aucun compte Composio n'est necessaire : c'est la page LinkedIn elle-meme.
"""
from urllib.parse import quote

from core.registre import outil

_LIMITE = 2900


def url_brouillon(texte: str) -> str:
    """Adresse du composeur LinkedIn avec le texte deja place."""
    propre = " ".join(str(texte or "").split())
    if len(propre) > _LIMITE:
        propre = propre[:_LIMITE].rstrip() + "…"
    return "https://www.linkedin.com/feed/?shareActive=true&text=" + quote(propre, safe="")


@outil(
    nom="rediger_linkedin",
    description="Ouvre LinkedIn avec un article deja ecrit dans le composeur. "
                "N'envoie JAMAIS le post : l'utilisateur clique lui-meme sur Publier. "
                "A utiliser des qu'il demande d'ecrire ou de preparer une publication "
                "LinkedIn. Redige le texte a partir de son sujet s'il n'a pas dicte "
                "l'article mot a mot. N'utilise pas Composio pour ca.",
    parametres={
        "type": "object",
        "properties": {
            "texte": {"type": "string",
                      "description": "Texte complet du post, pret a etre lu sur LinkedIn."},
        },
        "required": ["texte"],
    },
    lent=True,
    phrase_attente="J'ouvre LinkedIn.",
)
def rediger_linkedin(texte: str) -> str:
    """Affiche le brouillon. Ne clique pas sur Publier."""
    if not " ".join(str(texte or "").split()):
        return "Il me faut le texte de l'article."
    from core.ouvrir_web import nom_navigateur, ouvrir_url
    if not ouvrir_url(url_brouillon(texte)):
        return "Je n'ai pas pu ouvrir LinkedIn."
    return (f"LinkedIn est ouvert dans {nom_navigateur()}, avec le texte deja ecrit. "
            "Connecte-toi si la page le demande, puis clique toi-meme sur Publier.")
