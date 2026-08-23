"""El almacén durable de métricas (Vercel KV / Upstash Redis por REST).

Por qué hay tests con un Redis falso en vez de "confiar en que anda": lo que
esto arregla es un bug que NO se ve en una máquina con disco. En serverless
cada petición puede caer en una instancia nueva, así que el archivo de
métricas se perdía entre invocaciones y el dedup de nonces —que vivía en la
memoria del proceso— no deduplicaba nada. Los tests con archivo pasaban todos
igual. La única forma de cubrirlo es ejercitar el camino de KV.

El falso habla el protocolo de verdad (comandos como listas JSON, respuestas
en `{"result": …}`) para que un cambio en cómo se arma el pedido lo rompa.
"""
from __future__ import annotations

import json

import pytest

from cliente_ia import almacen_kv, metricas


class _RedisFalso:
    """Lo justo de Redis que usa el módulo: RPUSH, LRANGE, LTRIM, SET NX, DEL."""

    def __init__(self):
        self.listas: dict[str, list[str]] = {}
        self.claves: dict[str, str] = {}
        self.comandos: list[list] = []
        self.romper = False

    def __call__(self, pedido, timeout=None):
        if self.romper:
            raise OSError("el store no contesta")
        cmd = json.loads(pedido.data)
        self.comandos.append(cmd)
        assert pedido.headers.get("Authorization", "").startswith("Bearer "), (
            "el pedido tiene que ir autenticado")
        nombre = cmd[0].upper()
        if nombre == "RPUSH":
            self.listas.setdefault(cmd[1], []).extend(cmd[2:])
            r = len(self.listas[cmd[1]])
        elif nombre == "LRANGE":
            r = list(self.listas.get(cmd[1], []))
        elif nombre == "LTRIM":
            ini, fin = int(cmd[2]), int(cmd[3])
            lista = self.listas.get(cmd[1], [])
            self.listas[cmd[1]] = lista[ini:] if fin == -1 else lista[ini:fin + 1]
            r = "OK"
        elif nombre == "SET":
            if "NX" in cmd and cmd[1] in self.claves:
                r = None                     # ya existía: Upstash devuelve null
            else:
                self.claves[cmd[1]] = cmd[2]
                r = "OK"
        elif nombre == "DEL":
            self.listas.pop(cmd[1], None)
            r = "OK"
        else:                                                    # pragma: no cover
            raise AssertionError(f"comando no esperado: {nombre}")

        class _Resp:
            def __init__(self, cuerpo):
                self._c = cuerpo
            def read(self):
                return json.dumps({"result": self._c}).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        return _Resp(r)


@pytest.fixture
def kv(monkeypatch, tmp_path):
    import urllib.request
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    monkeypatch.setenv("KV_REST_API_URL", "https://ejemplo.upstash.io")
    monkeypatch.setenv("KV_REST_API_TOKEN", "un-token-secreto-de-upstash")
    falso = _RedisFalso()
    monkeypatch.setattr(urllib.request, "urlopen", falso)
    metricas._nonces_vistos = None
    return falso


