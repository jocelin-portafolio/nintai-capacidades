// Interfaz del chatbot NINTAI.
// Modos: "api" (backend con Claude), "demo-servidor" (backend sin clave) y
// "demo-local" (sin backend, por ejemplo en GitHub Pages). Los dos modos demo
// reproducen guion-demo.json y lo indican en pantalla.
// Todo el contenido dinámico se inserta con textContent (nunca innerHTML).

const $ = (id) => document.getElementById(id);
const ui = {
  mensajes: $("mensajes"), formulario: $("formulario"), texto: $("texto"), enviar: $("enviar"),
  aviso: $("aviso"), modo: $("modo"), sugerencia: $("sugerencia"), usarSugerencia: $("usarSugerencia"),
  vacio: $("vacio"), cargando: $("cargando"), mapa: $("mapa"), reiniciar: $("reiniciar"),
};

const estado = { modo: "api", sesionId: crypto.randomUUID(), guion: null, turno: 0, ocupado: false, burbuja: null };

function el(tag, attrs = {}, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") nodo.className = v;
    else nodo.setAttribute(k, v);
  }
  for (const h of hijos.flat()) {
    if (h == null) continue;
    nodo.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return nodo;
}

function agregarMensaje(texto, tipo) {
  const li = el("li", { class: `msg msg--${tipo}` }, texto);
  ui.mensajes.append(li);
  ui.mensajes.scrollTop = ui.mensajes.scrollHeight;
  return li;
}

function ocupado(si) {
  estado.ocupado = si;
  ui.enviar.disabled = si;
  ui.texto.disabled = si;
  if (!si) ui.texto.focus();
}

// ---------- Mapa ----------
const NIVELES = { basico: 1, intermedio: 2, avanzado: 3 };
const TIPOS = { tecnica: "técnica", blanda: "blanda", conocimiento: "conocimiento" };
const clp = (n) => "$" + Number(n).toLocaleString("es-CL");

function bloque(titulo, ...contenido) {
  return el("section", { class: "bloque" }, el("h3", {}, titulo), ...contenido);
}

function renderMapa(m) {
  const habilidades = el("div", { class: "habilidades" }, m.habilidades.map((h) =>
    el("div", { class: "hab" },
      el("strong", {}, h.nombre),
      el("div", { class: "hab__meta" },
        el("span", { class: "chip" }, TIPOS[h.tipo] || h.tipo),
        el("span", { class: "nivel", "aria-label": `Nivel ${h.nivel}`, title: `Nivel ${h.nivel}` },
          [1, 2, 3].map((i) => el("i", { class: i <= (NIVELES[h.nivel] || 1) ? "on" : "" })))),
      el("p", {}, h.evidencia))));

  const transferibles = el("ul", { class: "lista" }, m.transferibles.map((t) =>
    el("li", {}, el("strong", {}, t.habilidad), el("span", { class: "flecha" }, "→"),
      el("strong", {}, t.hacia), el("br"), t.por_que)));

  const rutas = m.rutas.map((r, i) =>
    el("div", { class: "ruta" },
      el("div", { class: "ruta__head" },
        el("strong", {}, (i === 0 ? "★ " : "") + r.titulo),
        el("span", { class: "chip chip--n" }, `${r.tipo} · ${r.horizonte_semanas} semanas`)),
      el("ol", {}, r.pasos.map((p) => el("li", {}, p)))));

  const s = m.micro_servicio;
  const servicio = el("section", { class: "bloque servicio" },
    el("h3", {}, "Micro-servicio que puedes ofrecer"),
    el("h4", {}, s.nombre),
    el("p", {}, s.descripcion),
    el("div", { class: "precio" }, `${clp(s.precio_referencial_clp.min)} – ${clp(s.precio_referencial_clp.max)} CLP`),
    el("dl", {},
      el("dt", {}, "Para"), el("dd", {}, s.cliente_objetivo),
      el("dt", {}, "Entregas"), el("dd", {}, s.entregables.join(" · ")),
      el("dt", {}, "Canal"), el("dd", {}, s.canal_venta)));

  const brechas = m.brechas.length
    ? bloque("Para seguir creciendo", el("ul", { class: "lista" }, m.brechas.map((b) =>
        el("li", {}, el("strong", {}, b.habilidad), el("span", { class: "flecha" }, "·"), b.recurso_sugerido))))
    : null;

  ui.mapa.replaceChildren(
    bloque("Tu perfil", el("p", { class: "resumen" }, m.resumen_perfil)),
    bloque("Habilidades", habilidades),
    bloque("Lo que puedes llevar a otros roles", transferibles),
    bloque("Rutas", ...rutas),
    servicio,
    brechas,
  );
  ui.vacio.hidden = true;
  ui.cargando.hidden = true;
  ui.mapa.hidden = false;
}

