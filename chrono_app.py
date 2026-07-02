#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChronoApp - Suivi du temps par projet et par tâche.

- Création de projets et de tâches avec temps estimé
- Timer PLAY / PAUSE sur chaque tâche (raccourci : ESPACE)
- Indicateur visuel si une tâche dépasse le temps estimé
- Dashboard des tâches actives, tous projets confondus
- Sauvegarde locale automatique (%APPDATA%\\ChronoApp\\data.json)
"""

import json
import os
import sys
import time
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

APP_NAME = "ChronoApp"
AUTOSAVE_MS = 15000  # sauvegarde auto toutes les 15 s
TICK_MS = 1000       # rafraîchissement de l'affichage


# ----------------------------- Stockage local ------------------------------

def data_dir() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


DATA_FILE = os.path.join(data_dir(), "data.json")


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Les timers ne tournent pas quand l'app est fermée
            for p in data.get("projects", []):
                for t in p.get("tasks", []):
                    t["running"] = False
                    t.pop("started_at", None)
            return data
        except Exception:
            # Fichier corrompu : on repart proprement sans écraser l'ancien
            try:
                os.replace(DATA_FILE, DATA_FILE + ".bak")
            except Exception:
                pass
    return {"projects": []}


def save_data(data: dict) -> None:
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


# ------------------------------- Utilitaires -------------------------------

def fmt_hms(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def task_elapsed(task: dict) -> float:
    elapsed = task.get("elapsed", 0.0)
    if task.get("running") and task.get("started_at"):
        elapsed += time.time() - task["started_at"]
    return elapsed


def task_over(task: dict) -> bool:
    est = task.get("estimate_min", 0)
    return est > 0 and task_elapsed(task) > est * 60


# ------------------------- Boîte de dialogue tâche --------------------------

class TaskDialog(simpledialog.Dialog):
    """Demande le nom de la tâche et le temps estimé (en minutes)."""

    def __init__(self, parent, title, name="", estimate=60):
        self._name = name
        self._estimate = estimate
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Nom de la tâche :").grid(row=0, column=0, sticky="w", pady=4)
        self.e_name = ttk.Entry(master, width=32)
        self.e_name.insert(0, self._name)
        self.e_name.grid(row=0, column=1, pady=4)

        ttk.Label(master, text="Temps estimé (minutes) :").grid(row=1, column=0, sticky="w", pady=4)
        self.e_est = ttk.Spinbox(master, from_=0, to=100000, width=10)
        self.e_est.delete(0, "end")
        self.e_est.insert(0, str(self._estimate))
        self.e_est.grid(row=1, column=1, sticky="w", pady=4)
        return self.e_name

    def validate(self):
        name = self.e_name.get().strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Le nom de la tâche est obligatoire.", parent=self)
            return False
        try:
            est = int(float(self.e_est.get()))
            if est < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(APP_NAME, "Le temps estimé doit être un nombre de minutes.", parent=self)
            return False
        self.result = (name, est)
        return True


# --------------------------------- Application ------------------------------

class ChronoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " — Suivi du temps")
        self.geometry("980x560")
        self.minsize(820, 460)

        self.data = load_data()
        self.selected_project_id = None
        self.last_toggled_task_id = None  # cible du raccourci ESPACE

        self._build_ui()
        self._refresh_projects()
        self.after(TICK_MS, self._tick)
        self.after(AUTOSAVE_MS, self._autosave)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Raccourci ESPACE : Play/Pause (sauf pendant la saisie de texte)
        self.bind_all("<space>", self._on_space)

    # ------------------------------ Interface ------------------------------

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26)
        style.configure("Over.TLabel", foreground="#c62828")

        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        # --- Panneau gauche : projets ---
        left = ttk.Frame(root)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="Projets", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.lb_projects = tk.Listbox(left, width=26, exportselection=False, activestyle="dotbox")
        self.lb_projects.pack(fill="y", expand=True, pady=4)
        self.lb_projects.bind("<<ListboxSelect>>", lambda e: self._on_project_select())

        pbtn = ttk.Frame(left)
        pbtn.pack(fill="x")
        ttk.Button(pbtn, text="＋ Projet", command=self._add_project).pack(side="left", expand=True, fill="x")
        ttk.Button(pbtn, text="🗑 Supprimer", command=self._delete_project).pack(side="left", expand=True, fill="x")

        # --- Panneau droit : onglets ---
        self.nb = ttk.Notebook(root)
        self.nb.pack(side="left", fill="both", expand=True)

        # Onglet Tâches
        tab_tasks = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab_tasks, text="  Tâches du projet  ")

        cols = ("task", "estimate", "elapsed", "status")
        self.tree = ttk.Treeview(tab_tasks, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("task", text="Tâche")
        self.tree.heading("estimate", text="Estimé")
        self.tree.heading("elapsed", text="Temps passé")
        self.tree.heading("status", text="État")
        self.tree.column("task", width=320, anchor="w")
        self.tree.column("estimate", width=90, anchor="center")
        self.tree.column("elapsed", width=110, anchor="center")
        self.tree.column("status", width=170, anchor="center")
        self.tree.tag_configure("over", foreground="#c62828")
        self.tree.tag_configure("running", background="#e8f5e9")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._toggle_selected())

        tbtn = ttk.Frame(tab_tasks)
        tbtn.pack(fill="x", pady=(6, 0))
        ttk.Button(tbtn, text="▶ / ⏸  Play-Pause  (ESPACE)", command=self._toggle_selected).pack(side="left")
        ttk.Button(tbtn, text="＋ Tâche", command=self._add_task).pack(side="left", padx=6)
        ttk.Button(tbtn, text="✎ Modifier", command=self._edit_task).pack(side="left")
        ttk.Button(tbtn, text="↺ Remettre à zéro", command=self._reset_task).pack(side="left", padx=6)
        ttk.Button(tbtn, text="🗑 Supprimer", command=self._delete_task).pack(side="left")

        # Onglet Dashboard
        tab_dash = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab_dash, text="  Dashboard — tâches actives  ")
        dcols = ("project", "task", "estimate", "elapsed", "status")
        self.dash = ttk.Treeview(tab_dash, columns=dcols, show="headings", selectmode="browse")
        for c, txt, w, a in (
            ("project", "Projet", 180, "w"),
            ("task", "Tâche", 280, "w"),
            ("estimate", "Estimé", 90, "center"),
            ("elapsed", "Temps passé", 110, "center"),
            ("status", "État", 160, "center"),
        ):
            self.dash.heading(c, text=txt)
            self.dash.column(c, width=w, anchor=a)
        self.dash.tag_configure("over", foreground="#c62828")
        self.dash.pack(fill="both", expand=True)
        self.dash.bind("<Double-1>", lambda e: self._toggle_from_dash())
        ttk.Label(
            tab_dash,
            text="Double-clic sur une ligne pour mettre en pause / reprendre.",
        ).pack(anchor="w", pady=(6, 0))

        # Barre d'état
        self.status = ttk.Label(self, anchor="w", padding=(8, 4))
        self.status.pack(fill="x", side="bottom")

    # ------------------------------- Projets -------------------------------

    def _project_by_id(self, pid):
        for p in self.data["projects"]:
            if p["id"] == pid:
                return p
        return None

    def _current_project(self):
        return self._project_by_id(self.selected_project_id)

    def _refresh_projects(self, keep=None):
        self.lb_projects.delete(0, "end")
        for p in self.data["projects"]:
            self.lb_projects.insert("end", p["name"])
        ids = [p["id"] for p in self.data["projects"]]
        if keep in ids:
            idx = ids.index(keep)
        elif ids:
            idx = 0
        else:
            idx = None
        if idx is not None:
            self.lb_projects.selection_set(idx)
            self.selected_project_id = ids[idx]
        else:
            self.selected_project_id = None
        self._refresh_tasks()
        self._refresh_dashboard()

    def _on_project_select(self):
        sel = self.lb_projects.curselection()
        if sel:
            self.selected_project_id = self.data["projects"][sel[0]]["id"]
            self._refresh_tasks()

    def _add_project(self):
        name = simpledialog.askstring(APP_NAME, "Nom du nouveau projet :", parent=self)
        if not name or not name.strip():
            return
        p = {"id": uuid.uuid4().hex, "name": name.strip(), "tasks": []}
        self.data["projects"].append(p)
        self._refresh_projects(keep=p["id"])
        self._save()

    def _delete_project(self):
        p = self._current_project()
        if not p:
            return
        if messagebox.askyesno(APP_NAME, f"Supprimer le projet « {p['name']} » et toutes ses tâches ?"):
            self.data["projects"].remove(p)
            self._refresh_projects()
            self._save()

    # -------------------------------- Tâches --------------------------------

    def _task_by_id(self, tid):
        for p in self.data["projects"]:
            for t in p["tasks"]:
                if t["id"] == tid:
                    return p, t
        return None, None

    def _selected_task(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        return self._task_by_id(sel[0])

    def _task_values(self, t):
        est = t.get("estimate_min", 0)
        est_txt = fmt_hms(est * 60) if est else "—"
        if t.get("running"):
            state = "▶ En cours"
        elif t.get("elapsed", 0) > 0:
            state = "⏸ En pause"
        else:
            state = "À faire"
        if task_over(t):
            state += "  ⚠ DÉPASSÉ"
        return (t["name"], est_txt, fmt_hms(task_elapsed(t)), state)

    def _task_tags(self, t):
        tags = []
        if task_over(t):
            tags.append("over")
        if t.get("running"):
            tags.append("running")
        return tuple(tags)

    def _refresh_tasks(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        p = self._current_project()
        if not p:
            return
        for t in p["tasks"]:
            self.tree.insert("", "end", iid=t["id"], values=self._task_values(t), tags=self._task_tags(t))
        for iid in sel:
            if self.tree.exists(iid):
                self.tree.selection_set(iid)

    def _add_task(self):
        p = self._current_project()
        if not p:
            messagebox.showinfo(APP_NAME, "Crée d'abord un projet.")
            return
        dlg = TaskDialog(self, "Nouvelle tâche")
        if dlg.result:
            name, est = dlg.result
            t = {"id": uuid.uuid4().hex, "name": name, "estimate_min": est,
                 "elapsed": 0.0, "running": False}
            p["tasks"].append(t)
            self._refresh_tasks()
            self.tree.selection_set(t["id"])
            self._save()

    def _edit_task(self):
        _, t = self._selected_task()
        if not t:
            return
        dlg = TaskDialog(self, "Modifier la tâche", t["name"], t.get("estimate_min", 0))
        if dlg.result:
            t["name"], t["estimate_min"] = dlg.result
            self._refresh_tasks()
            self._refresh_dashboard()
            self._save()

    def _reset_task(self):
        _, t = self._selected_task()
        if not t:
            return
        if messagebox.askyesno(APP_NAME, f"Remettre le compteur de « {t['name']} » à zéro ?"):
            t["elapsed"] = 0.0
            t["running"] = False
            t.pop("started_at", None)
            self._refresh_tasks()
            self._refresh_dashboard()
            self._save()

    def _delete_task(self):
        p, t = self._selected_task()
        if not t:
            return
        if messagebox.askyesno(APP_NAME, f"Supprimer la tâche « {t['name']} » ?"):
            p["tasks"].remove(t)
            self._refresh_tasks()
            self._refresh_dashboard()
            self._save()

    # ------------------------------ Play / Pause ----------------------------

    def _toggle_task(self, task):
        if task.get("running"):
            task["elapsed"] = task_elapsed(task)
            task["running"] = False
            task.pop("started_at", None)
        else:
            task["running"] = True
            task["started_at"] = time.time()
        self.last_toggled_task_id = task["id"]
        self._refresh_tasks()
        self._refresh_dashboard()
        self._save()

    def _toggle_selected(self):
        _, t = self._selected_task()
        if t:
            self._toggle_task(t)
        elif self.last_toggled_task_id:
            _, t = self._task_by_id(self.last_toggled_task_id)
            if t:
                self._toggle_task(t)

    def _toggle_from_dash(self):
        sel = self.dash.selection()
        if sel:
            _, t = self._task_by_id(sel[0])
            if t:
                self._toggle_task(t)

    def _on_space(self, event):
        # Ne pas intercepter la barre espace pendant une saisie de texte
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Spinbox, tk.Spinbox)):
            return
        # Dashboard visible → agir sur la ligne sélectionnée du dashboard
        if self.nb.index(self.nb.select()) == 1 and self.dash.selection():
            self._toggle_from_dash()
        else:
            self._toggle_selected()
        return "break"

    # ------------------------------- Dashboard ------------------------------

    def _refresh_dashboard(self):
        sel = self.dash.selection()
        self.dash.delete(*self.dash.get_children())
        for p in self.data["projects"]:
            for t in p["tasks"]:
                if t.get("running"):
                    v = self._task_values(t)
                    self.dash.insert("", "end", iid=t["id"],
                                     values=(p["name"], v[0], v[1], v[2], v[3]),
                                     tags=self._task_tags(t))
        for iid in sel:
            if self.dash.exists(iid):
                self.dash.selection_set(iid)

    # ----------------------------- Boucle & fin -----------------------------

    def _tick(self):
        # Met à jour les temps affichés sans recréer les lignes
        p = self._current_project()
        if p:
            for t in p["tasks"]:
                if self.tree.exists(t["id"]):
                    self.tree.item(t["id"], values=self._task_values(t), tags=self._task_tags(t))
        running = [(pr, t) for pr in self.data["projects"] for t in pr["tasks"] if t.get("running")]
        current_ids = set(self.dash.get_children())
        if {t["id"] for _, t in running} != current_ids:
            self._refresh_dashboard()
        else:
            for pr, t in running:
                v = self._task_values(t)
                self.dash.item(t["id"], values=(pr["name"], v[0], v[1], v[2], v[3]), tags=self._task_tags(t))
        n = len(running)
        over = sum(1 for _, t in running if task_over(t))
        msg = f"{n} tâche(s) active(s)"
        if over:
            msg += f"  —  ⚠ {over} en dépassement"
        msg += f"   |   Données : {DATA_FILE}"
        self.status.configure(text=msg, style="Over.TLabel" if over else "TLabel")
        self.after(TICK_MS, self._tick)

    def _save(self):
        try:
            save_data(self.data)
        except Exception as e:
            self.status.configure(text=f"Erreur de sauvegarde : {e}")

    def _autosave(self):
        self._save()
        self.after(AUTOSAVE_MS, self._autosave)

    def _on_close(self):
        # Fige les compteurs en cours puis sauvegarde
        for p in self.data["projects"]:
            for t in p["tasks"]:
                if t.get("running"):
                    t["elapsed"] = task_elapsed(t)
                    t["running"] = False
                    t.pop("started_at", None)
        self._save()
        self.destroy()


if __name__ == "__main__":
    app = ChronoApp()
    app.mainloop()