def test_sin_variables_no_se_activa(monkeypatch):
    """Es opt-in: el programa instalado tiene disco y no tiene por qué hablar
    con nadie. Hacen falta las DOS variables."""
    for v in ("KV_REST_API_URL", "KV_REST_API_TOKEN",
              "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    assert almacen_kv.activo() is False

    monkeypatch.setenv("KV_REST_API_URL", "https://ejemplo.upstash.io")
    assert almacen_kv.activo() is False, "con la URL sola no alcanza"
    monkeypatch.setenv("KV_REST_API_TOKEN", "t")
    assert almacen_kv.activo() is True


def test_tambien_se_activa_con_las_variables_de_upstash(monkeypatch):
    """Vercel KV inyecta `KV_REST_API_*`; un store de Upstash creado a mano
    inyecta `UPSTASH_REDIS_REST_*`. Los dos son el mismo servicio."""
    for v in ("KV_REST_API_URL", "KV_REST_API_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://ejemplo.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "t")
    assert almacen_kv.activo() is True


def test_los_eventos_van_al_store_y_no_al_disco(kv, tmp_path):
    """Lo que hace que la web pública acumule: el archivo ni se toca."""
    metricas.registrar_envios([{"canal": "email", "programa": "acme.com",
                                "segmento": "fintech"}])
    assert kv.listas[almacen_kv.CLAVE_EVENTOS], "no se guardó en el store"
    assert not (tmp_path / metricas.ARCHIVO).exists(), (
        "se escribió al disco teniendo un store durable")

    r = metricas.resumen("acme.com")
    assert r["envios"] == 1
    assert r["por_segmento"][0]["valor"] == "fintech"


def test_el_dedup_de_nonces_es_del_store_y_no_de_la_memoria(kv):
    """EL bug que esto arregla. En serverless el set en memoria no dedup nada:
    cada petición puede caer en una instancia recién creada. Se simula
    borrando la memoria del proceso entre llamadas — el dedup tiene que
    seguir funcionando igual, porque vive en Redis."""
    assert metricas._nonce_nuevo("abc") is True
    metricas._nonces_vistos = None                   # "otra instancia"
    assert metricas._nonce_nuevo("abc") is False, (
        "el nonce se olvidó al cambiar de instancia: el dedup no es durable")
    metricas._nonces_vistos = None
    assert metricas._nonce_nuevo("otro") is True

    # Y que sea UN comando atómico, no un GET y después un SET (que en dos
    # instancias en paralelo dejaría pasar los dos).
    sets = [c for c in kv.comandos if c[0].upper() == "SET"]
    assert sets and "NX" in sets[0] and "EX" in sets[0], sets[:1]


def test_reproducir_el_enlace_no_infla_la_conversion_en_serverless(kv):
    """El caso real, de punta a punta: el mismo click seis veces, con la
    memoria borrada en el medio como pasa entre invocaciones."""
    metricas.registrar_envios([{"canal": "email"} for _ in range(10)])
    for _ in range(6):
        metricas._nonces_vistos = None
        metricas.registrar_conversion({"canal": "email", "nonce": "n-1"})
    assert metricas.resumen()["conversiones"] == 1


def test_la_lista_no_crece_sin_techo(kv, monkeypatch):
    """`resumen()` lee la lista entera en cada llamada y el plan de KV cobra
    por comandos: sin recorte, la lectura crecería para siempre."""
    monkeypatch.setattr(almacen_kv, "MAX_EVENTOS", 20)
    for _ in range(60):
        metricas.registrar_envios([{"canal": "email"}])
    assert len(kv.listas[almacen_kv.CLAVE_EVENTOS]) <= 20
    # Y el recorte es perezoso: no se gasta un LTRIM por cada evento.
    trims = [c for c in kv.comandos if c[0].upper() == "LTRIM"]
    assert 0 < len(trims) <= 45, f"{len(trims)} LTRIM para 60 eventos"


def test_si_el_store_se_cae_no_se_rompe_nada(kv, tmp_path):
    """Un contador es accesorio: que Upstash tenga un mal minuto no puede
    convertir el pixel de un correo en un error. Se cae al disco y sigue."""
    kv.romper = True
    metricas.registrar_envios([{"canal": "email"}])          # no revienta
    assert (tmp_path / metricas.ARCHIVO).exists(), (
        "con el store caído tendría que haber caído al archivo")
    # Y leer devuelve vacío en vez de explotar.
    assert metricas.resumen()["envios"] == 0


def test_una_entrada_corrupta_no_tumba_el_tablero(kv):
    metricas.registrar_envios([{"canal": "email"}])
    kv.listas[almacen_kv.CLAVE_EVENTOS].append("{esto no es json")
    kv.listas[almacen_kv.CLAVE_EVENTOS].append("[1,2,3]")     # json pero no dict
    assert metricas.resumen()["envios"] == 1


def test_el_token_no_aparece_en_ningun_lado(kv, capsys):
    """Va en una cabecera de autenticación y en el host de la URL: si el
    módulo lo escupiera al log, quedaría en los registros de Vercel."""
    kv.romper = True
    metricas.registrar_envios([{"canal": "email"}])
    salida = capsys.readouterr()
    assert "un-token-secreto-de-upstash" not in salida.out + salida.err
    assert "ejemplo.upstash.io" not in salida.out + salida.err


def test_borrar_metricas_vacia_el_store(kv):
    metricas.registrar_envios([{"canal": "email"} for _ in range(3)])
    assert metricas.resumen()["envios"] == 3
    metricas.borrar_todo()
    assert metricas.resumen()["envios"] == 0


def test_el_embudo_entero_sobrevive_al_cambio_de_instancia(kv):
    """La prueba que resume el motivo de todo el módulo: se registra un envío
    en una "instancia", se cuenta la apertura en otra y el click en una
    tercera, y el resumen los ve a los tres."""
    metricas.registrar_envios([{"canal": "email", "segmento": "fintech"}
                               for _ in range(4)])
    metricas._nonces_vistos = None
    metricas.registrar_apertura({"canal": "email", "segmento": "fintech",
                                 "nonce": "a-1"})
    metricas._nonces_vistos = None
    metricas.registrar_conversion({"canal": "email", "segmento": "fintech",
                                   "nonce": "c-1"})
    metricas._nonces_vistos = None
    r = metricas.resumen()
    assert (r["envios"], r["aperturas"], r["conversiones"]) == (4, 1, 1)
    assert r["tasa_apertura"] == 0.25
