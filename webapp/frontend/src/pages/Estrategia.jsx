import React from "react";
import { urlSegura } from "../api.js";
import { Aviso, Copiar, etiquetasOla, Idioma, Ola, Tabla, Vacio } from "../componentes/Comunes.jsx";
import { Icono } from "../componentes/Iconos.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

/**
 * Los documentos estratégicos de la corrida activa (cliente_ia/estrategia.py):
 * ficha del producto, competencia, voz de marca y plan de contenido por
 * campaña. Es lo que okara.ai llama «strategy docs» + «agentes de contenido»,
 * derivado de lo que las seis fases ya midieron — acá no se pide nada al
 * servidor: la corrida ya trae la estrategia adentro.
 */

function Lista({ titulo, items }) {
  if (!items?.length) return null;
  return (
    <div className="doc-bloque">
      <h4 className="sub">{titulo}</h4>
      <ul className="doc-lista">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

function Dato({ etiqueta, valor }) {
  if (!valor) return null;
  return <p className="doc-dato"><span>{etiqueta}: </span>{valor}</p>;
}

function Claves({ titulo, items }) {
  if (!items?.length) return null;
  return (
    <div className="doc-bloque">
      <h4 className="sub">{titulo}</h4>
      <div>{items.map((x) => <span className="doc-clave" key={x}>{x}</span>)}</div>
    </div>
  );
}

const pct = (v) => `${Math.round(v * 100)}%`;

function Producto({ p }) {
  return (
    <section className="card">
      <h3>{t("estrategia.producto")}</h3>
      <Dato etiqueta={t("estrategia.propuesta")} valor={p.propuesta} />
      <Dato etiqueta={t("estrategia.categoria")} valor={p.categoria} />
      <Dato etiqueta={t("estrategia.tamano")} valor={p.tamano_objetivo} />
      <Lista titulo={t("estrategia.sectores")} items={p.sectores} />
      <Lista titulo={t("estrategia.dolores")} items={p.dolores} />
      <Lista titulo={t("estrategia.diferenciales")} items={p.diferenciales} />
      <div className="doc-bloque">
        <h4 className="sub">{t("estrategia.precios")}</h4>
        {p.precios?.length ? (
          <ul className="doc-lista">
            {p.precios.map((x) => (
              <li key={x.monto}>
                <b>{x.monto}</b>{x.periodo ? ` ${t(`estrategia.por_${x.periodo}`)}` : ""}
                <span className="doc-contexto"> — «{x.contexto}»</span>
              </li>
            ))}
          </ul>
        ) : <p className="nota" style={{ marginTop: 0 }}>{t("estrategia.sin_precios")}</p>}
      </div>
      <Claves titulo={t("estrategia.ctas")} items={p.ctas} />
    </section>
  );
}

function Voz({ voz }) {
  return (
    <section className="card">
      <h3>{t("estrategia.voz")}</h3>
      {voz.medido ? (
        <>
          <Dato etiqueta={t("estrategia.registro")} valor={t(`estrategia.registro_${voz.registro}`)} />
          <Dato etiqueta={t("estrategia.tono")}
                valor={`${t(`estrategia.tono_${voz.tono}`)} · ${t("estrategia.largo")}: ${voz.largo_frase}`} />
        </>
      ) : null}
      <Claves titulo={t("estrategia.palabras")} items={voz.palabras} />
      <Lista titulo={t("estrategia.pruebas")} items={voz.pruebas} />
      <Claves titulo={t("estrategia.evitar")} items={voz.superlativos} />
      <div className="doc-bloque">
        <h4 className="sub">{t("estrategia.reglas")}</h4>
        <ol className="doc-lista">{voz.reglas.map((r, i) => <li key={i}>{r}</li>)}</ol>
      </div>
    </section>
  );
}

function Competencia({ comp }) {
  const columnas = [
    { id: "nombre", titulo: t("tabla.empresa"),
      render: (f) => <><b>{f.nombre}</b> <span className="doc-contexto">{f.dominio}</span></> },
    { id: "pais", titulo: t("tabla.pais"), render: (f) => f.pais_nombre || "—" },
    { id: "solapamiento", titulo: t("tabla.solapamiento"),
      render: (f) => <span className="tnum">{pct(f.solapamiento)}</span> },
    { id: "afinidad", titulo: t("estrategia.afinidad"),
      // «ajena» (medida por debajo del umbral de descarte) se muestra con la
      // misma etiqueta que «baja»: la pantalla distingue tres grados, el
      // motor cuatro.
      render: (f) => {
        const clase = f.clase === "ajena" ? "baja" : f.clase;
        return clase
          ? <span className={`afin ${clase}`}>{t(`competencia.afin_${clase}`)}</span>
          : "—";
      } },
    { id: "posicionamiento", titulo: t("estrategia.posicionamiento"),
      render: (f) => f.posicionamiento || "—" },
  ];
  return (
    <section className="card">
      <h3>{t("estrategia.competencia")}</h3>
      <p className="doc-dato">{comp.posicion}</p>
      <Tabla columnas={columnas} filas={comp.filas} clave={(f) => f.dominio} />
    </section>
  );
}

function Campana({ c, etiquetas }) {
  return (
    <div className="plan-campana">
      <div className="plan-cabecera">
        <span>{c.sector}</span>
        <Ola nivel={c.nivel} etiquetas={etiquetas} />
        <Idioma codigo={c.idioma} />
        {c.pais_nombre ? <span className="doc-contexto">{c.pais_nombre}</span> : null}
      </div>
      <Dato etiqueta={t("estrategia.tema")} valor={c.tema} />
      <h4 className="sub">{t("estrategia.linkedin")}</h4>
      <pre className="post">{c.linkedin}</pre>
      <div className="acciones-envio"><Copiar texto={c.linkedin} /></div>
      <h4 className="sub">{t("estrategia.x")}</h4>
      <pre className="post">{c.x}</pre>
      <div className="acciones-envio">
        <Copiar texto={c.x} />
        <span className="doc-contexto tnum">{c.x.length}/280</span>
      </div>
      <h4 className="sub">{t("estrategia.reddit")}</h4>
      {/* Misma rejilla que las búsquedas de Explorar: es lo que acota el
          ancho de la tarjeta — suelta, una consulta larga desbordaba el
          celular. */}
      <div className="lista-busqueda">
        <a className="busq con-ico" href={urlSegura(c.reddit.url)} target="_blank"
           rel="noreferrer" title={c.reddit.consulta}>
          <Icono nombre="burbuja" tam={15} />
          <span className="red">Reddit</span>
          <span className="que">{c.reddit.consulta}</span>
          <Icono nombre="enlace_externo" tam={13} />
        </a>
      </div>
    </div>
  );
}

export default function Estrategia() {
  const { corrida, cargando } = useCorrida(getCorridaId());
  const e = corrida?.estrategia;
  const cabecera = (
    <>
      <h1 className="page-title">{t("estrategia.titulo")}</h1>
      <p className="page-sub">{t("estrategia.subtitulo")}</p>
    </>
  );
  if (cargando) return <>{cabecera}<Vacio texto={t("common.cargando")} /></>;
  if (!corrida) return <>{cabecera}<Vacio texto={t("estrategia.sin_corrida")} /></>;
  // Una corrida que todavía corre, o una guardada por una versión anterior,
  // no trae estrategia: se dice, en vez de una pantalla en blanco.
  if (!e?.producto) return <>{cabecera}<Vacio texto={t("estrategia.vacia")} /></>;

  const etiquetas = etiquetasOla(corrida);
  return (
    <>
      {cabecera}
      <div className="acciones-envio" style={{ marginBottom: 16 }}>
        <Copiar texto={e.markdown} etiqueta={t("estrategia.copiar_todo")} />
      </div>
      {!e.producto.medido ? <Aviso>{t("estrategia.no_medido")}</Aviso> : null}
      <div className="doc-grid">
        <Producto p={e.producto} />
        <Voz voz={e.voz} />
      </div>
      <Competencia comp={e.competencia} />
      <section className="card" style={{ marginTop: 16 }}>
        <h3>{t("estrategia.contenido")}</h3>
        <p className="nota" style={{ marginTop: 0 }}>{t("estrategia.contenido_ayuda")}</p>
        {e.contenido.length
          ? e.contenido.map((c) => <Campana key={c.campana_id} c={c} etiquetas={etiquetas} />)
          : <Vacio />}
      </section>
    </>
  );
}
