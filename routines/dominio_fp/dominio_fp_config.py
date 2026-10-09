"""
routines/dominio_fp/dominio_fp_config.py
========================================
Configuracion del analisis de dominio bloqueado (posible falso positivo).

El analisis recibe el dominio y, opcionalmente, el resolver DNS donde se
observo el bloqueo. Combina dos tipos de evidencia:

1. Capturas de fuentes publicas de reputacion, abiertas como lo haria un
   analista desde el navegador.
2. Resolucion con ``dig`` contra el resolver bajo analisis y contra
   resolvers publicos de referencia. En Windows se ejecuta a traves de
   WSL 2 y la salida se compone como imagen.

No se requieren credenciales.
"""
from __future__ import annotations

import ipaddress
import re

# --- Identificacion de la rutina --------------------------------------
ROUTINE_CODE = "DOMINIO_FP"
ROUTINE_NAME = "DOMINIO BLOQUEADO FP"
ROUTINE_DESC = ("Analisis de posible falso positivo de dominio "
                "bloqueado: reputacion en VirusTotal, MXToolbox, Whois "
                "y Google Safe Browsing, mas la comparacion de la "
                "resolucion DNS entre el resolver bajo analisis y "
                "resolvers publicos de referencia.")

#: Esta rutina no usa credenciales: todas las fuentes son publicas.
REQUIERE_CREDENCIALES = False

# --- Parametro de entrada ---------------------------------------------
#: Dominio sugerido al abrir la pantalla (solo un ejemplo).
DOMINIO_EJEMPLO = "ejemplo.com"

#: Validacion del dominio ingresado.
DOMINIO_REGEX = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-_]{1,63}"
    r"(\.[A-Za-z0-9-_]{1,63})+\.?$")


def normalizar_dominio(dominio: str) -> str:
    """Limpia el dominio: sin espacios, sin esquema y sin punto final."""
    valor = (dominio or "").strip().lower()
    valor = re.sub(r"^[a-z]+://", "", valor)   # quita http:// o https://
    valor = valor.split("/")[0]                # quita la ruta
    return valor.rstrip(".")


def dominio_valido(dominio: str) -> bool:
    return bool(DOMINIO_REGEX.match(normalizar_dominio(dominio)))


# --- Resolucion desde la linea de comandos ----------------------------
#: Resolvers publicos de REFERENCIA. Si el dominio resuelve en ellos pero
#: no en el resolver bajo analisis, el bloqueo es local a ese resolver.
DNS_REFERENCIA = ["8.8.8.8", "1.1.1.1"]


def resolver_valido(valor: str) -> bool:
    """Acepta una direccion IPv4 o IPv6 (sin puerto)."""
    try:
        ipaddress.ip_address((valor or "").strip())
        return True
    except ValueError:
        return False


#: En Windows el comando se ejecuta dentro de WSL 2.
USAR_WSL = True
WSL_COMANDO = ["wsl.exe", "--"]
DIG_TIMEOUT_S = 45

#: Comandos a ejecutar. ``{dns}`` y ``{dominio}`` se sustituyen.
COMANDOS_CLI = [
    {
        "key": "dig_{indice}",
        "title": "CLI dig — {rol} {dns}",
        "comando": "dig @{dns} {dominio}",
    },
]

# --- Composicion de la salida como imagen -----------------------------
# La evidencia de consola se compone como imagen con aspecto de terminal
# para incorporarla al reporte junto a las capturas web.
CLI_IMG_ANCHO = 1100
CLI_IMG_MARGEN = 18
CLI_IMG_FONDO = (24, 24, 32)
CLI_IMG_TEXTO = (222, 222, 230)
CLI_IMG_TITULO = (120, 200, 255)
CLI_IMG_FUENTE_PX = 15
CLI_IMG_INTERLINEA = 6
CLI_MAX_LINEAS = 60

# --- Navegador --------------------------------------------------------
# Se usa el Chromium de Playwright con su configuracion normal: sandbox
# activo, validacion de certificados y sin tecnicas para ocultar la
# automatizacion. Si una fuente muestra una verificacion antimaquina, la
# evidencia se marca como no obtenida y se consulta manualmente.
IGNORE_HTTPS_ERRORS = False
HEADLESS = True
VIEWPORT = {"width": 1600, "height": 1000}

# --- Tiempos de espera ------------------------------------------------
GOTO_TIMEOUT_MS = 60000
CLICK_TIMEOUT_MS = 12000
NETWORK_IDLE_TIMEOUT_MS = 8000
WAIT_AFTER_NAV_S = 7.0
DELAY_BETWEEN_PAGES_S = 1.5

WAIT_FOR_CONTENT = True
LOADING_TEXTS = ["loading", "cargando", "please wait", "analyzing"]

