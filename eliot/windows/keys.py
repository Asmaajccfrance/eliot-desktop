"""Conversion des raccourcis en français vers la syntaxe send_keys de pywinauto."""
from ..text import simplify

MODIFIERS = {"ctrl": "^", "control": "^", "controle": "^", "alt": "%", "maj": "+", "shift": "+", "majuscule": "+"}
KEYS = {
    "entree": "{ENTER}", "enter": "{ENTER}", "valider": "{ENTER}", "echap": "{ESC}", "echappe": "{ESC}",
    "escape": "{ESC}", "tab": "{TAB}", "tabulation": "{TAB}", "suppr": "{DELETE}", "supprimer": "{DELETE}",
    "retour": "{BACKSPACE}", "effacer": "{BACKSPACE}", "espace": "{SPACE}", "haut": "{UP}", "bas": "{DOWN}",
    "gauche": "{LEFT}", "droite": "{RIGHT}", "debut": "{HOME}", "fin": "{END}", "pageup": "{PGUP}",
    "pagedown": "{PGDN}", "windows": "{VK_LWIN}", "win": "{VK_LWIN}",
}
for _i in range(1, 13):
    KEYS[f"f{_i}"] = "{F%d}" % _i
SPECIAL = set("{}+^%~()[]")


def escape_text(text: str) -> str:
    return "".join("{%s}" % c if c in SPECIAL else ("{ENTER}" if c == "\n" else c) for c in text)


def to_send_keys(combo: str) -> str:
    words = simplify(combo.replace("+", " ")).split()
    words = [w for w in words if w not in {"la", "le", "touche", "touches", "et", "plus", "puis"}]
    if not words:
        raise ValueError("Raccourci vide.")
    mods, keys = "", []
    for word in words:
        if word in MODIFIERS:
            mods += MODIFIERS[word]
        elif word in KEYS:
            keys.append(KEYS[word])
        elif len(word) == 1:
            keys.append(word)
        else:
            raise ValueError(f"Touche inconnue : « {word} ».")
    if not keys:
        raise ValueError("Il manque la touche principale du raccourci.")
    return mods + ("(%s)" % "".join(keys) if mods and len(keys) > 1 else "".join(keys))
