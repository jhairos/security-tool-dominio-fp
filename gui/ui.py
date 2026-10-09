"""
gui/ui.py
=========
Capa de compatibilidad de interfaz grafica. Usa CustomTkinter si esta
instalado; de lo contrario cae automaticamente a tkinter/ttk.

Expone fabricas de widgets con una API minima y comun (frame, label,
button, entry, textbox, progressbar, checkbox, option_menu), de modo que
el resto de la GUI no dependa del framework subyacente.

Adaptado de la capa equivalente de NETWORK_CONFIG_ANALYZER.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

try:
    import customtkinter as ctk  # type: ignore
    USE_CTK = True
except Exception:  # noqa: BLE001
    ctk = None  # type: ignore
    USE_CTK = False


# --- Paleta ----------------------------------------------------------
COLORS = {
    "primary": "#1f6aa5",
    "primary_dark": "#144870",
    "sidebar": "#1a1a2e",
    "card": "#16213e",
    "accent": "#0f9d58",
    "danger": "#c0392b",
    "warning": "#e67e22",
    "info": "#2980b9",
    "muted": "#5a5a6e",
    "text_light": "#e6e6e6",
    "bg_dark": "#1e1e2e",
}

# --- Colores por estado uniforme de rutina ---------------------------
STATUS_COLORS = {
    "LISTO": COLORS["info"],
    "EJECUTANDO": COLORS["primary"],
    "OK": COLORS["accent"],
    "ADVERTENCIA": COLORS["warning"],
    "ERROR": COLORS["danger"],
}


def status_color(status: str) -> str:
    return STATUS_COLORS.get(str(status).upper(), COLORS["muted"])


# --- Ventana raiz -----------------------------------------------------
def ajustar_a_pantalla(root, ancho_max: int = 1500, alto_max: int = 950,
                       proporcion: float = 0.92) -> str:
    """
    Calcula una geometria que quepa en el monitor y centra la ventana.

    Una geometria fija se salia de las pantallas pequenas y obligaba a
    agrandar la ventana para ver los botones de resultado.
    """
    try:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
    except Exception:  # noqa: BLE001
        sw, sh = 1366, 768

    ancho = max(900, min(ancho_max, int(sw * proporcion)))
    alto = max(620, min(alto_max, int(sh * proporcion)))
    x = max(0, (sw - ancho) // 2)
    y = max(0, (sh - alto) // 3)
    return f"{ancho}x{alto}+{x}+{y}"


def create_root(title: str, geometry: str = "",
                theme: str = "dark",
                min_size: tuple[int, int] = (960, 600)) -> Any:
    """Crea la ventana raiz (CTk o Tk), ajustada al monitor."""
    if USE_CTK:
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        _configure_input_styles(root, theme)
    else:
        root = tk.Tk()
        _apply_ttk_theme(root, theme)
    root.title(title)
    root.geometry(geometry or ajustar_a_pantalla(root))
    root.minsize(*min_size)

    # En pantallas pequenas conviene arrancar maximizado.
    try:
        if root.winfo_screenheight() <= 800:
            root.state("zoomed")
    except Exception:  # noqa: BLE001
        pass
    return root


def _configure_input_styles(root: tk.Misc, theme: str) -> None:
    """
    Fuerza colores legibles en Entry/Combobox/Checkbutton (campos con
    fondo claro y texto oscuro). Evita el caso 'texto claro sobre fondo
    claro' que hace invisible lo que se escribe.
    """
    style = ttk.Style(root)
    dark = theme == "dark"
    field_bg = "#ffffff"
    field_fg = "#111111"
    style.configure("TEntry", fieldbackground=field_bg, foreground=field_fg,
                    insertcolor=field_fg)
    style.map("TEntry", foreground=[("disabled", "#888888")],
              fieldbackground=[("disabled", "#e0e0e0")])
    style.configure("TCombobox", fieldbackground=field_bg,
                    foreground=field_fg, arrowcolor="#111111",
                    selectbackground=field_bg, selectforeground=field_fg)
    style.map("TCombobox",
              fieldbackground=[("readonly", field_bg),
                               ("disabled", "#e0e0e0")],
              foreground=[("readonly", field_fg), ("disabled", "#888888")],
              selectbackground=[("readonly", field_bg)],
              selectforeground=[("readonly", field_fg)])
    try:
        root.option_add("*TCombobox*Listbox.background", field_bg)
        root.option_add("*TCombobox*Listbox.foreground", field_fg)
        root.option_add("*TCombobox*Listbox.selectBackground",
                        COLORS["primary"])
        root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    except tk.TclError:
        pass

    lbl_fg = "#e6e6e6" if dark else "#1a1a1a"
    frame_bg = COLORS["bg_dark"] if dark else "#f4f4f4"
    style.configure("TLabel", foreground=lbl_fg, background=frame_bg)
    style.configure("TFrame", background=frame_bg)
    style.configure("TCheckbutton", foreground=lbl_fg, background=frame_bg)
    style.map("TCheckbutton", foreground=[("active", lbl_fg)],
              background=[("active", frame_bg)])


def _apply_ttk_theme(root: tk.Tk, theme: str) -> None:
    """Configura un estilo ttk profesional para el modo fallback."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    dark = theme == "dark"
    bg = COLORS["bg_dark"] if dark else "#f4f4f4"
    fg = "#e6e6e6" if dark else "#1a1a1a"
    root.configure(bg=bg)
    style.configure(".", background=bg, foreground=fg)
    style.configure("Treeview",
                    background="#252537" if dark else "#ffffff",
                    foreground=fg,
                    fieldbackground="#252537" if dark else "#ffffff",
                    rowheight=24)
    style.configure("Treeview.Heading", background=COLORS["primary"],
                    foreground="#ffffff", font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[("selected", COLORS["primary"])])
    style.configure("TButton", padding=6)
    style.configure("TNotebook.Tab", padding=(12, 6))
    _configure_input_styles(root, theme)