# Textos de una verificacion antimaquina. Si aparecen, la captura NO es
# evidencia valida y se marca como no obtenida; la herramienta no intenta
# superar la verificacion.
CHALLENGE_TEXTS = [
    "performing security verification",
    "verifying you are human",
    "checking your browser",
    "just a moment",
    "verificacion de seguridad",
    "verificación de seguridad",
    "needs to review the security of your connection",
]

# --- Consultas por formulario ------------------------------------------
#: Espera a que aparezca el resultado tras lanzar la consulta.
FORMULARIO_TIMEOUT_MS = 40000
FORMULARIO_ESPERA_S = 6.0

#: Avisos con los que la herramienta indica que la consulta llego mal
#: escrita. Ocurria cuando el buscador conservaba texto anterior y el
#: tecleado se mezclaba ("mx:bcklist:dominio").
CONSULTA_RECHAZADA = [
    "An error has occurred with your lookup",
    "too many arguments",
    "we couldn't find any name servers",
]

#: Respuestas que impiden navegar: el servidor devuelve una descarga o
#: cancela la navegacion. Ocurria con la consulta directa de MXToolbox.
NAVEGACION_CANCELADA = [
    "ERR_ABORTED",
    "Download is starting",
    "net::ERR_FAILED",
]
CONTENT_RETRIES = 4
CONTENT_RETRY_WAIT_S = 5.0
SETTLE_AFTER_CONTENT_S = 2.0
MIN_CONTENT_CHARS = 60

LOADING_SELECTORS = [
    'div.spinner', 'div[class*="spinner" i]', 'div[class*="loading" i]',
    'div.loader', '[aria-busy="true"]',
]
LOADING_WAIT_TIMEOUT_MS = 12000

# --- Avisos de cookies y consentimiento -------------------------------
# Las paginas publicas muestran banners de cookies que tapan el informe.
MODAL_ATTEMPTS = 3
MODAL_RETRY_WAIT_S = 1.2
MODAL_WAIT_S = 0.7
MODAL_TRY_ESCAPE = True

MODAL_SELECTORS = [
    'button:has-text("Accept all")', 'button:has-text("Accept All")',
    'button:has-text("Aceptar todo")', 'button:has-text("Aceptar")',
    'button:has-text("Accept")', 'button:has-text("I agree")',
    'button:has-text("Got it")', 'button:has-text("Entendido")',
    'button:has-text("Continue")', 'button:has-text("Close")',
    'button[aria-label*="accept" i]', 'button[aria-label*="close" i]',
    'button#onetrust-accept-btn-handler',
    '#onetrust-accept-btn-handler',
    'button.fc-cta-consent', 'div[role="dialog"] button',
]

MODAL_PRESENT_SELECTORS = [
    'div[role="dialog"]', '#onetrust-banner-sdk', 'div.fc-consent-root',
    'div[class*="cookie" i]', 'div[class*="consent" i]',
]

# --- Captura ----------------------------------------------------------
CAPTURE_PANEL_ONLY = False
FULL_PAGE = True

# VirusTotal carga tipografias remotas y la captura de pagina completa
# agotaba el tiempo "waiting for fonts to load". Se concede mas margen
# y, si aun asi falla, se recurre a capturar solo la parte visible: una
# evidencia parcial es preferible a ninguna.
SCREENSHOT_TIMEOUT_MS = 90000
SCREENSHOT_REINTENTO_VIEWPORT = True
FALLBACK_FULL_PAGE = True
MIN_PANEL_WIDTH = 400
MIN_PANEL_HEIGHT = 250
MIN_PANEL_WIDTH_EXPLICIT = 200
MIN_PANEL_HEIGHT_EXPLICIT = 80
PANEL_SELECTORS = ['main', 'div[role="main"]', 'div#content', 'div.content']

