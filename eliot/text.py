import re

_ACCENTS = str.maketrans(
    "àâäáãåçéèêëíìîïñóòôöõúùûüýÿœæÀÂÄÁÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝŸŒÆ’`",
    "aaaaaaceeeeiiiinooooouuuuyyoaAAAAAACEEEEIIIINOOOOOUUUUYYOA''",
)


def norm(text: str) -> str:
    """Minuscules sans accents, même longueur que l'original (index alignés)."""
    return text.translate(_ACCENTS).lower()


def simplify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", norm(text or "")).strip()