def set_theme(theme: str, root: Optional[Any] = None) -> None:
    if USE_CTK:
        ctk.set_appearance_mode(theme)
    elif root is not None:
        _apply_ttk_theme(root, theme)


# --- Fabricas de widgets ---------------------------------------------
def frame(master: Any, **kw) -> Any:
    if USE_CTK:
        allowed = {k: v for k, v in kw.items()
                   if k in ("fg_color", "corner_radius", "width", "height",
                            "border_width", "border_color")}
        return ctk.CTkFrame(master, **allowed)
    for key in ("corner_radius", "fg_color", "border_color", "border_width"):
        kw.pop(key, None)
    return ttk.Frame(master, **{k: v for k, v in kw.items()
                                if k in ("width", "height", "padding")})


def label(master: Any, text: str = "", font: Optional[tuple] = None,
          **kw) -> Any:
    if USE_CTK:
        ctk_kw = {}
        if font:
            ctk_kw["font"] = ctk.CTkFont(
                family=font[0], size=font[1],
                weight="bold" if len(font) > 2 else "normal")
        for k in ("text_color", "anchor", "justify", "wraplength"):
            if k in kw:
                ctk_kw[k] = kw[k]
        return ctk.CTkLabel(master, text=text, **ctk_kw)
    tk_kw = {}
    if font:
        tk_kw["font"] = font
    for k in ("anchor", "justify", "wraplength", "foreground"):
        if k in kw:
            tk_kw[k] = kw[k]
    if "text_color" in kw and "foreground" not in tk_kw:
        tk_kw["foreground"] = kw["text_color"]
    return ttk.Label(master, text=text, **tk_kw)


def button(master: Any, text: str, command: Callable, **kw) -> Any:
    if USE_CTK:
        ctk_kw = {}
        for k in ("fg_color", "hover_color", "width", "height", "text_color"):
            if k in kw:
                ctk_kw[k] = kw[k]
        return ctk.CTkButton(master, text=text, command=command, **ctk_kw)
    return ttk.Button(master, text=text, command=command,
                      width=kw.get("width_chars", 0) or None)


def entry(master: Any, placeholder: str = "",
          textvariable: Optional[tk.Variable] = None,
          show: Optional[str] = None, **kw) -> Any:
    """Campo de texto. ``show='*'`` para contrasenas."""
    if USE_CTK:
        ctk_kw: dict = {"placeholder_text": placeholder,
                        "width": kw.get("width", 240)}
        if textvariable is not None:
            ctk_kw["textvariable"] = textvariable
        if show:
            ctk_kw["show"] = show
        return ctk.CTkEntry(master, **ctk_kw)
    tk_kw: dict = {"width": kw.get("width_chars", 34)}
    if textvariable is not None:
        tk_kw["textvariable"] = textvariable
    if show:
        tk_kw["show"] = show
    return ttk.Entry(master, **tk_kw)


def textbox(master: Any, **kw) -> tk.Text:
    """Area de texto (siempre tk.Text para compatibilidad)."""
    return tk.Text(master, wrap=kw.get("wrap", "word"), undo=True,
                   font=("Consolas", 10), bg="#1e1e2e", fg="#e6e6e6",
                   insertbackground="#e6e6e6", relief="flat",
                   height=kw.get("height", 10))


def scrolled_textbox(master: Any, height: int = 12) -> tk.Text:
    """Area de texto con barra de desplazamiento vertical."""
    container = tk.Frame(master, bg=COLORS["bg_dark"], highlightthickness=0)
    container.pack(fill="both", expand=True)
    txt = textbox(container, height=height)
    scroll = ttk.Scrollbar(container, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)
    return txt


def progressbar(master: Any) -> Any:
    if USE_CTK:
        pb = ctk.CTkProgressBar(master)
        pb.set(0)
        return pb
    return ttk.Progressbar(master, mode="determinate", maximum=100)


def set_progress(pb: Any, fraction: float) -> None:
    fraction = max(0.0, min(1.0, fraction))
    if USE_CTK:
        pb.set(fraction)
    else:
        pb["value"] = fraction * 100


def option_menu(master: Any, values: list, variable: tk.StringVar) -> Any:
    if USE_CTK:
        return ctk.CTkOptionMenu(master, values=values, variable=variable)
    return ttk.Combobox(master, values=values, textvariable=variable,
                        state="readonly", width=18)


def checkbox(master: Any, text: str, variable: tk.IntVar,
             command: Optional[Callable] = None) -> Any:
    if USE_CTK:
        return ctk.CTkCheckBox(master, text=text, variable=variable,
                               command=command)
    return ttk.Checkbutton(master, text=text, variable=variable,
                           command=command)


def section_title(master: Any, text: str) -> Any:
    return label(master, text, font=("Segoe UI", 18, "bold"))


def badge(master: Any, text: str, color: str) -> tk.Label:
    """Etiqueta de estado con color de fondo."""
    return tk.Label(master, text=f" {text} ", bg=color, fg="#ffffff",
                    font=("Segoe UI", 10, "bold"), padx=8, pady=2)
