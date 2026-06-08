import os
import tkinter as tk
from tkinterdnd2 import DND_FILES, COPY

class FileDragWidget(tk.Frame):

    def __init__(self, parent, path="", **kwargs):
        kwargs.setdefault("bg", "#313130")
        super().__init__(parent, **kwargs,
                         highlightthickness=1,
                         highlightbackground="#c8982a",
                         cursor="fleur")
        self._path = path
        self._build()

    def _build(self):
        tk.Label(self, text="CSV", font=("Segoe UI", 9),
                 bg=self["bg"], fg="#c8982a").pack(side="left", padx=(8, 0), pady=6)
        self._name_lbl = tk.Label(self,
                                   text=os.path.basename(self._path) if self._path else "—",
                                   font=("Consolas", 8),
                                   bg=self["bg"], fg="#e8e8e8")
        self._name_lbl.pack(side="left", padx=(4, 10), pady=6)

        # Register this frame and its children as drag sources
        for widget in (self, self._name_lbl):
            widget.drag_source_register(DND_FILES)
            widget.dnd_bind("<<DragInitCmd>>", self._on_drag_init)

    def set_path(self, path):
        self._path = path
        self._name_lbl.config(text=os.path.basename(path))

    def _on_drag_init(self, event):
        # tkdnd on Windows requires Tcl list syntax — wrap paths with spaces in braces
        p = self._path.replace('\\', '/')
        data = '{' + p + '}' if ' ' in p else p
        return (COPY, DND_FILES, data)
