// auto-cdlc: recepción de resultados enviados voluntariamente por quien usa el programa.
// Guarda cada envío (JSON comprimido con gzip) en el bucket R2 "ENVIOS". Solo quien tenga el
// token de administración (secreto ADMIN_TOKEN) puede listar y descargar.

const TAM_MAX = 3 * 1024 * 1024; // 3 MB por envío (una canción ocupa unos 100 KB comprimida)

function json(datos, estado = 200) {
  return new Response(JSON.stringify(datos), {
    status: estado,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function esAdmin(request, env) {
  const auth = request.headers.get("authorization") || "";
  return env.ADMIN_TOKEN && auth === `Bearer ${env.ADMIN_TOKEN}`;
}

async function recibir(request, env) {
  const ip = request.headers.get("cf-connecting-ip") || "desconocida";
  if (env.LIMITE) {
    const { success } = await env.LIMITE.limit({ key: ip });
    if (!success) return json({ error: "demasiados envíos, prueba más tarde" }, 429);
  }
  const cuerpo = await request.arrayBuffer();
  if (cuerpo.byteLength === 0 || cuerpo.byteLength > TAM_MAX) {
    return json({ error: "tamaño no válido" }, 413);
  }
  const b = new Uint8Array(cuerpo);
  if (b[0] !== 0x1f || b[1] !== 0x8b) return json({ error: "se espera gzip" }, 415);

  // comprobar que dentro hay un JSON de auto-cdlc
  let datos;
  try {
    const texto = await new Response(
      new Blob([cuerpo]).stream().pipeThrough(new DecompressionStream("gzip"))
    ).text();
    datos = JSON.parse(texto);
  } catch (e) {
    return json({ error: "contenido no válido" }, 400);
  }
  if (datos.programa !== "auto-cdlc") return json({ error: "contenido no válido" }, 400);

  const ahora = new Date();
  const dia = ahora.toISOString().slice(0, 10);
  const clave = `envios/${dia}/${ahora.toISOString().replace(/[:.]/g, "-")}_${crypto.randomUUID().slice(0, 8)}.json.gz`;
  await env.ENVIOS.put(clave, cuerpo, {
    httpMetadata: { contentType: "application/gzip" },
    customMetadata: {
      version: String(datos.version || "").slice(0, 20),
      instalacion: String(datos.instalacion || "").slice(0, 40),
      estado: String((datos.cancion || {}).estado || "").slice(0, 20),
    },
  });
  return json({ ok: true, clave });
}

async function listar(url, env) {
  const desde = url.searchParams.get("desde") || "";
  const claves = [];
  let cursor;
  do {
    const r = await env.ENVIOS.list({ prefix: "envios/", cursor, limit: 1000, startAfter: desde || undefined, include: ["customMetadata"] });
    for (const o of r.objects) claves.push({ clave: o.key, tam: o.size, fecha: o.uploaded, ...o.customMetadata });
    cursor = r.truncated ? r.cursor : undefined;
  } while (cursor && claves.length < 20000);
  return json({ envios: claves });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/envio") return recibir(request, env);
    if (request.method === "GET" && url.pathname === "/") {
      return new Response("auto-cdlc: servidor de envíos en marcha\n");
    }
    if (url.pathname === "/envios" || url.pathname.startsWith("/envios/")) {
      if (!esAdmin(request, env)) return json({ error: "no autorizado" }, 401);
      if (request.method === "GET" && url.pathname === "/envios") return listar(url, env);
      const clave = decodeURIComponent(url.pathname.slice(1));
      if (request.method === "GET") {
        const o = await env.ENVIOS.get(clave);
        if (!o) return json({ error: "no existe" }, 404);
        return new Response(o.body, { headers: { "content-type": "application/gzip" } });
      }
      if (request.method === "DELETE") {
        await env.ENVIOS.delete(clave);
        return json({ ok: true });
      }
    }
    return json({ error: "no encontrado" }, 404);
  },
};
