const LAT = -37.03;
const LON = -73.16;
const DIAS = 14;

const CODIGOS = {
  0:["Despejado","☀️"],      1:["Casi despejado","🌤️"], 2:["Parcial nublado","⛅"],
  3:["Nublado","☁️"],        45:["Neblina","🌫️"],       48:["Neblina helada","🌫️"],
  51:["Llovizna","🌦️"],      53:["Llovizna","🌦️"],      55:["Llovizna intensa","🌦️"],
  61:["Lluvia débil","🌧️"],  63:["Lluvia","🌧️"],        65:["Lluvia fuerte","⛈️"],
  66:["Lluvia helada","🌧️"], 67:["Lluvia helada","🌧️"],
  71:["Nieve","🌨️"],         73:["Nieve","🌨️"],         75:["Nieve intensa","🌨️"],
  80:["Chubascos","🌦️"],     81:["Chubascos","🌧️"],     82:["Chubascos fuertes","⛈️"],
  95:["Tormenta","⛈️"],      96:["Tormenta","⛈️"],      99:["Tormenta","⛈️"],
};

const describir = c => CODIGOS[c] || ["—", "·"];

// Qué escena de fondo le corresponde a cada código
const escenaDe = c => (c <= 1 ? "sol" : c <= 48 ? "nubes" : "lluvia");

const nombreDia = iso =>
  new Date(iso + "T12:00:00").toLocaleDateString("es-CL", { weekday:"short", day:"numeric" });

const nombreLargo = iso =>
  new Date(iso + "T12:00:00").toLocaleDateString("es-CL",
    { weekday:"long", day:"numeric", month:"long" });

let datos = null;
let seleccion = null;


/* ---------------- Datos ---------------- */

async function pedir() {
  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.search = new URLSearchParams({
    latitude: LAT,
    longitude: LON,
    current: "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
    hourly:  "temperature_2m,precipitation,precipitation_probability,wind_speed_10m",
    daily:   "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum," +
             "precipitation_probability_max,wind_speed_10m_max",
    wind_speed_unit: "kmh",
    timezone: "auto",
    forecast_days: DIAS,
  });

  const r = await fetch(url);
  if (!r.ok) throw new Error("API " + r.status);
  return r.json();
}


/* ---------------- Fondo animado ---------------- */

/* ---------------- Fondo en video ---------------- */

const VIDEOS = {
  sol:    "fondos/sol.mp4",
  nubes:  "fondos/nubes.mp4",
  lluvia: "fondos/lluvia.mp4",
};

let escenaActual = null;

function montarEscena(codigo, fecha) {
  const tipo  = escenaDe(codigo);
  const video = document.getElementById("fondo");
  const velo  = document.getElementById("velo");

  // El velo se oscurece de noche, sin importar el clima
  const hora  = new Date().getHours();
  const esHoy = fecha === datos.daily.time[0];
  velo.classList.toggle("noche", esHoy && (hora < 7 || hora >= 20));

  // Si ya está puesto ese video, no lo reiniciamos
  if (tipo === escenaActual) return;
  escenaActual = tipo;

  video.classList.remove("visible");          // se desvanece
  setTimeout(() => {
    video.src = VIDEOS[tipo];
    video.load();
    video.play().catch(() => {});             // por si el navegador bloquea el autoplay
  }, 350);
}


/* ---------------- Pintado ---------------- */

function pintarAhora(c) {
  const [texto, icono] = describir(c.weather_code);
  document.getElementById("icono-ahora").textContent = icono;
  document.getElementById("temp-ahora").textContent = Math.round(c.temperature_2m) + "°";
  document.getElementById("cond-ahora").textContent = texto;
  document.getElementById("extra-ahora").textContent =
    `sensación ${Math.round(c.apparent_temperature)}° · viento ${Math.round(c.wind_speed_10m)} km`;
}

