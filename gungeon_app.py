#!/usr/bin/env python3
"""
Le Registre du Gungeon - Application de bureau
=================================================

Ouvre "Le Registre du Gungeon" (gungeon_registre.html) dans une vraie
fenetre d'application, avec un bouton "Actualiser depuis ma sauvegarde"
dans les onglets GunBook et Boss qui relit automatiquement votre fichier
de sauvegarde Enter the Gungeon et coche les armes/objets/boss vanilla
deja rencontres - sans avoir a exporter/importer un fichier JSON a la main.

INSTALLATION (une seule fois)
    pip install pywebview vdf

LANCEMENT
    python gungeon_app.py

Ce dossier doit contenir les 3 fichiers ensemble :
    gungeon_app.py          (ce script)
    gungeon_registre.html   (le site)
    guid_map_data.json      (table de correspondance GUID -> catalogue)

Pour obtenir un .exe unique (pas besoin de Python pour l'utiliser
ensuite), voir build.bat fourni a cote de ce script.

Le fichier de sauvegarde est cherche automatiquement dans :
    %userprofile%\\AppData\\LocalLow\\Dodge Roll\\Enter the Gungeon\\Slot{A,B,C}.save
Si aucun n'est trouve automatiquement, un selecteur de fichier s'ouvre.

Les trophees Steam sont lus automatiquement depuis le cache local du client
Steam (dossier appcache/stats de l'installation Steam) - aucune configuration
necessaire, ca marche des que Steam a synchronise les stats du jeu au moins
une fois. Le module 'vdf' (installe ci-dessus) sert a decoder ce cache.
"""

import os
import sys
import json
import glob
import threading
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))


def resource_path(filename):
    """Retrouve un fichier de donnees, que le script tourne normalement
    (python gungeon_app.py) ou une fois transforme en .exe autonome par
    PyInstaller (mode --onefile : les fichiers ajoutes avec --add-data
    sont extraits dans un dossier temporaire pointe par sys._MEIPASS)."""
    base = getattr(sys, '_MEIPASS', HERE)
    return os.path.join(base, filename)


HTML_PATH = resource_path('gungeon_registre.html')
GUID_MAP_PATH = resource_path('guid_map_data.json')


def _overlay_html_url():
    """URL file:// explicite (construite a la main plutot que de laisser
    pywebview deviner) vers gungeon_registre.html, avec #overlay=1 en
    fragment : c'est ce que le script cote JS lit tout en haut (voir
    IS_OVERLAY) pour savoir qu'il doit afficher la petite vue "partie en
    cours" au lieu de l'appli complete. On construit nous-memes une URL
    commencant par "file://" (plutot que de passer HTML_PATH tel quel a
    create_window) car les versions recentes de pywebview traitent un simple
    chemin local comme un site a servir via un mini serveur HTTP interne
    (calcul d'un chemin relatif ensuite recolle a une URL de serveur) - un
    chemin auquel on a simplement ajoute un suffixe n'existe plus tel quel
    sur disque et ce mecanisme echouerait (fichier introuvable). Une URL qui
    commence deja par "file://" est en revanche utilisee telle quelle, sans
    passer par ce mecanisme.

    pathlib.Path.as_uri() plutot qu'un urllib.request.pathname2url() concatene
    a la main avec 'file://' : sous Windows, pathname2url() renvoie DEJA un
    chemin commencant par "///" (ex. ///C:/Users/...) - lui recoller 'file://'
    devant produisait donc "file://///C:/..." (5 barres obliques), une URL
    invalide. as_uri() gere cette subtilite correctement et produit toujours
    exactement "file:///C:/...".

    #fragment plutot que ?query : meme apres avoir corrige les barres
    obliques ci-dessus, WebView2 (backend Windows de pywebview, base sur
    System.Uri/CoreWebView2) continuait a renvoyer ERR_FILE_NOT_FOUND avec
    "?overlay=1" - la query string d'une URL file: n'est apparemment pas
    traitee de la meme facon que pour http(s) par ce moteur et finit par
    faire partie du chemin de fichier recherche (qui n'existe donc plus tel
    quel sur disque). Un FRAGMENT (#...) est en revanche par definition
    toujours purement cote client, jamais utilise par un navigateur ou une
    bibliotheque quelconque pour resoudre la ressource elle-meme (que ce
    soit http(s) ou file:) - c'est le seul suffixe garanti sans danger ici,
    et il reste lisible cote JS via location.hash."""
    return Path(os.path.abspath(HTML_PATH)).as_uri() + '#overlay=1'


# Reference vers la fenetre "partie en cours" (overlay), s'il y en a une
# ouverte actuellement - au niveau module plutot que sur Api, car un seul
# processus n'en a jamais besoin de plus d'une a la fois, et Api.__init__
# n'a autrement aucune raison d'etre traversee par de l'etat de fenetre.
# Le verrou evite une double creation si deux appels JS quasi simultanes
# (fenetre principale relancee juste apres un crash, sondages qui se
# chevauchent, etc.) arrivaient malgre tout jusqu'ici en meme temps.
_overlay_window = None
_overlay_window_lock = threading.Lock()

GUNS_TOTAL = 237
ITEMS_TOTAL = 258
BOSSES_TOTAL = 30
SECRETS_TOTAL = 13
NPCS_TOTAL = 19
QUESTS_TOTAL = 15
STEAM_APP_ID = '311690'

