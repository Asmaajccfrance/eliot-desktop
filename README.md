# ELIOT V1.0 — Assistant IA vocal pour Windows

ELIOT est un assistant personnel (Python + PySide6) qui comprend des demandes vocales ou écrites et agit sur
Windows : applications autorisées, clavier/souris, navigateur, dossiers, tâches supervisées en plusieurs étapes.

## 1. Construire `ELIOT.exe` (à faire une fois, sur un PC Windows 10/11)

1. Installer **Python 3.11 ou 3.12** depuis https://www.python.org/downloads/ (cocher *Add python.exe to PATH*).
2. Copier ce dossier `eliot_desktop` sur le PC (par exemple `C:\ELIOT`).
3. Double-cliquer sur **`build_exe.bat`**. Le script :
   crée l'environnement, installe les dépendances, installe Chromium, génère l'icône, lance les tests puis
   construit l'exécutable.
4. Résultat : **`dist\ELIOT\ELIOT.exe`** (garder tout le dossier `dist\ELIOT`, l'exe a besoin de ses fichiers).

Pour lancer sans construire l'exe : `run_eliot.bat` (après un premier `build_exe.bat`).

### Installer sur les 2 ou 3 autres PC
- **Simple** : copier le dossier `dist\ELIOT` sur l'autre PC et lancer `ELIOT.exe`.
- **Installateur** : installer Inno Setup 6 (https://jrsoftware.org/isinfo.php), ouvrir `installer\eliot.iss`,
  cliquer sur *Compile* → `dist\ELIOT-Setup-1.0.0.exe` (raccourci Bureau, démarrage avec Windows en option).
- Au premier usage du navigateur, ELIOT télécharge Chromium automatiquement s'il manque (connexion requise).

Chaque PC garde ses propres paramètres, conversations et autorisations dans `%APPDATA%\ELIOT`.

## 2. Moteur IA et voix
| Réglage | Options |
| --- | --- |
| Moteur (Paramètres > Intelligence artificielle) | Clé Emergent intégrée (par défaut) · Ma clé Anthropic (stockée dans le Gestionnaire d'identification Windows) · Démonstration |
| Modèle | Claude Sonnet 4.5 (défaut), Sonnet 4.6, Haiku 4.5, Opus 4.5 |
| Voix | Voix réaliste OpenAI (secours automatique Microsoft Hortense) · Hortense seule · Aucune |
| Micro | Transcription française OpenAI Whisper (clé OpenAI optionnelle, sinon clé Emergent) |

⚠️ La clé Emergent est intégrée dans l'exécutable : toute personne qui possède le `.exe` peut l'extraire et
consommer le crédit. Ne diffuse l'exe qu'à des personnes de confiance.

## 3. Exemples de commandes
- « Eliot, ouvre Firefox » → ouvre Firefox, ou l'active s'il est déjà ouvert (bug V0.5 corrigé).
- « Active la fenêtre Cursor » · « Liste les fenêtres ouvertes » · « Ferme la calculatrice »
- « Ouvre le Bloc-notes puis écris Bonjour » · « Appuie sur ctrl s » · « Clique sur Enregistrer dans Word »
- « Ouvre Firefox et recherche la météo à Lyon » (recherche dans Firefox)
- « Recherche les horaires de la poste » → « Ouvre le premier résultat » → « Résume la page »
- « Range le dossier Téléchargements » → « Annule le rangement »
- « Vérifie si wikipedia.org fonctionne » (tâche planifiée par Claude, réévaluée après chaque étape)
- Pendant une confirmation : dire « oui » / « non ». « Stop » ou Échap arrête tout.

## 4. Sécurité
- Seules les applications **actives** dans *Applications autorisées* peuvent être ouvertes ; écrire/cliquer
  nécessite en plus la case **Contrôle clavier/souris**.
- Seuls les **dossiers autorisés** sont accessibles ; le dernier rangement est annulable.
- Navigation limitée aux **domaines autorisés** (les résultats de recherche peuvent être ouverts, réglable).
- Toute modification (écrire, cliquer, raccourci, fermer, ranger) demande **confirmation**.
- Budgets par tâche : nombre d'étapes et durée maximale ; boutons Pause / Reprendre / STOP.

## 5. Tests
Diagnostic rapide de l'exe : `ELIOT.exe --selftest` écrit le résultat dans `%APPDATA%\ELIOT\autotest.txt`.

`python -m pytest -q` (114 tests hors ligne). Tests réels IA/voix : `set ELIOT_LIVE=1` puis
`python -m pytest tests\test_live.py`.

## 6. Structure
```
eliot/
  app.py, services.py, assistant.py      démarrage, assemblage, compréhension des demandes
  commands/router.py                     routage : ouvrir / activer / lister / écrire / rechercher…
  apps/registry.py, launcher.py          gestionnaire d'applications autorisées, lancement
  windows/control.py, keys.py            UI Automation (pywinauto), clavier, souris
  web/browser.py                         Playwright + Chromium (profil séparé)
  files/manager.py                       dossiers autorisés, rangement, annulation
  agent_workflows/                       outils, planification Claude, exécution supervisée
  llm/engine.py                          Claude (clé Emergent ou Anthropic)
  voice/                                 micro + Whisper, voix OpenAI, Hortense
  ui/                                    interface PySide6
```

## 7. Nouveautés V0.7 → V1.0
- **« Hey Eliot »** (Paramètres > Voix) : écoute permanente hors ligne avec Vosk (modèle français de 45 Mo,
  téléchargé automatiquement au premier lancement). Quand Vosk croit entendre « Eliot », un extrait de 3 à 8 s est
  confirmé par Whisper (option désactivable, mais Vosk seul reconnaît mal le prénom). Exemple : « Hey Eliot, ouvre
  Firefox » exécute directement la commande, « Hey Eliot » seul ouvre le micro.
- **Conversation naturelle** : après une réponse vocale, ELIOT réécoute automatiquement (« oui » / « non » pour les
  confirmations, nouvelle question…). Il se tait si tu ne dis rien.
- **Barre des tâches** : ELIOT reste actif près de l'horloge quand on ferme la fenêtre (Hey Eliot et rappels) ;
  clic droit > Quitter. Une seule instance à la fois.
- **Messagerie** (Paramètres > Messagerie) : Outlook classique installé (aucune clé) et/ou Gmail (mot de passe
  d'application). « Consulte mes nouveaux e-mails et prépare les réponses » → « envoie la réponse 2 » (envoi réel
  après confirmation) ou « enregistre les brouillons ». Les e-mails ne sont pas marqués comme lus.
- **Mémoire** : « retiens que… », « que sais-tu sur moi ? », « oublie que… » (+ écran Mémoire). Claude s'en sert
  dans chaque conversation.
- **Rappels et tâches programmées** : « rappelle-moi d'appeler Paul demain à 15h », « rappelle-moi dans 10 minutes
  de… », « chaque matin à 9h, consulte mes e-mails et prépare les réponses », « tous les lundis à 8h, range le
  dossier Téléchargements », « liste mes rappels », « supprime le rappel 2 ».
- **Projets de code** : ajoute le dossier du projet dans *Dossiers autorisés*, puis « analyse le projet monsite »
  (lance pytest / npm test après confirmation et Claude explique les erreurs et propose les corrections), « ouvre
  mon projet monsite dans Cursor ». ELIOT propose les corrections mais ne modifie pas encore les fichiers lui-même.

## 8. Limites connues
- Les rappels ne s'exécutent que si ELIOT est ouvert ou dans la barre des tâches (cocher « Lancer au démarrage »).
- Outlook « nouveau » (application web) n'est pas pilotable : il faut Outlook classique.
- Les voix OpenAI gardent un léger accent anglais.
