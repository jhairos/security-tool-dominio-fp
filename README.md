# Security Tool Jairo Suntaxi C — Dominio bloqueado FP

Herramienta de escritorio en Python para investigar un **dominio bloqueado
por una plataforma de seguridad DNS** y decidir, con evidencia, si el
bloqueo se sostiene o si puede tratarse de un falso positivo.

*English summary below.*

## Qué hace

Responde por separado dos preguntas que suelen mezclarse:

1. **¿El fallo es realmente un bloqueo de política?** Resuelve el dominio con
   `dig` contra el resolver donde se observó el bloqueo y contra resolvers
   públicos de referencia (8.8.8.8 y 1.1.1.1). Lee el estado (RCODE), las
   banderas y los *Extended DNS Errors* (EDE, RFC 8914) de cada respuesta y
   atribuye el fallo:

   | Atribución | Condición |
   | --- | --- |
   | `BLOQUEO_CONFIRMADO` | El resolver analizado devuelve un EDE de política (4, 15, 16, 17 o 18). |
   | `BLOQUEO_PROBABLE` | El resolver analizado falla y al menos una referencia resuelve. |
   | `NO_ATRIBUIBLE` | Las referencias también fallan (por ejemplo, SERVFAIL con EDE 22/23: delegación rota). |
   | `SIN_BLOQUEO` | El resolver analizado devuelve respuestas. |
   | `SIN_RESOLVER_ANALIZADO` | No se indicó el resolver donde se observó el bloqueo. |

2. **¿Las fuentes de reputación respaldan el bloqueo?** Abre y captura las
   páginas públicas de VirusTotal (dominio y relaciones), MXToolbox
   (Blacklist Check), Whois y Google Safe Browsing (Transparency Report).

El resultado es un paquete de evidencias: `index.html`, `gmail.html`,
`reporte_gmail.docx` y un ZIP con las capturas, más la salida de `dig` en
texto. El encabezado del reporte incluye la comparación DNS y su
interpretación. **La clasificación final la decide el analista.**

## Instalación (Windows)

1. Python 3.10 o superior, con tkinter.
2. WSL 2 con `dig`: `sudo apt install dnsutils`.
3. Ejecutar `instalar.bat` (instala dependencias y Chromium para Playwright).
4. Ejecutar `ejecutar.bat`.

En Linux: `pip install -r requirements.txt`, `python -m playwright install chromium`,
instalar `dnsutils` y ejecutar `python main.py`.

## Uso

- **Dominio a analizar** (obligatorio).
- **Resolver bajo análisis**: IP del DNS donde se observó el bloqueo. Sin él,
  la herramienta avisa que el bloqueo no se podrá atribuir.
- **Ticket** (opcional): referencia que se muestra en el reporte.

Sin interfaz gráfica:

```bash
python -m routines.dominio_fp.dominio_fp_runner --dominio ejemplo.com --resolver 192.0.2.53
```

## Pruebas

```bash
python -m unittest discover -s tests -v
```

18 pruebas: normalización y validación de entradas, lectura de `dig` en los
formatos de las versiones 9.11 (EDE en hexadecimal) y 9.18 (EDE
decodificado), atribución del bloqueo en todos sus estados, escape del texto
externo en el HTML y configuración del navegador.

## Uso responsable y límites

- Las fuentes se consultan **como lo haría un analista desde el navegador**:
  una consulta por fuente y por dominio, con el navegador en su configuración
  normal. La herramienta **no intenta superar verificaciones antimáquina**;
  si una fuente la muestra, la evidencia se marca como no obtenida. Por eso
  Cisco Talos no se incluye.
- Respete los términos de uso de cada proveedor. Para uso automatizado o de
  alto volumen, utilice sus API oficiales (por ejemplo, la API de VirusTotal).
- Las fuentes de reputación se contradicen con frecuencia y tardan en
  reflejar campañas nuevas. Una sola fuente no debe decidir el caso.
- El soporte de EDE depende del resolver. Sin EDE, un fallo solo en el
  resolver analizado se reporta como *probable*, no como confirmado.

## English summary

Desktop tool (Python, Tkinter, Playwright) for evidence-based triage of a
domain blocked by a DNS security platform. It compares `dig` answers from the
resolver under investigation and public reference resolvers, decodes
Extended DNS Errors (RFC 8914) to tell a policy block from a broken
delegation, captures public reputation pages (VirusTotal, MXToolbox, Whois,
Google Safe Browsing) and produces HTML/DOCX reports with an evidence ZIP.
It never bypasses anti-bot checks and leaves the final decision to the
analyst. Tests: `python -m unittest discover -s tests`.

## Autor

MSc. Medardo Jairo Suntaxi Cocanguilla, C|EH — Ecuador.
Trabajos relacionados: [mtr-geo](https://github.com/jhairos/mtr-geo) y el
white paper *Reducing False Positives in Heuristic DNS Tunneling Detection*
(DOI [10.5281/zenodo.23223210](https://doi.org/10.5281/zenodo.23223210)).

## Licencia

MIT — ver [LICENSE](LICENSE).