# Correspondance (categorie, index dans DATA.secrets/npcs/quests du site) ->
# condition(s) sur les drapeaux persistants du jeu (liste "m_flags" du fichier
# de sauvegarde, valeurs de l'enum GungeonFlags reel). Etablie en comparant :
# (1) le texte francais de chaque entree de secrets/npcs/quests dans
#     gungeon_registre.html,
# (2) les 179 drapeaux effectivement presents dans une vraie sauvegarde de
#     joueur (utilisateur de cette appli) pour confirmer les noms plausibles,
# (3) le dump complet de l'enum GungeonFlags via reflection sur le vrai
#     Assembly-CSharp.dll publicise, pour ne pas se limiter aux drapeaux deja
#     obtenus par ce joueur precis.
#
# mode 'any' : au moins un des drapeaux listes suffit. mode 'all' : il faut
# TOUS les drapeaux listes (utilise quand l'entree combine plusieurs jalons
# distincts, ex. "terminez le tutoriel ET vainquez tel boss").
#
# Le jeu ne persiste PAS de drapeau dedie pour chaque secret/PNJ/quete : les
# entrees absentes d'ici (Doug, Professeur Goopton, Old Red, Cursula, Flynt,
# la plupart des secrets bases sur une salle cachee comme le Marche Noir,
# ainsi que le deblocage des personnages Robot/Balle) reposent sur des seuils
# calcules en direct par le jeu (ex. "avoir porte 4 bombes simultanement")
# ou sur une decouverte de salle geometrique, sans etat persistant lisible
# depuis le fichier de sauvegarde - elles restent donc a cocher a la main.
SECRET_FLAG_MAP = {
    0: {'mode': 'any', 'flags': ['ACHIEVEMENT_ACCESS_OUBLIETTE']},          # L'Oubliette
    1: {'mode': 'any', 'flags': ['ACHIEVEMENT_ACCESS_ABBEY']},              # L'Abbaye du Vrai Fusil
    3: {'mode': 'any', 'flags': ['RESOURCEFUL_RAT_COMPLETE']},              # Le Repaire du Rat Ruse
    6: {'mode': 'any', 'flags': ['MUNCHER_EVIL_COMPLETE']},                 # Les Munchers Malefiques
    10: {'mode': 'any', 'flags': ['MONSTERMANUEL_EVER_TALKED']},            # Manuel le Monstre
    12: {'mode': 'any', 'flags': ['TONIC_ACTIVE_IN_FOYER', 'BOWLER_ACTIVE_IN_FOYER']},  # La Chaine de la Sorciere
}
NPC_FLAG_MAP = {
    0: {'mode': 'any', 'flags': ['META_SHOP_ACTIVE_IN_FOYER']},             # Ox et Cadence
    1: {'mode': 'any', 'flags': ['LEDGEGOBLIN_ACTIVE_IN_FOYER']},           # Le Gobelin du Rebord
    # Contrairement aux autres PNJ, l'Aventurier Perdu ne pose jamais le
    # drapeau ACTIVE_IN_FOYER (verifie sur une vraie sauvegarde ou il est
    # deja libere) - RESCUED_FROM_CELL est ici le signal fiable.
    4: {'mode': 'any', 'flags': ['LOST_ADVENTURER_RESCUED_FROM_CELL', 'LOST_ADVENTURER_EVER_HELPED']},  # L'Aventurier Perdu
    5: {'mode': 'any', 'flags': ['FRIFLE_ACTIVE_IN_FOYER']},                # Frifle et le Mousquet Gris
    6: {'mode': 'any', 'flags': ['GUNSLING_KING_ACTIVE_IN_FOYER']},         # Le Roi Tire et Manservantes
    10: {'mode': 'any', 'flags': ['SYNERGRACE_UNLOCKED']},                  # Synergrace
    11: {'mode': 'any', 'flags': ['VAMPIRE_RELEASED']},                     # Le Vampire
    12: {'mode': 'any', 'flags': ['SORCERESS_ACTIVE_IN_FOYER']},            # La Sorciere
    13: {'mode': 'any', 'flags': ['DAISUKE_ACTIVE_IN_FOYER']},              # Daisuke
    14: {'mode': 'any', 'flags': ['TONIC_ACTIVE_IN_FOYER']},                # Tonic
    15: {'mode': 'any', 'flags': ['BOWLER_ACTIVE_IN_FOYER']},               # Bowler
    16: {'mode': 'all', 'flags': ['TUTORIAL_COMPLETED', 'BOSSKILLED_BLOCKNER']},  # Ser Manuel et Blockner
    17: {'mode': 'any', 'flags': ['WINCHESTER_MET_PREVIOUSLY']},            # Winchester
    18: {'mode': 'any', 'flags': ['ACHIEVEMENT_NOBOSSDAMAGE_CASTLE']},      # Le Tailleur
}
QUEST_FLAG_MAP = {
    1: {'mode': 'any', 'flags': ['META_SHOP_RECEIVED_ROBOT_ARM_REWARD']},   # Le bras de rechange du Golem
    2: {'mode': 'any', 'flags': ['BOSSKILLED_BLOCKNER']},                   # Venger Manuel
    3: {'mode': 'any', 'flags': ['FRIFLE_CORE_HUNTS_COMPLETE']},            # Les contrats de chasse de Frifle
    4: {'mode': 'all', 'flags': ['SORCERESS_ACTIVE_IN_FOYER', 'TONIC_ACTIVE_IN_FOYER',
                                  'BOWLER_ACTIVE_IN_FOYER', 'DAISUKE_ACTIVE_IN_FOYER']},  # La Chaine de la Sorciere
    7: {'mode': 'any', 'flags': ['RESOURCEFUL_RAT_COMPLETE']},              # Le Repaire du Rat Ruse
    8: {'mode': 'any', 'flags': ['ACHIEVEMENT_ACCESS_OUBLIETTE']},          # L'Oubliette
    9: {'mode': 'any', 'flags': ['ACHIEVEMENT_ACCESS_ABBEY']},              # L'Abbaye du Vrai Fusil
    11: {'mode': 'any', 'flags': ['DAISUKE_CHALLENGE_COMPLETE']},           # L'epreuve de Daisuke
    12: {'mode': 'any', 'flags': ['TONIC_TURBO_MODE_COMPLETE']},            # L'epreuve de Tonic
    13: {'mode': 'any', 'flags': ['WINCHESTER_ACHIEVEMENT_REWARD_GIVEN']},  # Le jeu de Winchester
    14: {'mode': 'any', 'flags': ['GUNSLING_KING_ACHIEVEMENT_REWARD_GIVEN']},  # Le pari du Roi Tire
}


def flags_to_checklist(flag_map, total, flags_set):
    """Applique un FLAG_MAP (SECRET_FLAG_MAP/NPC_FLAG_MAP/QUEST_FLAG_MAP) a
    l'ensemble de drapeaux persistants d'une sauvegarde (flags_set) pour
    produire un tableau de booleens de longueur `total`, dans le meme ordre
    que le catalogue DATA correspondant cote site. Les indices absents du
    FLAG_MAP restent a False (aucun drapeau fiable connu - voir le
    commentaire au-dessus de SECRET_FLAG_MAP) : ce n'est pas une erreur, ces
    entrees restent volontairement a cocher a la main."""
    result = [False] * total
    for idx, cond in flag_map.items():
        if idx >= total:
            continue
        wanted = cond['flags']
        if cond['mode'] == 'all':
            result[idx] = all(f in flags_set for f in wanted)
        else:
            result[idx] = any(f in flags_set for f in wanted)
    return result

