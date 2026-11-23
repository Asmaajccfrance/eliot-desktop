"""Routage des commandes : distingue ouvrir une application, activer une fenêtre, lister les fenêtres, etc."""
import re
from dataclasses import dataclass

from ..text import norm


@dataclass
class Intent:
    kind: str
    target: str = ""
    text: str = ""
    extra: str = ""


WAKE = re.compile(r"^\s*(?:(?:hey|he|hei|ok|dis|salut|bonjour)\s+)?(?:eliott?|elliott?|elio)\b[\s,!:.\-]*")
POLITE = re.compile(
    r"(?:\b(?:est-ce que tu peux|est ce que tu peux|est-ce que tu pourrais|peux-tu|peux tu|pourrais-tu|"
    r"pourrais tu|tu peux|tu pourrais|j'aimerais que tu|je veux que tu|je voudrais que tu|merci de|"
    r"s'il te plait|s'il vous plait|stp|svp)\b|\bmerci$)[\s,]*"
)
OPEN = r"(?:ouvre|ouvrir|ouvres|lance|lancer|lances|demarre|demarrer|execute|executer)"
ART = r"(?:(?:l'|le |la |les |un |une |mon |ma |mes )?(?:application |appli |app |logiciel |programme )?(?:de |d')?)"
NEXT_VERBS = (r"recherche|cherche|ouvre|lance|ecris|tape|saisis|va|lis|resume|verifie|organise|range|"
              r"clique|appuie|ferme|active|affiche|liste|attends|prepare")
SPLIT = re.compile(
    r"\s*,?\s*(?:\bpuis\b|\bet ensuite\b|\bensuite\b|\bet apres\b|\bet enfin\b|\bet\b(?=\s+(?:" + NEXT_VERBS + r")\b))\s*"
)
TASK_START = re.compile(r"^(?:verifie|prepare|effectue|consulte|fais|realise|accomplis|occupe-toi|analyse|corrige|"
                        r"redige|trouve|compare|organise)\b")
SCHEDULE = re.compile(r"^(?:rappelle-moi|rappelle moi|fais-moi penser|fais moi penser|previens-moi|previens moi|programme|"
                      r"planifie|automatise)\b|^(?:chaque|tous les|toutes les)\b")
MAILS = r"(?:e-?mails?|mails?|courriels?|messages?(?: electroniques)?)"

ORDINALS = {"premier": 1, "1er": 1, "1": 1, "deuxieme": 2, "second": 2, "2e": 2, "2": 2, "troisieme": 3,
            "3e": 3, "3": 3, "quatrieme": 4, "4e": 4, "4": 4, "cinquieme": 5, "5e": 5, "5": 5}

