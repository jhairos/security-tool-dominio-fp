"""
Pruebas del analisis de dominio bloqueado.

    python -m unittest discover -s tests -v

No requieren red, navegador ni dig: las salidas de dig usadas aqui son
textos con el mismo formato que produce dig 9.11 y dig 9.18.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from routines.dominio_fp import dominio_fp_config as cfg  # noqa: E402
from routines.dominio_fp import dominio_fp_dns as dnsx  # noqa: E402
from utils import report_builder  # noqa: E402


def _hex(codigo: int, texto: str) -> str:
    datos = codigo.to_bytes(2, "big") + texto.encode()
    return " ".join(f"{b:02x}" for b in datos)


# Respuesta de dig 9.11: EDE en hexadecimal (OPT=15). Direcciones de
# documentacion (RFC 5737).
DIG_SERVFAIL_911 = f""";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 29113
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1
;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 512
; OPT=15: {_hex(23, "[203.0.113.155] rcode=REFUSED for example.test A")}
; OPT=15: {_hex(22, "At delegation example.test for example.test A")}
"""

# dig 9.18: EDE ya decodificado.
DIG_BLOCKED_918 = """;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 1
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1
; EDE: 15 (Blocked): (domain on threat feed)
"""

DIG_REFUSED_AA = """;; ->>HEADER<<- opcode: QUERY, status: REFUSED, id: 35352
;; flags: qr aa rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1
"""

DIG_OK = """;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 7
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1
example.test.  300 IN A 203.0.113.10
"""


class TestEntrada(unittest.TestCase):
    def test_normalizacion(self):
        self.assertEqual(cfg.normalizar_dominio(" HTTPS://Ejemplo.COM/x "), "ejemplo.com")
        self.assertEqual(cfg.normalizar_dominio("ejemplo.com."), "ejemplo.com")

    def test_validacion_dominio(self):
        self.assertTrue(cfg.dominio_valido("sub.ejemplo.co.uk"))
        for malo in ("", "sinpunto", "espacios en medio.com"):
            self.assertFalse(cfg.dominio_valido(malo), malo)

    def test_validacion_resolver(self):
        self.assertTrue(cfg.resolver_valido("192.0.2.53"))
        self.assertTrue(cfg.resolver_valido("2001:db8::53"))
        for malo in ("", "dns.ejemplo.com", "192.0.2.53:53", "1.2.3"):
            self.assertFalse(cfg.resolver_valido(malo), malo)

    def test_comandos_con_resolver(self):
        cmds = cfg.build_comandos("ejemplo.com", "192.0.2.53")
        self.assertEqual([c["rol"] for c in cmds], ["analizado", "referencia", "referencia"])
        self.assertEqual(cmds[0]["comando"], "dig @192.0.2.53 ejemplo.com")

    def test_comandos_sin_resolver(self):
        cmds = cfg.build_comandos("ejemplo.com")
        self.assertEqual({c["dns"] for c in cmds}, set(cfg.DNS_REFERENCIA))


class TestLecturaDig(unittest.TestCase):
    def test_ede_hexadecimal(self):
        r = dnsx.leer_dig(DIG_SERVFAIL_911, "198.51.100.1", "referencia")
        self.assertEqual(r.estado, "SERVFAIL")
        self.assertEqual([e.codigo for e in r.ede], [23, 22])
        self.assertIn("rcode=REFUSED", r.ede[0].texto)
        self.assertIn("No Reachable Authority", str(r.ede[1]))

    def test_ede_decodificado(self):
        r = dnsx.leer_dig(DIG_BLOCKED_918, "192.0.2.53", "analizado")
        self.assertEqual(r.estado, "NXDOMAIN")
        self.assertEqual(r.ede[0].codigo, 15)

    def test_banderas_y_respuestas(self):
        r = dnsx.leer_dig(DIG_REFUSED_AA, "192.0.2.53", "analizado")
        self.assertIn("aa", r.banderas)
        self.assertIn("con bandera AA", r.resumen())
        self.assertTrue(dnsx.leer_dig(DIG_OK).resolvio)

    def test_sin_respuesta(self):
        r = dnsx.leer_dig(";; connection timed out; no servers could be reached")
        self.assertEqual(r.estado, "SIN_RESPUESTA")
        self.assertTrue(r.fallo)


class TestAtribucion(unittest.TestCase):
    def _r(self, salida, dns, rol):
        return dnsx.leer_dig(salida, dns, rol)

    def test_confirmado_por_ede_de_politica(self):
        estado, _ = dnsx.atribuir([self._r(DIG_BLOCKED_918, "192.0.2.53", "analizado")])
        self.assertEqual(estado, dnsx.BLOQUEO_CONFIRMADO)

    def test_probable_si_la_referencia_resuelve(self):
        estado, _ = dnsx.atribuir([self._r(DIG_REFUSED_AA, "192.0.2.53", "analizado"),
                                   self._r(DIG_OK, "198.51.100.1", "referencia")])
        self.assertEqual(estado, dnsx.BLOQUEO_PROBABLE)

    def test_no_atribuible_con_delegacion_rota(self):
        # Caso real del 9 de octubre de 2026 (whtsapp.online), con
        # direcciones de documentacion.
        estado, texto = dnsx.atribuir([
            self._r(DIG_REFUSED_AA, "192.0.2.53", "analizado"),
            self._r(DIG_SERVFAIL_911, "198.51.100.1", "referencia"),
            self._r(DIG_SERVFAIL_911, "198.51.100.2", "referencia")])
        self.assertEqual(estado, dnsx.NO_ATRIBUIBLE)
        self.assertIn("EDE 22/23", texto)

    def test_sin_bloqueo(self):
        estado, _ = dnsx.atribuir([self._r(DIG_OK, "192.0.2.53", "analizado")])
        self.assertEqual(estado, dnsx.SIN_BLOQUEO)

    def test_sin_resolver_analizado(self):
        estado, texto = dnsx.atribuir([self._r(DIG_SERVFAIL_911, "198.51.100.1", "referencia")])
        self.assertEqual(estado, dnsx.SIN_RESOLVER)
        self.assertIn("servidores autoritativos", texto)


class TestReporte(unittest.TestCase):
    def test_texto_escapado_en_html(self):
        html = report_builder.intro_html("Respuesta <script>x</script>\n\nhttps://ejemplo.com")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('<a href="https://ejemplo.com"', html)

    def test_intro_con_comparacion_dns(self):
        texto = dnsx.texto_para_reporte([
            dnsx.leer_dig(DIG_REFUSED_AA, "192.0.2.53", "analizado"),
            dnsx.leer_dig(DIG_SERVFAIL_911, "198.51.100.1", "referencia")])
        self.assertIn("Atribución del bloqueo: NO_ATRIBUIBLE", texto)
        self.assertIn("192.0.2.53 (analizado): REFUSED, con bandera AA", texto)


class TestNavegador(unittest.TestCase):
    def test_configuracion_normal_del_navegador(self):
        self.assertFalse(cfg.IGNORE_HTTPS_ERRORS)
        for nombre in ("STEALTH_ARGS", "BROWSER_CHANNEL", "USE_PERSISTENT_PROFILE",
                       "FORZAR_VENTANA_VISIBLE"):
            self.assertFalse(hasattr(cfg, nombre), nombre)

    def test_fuentes(self):
        titulos = cfg.fuente_titulos()
        self.assertEqual(len(titulos), 5)
        self.assertTrue(all("{dominio}" not in p["url"] for p in cfg.build_pages("ejemplo.com")))


if __name__ == "__main__":
    unittest.main()