# Correspondance (groupe de stat, index de bit) -> position dans DATA.achievements
# du site, dans le meme ordre que ce tableau (index 0 = "Adoubement"/"Knighted",
# etc.). Etablie une fois pour toutes en comparant le nom francais officiel de
# chaque trophee dans UserGameStatsSchema_311690.bin (fichier de cache Steam,
# format VDF binaire) avec le nom francais deja present dans DATA.achievements :
# correspondance exacte et unique trouvee pour les 54 trophees, aucune ambiguite.
# Steam ne renumerote pas les trophees d'un jeu existant apres coup, donc cette
# table reste valable meme si de nouveaux trophees etaient ajoutes plus tard
# (ils arriveraient avec de nouveaux index, sans decaler les 54 actuels).
ACHIEVEMENT_STAT_MAP = [
    (1, 31), (1, 18), (2, 1), (1, 1), (2, 3), (1, 26), (2, 5), (1, 10), (1, 16),
    (1, 11), (2, 9), (2, 6), (1, 30), (1, 4), (1, 19), (2, 14), (1, 8), (1, 9),
    (1, 23), (1, 6), (1, 12), (1, 7), (1, 20), (1, 5), (1, 27), (2, 11), (2, 2),
    (1, 13), (2, 12), (1, 17), (1, 25), (2, 13), (2, 10), (1, 0), (1, 15), (1, 14),
    (1, 24), (1, 3), (1, 28), (2, 16), (2, 17), (2, 15), (1, 29), (2, 0), (2, 20),
    (2, 21), (1, 22), (1, 2), (2, 19), (2, 7), (2, 4), (2, 18), (1, 21), (2, 8),
]


def default_save_dir():
    userprofile = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    return os.path.join(userprofile, 'AppData', 'LocalLow', 'Dodge Roll', 'Enter the Gungeon')


def _default_data_dir():
    """Le dossier de donnees PAR DEFAUT (jamais deplace) : %APPDATA%\\RegistreDuGungeon,
    ou un repli si APPDATA/LOCALAPPDATA sont absents/inutilisables. C'est ICI,
    et seulement ici, qu'est toujours ecrit app_settings.json - meme si
    l'utilisateur redirige ensuite le dossier de DONNEES DE JEU ailleurs via
    les Parametres de l'appli : il faut un emplacement fixe et connu d'avance
    pour retrouver ce reglage avant meme de savoir ou chercher le reste."""
    appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
    if appdata:
        d = os.path.join(appdata, 'RegistreDuGungeon')
    else:
        d = _fallback_data_dir()
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = _fallback_data_dir()
    return d


def _settings_path():
    return os.path.join(_default_data_dir(), 'app_settings.json')


def load_app_settings():
    """Lit app_settings.json (reglages de l'appli elle-meme : dossiers
    personnalises, ecrans preferes pour les fenetres, assistant de premier
    lancement deja vu ou non). Renvoie des valeurs par defaut (None = "pas de
    reglage personnalise") si le fichier n'existe pas encore ou est
    illisible - ce n'est jamais une erreur bloquante, l'appli doit toujours
    pouvoir demarrer sans ce fichier."""
    path = _settings_path()
    defaults = {
        'dataDirectory': None, 'mainScreenIndex': None, 'overlayScreenIndex': None,
        'saveDirectory': None, 'steamDirectory': None, 'firstRunCompleted': False,
    }
    if not os.path.isfile(path):
        return defaults
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in defaults:
                if k in data:
                    defaults[k] = data[k]
            if 'firstRunCompleted' not in data:
                # Fichier de reglages deja present mais ecrit par une version
                # de l'appli anterieure a l'assistant de premier lancement :
                # cet utilisateur a deja utilise l'appli, il ne faut pas lui
                # imposer l'assistant comme s'il s'agissait d'une toute
                # premiere installation.
                defaults['firstRunCompleted'] = True
    except Exception:
        pass
    return defaults


def save_app_settings_to_disk(settings):
    """Ecriture atomique (fichier temporaire + remplacement), meme raisonnement
    que save_progress() : evite un app_settings.json a moitie ecrit si l'appli
    plante/l'ordinateur s'eteint pile pendant l'ecriture."""
    path = _settings_path()
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def effective_data_dir():
    """Dossier reellement utilise pour live_progress.json/run_history.json/
    progression.json : celui choisi dans les Parametres s'il est valide,
    sinon le dossier par defaut. Relu depuis le disque a CHAQUE appel (jamais
    mis en cache) expres : un changement de dossier dans les Parametres doit
    s'appliquer immediatement au sondage suivant, sans avoir a redemarrer
    l'appli."""
    settings = load_app_settings()
    custom = settings.get('dataDirectory')
    if custom:
        try:
            os.makedirs(custom, exist_ok=True)
            return custom
        except OSError:
            pass
    return _default_data_dir()


def _fallback_data_dir():
    """Dossier de repli si APPDATA/LOCALAPPDATA sont absents ou inutilisables.

    En mode normal (script), HERE (dossier du .py) convient. Mais une fois
    transforme en .exe --onefile par PyInstaller, HERE (via resource_path)
    pointe vers sys._MEIPASS, un dossier temporaire d'extraction que
    PyInstaller supprime a la fermeture de l'appli - tout ce qui y serait
    ecrit (progression.json) disparaitrait donc au prochain lancement. Dans
    ce cas on utilise plutot le dossier contenant l'executable lui-meme, qui
    lui persiste."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return HERE


def progress_file_path():
    """Emplacement du fichier ou est sauvegardee automatiquement la progression
    cochee sur le site (independant du fichier de sauvegarde du jeu lui-meme).
    Utilise effective_data_dir() : suit donc automatiquement un changement de
    dossier fait dans les Parametres, meme fichier que celui lu par
    read_live_data() pour live_progress.json/run_history.json (les trois
    fichiers vivent toujours ensemble, dans le meme dossier)."""
    return os.path.join(effective_data_dir(), 'progression.json')


def effective_save_dir():
    """Dossier reellement utilise pour chercher SlotA/B/C.save : celui choisi
    dans les Parametres s'il est valide, sinon le dossier par defaut. Comme
    effective_data_dir(), relu depuis le disque a chaque appel (jamais mis en
    cache) pour qu'un changement dans les Parametres s'applique immediatement."""
    settings = load_app_settings()
    custom = settings.get('saveDirectory')
    if custom and os.path.isdir(custom):
        return custom
    return default_save_dir()


def find_save_candidates():
    """Retourne les fichiers SlotA/B/C.save trouves, tries du plus recent au plus ancien."""
    d = effective_save_dir()
    candidates = []
    for slot in ('SlotA.save', 'SlotB.save', 'SlotC.save'):
        p = os.path.join(d, slot)
        if os.path.isfile(p):
            candidates.append(p)
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates


class SteamReadError(Exception):
    """Erreur de lecture des trophees Steam avec un message deja adapte a l'utilisateur."""
    pass


_steam_install_dir_cache = None
_steam_install_dir_cached = False


