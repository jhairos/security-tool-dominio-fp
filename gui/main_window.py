"""Ventana exclusiva del analizador de dominios."""
import tkinter as tk
from config import APP_NAME,APP_VERSION,DEFAULT_THEME,WINDOW_GEOMETRY,WINDOW_MIN_SIZE
from gui import ui
from gui.dominio_fp_view import DominioFPView
from services.dominio_fp_service import DominioFPService

class MainWindow:
    def __init__(self,theme=DEFAULT_THEME):
        self.root=ui.create_root(f"{APP_NAME} v{APP_VERSION}",geometry=WINDOW_GEOMETRY,theme=theme,min_size=WINDOW_MIN_SIZE)
        bar=tk.Frame(self.root,bg=ui.COLORS["primary_dark"],height=52)
        bar.pack(fill="x")
        tk.Label(bar,text=APP_NAME,bg=ui.COLORS["primary_dark"],fg="white",font=("Segoe UI",16,"bold")).pack(side="left",padx=16,pady=10)
        self.content=tk.Frame(self.root,bg=ui.COLORS["bg_dark"])
        self.content.pack(fill="both",expand=True)
        self.statusbar=tk.Label(self.root,text="Estado: Listo",anchor="w",bg=ui.COLORS["primary_dark"],fg="white")
        self.statusbar.pack(side="bottom",fill="x")
        self.service=DominioFPService()
        self.current_view=DominioFPView(self.content,self)
    def get_service(self,routine_code):
        if routine_code.upper()!="DOMINIO_FP":
            raise KeyError(routine_code)
        return self.service
    def set_status(self,text):
        self.statusbar.configure(text=f"Estado: {text}")
    def run(self):
        self.root.mainloop()
