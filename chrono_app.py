#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChronoApp - Suivi du temps par projet, tache et sous-tache.

- Projets > taches > sous-taches, chacun avec un temps estime
- Timer PLAY / PAUSE sur chaque ligne (raccourci : ESPACE)
- Indicateur rouge si une ligne depasse son temps estime
- Dashboard des lignes actives, tous projets confondus
- Sauvegarde locale automatique (%APPDATA%\\ChronoApp\\data.json)
- Alerte a la fermeture si des timers sont encore actifs
"""

import json
import os
import sys
import time
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

APP_NAME = "ChronoApp"
AUTOSAVE_MS = 15000
TICK_MS = 1000


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


def _sanitize_node(n: dict) -> None:
    n["running"] = False
    n.pop("started_at", None)
    n.setdefault("elapsed", 0.0)
    n.setdefault("estimate_min", 0)
    n.setdefault("pinned", False)


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for p in data.get("projects", []):
                for t in p.get("tasks", []):
                    _sanitize_node(t)
                    t.setdefault("subtasks", [])
                    for s in t["subtasks"]:
                        _sanitize_node(s)
            return data
        except Exception:
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
    """Format jours / heures / minutes (secondes visibles sous l'heure)."""
    seconds = int(max(0, seconds))
    j, r = divmod(seconds, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if j:
        return f"{j}j {h:02d}h {m:02d}m"
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def node_elapsed(node: dict) -> float:
    elapsed = node.get("elapsed", 0.0)
    if node.get("running") and node.get("started_at"):
        elapsed += time.time() - node["started_at"]
    return elapsed


def node_over(node: dict) -> bool:
    est = node.get("estimate_min", 0)
    return est > 0 and node_elapsed(node) > est * 60


# ------------------------- Boite de dialogue tache --------------------------

class TaskDialog(simpledialog.Dialog):
    """Demande le nom et le temps estime (en minutes)."""

    def __init__(self, parent, title, name="", estimate=60):
        self._name = name
        self._estimate = estimate
        self.result = None
        super().__init__(parent, title)

    UNITS = (("minutes", 1), ("heures", 60), ("jours", 1440))

    def _best_unit(self, est_min):
        if est_min > 0 and est_min % 1440 == 0:
            return est_min // 1440, "jours"
        if est_min > 0 and est_min % 60 == 0:
            return est_min // 60, "heures"
        return est_min, "minutes"

    def body(self, master):
        ttk.Label(master, text="Nom :").grid(row=0, column=0, sticky="w", pady=4)
        self.e_name = ttk.Entry(master, width=32)
        self.e_name.insert(0, self._name)
        self.e_name.grid(row=0, column=1, columnspan=2, pady=4, sticky="w")

        ttk.Label(master, text="Temps estime (0 = aucun) :").grid(row=1, column=0, sticky="w", pady=4)
        val, unit = self._best_unit(self._estimate)
        self.e_est = ttk.Spinbox(master, from_=0, to=100000, width=8)
        self.e_est.delete(0, "end")
        self.e_est.insert(0, str(val))
        self.e_est.grid(row=1, column=1, sticky="w", pady=4)
        self.e_unit = ttk.Combobox(master, state="readonly", width=9,
                                   values=[u[0] for u in self.UNITS])
        self.e_unit.set(unit)
        self.e_unit.grid(row=1, column=2, sticky="w", padx=(6, 0), pady=4)
        return self.e_name

    def validate(self):
        name = self.e_name.get().strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Le nom est obligatoire.", parent=self)
            return False
        try:
            val = float(self.e_est.get())
            if val < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(APP_NAME, "Le temps estime doit etre un nombre.", parent=self)
            return False
        factor = dict(self.UNITS)[self.e_unit.get()]
        self.result = (name, int(round(val * factor)))
        return True


# --------------------------------- Application ------------------------------

class ChronoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " - Suivi du temps")
        self.geometry("1000x580")
        self.minsize(860, 470)

        self.data = load_data()
        self.selected_project_id = None
        self.last_toggled_id = None

        self._build_ui()
        self._refresh_projects()
        self.after(TICK_MS, self._tick)
        self.after(AUTOSAVE_MS, self._autosave)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
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

        # --- Projets ---
        left = ttk.Frame(root)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="Projets", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.lb_projects = tk.Listbox(left, width=24, exportselection=False, activestyle="dotbox")
        self.lb_projects.pack(fill="y", expand=True, pady=4)
        self.lb_projects.bind("<<ListboxSelect>>", lambda e: self._on_project_select())
        pbtn = ttk.Frame(left)
        pbtn.pack(fill="x")
        ttk.Button(pbtn, text="+ Projet", command=self._add_project).pack(side="left", expand=True, fill="x")
        ttk.Button(pbtn, text="Suppr.", command=self._delete_project).pack(side="left", expand=True, fill="x")

        # --- Onglets ---
        self.nb = ttk.Notebook(root)
        self.nb.pack(side="left", fill="both", expand=True)

        # Onglet Taches (hierarchique)
        tab_tasks = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab_tasks, text="  Taches du projet  ")

        cols = ("estimate", "elapsed", "status")
        self.tree = ttk.Treeview(tab_tasks, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Tache / sous-tache")
        self.tree.heading("estimate", text="Estime")
        self.tree.heading("elapsed", text="Temps passe")
        self.tree.heading("status", text="Etat")
        self.tree.column("#0", width=340, anchor="w")
        self.tree.column("estimate", width=90, anchor="center")
        self.tree.column("elapsed", width=110, anchor="center")
        self.tree.column("status", width=170, anchor="center")
        self.tree.tag_configure("over", foreground="#c62828")
        self.tree.tag_configure("running", background="#e8f5e9")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._toggle_selected())

        tbtn = ttk.Frame(tab_tasks)
        tbtn.pack(fill="x", pady=(6, 0))
        ttk.Button(tbtn, text="Play / Pause  (ESPACE)", command=self._toggle_selected).pack(side="left")
        ttk.Button(tbtn, text="+ Tache", command=self._add_task).pack(side="left", padx=6)
        ttk.Button(tbtn, text="+ Sous-tache", command=self._add_subtask).pack(side="left")
        ttk.Button(tbtn, text="Epingler", command=self._pin_node).pack(side="left", padx=6)
        ttk.Button(tbtn, text="Monter", command=lambda: self._move_node(-1)).pack(side="left")
        ttk.Button(tbtn, text="Descendre", command=lambda: self._move_node(1)).pack(side="left", padx=6)
        ttk.Button(tbtn, text="Modifier", command=self._edit_node).pack(side="left")
        ttk.Button(tbtn, text="Remise a zero", command=self._reset_node).pack(side="left")
        ttk.Button(tbtn, text="Supprimer", command=self._delete_node).pack(side="left", padx=6)

        # Onglet Dashboard
        tab_dash = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab_dash, text="  Dashboard - actives  ")
        dcols = ("estimate", "elapsed", "status")
        self.dash = ttk.Treeview(tab_dash, columns=dcols, show="tree headings", selectmode="browse")
        self.dash.heading("#0", text="Projet / ligne active")
        self.dash.column("#0", width=340, anchor="w")
        for c, txt, w, a in (
            ("estimate", "Estime", 100, "center"),
            ("elapsed", "Temps passe", 120, "center"),
            ("status", "Etat", 160, "center"),
        ):
            self.dash.heading(c, text=txt)
            self.dash.column(c, width=w, anchor=a)
        self.dash.tag_configure("over", foreground="#c62828")
        self.dash.tag_configure("proj", foreground="#4aa3a0")
        self.dash.pack(fill="both", expand=True)
        self.dash.bind("<Double-1>", lambda e: self._toggle_from_dash())
        ttk.Label(tab_dash, text="Double-clic (ou ESPACE) pour mettre en pause / reprendre.").pack(anchor="w", pady=(6, 0))

        # Onglet Comparatif : passe vs estime
        tab_cmp = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab_cmp, text="  Comparatif  ")
        self.cmp = ttk.Treeview(tab_cmp, columns=("elapsed", "estimate", "delta"),
                                show="tree headings", selectmode="none")
        self.cmp.heading("#0", text="Projet / tache (sous-taches incluses)")
        self.cmp.column("#0", width=330, anchor="w")
        for c, txt in (("elapsed", "Temps passe"), ("estimate", "Estime"), ("delta", "Ecart")):
            self.cmp.heading(c, text=txt)
            self.cmp.column(c, width=115, anchor="center")
        self.cmp.tag_configure("over", foreground="#c62828")
        self.cmp.tag_configure("proj", foreground="#4aa3a0")
        self.cmp.pack(fill="both", expand=True)

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
        idx = ids.index(keep) if keep in ids else (0 if ids else None)
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
        if name and name.strip():
            p = {"id": uuid.uuid4().hex, "name": name.strip(), "tasks": []}
            self.data["projects"].append(p)
            self._refresh_projects(keep=p["id"])
            self._save()

    def _delete_project(self):
        p = self._current_project()
        if p and messagebox.askyesno(APP_NAME, f"Supprimer le projet <<{p['name']}>> et tout son contenu ?"):
            self.data["projects"].remove(p)
            self._refresh_projects()
            self._save()

    # ------------------------- Recherche de noeuds -------------------------

    def _find(self, nid):
        """Retourne (project, parent_task_or_None, node) pour un id donne."""
        for p in self.data["projects"]:
            for t in p["tasks"]:
                if t["id"] == nid:
                    return p, None, t
                for s in t.get("subtasks", []):
                    if s["id"] == nid:
                        return p, t, s
        return None, None, None

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None, None, None
        return self._find(sel[0])

    def _iter_nodes(self):
        for p in self.data["projects"]:
            for t in p["tasks"]:
                yield p, None, t
                for s in t.get("subtasks", []):
                    yield p, t, s

    # -------------------------- Affichage des taches -----------------------

    def _node_values(self, n):
        est = n.get("estimate_min", 0)
        est_txt = fmt_hms(est * 60) if est else "-"
        if n.get("running"):
            state = "En cours"
        elif n.get("elapsed", 0) > 0:
            state = "En pause"
        else:
            state = "A faire"
        if node_over(n):
            state += "  ! DEPASSE"
        return (est_txt, fmt_hms(node_elapsed(n)), state)

    def _node_tags(self, n):
        tags = []
        if node_over(n):
            tags.append("over")
        if n.get("running"):
            tags.append("running")
        return tuple(tags)

    def _refresh_tasks(self):
        opened = {i for i in self.tree.get_children() if self.tree.item(i, "open")}
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        p = self._current_project()
        if not p:
            return
        for t in p["tasks"]:
            t_txt = ("📌 " if t.get("pinned") else "") + t["name"]
            self.tree.insert("", "end", iid=t["id"], text=t_txt,
                             values=self._node_values(t), tags=self._node_tags(t),
                             open=(t["id"] in opened or True))
            for s in t.get("subtasks", []):
                s_txt = "   - " + ("📌 " if s.get("pinned") else "") + s["name"]
                self.tree.insert(t["id"], "end", iid=s["id"], text=s_txt,
                                 values=self._node_values(s), tags=self._node_tags(s))
        for iid in sel:
            if self.tree.exists(iid):
                self.tree.selection_set(iid)

    def _add_task(self):
        p = self._current_project()
        if not p:
            messagebox.showinfo(APP_NAME, "Cree d'abord un projet.")
            return
        dlg = TaskDialog(self, "Nouvelle tache")
        if dlg.result:
            name, est = dlg.result
            t = {"id": uuid.uuid4().hex, "name": name, "estimate_min": est,
                 "elapsed": 0.0, "running": False, "subtasks": []}
            p["tasks"].append(t)
            self._refresh_tasks()
            self.tree.selection_set(t["id"])
            self._save()

    def _add_subtask(self):
        _, parent, node = self._selected()
        # Si une sous-tache est selectionnee, on ajoute a sa tache parente
        task = node if (node and parent is None) else parent
        if not task:
            messagebox.showinfo(APP_NAME, "Selectionne une tache pour lui ajouter une sous-tache.")
            return
        dlg = TaskDialog(self, "Nouvelle sous-tache")
        if dlg.result:
            name, est = dlg.result
            s = {"id": uuid.uuid4().hex, "name": name, "estimate_min": est,
                 "elapsed": 0.0, "running": False}
            task.setdefault("subtasks", []).append(s)
            self._refresh_tasks()
            self.tree.selection_set(s["id"])
            self._save()

    def _pin_node(self):
        p, parent, n = self._selected()
        if not n:
            return
        n["pinned"] = not n.get("pinned")
        arr = parent["subtasks"] if parent else p["tasks"]
        if n["pinned"]:
            arr.remove(n)
            arr.insert(0, n)
        self._refresh_tasks()
        self.tree.selection_set(n["id"])
        self._save()

    def _move_node(self, d):
        p, parent, n = self._selected()
        if not n:
            return
        arr = parent["subtasks"] if parent else p["tasks"]
        i = arr.index(n)
        j = i + d
        if 0 <= j < len(arr):
            arr[i], arr[j] = arr[j], arr[i]
            self._refresh_tasks()
            self.tree.selection_set(n["id"])
            self._save()

    def _edit_node(self):
        _, _, n = self._selected()
        if not n:
            return
        dlg = TaskDialog(self, "Modifier", n["name"], n.get("estimate_min", 0))
        if dlg.result:
            n["name"], n["estimate_min"] = dlg.result
            self._refresh_tasks()
            self._refresh_dashboard()
            self._save()

    def _reset_node(self):
        _, _, n = self._selected()
        if n and messagebox.askyesno(APP_NAME, f"Remettre le compteur de <<{n['name']}>> a zero ?"):
            n["elapsed"] = 0.0
            n["running"] = False
            n.pop("started_at", None)
            self._refresh_tasks()
            self._refresh_dashboard()
            self._save()

    def _delete_node(self):
        p, parent, n = self._selected()
        if not n:
            return
        kind = "sous-tache" if parent else "tache"
        if messagebox.askyesno(APP_NAME, f"Supprimer la {kind} <<{n['name']}>> ?"):
            if parent:
                parent["subtasks"].remove(n)
            else:
                p["tasks"].remove(n)
            self._refresh_tasks()
            self._refresh_dashboard()
            self._save()

    # ------------------------------ Play / Pause ----------------------------

    def _toggle(self, node):
        if node.get("running"):
            node["elapsed"] = node_elapsed(node)
            node["running"] = False
            node.pop("started_at", None)
        else:
            node["running"] = True
            node["started_at"] = time.time()
        self.last_toggled_id = node["id"]
        self._refresh_tasks()
        self._refresh_dashboard()
        self._save()

    def _toggle_selected(self):
        _, _, n = self._selected()
        if n:
            self._toggle(n)
        elif self.last_toggled_id:
            _, _, n = self._find(self.last_toggled_id)
            if n:
                self._toggle(n)

    def _toggle_from_dash(self):
        sel = self.dash.selection()
        if sel:
            _, _, n = self._find(sel[0])
            if n:
                self._toggle(n)

    def _on_space(self, event):
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Spinbox, tk.Spinbox)):
            return
        if self.nb.index(self.nb.select()) == 1 and self.dash.selection():
            self._toggle_from_dash()
        else:
            self._toggle_selected()
        return "break"

    # ------------------------------- Dashboard ------------------------------

    def _item_label(self, parent, node):
        return f"{parent['name']} > {node['name']}" if parent else node["name"]

    def _refresh_dashboard(self):
        sel = self.dash.selection()
        self.dash.delete(*self.dash.get_children())
        # Regrouper les lignes actives par projet
        groups = []
        for p in self.data["projects"]:
            rows = [(parent, n) for pr, parent, n in self._iter_nodes()
                    if pr is p and n.get("running")]
            if rows:
                rows.sort(key=lambda x: (not node_over(x[1]), -node_elapsed(x[1])))
                n_over = sum(1 for _, n in rows if node_over(n))
                max_el = max(node_elapsed(n) for _, n in rows)
                groups.append((p, rows, n_over, max_el))
        # Projets avec depassement d'abord, puis plus longue activite
        groups.sort(key=lambda g: (g[2] == 0, -g[3]))
        for p, rows, n_over, _ in groups:
            label = f"{p['name']}  ({len(rows)} active(s)"
            label += f", {n_over} depassee(s))" if n_over else ")"
            pid = "proj_" + p["id"]
            self.dash.insert("", "end", iid=pid, text=label, open=True,
                             tags=("proj",) if not n_over else ("proj", "over"))
            for parent, n in rows:
                est, elapsed, state = self._node_values(n)
                self.dash.insert(pid, "end", iid=n["id"],
                                 text="   " + self._item_label(parent, n),
                                 values=(est, elapsed, state), tags=self._node_tags(n))
        for iid in sel:
            if self.dash.exists(iid):
                self.dash.selection_set(iid)

    # ------------------------------ Comparatif ------------------------------

    def _task_totals(self, t):
        el = node_elapsed(t)
        est = t.get("estimate_min", 0) * 60
        for st in t.get("subtasks", []):
            el += node_elapsed(st)
            est += st.get("estimate_min", 0) * 60
        return el, est

    def _fmt_delta(self, el, est):
        d = el - est
        return ("+" if d >= 0 else "-") + fmt_hms(abs(d))

    def _refresh_compare(self):
        self.cmp.delete(*self.cmp.get_children())
        projs = []
        for p in self.data["projects"]:
            el = est = 0
            for t in p["tasks"]:
                tel, test_ = self._task_totals(t)
                el += tel
                est += test_
            projs.append((p, el, est))
        projs.sort(key=lambda x: -(x[1] - x[2]))
        for p, el, est in projs:
            over = est > 0 and el > est
            pid = "cmp_" + p["id"]
            self.cmp.insert("", "end", iid=pid, text=p["name"], open=True,
                            values=(fmt_hms(el),
                                    fmt_hms(est) if est else "-",
                                    self._fmt_delta(el, est) if est else "-"),
                            tags=("proj", "over") if over else ("proj",))
            rows = [(t, *self._task_totals(t)) for t in p["tasks"]]
            rows.sort(key=lambda x: -(x[1] - x[2]))
            for t, tel, test_ in rows:
                t_over = test_ > 0 and tel > test_
                self.cmp.insert(pid, "end", iid="cmp_" + t["id"], text="   " + t["name"],
                                values=(fmt_hms(tel),
                                        fmt_hms(test_) if test_ else "-",
                                        self._fmt_delta(tel, test_) if test_ else "-"),
                                tags=("over",) if t_over else ())

    # ----------------------------- Boucle & fin -----------------------------

    def _tick(self):
        p = self._current_project()
        if p:
            for _, _, n in [(p, None, t) for t in p["tasks"]] + \
                           [(p, t, s) for t in p["tasks"] for s in t.get("subtasks", [])]:
                if self.tree.exists(n["id"]):
                    self.tree.item(n["id"], values=self._node_values(n), tags=self._node_tags(n))
        running = [(pr, par, n) for pr, par, n in self._iter_nodes() if n.get("running")]
        self._refresh_dashboard()
        self._refresh_compare()
        over = sum(1 for _, _, n in running if node_over(n))
        msg = f"{len(running)} ligne(s) active(s)"
        if over:
            msg += f"  -  ! {over} en depassement"
        msg += f"   |   Donnees : {DATA_FILE}"
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
        running = [n for _, _, n in self._iter_nodes() if n.get("running")]
        if running:
            names = ", ".join(n["name"] for n in running[:5])
            if len(running) > 5:
                names += ", ..."
            ok = messagebox.askyesno(
                APP_NAME,
                f"{len(running)} tache(s) sont encore actives :\n{names}\n\n"
                "Quitter quand meme ? Les timers seront mis en pause et sauvegardes.",
                icon="warning",
            )
            if not ok:
                return
        for _, _, n in self._iter_nodes():
            if n.get("running"):
                n["elapsed"] = node_elapsed(n)
                n["running"] = False
                n.pop("started_at", None)
        self._save()
        self.destroy()


if __name__ == "__main__":
    ChronoApp().mainloop()
