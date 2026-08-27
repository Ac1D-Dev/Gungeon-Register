# Le Registre du Gungeon

Application de bureau compagnon du mod BepInEx **GR - Gungeon Register** pour *Enter the Gungeon* ([page Thunderstore](https://thunderstore.io/c/enter-the-gungeon/p/Ac1D/Gungeon_Register/)).

Elle affiche dans une interface simple les données écrites par le mod pendant que vous jouez : historique des runs (personnage, seed, étages atteints, résultat, objets/armes ramassés colorés par tier de qualité D/C/B/A/S, combats de boss), statistiques en direct, notifications de découverte, plus une petite fenêtre de suivi superposable pendant une run.

## Fonctionnement

Le mod (côté jeu) écrit en continu des fichiers JSON simples (`live_progress.json`, `run_history.json`) dans un dossier de données (par défaut `%APPDATA%\RegistreDuGungeon`). Cette application se contente de **lire** ces fichiers et de les afficher — elle ne modifie jamais de fichier de sauvegarde du jeu, et le mod fonctionne très bien tout seul sans elle (les fichiers JSON restent consultables/réutilisables ailleurs).

Il n'y a **aucun lancement automatique** : vous ouvrez cette application quand vous voulez consulter votre progression, avant, après, ou pendant une run.

## Technologies

- Python 3 + [pywebview](https://pywebview.flowrl.com/) pour la fenêtre native.
- Interface en HTML/CSS/JS pur (`gungeon_registre.html`), pas de framework front-end.
- Empaquetée en `.exe` autonome (aucune installation de Python requise côté joueur) via [PyInstaller](https://pyinstaller.org/), voir `build.bat`.

## Fichiers

- `gungeon_app.py` — backend Python (lecture des fichiers JSON du mod, lecture optionnelle de la sauvegarde du jeu et des stats Steam, réglages).
- `gungeon_registre.html` — toute l'interface (structure, style, logique JS), fichier unique.
- `guid_map_data.json` — table de correspondance entre les identifiants internes du jeu et les noms/objets affichés.
- `build.bat` — script Windows qui compile `gungeon_app.py` en `RegistreDuGungeon.exe` avec PyInstaller.
- `gungeon_icon.ico` — icône de l'application.

## Compiler soi-même

Sous Windows, avec Python 3 installé :

```
pip install pywebview pyinstaller
build.bat
```

L'exécutable `RegistreDuGungeon.exe` est généré dans `dist\`.

## Licence / usage

Projet personnel, fourni tel quel, sans garantie. Le code est visible ici pour transparence (notamment vis-à-vis de la modération Thunderstore du mod associé) — aucun exécutable de ce dépôt n'est téléchargé ou lancé automatiquement par le mod.