def find_steam_install_dir():
    """Retrouve le dossier d'installation du client Steam (celui qui contient
    appcache/stats, PAS le dossier ou est installe le jeu lui-meme : ce sont
    deux choses differentes, le premier ne bouge pas meme si le jeu est
    installe sur un autre disque via une bibliotheque Steam secondaire).

    Un dossier choisi manuellement dans les Parametres est toujours prioritaire
    (verifie a CHAQUE appel, avant meme de toucher au cache) : ca reste tres
    peu couteux (juste une lecture JSON + un os.path.isdir), et ca permet a un
    changement dans les Parametres de s'appliquer immediatement, comme pour
    effective_data_dir()/effective_save_dir().

    A defaut de reglage manuel, le resultat de l'auto-detection (registre
    Windows + acces disque, plus couteux) est mis en cache pour le processus :
    ce dossier ne change jamais tant que l'appli tourne, or ce lookup etait
    refait a chaque sondage cote JS (environ toutes les 15s)."""
    settings = load_app_settings()
    override = settings.get('steamDirectory')
    if override and os.path.isdir(override):
        return override

    global _steam_install_dir_cache, _steam_install_dir_cached
    if _steam_install_dir_cached:
        return _steam_install_dir_cache
    _steam_install_dir_cached = True
    _steam_install_dir_cache = _find_steam_install_dir_uncached()
    return _steam_install_dir_cache


def _find_steam_install_dir_uncached():
    try:
        import winreg
        for hive, key_path, value_name in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        ):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                    if value and os.path.isdir(value):
                        return value
            except OSError:
                continue
    except ImportError:
        pass  # winreg n'existe que sous Windows

    for fallback in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        if os.path.isdir(fallback):
            return fallback
    return None


_user_game_stats_file_cache = None


def find_user_game_stats_file(steam_dir, app_id=STEAM_APP_ID):
    """Retrouve UserGameStats_<accountid>_<appid>.bin dans appcache/stats. Ce
    fichier est un cache binaire (format VDF binaire de Valve) que le client
    Steam ecrit localement des qu'il synchronise les stats/trophees du jeu
    avec ses serveurs (typiquement en cours de partie et/ou a la fermeture du
    jeu) - independant du mod BepInEx, ca marche meme sans lui.

    On identifie le compte Steam actif en prenant simplement le fichier le
    plus recemment modifie parmi ceux qui correspondent a cet appid : plus
    simple et tout aussi fiable que de decoder loginusers.vdf pour retrouver
    le compte "actif", et ca fonctionne meme sur un PC partage entre plusieurs
    comptes Steam (on prend alors les trophees du compte qui a joue le plus
    recemment).

    Le chemin trouve est mis en cache pour le processus (meme raison que
    find_steam_install_dir : ce glob + tri par date etait refait a chaque
    sondage). Si le fichier cache disparait entre-temps (nouveau profil
    Steam, reinstallation...), on relance simplement la recherche."""
    global _user_game_stats_file_cache
    if _user_game_stats_file_cache and os.path.isfile(_user_game_stats_file_cache):
        return _user_game_stats_file_cache

    stats_dir = os.path.join(steam_dir, 'appcache', 'stats')
    pattern = os.path.join(stats_dir, f'UserGameStats_*_{app_id}.bin')
    candidates = glob.glob(pattern)
    if not candidates:
        _user_game_stats_file_cache = None
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    _user_game_stats_file_cache = candidates[0]
    return _user_game_stats_file_cache


def read_steam_achievements_data():
    """Lit l'etat des 54 trophees Steam d'Enter the Gungeon directement depuis
    le cache local du client Steam (aucune dependance au mod BepInEx). Renvoie
    un tableau de 54 booleens dans le meme ordre que DATA.achievements cote
    site (voir ACHIEVEMENT_STAT_MAP)."""
    try:
        import vdf
    except ImportError:
        raise SteamReadError(
            "Le module Python 'vdf' n'est pas installe (necessaire pour lire les trophees Steam).\n\n"
            "Lancez : pip install vdf"
        )

    steam_dir = find_steam_install_dir()
    if not steam_dir:
        raise SteamReadError(
            "Installation Steam introuvable automatiquement.\n\n"
            "La recuperation des trophees Steam necessite que Steam soit installe sur cet ordinateur."
        )

    stats_path = find_user_game_stats_file(steam_dir)
    if not stats_path:
        raise SteamReadError(
            "Aucune donnee de trophees Steam trouvee pour Enter the Gungeon.\n\n"
            "Ce fichier est cree par Steam la premiere fois qu'il synchronise vos statistiques pour ce "
            "jeu (en general en cours de partie, ou juste apres l'avoir quitte). Lancez le jeu au moins "
            "une fois avec Steam actif, jouez quelques instants, puis reessayez."
        )

    with open(stats_path, 'rb') as f:
        raw = f.read()

    try:
        parsed = vdf.binary_loads(raw, mapper=dict)
    except Exception as e:
        raise SteamReadError(f"Le fichier de trophees Steam n'a pas pu etre lu (format inattendu) : {e}")

    cache = parsed.get('cache', {})
    unlocked = []
    for group_id, bit_index in ACHIEVEMENT_STAT_MAP:
        group = cache.get(str(group_id), {})
        is_unlocked = False
        # Source principale : AchievementTimes ne contient que les trophees
        # deja debloques (cle = index de bit, valeur = horodatage Unix du
        # deblocage) - sa seule presence suffit, peu importe la valeur.
        achievement_times = group.get('AchievementTimes')
        if isinstance(achievement_times, dict):
            # AchievementTimes ne liste QUE les trophees deja debloques : si
            # le dictionnaire est present mais que ce bit precis n'y figure
            # pas, c'est que ce trophee est bel et bien verrouille (et non
            # une raison de retomber sur le bitfield brut, qui peut etre
            # obsolete/desynchronise par rapport a AchievementTimes).
            is_unlocked = str(bit_index) in achievement_times
        else:
            # Filet de securite : uniquement si AchievementTimes est absent
            # ou n'est pas du tout un dictionnaire pour ce groupe, on retombe
            # sur la lecture directe du bit dans le champ bitfield 'data'
            # du groupe (entier signe 32 bits).
            raw_data = group.get('data')
            if isinstance(raw_data, int):
                unsigned = raw_data & 0xFFFFFFFF
                is_unlocked = bool((unsigned >> bit_index) & 1)
        unlocked.append(is_unlocked)

    return {
        'achievements': unlocked,
        'unlockedCount': sum(1 for v in unlocked if v),
        'source': stats_path,
        'mtime': os.path.getmtime(stats_path),
    }


class SaveReadError(Exception):
    """Erreur de lecture de sauvegarde avec un message deja adapte a l'utilisateur."""
    pass