RULES = [
    ("list_schedules", r"(?:liste|montre|affiche|quels sont|lis)(?:-moi)? (?:mes |les )?(?:rappels|taches programmees|"
                       r"programmations|automatisations)|^mes rappels$"),
    ("delete_schedule", r"^(?:supprime|annule|efface|retire) (?:le |la |l')?(?:rappel|tache programmee|automatisation|"
                        r"programmation) (?:n(?:o|°|umero) ?)?(?P<x>\d+)"),
    ("list_memory", r"(?:que sais-tu|qu'est-ce que tu sais|que retiens-tu|montre ta memoire|ta memoire|tes souvenirs|"
                    r"ce que tu as retenu)"),
    ("forget", r"^(?:oublie|efface de ta memoire|supprime de ta memoire)(?: que| le fait que| ce que)? (?P<x>.+)$"),
    ("remember", r"^(?:retiens|souviens-toi|souviens toi|rappelle-toi|rappelle toi|n'oublie pas|memorise|note)(?: bien)?"
                 r"(?: que| de| d'|:)? (?P<x>.+)$"),
    ("read_email", r"^(?:lis|lire|ouvre|montre|affiche)(?:-moi)? (?:l'|le |la )?" + MAILS + r" (?:n(?:o|°|umero) ?)?(?P<x>\d+)"),
    ("check_emails", r"^(?:consulte|lis|lire|verifie|montre|affiche|resume|regarde|liste|releve|ouvre)(?:-moi| moi)? "
                     r"(?:mes |les |mes derniers |mes nouveaux |les nouveaux |les derniers )?(?:nouveaux |derniers )?"
                     + MAILS + r"(?: non lus)?(?: (?:sur|dans|de) (?P<x>outlook|gmail))?\b"
                     r"|^(?:ai-je|j'ai|est-ce que j'ai) (?:des |de )?(?:nouveaux )?" + MAILS),
    ("prepare_replies", r"^(?:prepare|redige|ecris|propose)(?:-moi| moi)? (?:les |des |une |la )?reponses?"
                        r"(?: (?:aux|a ces|a mes|a mes nouveaux|pour les) " + MAILS + r")?(?P<x>.*)$"),
    ("send_reply", r"^(?:envoie|envoyer|expedie)(?:-la| la)? (?:la )?reponse (?:n(?:o|°|umero) ?|au mail |a l'e-?mail |"
                   r"au message )?(?P<x>\d+)"),
    ("save_drafts", r"(?:enregistre|sauvegarde|mets?|garde)(?:-les| les)? (?:reponses |les reponses )?(?:en |dans les |"
                    r"comme )?brouillons?"),
    ("analyze_project", r"^(?:analyse|verifie|controle|teste|lance les tests|cherche les erreurs)(?: les erreurs| les tests)?"
                        r"(?: de| du| dans)? (?:mon |le |ce )?(?:projet|code|application) (?P<x>.+)$"),
    ("open_in_app", r"^" + OPEN + r" (?:mon |le |ce |le dossier |mon dossier )?(?:projet |dossier )?(?P<x>.+?) "
                    r"(?:dans|avec|sous) (?P<w>cursor|vs ?code|visual studio code|l'explorateur|explorateur)$"),
    ("stop", r"^(?:stop|arrete(?:-toi| tout|-tout)?|tais-toi|silence|annule tout|stoppe)$"),
    ("list_windows", r"(?:liste|lister|montre|affiche|quelles sont|donne)(?:-moi)?\b.*\bfenetres?\b|^fenetres ouvertes$"
                     r"|^quelles fenetres"),
    ("list_apps", r"(?:applications|logiciels|applis)\b.*\b(?:autorisee?s?|disponibles?|permise?s?)\b"
                  r"|^quel(?:le)?s? (?:sont les )?(?:logiciels|applications)"),
    ("time", r"^(?:quelle heure|il est quelle heure|l'heure|donne-moi l'heure)"),
    ("date", r"^(?:quel jour|quelle date|on est quel jour|la date|on est le combien)"),
    ("help", r"^(?:aide|help|que sais-tu faire|qu'est-ce que tu sais faire|que peux-tu faire|tes capacites)"),
    ("read_page", r"^(?:lis|lire|resume|resumer|que dit)(?:-moi| moi)? (?:la |cette |le contenu de la )?page"),
    ("undo", r"^(?:annule|defais|annuler) (?:le |la |l')?(?:dernier |derniere )?(?:rangement|organisation|tri)"),
    ("open_result", r"^(?:" + OPEN[3:-1] + r"|va sur|clique sur|lis) (?:le |la )?(?P<x>premier|1er|deuxieme|second|2e|"
                    r"troisieme|3e|quatrieme|4e|cinquieme|5e|[1-5])(?: |e )?(?:resultat|lien)"),
    ("organize_folder", r"^(?:organise|range|trie|classe|ranger|organiser)r? (?:les fichiers |le contenu )?(?:du |le |de |des |"
                        r"de mon |mon |ma )?(?:dossier |repertoire )?(?P<x>.+)$"),
    ("list_folder", r"^(?:liste|montre|affiche|lister)(?:-moi)? (?:les )?(?:fichiers|contenu|documents) (?:du |de |des |"
                    r"dans |de mon |dans le |dans mon )?(?:dossier |repertoire )?(?P<x>.+)$"),
    ("open_folder", r"^" + OPEN + r" (?:le |mon |ma |l')?(?:dossier|repertoire) (?:des |de |du )?(?P<x>.+)$"),
    ("activate_window", r"^(?:active|reactive|bascule (?:sur|vers)|passe (?:sur|a)|mets? au premier plan|"
                        r"affiche la fenetre|montre la fenetre|va (?:sur|dans) la fenetre|reviens sur|"
                        r"retourne sur)\s+(?:la fenetre\s+)?(?:de |d'|du )?(?P<x>.+)$"),
    ("close_app", r"^(?:ferme|fermer|quitte|quitter)\s+" + ART + r"(?P<x>.+)$"),
    ("web_search", r"^(?:fais une |fait une |lance une )?(?:recherche|recherches|cherche|chercher|google|rechercher)"
                   r"(?:-moi| moi)?\s+(?:sur (?:internet|le web|google|duckduckgo)\s+)?(?:pour |sur |des informations "
                   r"sur |de l'information sur |des infos sur |une info sur )?(?P<x>.+)$"),
    ("open_url", r"^(?:va|aller|navigue|rends-toi|vas) (?:sur|a|vers) (?:le site |la page |mon site )?"
                 r"(?P<x>(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/\S*)?)$"),
    ("open_url", r"^" + OPEN + r" (?:le site |la page |l'adresse |mon site )?(?P<x>(?:https?://)?[\w-]+(?:\.[\w-]+)*"
                 r"\.(?:com|fr|org|net|io|dev|be|ch|eu|info|app|ai)(?:/\S*)?)$"),
    ("type_text", r"^(?:ecris|ecrire|tape|taper|saisis|saisir|redige)\s+(?P<x>.+)$"),
    ("press_keys", r"^(?:appuie sur|appuyer sur|presse|fais le raccourci|raccourci|touche)\s+(?P<x>.+)$"),
    ("click", r"^(?:clique|cliquer|clic|clique-moi)\s+(?:sur\s+)?(?P<x>.+)$"),
    ("open_app", r"^" + OPEN + r"\s+" + ART + r"(?P<x>.+)$"),
]
COMPILED = [(kind, re.compile(rx)) for kind, rx in RULES]


