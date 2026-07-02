# ChronoApp ⏱

Suivi du temps par **projet → tâche → sous-tâche**, avec timers Play/Pause,
indicateur de dépassement, dashboard des tâches actives et **sauvegarde locale**.

Deux versions **indépendantes**, chacune avec ses propres données locales — **aucune synchronisation entre PC et mobile** (comme demandé).

---

## 🖥️ Version PC (Windows 11) — `chrono_app.py`

Application de bureau (Python/Tkinter), livrée en exécutable.

**Fonctionnalités**
- Projets, tâches et **sous-tâches** (hiérarchie dépliable), chacun avec un temps estimé
- Timer **Play/Pause** sur chaque ligne — raccourci **ESPACE**
- Ligne en **rouge + « ! DÉPASSÉ »** quand le temps estimé est dépassé
- **Dashboard** des lignes actives, tous projets confondus
- Sauvegarde locale auto dans `%APPDATA%\ChronoApp\data.json` (toutes les 15 s + à la fermeture)
- **Alerte à la fermeture** si des timers sont encore actifs

**Installation**
1. Onglet **[Releases](../../releases/latest)** → télécharger **`ChronoApp.exe`**.
2. Double-cliquer pour lancer. Aucune installation supplémentaire.
   (SmartScreen peut avertir la 1ʳᵉ fois → « Informations complémentaires » → « Exécuter quand même ».)

L'exécutable est compilé automatiquement par GitHub Actions à chaque push sur `main`.

---

## 📱 Version mobile (et navigateur PC) — dossier `mobile/`

Web app installable (PWA). Fonctionne sur **iPhone / Android** et dans n'importe quel navigateur.
Données stockées **localement sur l'appareil** (localStorage), séparées de la version PC.

**Fonctionnalités** : identiques à la version PC — projets, tâches, sous-tâches, timers Play/Pause,
indicateur de dépassement, dashboard des actives, sauvegarde locale, **alerte à la fermeture** si une tâche tourne.

**Mise en ligne (une fois)**
1. Repo → **Settings → Pages** → *Source : Deploy from a branch* → branche `main`, dossier `/ (root)` → **Save**.
2. Attendre ~1 min. L'URL de la version mobile sera :
   `https://fairygle.github.io/chrono_app/mobile/`
3. Ouvrir cette URL sur le téléphone → menu du navigateur → **« Ajouter à l'écran d'accueil »**.
   L'app s'ouvre alors en plein écran et fonctionne **hors-ligne**.

> Astuce : `Play/Pause` = bouton rond ambre. `⋮` = modifier / remettre à zéro / supprimer.
> L'alerte de fermeture s'affiche de façon fiable sur navigateur de bureau ; sur mobile,
> le système peut fermer l'onglet sans confirmation, mais les compteurs sont sauvegardés
> chaque seconde et repris à la réouverture, donc rien n'est perdu.

---

## Développement

```bash
python chrono_app.py                 # lancer la version PC (Python 3.10+, Tkinter)

pip install pyinstaller              # compiler l'exécutable Windows
pyinstaller --onefile --noconsole --name ChronoApp chrono_app.py
```

La version mobile est un simple fichier statique : ouvrir `mobile/index.html` dans un navigateur.