# Enter the Gungeon chiffre le corps de ses fichiers de sauvegarde avec un XOR
# repetant cette cle secrete (extraite du code source du jeu). Le dernier
# octet de la cle (un simple "\n" final) n'est en realite jamais utilise a
# cause d'une particularite de la boucle de cyclage du jeu : l'index repart a
# 0 des qu'il atteint len(cle) - 1, donc la longueur de cycle effective est
# len(SAVE_XOR_KEY) - 1.
SAVE_XOR_KEY = (
    b"Putting in a super basic encryption pass so our saves are a little "
    b"harder to edit than just opening a text or hex editor.  Need a secret "
    b"key or some such... so here's some nonsense.\n"
)
SAVE_VERSION_HEADER = b"version: 0\n"


def xor_decrypt_save_body(body):
    """Dechiffre le corps (apres l'en-tete de version) d'un fichier .save."""
    cycle_len = len(SAVE_XOR_KEY) - 1
    decoded = bytearray(len(body))
    index = 0
    for i, byte in enumerate(body):
        decoded[i] = SAVE_XOR_KEY[index] ^ byte
        index += 1
        if index >= cycle_len:
            index = 0
    return bytes(decoded)


def decode_save(path, guid_map):
    slot_name = os.path.basename(path)

    # Lire en binaire d'abord : certains fichiers de sauvegarde contiennent un
    # BOM UTF-8 et/ou des octets NUL de bourrage a la fin (quand le jeu
    # ecrase une sauvegarde plus longue par une plus courte sans tronquer le
    # fichier). Les ignorer evite de faire planter le decodage JSON pour rien.
    with open(path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    raw = raw.rstrip(b'\x00')

    if not raw.strip():
        raise SaveReadError(
            f"Le fichier {slot_name} est vide.\n\n"
            "C'est normal si vous n'avez pas encore lance une partie sur ce slot : "
            "Enter the Gungeon ne cree/remplit ce fichier qu'apres avoir demarre (et un peu joue) "
            "une partie sur ce slot de sauvegarde.\n\n"
            "Lancez le jeu, choisissez ce slot, jouez quelques instants, puis reessayez."
        )

    if not raw.startswith(SAVE_VERSION_HEADER):
        raise SaveReadError(
            f"Le fichier {slot_name} ne ressemble pas a une sauvegarde Enter the Gungeon valide "
            "(l'en-tete attendu est absent).\n\n"
            "Verifiez que vous avez bien selectionne un fichier SlotA.save, SlotB.save ou SlotC.save."
        )

    body = raw[len(SAVE_VERSION_HEADER):]

    # Les versions recentes du jeu ecrivent le corps du fichier en JSON EN
    # CLAIR (verifie empiriquement sur une vraie sauvegarde de joueur) - le
    # XOR decrit plus haut ne s'applique donc plus. On essaie d'abord le
    # texte brut (cas actuel), et on ne retombe sur le dechiffrement XOR que
    # si ca echoue : ca couvre a la fois les sauvegardes actuelles et
    # d'eventuelles sauvegardes plus anciennes/autres plateformes qui
    # utiliseraient encore l'ancien format chiffre, sans avoir a deviner
    # lequel des deux s'applique a l'avance.
    save = None
    for candidate_bytes in (body, xor_decrypt_save_body(body)):
        content = candidate_bytes.decode('utf-8', errors='replace').strip()
        try:
            # raw_decode ne lit que le premier objet JSON valide et ignore
            # tout ce qui suit (utile s'il reste des octets de bourrage/
            # anciennes donnees apres la fin du JSON, ce qui ferait echouer
            # json.loads).
            save, _end = json.JSONDecoder().raw_decode(content)
            break
        except json.JSONDecodeError:
            continue

    if save is None:
        raise SaveReadError(
            f"Le fichier {slot_name} n'a pas pu etre lu : son contenu semble incomplet ou corrompu.\n\n"
            "Cela peut arriver si le jeu etait en train d'ecrire la sauvegarde au meme moment. "
            "Fermez le jeu proprement (ou attendez la fin d'une partie), puis reessayez."
        )

    trackables = save.get('m_encounteredTrackables', {})

    guns_state = {}
    items_state = {}
    bosses_state = {}
    matched = 0
    for guid, info in trackables.items():
        if info.get('encounterCount', 0) <= 0:
            continue
        target = guid_map.get(guid)
        if not target:
            continue
        matched += 1
        idx = target['idx']
        cat = target['cat']
        if cat == 'guns':
            guns_state[idx] = True
        elif cat == 'items':
            items_state[idx] = True
        elif cat == 'bosses':
            bosses_state[idx] = True

    guns_array = [guns_state.get(i, False) for i in range(GUNS_TOTAL)]
    items_array = [items_state.get(i, False) for i in range(ITEMS_TOTAL)]
    bosses_array = [bosses_state.get(i, False) for i in range(BOSSES_TOTAL)]

    # m_flags est la liste (deja en clair, pas besoin de guid_map) des
    # drapeaux persistants de progression du jeu (PNJ liberes, secrets
    # trouves, defis reussis...) - voir SECRET_FLAG_MAP/NPC_FLAG_MAP/
    # QUEST_FLAG_MAP plus haut pour la correspondance vers les onglets
    # Secrets/PNJ/Quetes du site.
    flags_list = save.get('m_flags', [])
    flags_set = set(flags_list) if isinstance(flags_list, list) else set()
    secrets_array = flags_to_checklist(SECRET_FLAG_MAP, SECRETS_TOTAL, flags_set)
    npcs_array = flags_to_checklist(NPC_FLAG_MAP, NPCS_TOTAL, flags_set)
    quests_array = flags_to_checklist(QUEST_FLAG_MAP, QUESTS_TOTAL, flags_set)

    return {
        'guns': guns_array,
        'items': items_array,
        'bosses': bosses_array,
        'secrets': secrets_array,
        'npcs': npcs_array,
        'quests': quests_array,
        'matched': matched,
        'gunsFound': sum(guns_array),
        'itemsFound': sum(items_array),
        'bossesFound': sum(bosses_array),
        'source': path,
        'trackablesInSave': len(trackables),
        'mtime': os.path.getmtime(path),
    }


def merge_decoded_saves(decoded_list):
    """Fusionne plusieurs resultats de decode_save() (un par slot A/B/C) en un
    seul etat de progression, par simple OU logique arme-par-arme/objet-par-
    objet/boss-par-boss. Contrairement au reste des trois champs qui
    n'appartient qu'a UN slot a la fois (une run en cours, une seed...), le
    "rencontre au moins une fois" d'une arme/d'un objet/d'un boss est une
    propriete qui s'accumule sur TOUS les slots joues par ce joueur au fil du
    temps - lire uniquement le slot le plus recent (comme avant) faisait
    perdre silencieusement la progression enregistree sur les autres slots
    des qu'on relance l'appli apres avoir joue un slot different."""
    guns_array = [False] * GUNS_TOTAL
    items_array = [False] * ITEMS_TOTAL
    bosses_array = [False] * BOSSES_TOTAL
    secrets_array = [False] * SECRETS_TOTAL
    npcs_array = [False] * NPCS_TOTAL
    quests_array = [False] * QUESTS_TOTAL
    sources = []
    trackables_total = 0
    mtimes = []
    for d in decoded_list:
        sources.append(d['source'])
        trackables_total += d.get('trackablesInSave', 0)
        if d.get('mtime') is not None:
            mtimes.append(d['mtime'])
        for i, v in enumerate(d['guns']):
            if v:
                guns_array[i] = True
        for i, v in enumerate(d['items']):
            if v:
                items_array[i] = True
        for i, v in enumerate(d['bosses']):
            if v:
                bosses_array[i] = True
        for i, v in enumerate(d.get('secrets', [])):
            if v:
                secrets_array[i] = True
        for i, v in enumerate(d.get('npcs', [])):
            if v:
                npcs_array[i] = True
        for i, v in enumerate(d.get('quests', [])):
            if v:
                quests_array[i] = True

    return {
        'guns': guns_array,
        'items': items_array,
        'bosses': bosses_array,
        'secrets': secrets_array,
        'npcs': npcs_array,
        'quests': quests_array,
        'gunsFound': sum(guns_array),
        'itemsFound': sum(items_array),
        'bossesFound': sum(bosses_array),
        'matched': sum(guns_array) + sum(items_array) + sum(bosses_array),
        'source': sources[0] if len(sources) == 1 else ', '.join(sources),
        'sources': sources,
        'trackablesInSave': trackables_total,
        'mtime': max(mtimes) if mtimes else None,
    }


class Api:
    def __init__(self):
        # En mode --windowed (le .exe distribue), il n'y a pas de console
        # pour voir une exception non attrapee ici : un guid_map_data.json
        # corrompu ou manquant plantait l'appli au tout premier lancement
        # sans le moindre message visible, avant meme que webview.start()
        # n'ouvre une fenetre. On degrade plutot vers un dictionnaire vide :
        # la lecture de sauvegarde/live-tracking sera juste inoperante (aucun
        # GUID ne matchera), mais l'appli s'ouvre et affiche un site
        # utilisable.
        try:
            with open(GUID_MAP_PATH, encoding='utf-8') as f:
                self.guid_map = json.load(f)
        except Exception as e:
            print(f"[Registre] guid_map_data.json illisible, fonctionnalites de lecture de sauvegarde desactivees : {e}")
            self.guid_map = {}

    def list_save_files(self):
        try:
            return find_save_candidates()
        except Exception as e:
            return {'error': str(e)}

    def read_save_and_get_progress(self, path=None):
        try:
            if not path:
                candidates = find_save_candidates()
                if not candidates:
                    return {'error': (
                        "Aucun fichier de sauvegarde trouve automatiquement dans :\n" + effective_save_dir() +
                        "\n\nUtilisez le bouton \"Choisir un fichier...\" pour le selectionner manuellement, "
                        "ou changez le dossier de sauvegarde dans les Parametres (⚙) si le jeu est installe ailleurs."
                    )}
                if len(candidates) == 1:
                    return decode_save(candidates[0], self.guid_map)
                # Plusieurs slots (A/B/C) existent : la progression "rencontre
                # au moins une fois" doit etre cumulee sur tous, pas seulement
                # lue depuis le slot le plus recemment modifie (voir
                # merge_decoded_saves pour le raisonnement complet).
                decoded = [decode_save(p, self.guid_map) for p in candidates]
                return merge_decoded_saves(decoded)

            if not os.path.isfile(path):
                return {'error': f"Fichier introuvable : {path}"}

            result = decode_save(path, self.guid_map)
            return result
        except SaveReadError as e:
            return {'error': str(e)}
        except Exception as e:
            return {'error': f"Erreur inattendue lors de la lecture de la sauvegarde : {e}"}

    def choose_save_file(self):
        try:
            import webview
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                directory=effective_save_dir(),
                file_types=('Sauvegardes Gungeon (*.save)', 'Tous les fichiers (*.*)')
            )
            if not result:
                return None
            path = result[0]
            return self.read_save_and_get_progress(path)
        except Exception as e:
            return {'error': f"Erreur inattendue lors de l'ouverture du selecteur de fichier : {e}"}

    def save_progress(self, state_json_str):
        """Sauvegarde automatiquement la progression cochee sur le site (JSON)
        dans un fichier local, pour qu'elle soit retrouvee au prochain lancement."""
        try:
            path = progress_file_path()
            # Ecriture atomique (fichier temporaire + remplacement) : sans ca,
            # un crash/une coupure de courant pile pendant l'ecriture (ou Le
            # Registre relu au meme instant par un autre processus) pouvait
            # laisser progression.json a moitie ecrit et donc corrompu/perdu.
            tmp_path = path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(state_json_str)
            os.replace(tmp_path, path)
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def load_progress(self):
        """Recharge la progression sauvegardee automatiquement lors du dernier
        lancement. Renvoie {'exists': False} si aucun fichier n'existe encore
        (premier lancement - cas normal, pas une erreur), ou
        {'exists': True, 'corrupted': True, 'error': ...} si le fichier existe
        mais n'a pas pu etre lu/parse (auparavant les deux cas renvoyaient
        silencieusement None, rendant impossible pour le site de distinguer
        "rien a charger" de "quelque chose s'est mal passe, avertir
        l'utilisateur plutot que de repartir silencieusement de zero")."""
        path = progress_file_path()
        if not os.path.isfile(path):
            return {'exists': False}
        try:
            with open(path, encoding='utf-8') as f:
                content = f.read()
            if not content.strip():
                return {'exists': False}
            data = json.loads(content)
            return {'exists': True, 'corrupted': False, 'data': data}
        except Exception as e:
            return {'exists': True, 'corrupted': True, 'error': str(e)}

    def read_live_data(self):
        """Relit (si presents) les fichiers live_progress.json et run_history.json
        ecrits en direct par le mod BepInEx optionnel "Le Registre du Gungeon -
        Live Tracker", pendant que le jeu tourne. Renvoie None pour un fichier
        absent (mod non installe ou jamais encore lance) plutot que de faire
        echouer tout l'appel : les deux sources sont independantes."""
        result = {'liveProgress': None, 'runHistory': None}
        base_dir = os.path.dirname(progress_file_path())

        live_path = os.path.join(base_dir, 'live_progress.json')
        if os.path.isfile(live_path):
            try:
                with open(live_path, encoding='utf-8') as f:
                    content = f.read()
                if content.strip():
                    data = json.loads(content)
                    data['_mtime'] = os.path.getmtime(live_path)
                    result['liveProgress'] = data
            except Exception:
                pass

        history_path = os.path.join(base_dir, 'run_history.json')
        if os.path.isfile(history_path):
            try:
                with open(history_path, encoding='utf-8') as f:
                    content = f.read()
                if content.strip():
                    data = json.loads(content)
                    data['_mtime'] = os.path.getmtime(history_path)
                    result['runHistory'] = data
            except Exception:
                pass

        return result

    def open_run_overlay(self, run_id=None):
        """Ouvre (ou remet au premier plan si deja ouverte) la petite fenetre
        "partie en cours" - appelee depuis le JS de la fenetre principale des
        qu'une nouvelle run apparait "in_progress" (voir pollLiveData/
        overlayOpenedForRunId cote HTML). run_id n'est pas utilise ici (la
        fenetre determine elle-meme quelle run afficher via son propre
        sondage de run_history.json) - il est seulement accepte pour
        eventuellement l'exploiter plus tard (log, etc.) sans casser l'appel."""
        global _overlay_window
        try:
            import webview
        except Exception as e:
            return {'ok': False, 'error': str(e)}

        with _overlay_window_lock:
            if _overlay_window is not None:
                try:
                    # Fenetre deja ouverte (run precedente encore affichee,
                    # ou double-declenchement) : on se contente de la
                    # ramener au premier plan plutot que d'en ouvrir une
                    # deuxieme. Si la reference est perimee (fermee entre-
                    # temps sans que le callback 'closed' n'ait encore mis
                    # _overlay_window a None), l'appel leve et on retombe
                    # sur la creation normale ci-dessous.
                    _overlay_window.restore()
                    _overlay_window.show()
                    return {'ok': True, 'alreadyOpen': True}
                except Exception:
                    _overlay_window = None

            overlay_screen = None
            try:
                settings = load_app_settings()
                idx = settings.get('overlayScreenIndex')
                if idx is not None:
                    screens = webview.screens
                    if 0 <= idx < len(screens):
                        overlay_screen = screens[idx]
            except Exception:
                overlay_screen = None

            overlay_kwargs = dict(
                js_api=self,
                width=420,
                height=720,
                min_size=(340, 460),
                background_color='#12100d',
                on_top=True,
            )
            try:
                # Meme raisonnement que pour la fenetre principale (voir
                # main()) : 'screen' peut etre absent sur une vieille version
                # de pywebview, on retente alors sans lui plutot que de ne
                # jamais ouvrir la fenetre de suivi du tout.
                new_window = webview.create_window(
                    'Partie en cours — Le Registre du Gungeon',
                    _overlay_html_url(),
                    screen=overlay_screen,
                    **overlay_kwargs
                )
            except TypeError:
                new_window = webview.create_window(
                    'Partie en cours — Le Registre du Gungeon',
                    _overlay_html_url(),
                    **overlay_kwargs
                )

                def _on_closed():
                    global _overlay_window
                    _overlay_window = None

                new_window.events.closed += _on_closed
                _overlay_window = new_window
                return {'ok': True}
            except Exception as e:
                return {'ok': False, 'error': str(e)}

    def read_steam_achievements(self):
        """Relit l'etat des trophees Steam depuis le cache local du client
        Steam (voir read_steam_achievements_data). Ne fait jamais planter
        l'appel : une erreur (Steam non trouve, jeu jamais synchronise, etc.)
        est renvoyee comme un simple message, le site l'ignore silencieusement
        et reessaiera au prochain sondage."""
        try:
            return read_steam_achievements_data()
        except SteamReadError as e:
            return {'error': str(e)}
        except Exception as e:
            return {'error': f"Erreur inattendue lors de la lecture des trophees Steam : {e}"}

    def export_progress(self, state_json_str):
        """Exporte la progression vers un fichier choisi par l'utilisateur, via
        une vraie boite de dialogue "Enregistrer sous". Le telechargement via
        un lien <a download> ne fonctionne pas de facon fiable dans toutes les
        fenetres d'application (WebView2/WKWebView selon la plateforme), donc
        on passe par l'API native de pywebview cote Python."""
        try:
            import webview
            result = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                directory=os.path.expanduser('~'),
                save_filename='gungeon_progression.json',
                file_types=('Fichiers JSON (*.json)', 'Tous les fichiers (*.*)')
            )
            if not result:
                return {'ok': False, 'cancelled': True}
            path = result if isinstance(result, str) else result[0]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(state_json_str)
            return {'ok': True, 'path': path}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ---- Parametres (dossier de donnees + ecran d'affichage) ----

    def get_app_settings(self):
        """Renvoie les reglages personnalises actuels, plus des valeurs
        calculees utiles a l'affichage cote site : dossiers par defaut (pour
        afficher '(par defaut)' si aucun dossier personnalise n'est choisi) et
        dossiers reellement utilises en ce moment (effectiveSteamDirectory
        peut etre None si Steam n'a pas ete detecte automatiquement ET
        qu'aucun dossier n'a ete choisi a la main)."""
        settings = load_app_settings()
        settings['defaultDataDirectory'] = _default_data_dir()
        settings['effectiveDataDirectory'] = effective_data_dir()
        settings['defaultSaveDirectory'] = default_save_dir()
        settings['effectiveSaveDirectory'] = effective_save_dir()
        try:
            settings['effectiveSteamDirectory'] = find_steam_install_dir()
        except Exception:
            settings['effectiveSteamDirectory'] = None
        return settings

    def choose_data_directory(self):
        """Ouvre une vraie boite de dialogue "Choisir un dossier" et
        enregistre immediatement le choix. Le nouveau dossier est utilise des
        le prochain sondage (effective_data_dir() relit le fichier de
        reglages a chaque appel, voir son commentaire) - pas besoin de
        redemarrer l'appli pour ca."""
        try:
            import webview
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=effective_data_dir(),
            )
            if not result:
                return {'ok': False, 'cancelled': True}
            chosen = result[0] if isinstance(result, (list, tuple)) else result
            settings = load_app_settings()
            settings['dataDirectory'] = chosen
            save_app_settings_to_disk(settings)
            return {'ok': True, 'dataDirectory': chosen}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def reset_data_directory(self):
        """Revient au dossier par defaut (%APPDATA%\\RegistreDuGungeon)."""
        try:
            settings = load_app_settings()
            settings['dataDirectory'] = None
            save_app_settings_to_disk(settings)
            return {'ok': True, 'dataDirectory': _default_data_dir()}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def choose_save_directory(self):
        """Meme principe que choose_data_directory(), pour le dossier ou sont
        cherches SlotA/B/C.save (utile si le jeu/la sauvegarde est ailleurs
        que l'emplacement standard, ex. profil Windows different, disque
        externe, configuration OneDrive qui deplace AppData...)."""
        try:
            import webview
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=effective_save_dir(),
            )
            if not result:
                return {'ok': False, 'cancelled': True}
            chosen = result[0] if isinstance(result, (list, tuple)) else result
            settings = load_app_settings()
            settings['saveDirectory'] = chosen
            save_app_settings_to_disk(settings)
            return {'ok': True, 'saveDirectory': chosen}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def reset_save_directory(self):
        try:
            settings = load_app_settings()
            settings['saveDirectory'] = None
            save_app_settings_to_disk(settings)
            return {'ok': True, 'saveDirectory': default_save_dir()}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def choose_steam_directory(self):
        """Dossier d'INSTALLATION de Steam lui-meme (celui qui contient
        steamapps/, appcache/...), pas le dossier du jeu - voir
        find_steam_install_dir(). Invalide aussi les caches d'auto-detection
        (dossier Steam + fichier de stats trouve) : sans ca, un changement de
        dossier en cours de session pourrait continuer a lire les trophees de
        l'ancien emplacement jusqu'au redemarrage de l'appli."""
        try:
            import webview
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=find_steam_install_dir() or os.path.expanduser('~'),
            )
            if not result:
                return {'ok': False, 'cancelled': True}
            chosen = result[0] if isinstance(result, (list, tuple)) else result
            settings = load_app_settings()
            settings['steamDirectory'] = chosen
            save_app_settings_to_disk(settings)
            global _steam_install_dir_cached, _user_game_stats_file_cache
            _steam_install_dir_cached = False
            _user_game_stats_file_cache = None
            return {'ok': True, 'steamDirectory': chosen}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def reset_steam_directory(self):
        try:
            settings = load_app_settings()
            settings['steamDirectory'] = None
            save_app_settings_to_disk(settings)
            global _steam_install_dir_cached, _user_game_stats_file_cache
            _steam_install_dir_cached = False
            _user_game_stats_file_cache = None
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def mark_first_run_completed(self):
        """Empeche l'assistant de premier lancement de se redeclencher au
        prochain demarrage. Appele des que la fenetre des Parametres se ferme
        (quel que soit le moyen : croix, Echap, clic hors modale) quand elle a
        ete ouverte en mode "premier lancement" - voir openSettings() cote
        JS. Volontairement independant de tout dossier effectivement change :
        le but est juste de savoir si l'utilisateur a deja vu cet ecran une
        fois, pas de verifier qu'il a modifie quelque chose."""
        try:
            settings = load_app_settings()
            settings['firstRunCompleted'] = True
            save_app_settings_to_disk(settings)
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def list_screens(self):
        """Enumere les ecrans disponibles (webview.screens) pour peupler les
        listes deroulantes des Parametres. Renvoie une liste de dictionnaires
        simples (serialisables) plutot que les objets Screen eux-memes."""
        try:
            import webview
            screens = webview.screens
            return [
                {'index': i, 'width': s.width, 'height': s.height, 'x': s.x, 'y': s.y}
                for i, s in enumerate(screens)
            ]
        except Exception as e:
            return {'error': str(e)}

    def save_screen_settings(self, main_screen_index, overlay_screen_index):
        """Enregistre l'ecran choisi pour la fenetre principale et pour la
        fenetre de suivi (None = ecran par defaut du systeme pour l'un ou
        l'autre). Deplace aussi IMMEDIATEMENT la fenetre principale deja
        ouverte si possible (window.move) : sans ca l'utilisateur devrait
        deviner qu'un redemarrage est necessaire. La fenetre de suivi, elle,
        est recreee a chaque nouvelle run (voir open_run_overlay) et prendra
        le nouvel ecran naturellement des sa prochaine ouverture."""
        try:
            settings = load_app_settings()
            settings['mainScreenIndex'] = main_screen_index
            settings['overlayScreenIndex'] = overlay_screen_index
            save_app_settings_to_disk(settings)

            applied_now = False
            try:
                import webview
                screens = webview.screens
                if (main_screen_index is not None
                        and 0 <= main_screen_index < len(screens)
                        and webview.windows):
                    s = screens[main_screen_index]
                    webview.windows[0].move(s.x, s.y)
                    applied_now = True
            except Exception:
                # move() indisponible sur cette version de pywebview, ou pas
                # de fenetre principale a deplacer maintenant : pas grave, le
                # reglage est deja enregistre et s'appliquera au prochain
                # demarrage de toute facon (voir main()).
                pass

            return {'ok': True, 'appliedNow': applied_now}
        except Exception as e:
            return {'ok': False, 'error': str(e)}