def clean(raw: str):
    orig = (raw or "").strip()
    low = norm(orig)
    m = WAKE.match(low)
    if m:
        orig, low = orig[m.end():], low[m.end():]
    while True:
        m = POLITE.search(low)
        if not m:
            break
        orig = orig[:m.start()] + orig[m.end():]
        low = low[:m.start()] + low[m.end():]
    strip = " ,.!?;:"
    lead = len(low) - len(low.lstrip(strip))
    orig, low = orig[lead:], low[lead:]
    tail = len(low.rstrip(strip))
    return orig[:tail], low[:tail]


def split_segments(raw: str) -> list:
    orig, low = clean(raw)
    parts, last = [], 0
    for m in SPLIT.finditer(low):
        parts.append(orig[last:m.start()])
        last = m.end()
    parts.append(orig[last:])
    return [p.strip(" ,.") for p in parts if p.strip(" ,.")]


def _strip_quotes(text: str) -> str:
    return text.strip().strip("\"'«»“” ").strip()


def parse(raw: str) -> Intent:
    orig, low = clean(raw)
    if not low:
        return Intent("chat", text=raw.strip())
    if SCHEDULE.match(low):
        return Intent("schedule", text=orig)
    if len(split_segments(raw)) > 1:
        return Intent("task", text=orig)
    intent = match_rules(orig, low)
    if intent is None and TASK_START.match(low):
        return Intent("task", text=orig)
    return intent or Intent("chat", text=orig)


def match_rules(orig: str, low: str):
    for kind, rx in COMPILED:
        m = rx.search(low)
        if not m:
            continue
        target = _strip_quotes(orig[m.start("x"):m.end("x")]) if "x" in rx.groupindex else ""
        if kind == "type_text":
            return _type_intent(target)
        if kind == "open_result":
            return Intent(kind, target=str(ORDINALS.get(norm(target), 1)))
        if kind == "click":
            return _click_intent(target)
        if kind == "open_in_app":
            return Intent(kind, target=_strip_quotes(orig[m.start("w"):m.end("w")]), text=target)
        return Intent(kind, target=target, text=orig)
    return None


def _split_in(target: str):
    low = norm(target)
    m = list(re.finditer(r"\s+dans (?:le |la |l'|les |mon |ma )?(?:fenetre |application |logiciel )?(?:de |du )?", low))
    if not m:
        return target, ""
    last = m[-1]
    return target[:last.start()], target[last.end():]


def _type_intent(target: str) -> Intent:
    text, window = _split_in(target)
    return Intent("type_text", target=_strip_quotes(window), text=_strip_quotes(text))


def _click_intent(target: str) -> Intent:
    name, window = _split_in(target)
    name = re.sub(r"^(?:le |la |l'|les )?(?:bouton |menu |onglet |lien )?", "", name, flags=re.I)
    return Intent("click", target=_strip_quotes(window), text=_strip_quotes(name))
