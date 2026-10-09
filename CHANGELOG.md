# Historial de versiones

## 3.0.0 — 2026-10-09

- **Resolver bajo análisis.** Nuevo campo en la interfaz y parámetro
  `--resolver` en la línea de comandos. `dig` se ejecuta contra ese resolver
  y contra las referencias 8.8.8.8 y 1.1.1.1. En la 2.3.3 solo se consultaban
  resolvers públicos, de modo que no se podía comprobar si existía un bloqueo.
- **Interpretación DNS** (`dominio_fp_dns.py`). Lee RCODE, banderas y
  Extended DNS Errors en los formatos de dig 9.11 (hexadecimal, `OPT=15`) y
  dig 9.18 (`EDE:`), y atribuye el fallo: confirmado, probable, no atribuible,
  sin bloqueo o sin resolver analizado. El resultado encabeza el reporte.
- La salida de `dig` se guarda también en texto, junto a su imagen.
- **Navegador en configuración normal.** Se eliminan los argumentos para
  ocultar la automatización, el perfil persistente que conservaba la cookie de
  verificación, la espera y recarga ante verificaciones antimáquina, el canal
  de Chrome instalado, `--no-sandbox` y la omisión de errores de certificado.
  Una verificación antimáquina se registra como evidencia no obtenida.
- El texto externo (respuestas DNS) se escapa antes de insertarlo en el HTML.
- Se retiran el almacenamiento de credenciales, el inicio de sesión web, la
  carga de `.env` y la dependencia `keyring`: el análisis no usa credenciales.
- Se eliminan las referencias al marco de automatización del que provenía el
  módulo y los registros vacíos.
- 18 pruebas automatizadas (`tests/`), README, licencia MIT y CITATION.cff.

## 2.3.3 (v2) — 2026-10-09

- El análisis de dominio se separa como herramienta independiente con su
  propia ventana. Ticket opcional sin valor precargado; DNS solo públicos.

## 2.2.0 – 2.3.3 — versiones previas

Primeras versiones del análisis, dentro de un marco privado de automatización
del autor:

- Consulta y captura de VirusTotal (dominio y relaciones), MXToolbox, Whois y
  Google Safe Browsing; salida de `dig` compuesta como imagen.
- MXToolbox: la consulta se escribe en el buscador y se comprueba antes de
  lanzarla, porque el texto anterior corrompía la búsqueda.
- Captura con tres alternativas (página completa, protocolo del navegador y
  parte visible) cuando VirusTotal agotaba el tiempo cargando tipografías.
- Cisco Talos se retiró por exigir verificación antimáquina.
- Encabezado del reporte y referencia de ticket opcional.