function pintarDias(d) {
  const cont = document.getElementById("dias");
  cont.innerHTML = "";

  const minG = Math.min(...d.temperature_2m_min);
  const maxG = Math.max(...d.temperature_2m_max);
  const span = (maxG - minG) || 1;

  d.time.forEach((fecha, i) => {

    if (i === 7) {
      const sep = document.createElement("p");
      sep.className = "separador";
      sep.textContent = "tendencia · menos confiable";
      cont.appendChild(sep);
    }

    const min = d.temperature_2m_min[i];
    const max = d.temperature_2m_max[i];
    const mm  = d.precipitation_sum[i] ?? 0;
    const pr  = d.precipitation_probability_max[i];
    const [texto, icono] = describir(d.weather_code[i]);

    const fila = document.createElement("article");
    fila.className = "dia" + (i >= 7 ? " tendencia" : "");
    fila.dataset.fecha = fecha;
    fila.style.animationDelay = (i * 35) + "ms";
    fila.title = texto;

    fila.innerHTML = `
      <span class="nombre">${i === 0 ? "Hoy" : nombreDia(fecha)}</span>
      <span class="icono">${icono}</span>
      <span class="agua">
        ${mm > 0 ? `<span class="mm">${mm.toFixed(1)} mm</span>` : ""}
        ${pr ? `<span class="pr">${pr}%</span>` : ""}
      </span>
      <span class="min">${Math.round(min)}°</span>
      <span class="barra">
        <span class="rango" style="left:${(min - minG) / span * 100}%;
                                   width:${(max - min) / span * 100}%"></span>
      </span>
      <span class="max">${Math.round(max)}°</span>
    `;

    fila.addEventListener("click", () => pintarDetalle(fecha));
    cont.appendChild(fila);
  });
}