# --- Fuentes publicas de validacion -----------------------------------
# key, titulo y plantilla de direccion. {dominio} se sustituye.
FUENTES = [
    {
        "key": "01_virustotal",
        "title": "VirusTotal — Dominio",
        "url": "https://www.virustotal.com/gui/domain/{dominio}",
        "wait_s": 12.0,
        "content_retries": 6,
    },
    {
        "key": "02_virustotal_rel",
        "title": "VirusTotal — Relations",
        "url": "https://www.virustotal.com/gui/domain/{dominio}/relations",
        "wait_s": 12.0,
        "content_retries": 6,
    },
    # Cisco Talos (talosintelligence.com/reputation_center) no se incluye:
    # exige una verificacion antimaquina. Se consulta manualmente.
    {
        # MXToolbox no ejecuta la consulta al cambiar el fragmento: hay
        # que escribir el dominio en el buscador y lanzar la
        # comprobacion. El prefijo "blacklist:" selecciona por si solo
        # la opcion "Blacklist Check" del boton.
        "key": "04_mxtoolbox",
        "title": "MXToolbox — Blacklist Check",
        "url": "https://mxtoolbox.com/SuperTool.aspx",
        "formulario": {
            "campo": [
                'input#tbSuperToolInput',
                'input[placeholder*="Lookup" i]',
                'input[type="text"]',
            ],
            "valor": "blacklist:{dominio}",
            "boton": [
                'a#tbSuperToolSearch',
                'button:has-text("Blacklist Check")',
                'input[value*="Blacklist" i]',
                'button[type="submit"]', 'input[type="submit"]',
            ],
            "resultado": [
                'table:has-text("Blacklist")',
                'div[id*="Results" i]',
            ],
        },
        "referencia_hash": "#blacklist:{dominio}",
        "wait_s": 12.0,
        "content_retries": 8,
    },
    {
        "key": "05_whois",
        "title": "Whois — Registro del dominio",
        "url": "https://www.whois.com/whois/{dominio}",
        "wait_s": 8.0,
    },
    {
        "key": "06_google_sb",
        "title": "Google Safe Browsing — Transparency Report",
        "url": ("https://transparencyreport.google.com/safe-browsing/"
                "search?url={dominio}"),
        "wait_s": 12.0,
        "content_retries": 6,
    },
]


def build_pages(dominio: str) -> list[dict]:
    """Construye las direcciones a consultar para el dominio indicado."""
    limpio = normalizar_dominio(dominio)
    paginas = []
    for fuente in FUENTES:
        item = dict(fuente)
        item["url"] = fuente["url"].format(dominio=limpio)
        item["title"] = fuente["title"].format(dominio=limpio)
        # Formulario: el dominio se escribe en el buscador de la fuente.
        if fuente.get("formulario"):
            formulario = dict(fuente["formulario"])
            formulario["valor"] = formulario["valor"].format(dominio=limpio)
            item["formulario"] = formulario

        if fuente.get("consulta_hash"):
            item["consulta_hash"] = fuente["consulta_hash"].format(
                dominio=limpio)
            item["referencia"] = item["url"] + item["consulta_hash"]
        elif fuente.get("referencia_hash"):
            # La consulta se lanza desde el formulario, pero el reporte
            # muestra la direccion equivalente para poder repetirla.
            item["referencia"] = item["url"] + fuente[
                "referencia_hash"].format(dominio=limpio)
        else:
            item["referencia"] = item["url"]
        paginas.append(item)
    return paginas


def build_comandos(dominio: str, resolver: str = "") -> list[dict]:
    """
    Construye los comandos de consola: uno por servidor DNS.

    Primero el resolver bajo analisis (si se indico) y despues los
    resolvers de referencia. Cada uno se consulta por separado para
    comparar las respuestas.
    """
    limpio = normalizar_dominio(dominio)
    servidores = []
    resolver = (resolver or "").strip()
    if resolver:
        servidores.append((resolver, "analizado", "resolver bajo analisis"))
    for ref in DNS_REFERENCIA:
        if ref != resolver:
            servidores.append((ref, "referencia", "referencia"))

    comandos = []
    for indice, (servidor, rol, rol_texto) in enumerate(servidores, start=1):
        for base in COMANDOS_CLI:
            item = dict(base)
            item["key"] = base["key"].format(indice=indice)
            item["comando"] = base["comando"].format(dns=servidor,
                                                     dominio=limpio)
            item["title"] = base["title"].format(dns=servidor, rol=rol_texto,
                                                 dominio=limpio)
            item["dns"] = servidor
            item["rol"] = rol
            comandos.append(item)
    return comandos


def fuente_titulos() -> list[str]:
    return [f["title"] for f in FUENTES]


# --- Encabezado del reporte -------------------------------------------
INTRO_PLANTILLA = (
    "Se presenta el reporte de validación de reputación y nivel de "
    "confianza del dominio {dominio}, mediante consultas a fuentes "
    "abiertas (OSINT), para determinar posibles riesgos de seguridad "
    "y recomendar mantener el bloqueo o su inclusión en lista blanca."
)
INTRO_TICKET = "Ticket: {ticket}"
TICKET_EJEMPLO = ""


def build_intro(dominio: str, ticket: str = "") -> str:
    """Genera la introducción del informe y agrega ticket si se ingresa."""
    texto = INTRO_PLANTILLA.format(dominio=normalizar_dominio(dominio))
    if (ticket or "").strip():
        texto += "\n\n" + INTRO_TICKET.format(ticket=ticket.strip())
    return texto


# --- Reportes ---------------------------------------------------------
REPORT_TITLE = "Security Tool Jairo Suntaxi C — Investigación de dominios"
PLATFORM_LABEL = "DOMINIO BLOQUEADO FP"
FOOTER_AUTHOR = "Jairo Suntaxi C ©"
DOCX_IMAGE_WIDTH_INCHES = 6.6
FILE_ZIP_PREFIX = "evidencias_DOMINIO_FP_"
