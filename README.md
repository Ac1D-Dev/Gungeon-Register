# GR - Gungeon Register

Suivi de progression en direct pour **Enter the Gungeon** : objets et armes découverts, historique des runs, statistiques en direct (vie, armure, argent, clés, blancs, inventaire, qualité moyenne du loadout), avec une application de bureau compagnon (**Le Registre du Gungeon**) qui affiche tout ça dans une jolie interface, plus une fenêtre de suivi superposable pendant une run.

## Fonctionnalités

- Historique complet des runs (personnage, seed, étages atteints, résultat, objets/armes ramassés colorés par tier de qualité D/C/B/A/S, combats de boss).
- Fenêtre de suivi en direct affichable pendant une run : vie/armure, argent, clés, blancs, nombre d'armes/objets tenus, qualité moyenne du loadout.
- Notifications à l'écran lors d'une nouvelle découverte (arme, objet, boss).
- Application de bureau compagnon (`RegistreDuGungeon.exe`) qui affiche tout ça dans une jolie interface : aucune installation, aucun Python requis pour l'utiliser.
- Fonctionne même sans l'application de bureau : les données sont écrites dans de simples fichiers JSON, consultables ou réutilisables ailleurs.

## Installation

**Via un gestionnaire de mods (r2modman / Thunderstore Mod Manager) :** installez normalement, `BepInExPack_EtG` et `QualityColors` seront installés automatiquement comme dépendances.

**Installation manuelle :** extrayez le contenu de cette archive dans `BepInEx\plugins\` (créez un sous-dossier `Gungeon_Register`, ou utilisez celui déjà présent dans l'archive).

Le mod fonctionne seul dès l'installation : les données sont écrites dans de simples fichiers JSON, consultables sans rien d'autre. L'application de bureau compagnon **Le Registre du Gungeon** (`RegistreDuGungeon.exe`) est incluse dans ce package et se lance automatiquement avec le jeu — EXE disponible juste ICI : [https://github.com/Ac1D-Dev/Gungeon-Register](https://github.com/Ac1D-Dev/Gungeon-Register/releases/tag/2.7.2). Pour désactiver le lancement automatique, mettez `AutoLaunchApp` à `false` dans le fichier de config généré après le premier lancement (voir Configuration ci-dessous).

## Configuration

Un fichier de config BepInEx est généré au premier lancement (`BepInEx\config\user.registredugungeon.livetracker.cfg`) :

- `DataDirectory` — dossier où écrire `live_progress.json` et `run_history.json` (par défaut `%APPDATA%\RegistreDuGungeon`).
- `NotificationsEnabled` — afficher ou non les popups de découverte à l'écran.
- `AutoLaunchApp` — lancer automatiquement `RegistreDuGungeon.exe` au démarrage du jeu (activé par défaut).

## Notes

- Les couleurs de qualité D/C/B/A/S utilisées pour les chips d'objets sont alignées sur celles du mod QualityColors.
- Le mod ne modifie aucun fichier de sauvegarde du jeu ; il lit uniquement les informations déjà exposées par celui-ci.

Voir `CHANGELOG.md` pour l'historique des versions.