function pintarDetalle(fecha) {
  seleccion = fecha;
  const H = datos.hourly, D = datos.daily;
  const di = D.time.indexOf(fecha);

  // Índices de las horas que pertenecen a este día.
  // Ojo: en Chile hay cambio de hora, así que un día puede tener 23 o 25 horas.
  const idx = [];
  for (let i = 0; i < H.time.length; i++)
    if (H.time[i].slice(0, 10) === fecha) idx.push(i);

  const horas  = idx.map(i => H.time[i].slice(11, 13));
  const temps  = idx.map(i => H.temperature_2m[i]);
  const lluv   = idx.map(i => H.precipitation[i] ?? 0);
  const prob   = idx.map(i => H.precipitation_probability[i] ?? 0);
  const viento = idx.map(i => H.wind_speed_10m[i]);

  const maxLl = Math.max(0.6, ...lluv);
  const minT  = Math.min(...temps);
  const spanT = (Math.max(...temps) - minT) || 1;

  const puntos = temps.map((t, i) => {
    const x = ((i + 0.5) / temps.length) * 240;
    const y = 54 - ((t - minT) / spanT) * 44;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const columnas = idx.map((_, i) => `
    <div class="hcol"
         data-h="${horas[i]}"
         data-t="${Math.round(temps[i])}"
         data-mm="${lluv[i].toFixed(1)}"
         data-pr="${prob[i]}"
         data-km="${Math.round(viento[i])}">
      <div class="hbar"><i style="height:${(lluv[i] / maxLl * 100).toFixed(0)}%"></i></div>
      <span class="hhora${+horas[i] % 3 === 0 ? " marcada" : ""}">${horas[i]}</span>
    </div>`).join("");

  const [texto, icono] = describir(D.weather_code[di]);

  document.getElementById("detalle").innerHTML = `
    <div class="d-cab">
      <span class="d-icono">${icono}</span>
      <div>
        <h2>${nombreLargo(fecha)}</h2>
        <p>${texto}</p>
      </div>
    </div>

    <div class="d-datos">
      <div><b>${Math.round(D.temperature_2m_max[di])}°</b><span>máxima</span></div>
      <div><b>${Math.round(D.temperature_2m_min[di])}°</b><span>mínima</span></div>
      <div><b>${(D.precipitation_sum[di] ?? 0).toFixed(1)}</b><span>mm en el día</span></div>
      <div><b>${D.precipitation_probability_max[di] ?? "–"}%</b><span>prob. máx</span></div>
      <div><b>${Math.round(D.wind_speed_10m_max[di])}</b><span>nudos máx</span></div>
    </div>

    <div class="d-grafico">
      <svg class="curva" viewBox="0 0 240 60" preserveAspectRatio="none">
        <polyline points="${puntos}"/>
      </svg>
      <div class="horas">${columnas}</div>
    </div>

    <p class="d-pie">
      línea = temperatura · barras = lluvia por hora (máximo ${maxLl.toFixed(1)} mm)
    </p>
  `;

  montarEscena(D.weather_code[di], fecha);

  document.querySelectorAll(".dia").forEach(e =>
    e.classList.toggle("activo", e.dataset.fecha === fecha));
}

/* ---------------- Histórico ---------------- */

function pintarHistorico() {
  const cont = document.getElementById("historico");
  const hay  = typeof HISTORICO !== "undefined" && HISTORICO.filas.length;

  if (!hay) {
    cont.innerHTML = `
      <h3>Verificación</h3>
      <p class="h-vacio">Todavía no hay días verificados. El recolector guarda cada
      pronóstico y lo compara cuando el día llega — necesita unos días de rodaje.</p>`;
    return;
  }

  const filas = HISTORICO.filas.filter(f => f.anticipacion >= 1 && f.anticipacion <= 5);

  const cuerpo = filas.map(f => `
    <tr>
      <td class="h-modelo">${f.modelo}</td>
      <td>${f.anticipacion}</td>
      <td>${f.casos}</td>
      <td>${f.err_temp   ?? "–"}</td>
      <td>${f.err_lluvia ?? "–"}</td>
      <td>${f.acierto != null ? Math.round(f.acierto * 100) + "%" : "–"}</td>
    </tr>`).join("");

  cont.innerHTML = `
    <h3>Verificación · ${HISTORICO.dias_verificados} días comparados</h3>
    <table class="h-tabla">
      <thead>
        <tr>
          <th>modelo</th><th>días antes</th><th>casos</th>
          <th>error °C</th><th>error mm</th><th>acierto lluvia</th>
        </tr>
      </thead>
      <tbody>${cuerpo}</tbody>
    </table>
    <p class="d-pie">actualizado ${HISTORICO.actualizado}</p>`;
}

/* ---------------- Ciclo ---------------- */

function actualizar() {
  pedir()
    .then(j => {
      datos = j;
      pintarAhora(j.current);
      pintarDias(j.daily);
      pintarDetalle(j.daily.time.includes(seleccion) ? seleccion : j.daily.time[0]);
      document.getElementById("estado").textContent =
        "actualizado " + new Date().toLocaleTimeString("es-CL",
          { hour: "2-digit", minute: "2-digit" });
    })
    .catch(e => {
      document.getElementById("estado").textContent = "sin conexión — " + e.message;
    });
}
/* ---------------- Tooltip ---------------- */

const tip = document.getElementById("tip");
const panel = document.getElementById("detalle");

panel.addEventListener("mousemove", e => {
  const col = e.target.closest(".hcol");
  if (!col) { tip.classList.remove("visible"); return; }

  const d = col.dataset;
  tip.innerHTML = `
    <b>${d.h}:00</b>
    <span>${d.t}° · ${d.km} km</span>
    <span class="t-agua">${d.mm} mm · ${d.pr}% de probabilidad</span>
  `;
  tip.classList.add("visible");

  // Lo corremos al otro lado si se sale de la pantalla
  const m = 14;
  let x = e.clientX + m;
  let y = e.clientY + m;
  if (x + tip.offsetWidth  > window.innerWidth  - 8) x = e.clientX - tip.offsetWidth  - m;
  if (y + tip.offsetHeight > window.innerHeight - 8) y = e.clientY - tip.offsetHeight - m;
  tip.style.left = x + "px";
  tip.style.top  = y + "px";
});

panel.addEventListener("mouseleave", () => tip.classList.remove("visible"));


document.getElementById("fondo")
  .addEventListener("loadeddata", e => e.target.classList.add("visible"));

pintarHistorico();
  
actualizar();
setInterval(actualizar, 15 * 60 * 1000);