def main():
    import webview

    if not os.path.isfile(HTML_PATH):
        print(f"Introuvable : {HTML_PATH}")
        print("Placez gungeon_app.py, gungeon_registre.html et guid_map_data.json dans le meme dossier.")
        sys.exit(1)
    if not os.path.isfile(GUID_MAP_PATH):
        print(f"Introuvable : {GUID_MAP_PATH}")
        print("Placez gungeon_app.py, gungeon_registre.html et guid_map_data.json dans le meme dossier.")
        sys.exit(1)

    api = Api()

    # Ecran choisi dans les Parametres pour la fenetre principale, s'il y en
    # a un et qu'il correspond toujours a un ecran reellement branche (un
    # ecran externe debranche depuis le dernier lancement, par exemple, ne
    # doit pas empecher l'appli de s'ouvrir - on retombe alors simplement sur
    # le comportement par defaut de pywebview, sans lever d'erreur).
    main_screen = None
    try:
        settings = load_app_settings()
        idx = settings.get('mainScreenIndex')
        if idx is not None:
            screens = webview.screens
            if 0 <= idx < len(screens):
                main_screen = screens[idx]
    except Exception:
        main_screen = None

    window_kwargs = dict(
        js_api=api,
        width=1440,
        height=980,
        min_size=(1000, 700),
        background_color='#12100d',
    )
    try:
        # 'screen' n'existe que depuis pywebview 4.x : sur une version plus
        # ancienne deja installee chez un utilisateur (pip install ne force
        # pas de mise a jour d'un paquet deja present), passer ce mot-cle
        # leverait un TypeError qui empecherait l'appli de s'ouvrir du tout.
        # On retente alors sans lui plutot que de planter au demarrage - la
        # seule consequence est que le choix d'ecran n'est pas applique.
        window = webview.create_window('Le Registre du Gungeon', HTML_PATH, screen=main_screen, **window_kwargs)
    except TypeError:
        window = webview.create_window('Le Registre du Gungeon', HTML_PATH, **window_kwargs)
    webview.start()


if __name__ == '__main__':
    main()