// ---------- Eventos del agente ----------
function manejarEvento(ev) {
  switch (ev.tipo) {
    case "texto":
      if (!estado.burbuja) estado.burbuja = agregarMensaje("", "bot msg--escribiendo");
      estado.burbuja.textContent += ev.texto;
      ui.mensajes.scrollTop = ui.mensajes.scrollHeight;
      break;
    case "generando_mapa":
      ui.vacio.hidden = true;
      ui.cargando.hidden = false;
      break;
    case "mapa":
      renderMapa(ev.mapa);
      break;
    case "error":
      if (ev.descartar && estado.burbuja) { estado.burbuja.remove(); estado.burbuja = null; }
      ui.cargando.hidden = true;
      agregarMensaje(ev.mensaje, "error");
      break;
    case "fin":
      if (estado.burbuja) estado.burbuja.classList.remove("msg--escribiendo");
      estado.burbuja = null;
      if (ev.uso && estado.modo === "api" && ev.uso.output_tokens) mostrarUso(ev.uso);
      break;
  }
}

function mostrarUso(u) {
  let nodo = document.querySelector(".uso");
  if (!nodo) { nodo = el("p", { class: "uso" }); ui.mapa.after(nodo); }
  nodo.textContent = `${u.input_tokens + u.cache_read_tokens} tokens de entrada (${u.cache_read_tokens} en caché) · ${u.output_tokens} de salida · US$ ${u.costo_usd.toFixed(4)}`;
}

async function enviarApi(texto) {
  const res = await fetch("api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sesion_id: estado.sesionId, texto }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const lector = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await lector.read();
    if (done) break;
    buffer += value;
    let corte;
    while ((corte = buffer.indexOf("\n\n")) !== -1) {
      const linea = buffer.slice(0, corte).trim();
      buffer = buffer.slice(corte + 2);
      if (linea.startsWith("data: ")) manejarEvento(JSON.parse(linea.slice(6)));
    }
  }
}

const pausa = (ms) => new Promise((r) => setTimeout(r, ms));

async function enviarDemoLocal() {
  const turnos = estado.guion.turnos;
  const turno = turnos[Math.min(estado.turno, turnos.length - 1)];
  await pausa(450);
  if (turno.generando) {
    manejarEvento({ tipo: "generando_mapa" });
    await pausa(900);
    manejarEvento({ tipo: "mapa", mapa: estado.guion.mapa });
  }
  for (const palabra of turno.asistente.split(" ")) {
    manejarEvento({ tipo: "texto", texto: palabra + " " });
    await pausa(28);
  }
  manejarEvento({ tipo: "fin" });
}

function actualizarSugerencia() {
  const esDemo = estado.modo !== "api" && estado.guion;
  const turno = esDemo && estado.guion.turnos[estado.turno];
  ui.sugerencia.hidden = !turno;
  if (turno) ui.usarSugerencia.textContent = turno.usuario;
}

async function enviar(texto) {
  if (estado.ocupado || !texto.trim()) return;
  agregarMensaje(texto, "user");
  ui.texto.value = "";
  ui.sugerencia.hidden = true;
  ocupado(true);
  try {
    if (estado.modo === "demo-local") await enviarDemoLocal();
    else await enviarApi(texto);
  } catch (e) {
    manejarEvento({ tipo: "error", mensaje: "No pude conectarme. Intenta de nuevo.", descartar: true });
    manejarEvento({ tipo: "fin" });
  }
  estado.turno += 1;
  actualizarSugerencia();
  ocupado(false);
}

// ---------- Inicio ----------
function reiniciar() {
  if (estado.modo !== "demo-local") {
    fetch(`api/sesion/${estado.sesionId}`, { method: "DELETE" }).catch(() => {});
  }
  estado.sesionId = crypto.randomUUID();
  estado.turno = 0;
  estado.burbuja = null;
  ui.mensajes.replaceChildren();
  ui.mapa.hidden = true;
  ui.cargando.hidden = true;
  ui.vacio.hidden = false;
  document.querySelector(".uso")?.remove();
  saludar();
}

function saludar() {
  const saludo = estado.guion?.saludo ||
    "Hola, soy el asistente de NINTAI. Vamos a descubrir qué sabes hacer y cómo convertirlo en nuevas oportunidades. Para empezar, ¿a qué te has dedicado en los últimos años?";
  agregarMensaje(saludo, "bot");
  actualizarSugerencia();
}

async function iniciar() {
  try {
    const r = await fetch("api/estado");
    if (!r.ok) throw new Error();
    estado.modo = (await r.json()).demo ? "demo-servidor" : "api";
  } catch {
    estado.modo = "demo-local";
  }
  if (estado.modo !== "api") {
    estado.guion = await (await fetch("guion-demo.json")).json();
    ui.modo.hidden = false;
    ui.modo.textContent = "Modo demo";
    ui.aviso.hidden = false;
    ui.aviso.textContent = estado.guion.aviso;
  }
  saludar();
  // ?reproducir=1 reproduce sola la conversación de ejemplo (solo en modo demo).
  if (estado.modo !== "api" && new URLSearchParams(location.search).has("reproducir")) {
    while (!ui.sugerencia.hidden) {
      await pausa(700);
      await enviar(ui.usarSugerencia.textContent);
    }
  }
}

ui.formulario.addEventListener("submit", (e) => { e.preventDefault(); enviar(ui.texto.value); });
ui.texto.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(ui.texto.value); }
});
ui.texto.addEventListener("input", () => {
  ui.texto.style.height = "auto";
  ui.texto.style.height = Math.min(ui.texto.scrollHeight, 160) + "px";
});
ui.usarSugerencia.addEventListener("click", () => enviar(ui.usarSugerencia.textContent));
ui.reiniciar.addEventListener("click", reiniciar);

iniciar();
