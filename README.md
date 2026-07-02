# ChronoApp ⏱

Application Windows de suivi du temps par projet et par tâche.

## Fonctionnalités

- Création de **projets** et de **tâches** avec un **temps estimé** (en minutes)
- **Timer PLAY / PAUSE** sur chaque tâche
- Raccourci clavier **ESPACE** pour Play/Pause sur la tâche sélectionnée
- **Indicateur rouge ⚠ DÉPASSÉ** quand une tâche dure plus longtemps que l'estimation
- **Dashboard** des tâches actives, tous projets confondus
- **Sauvegarde locale automatique** dans `%APPDATA%\ChronoApp\data.json` (toutes les 15 s et à la fermeture)

## Installation (Windows 11)

1. Allez dans l'onglet **[Releases](../../releases/latest)** du repo.
2. Téléchargez **`ChronoApp.exe`**.
3. Double-cliquez sur le fichier pour lancer l'application. Aucune installation supplémentaire n'est nécessaire.

> Windows SmartScreen peut afficher un avertissement la première fois (exécutable non signé) : cliquez sur « Informations complémentaires » → « Exécuter quand même ».

## Utilisation

1. Créez un projet (bouton **＋ Projet**).
2. Ajoutez des tâches avec leur temps estimé (**＋ Tâche**).
3. Sélectionnez une tâche puis appuyez sur **ESPACE** (ou double-clic, ou le bouton ▶/⏸) pour démarrer / mettre en pause le chrono.
4. L'onglet **Dashboard** liste toutes les tâches en cours, tous projets confondus.
5. Une tâche qui dépasse son estimation passe en **rouge** avec la mention **⚠ DÉPASSÉ**.

## Compilation

L'exécutable est généré automatiquement par GitHub Actions (PyInstaller) à chaque push sur `main`,
et publié dans la release `latest`.

Pour compiler manuellement :

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name ChronoApp chrono_app.py
```

Pour lancer sans compiler (Python 3.10+ requis) :

```bash
python chrono_app.py
```

## ⚙️ Activer la compilation automatique (1 fois)

Le token utilisé n'avait pas la permission `workflow`, le fichier de build est donc fourni
dans `workflow-a-installer/build-windows.yml`. Pour l'activer :

1. Sur GitHub, ouvrez le repo → **Add file → Create new file**.
2. Nommez le fichier : `.github/workflows/build-windows.yml`
3. Collez-y le contenu de `workflow-a-installer/build-windows.yml` et validez (**Commit**).
4. L'onglet **Actions** compilera `ChronoApp.exe` et le publiera dans **Releases** en ~3 minutes.
