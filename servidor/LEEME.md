# Servidor de envíos (Cloudflare Workers + R2)

Recibe los resultados que la gente envía de forma voluntaria al procesar canciones:

- el diagnóstico, el informe y la tablatura de cada canción;
- nunca el audio ni la letra, y sin rutas personales.

Cada envío es un `.json.gz` de unos 10 KB que se guarda en un bucket de R2. Solo quien tenga el token de
administración puede listarlos, descargarlos o borrarlos.

Entra de sobra en el plan gratuito de Cloudflare: 100.000 peticiones al día en Workers y 10 GB en R2.

## Ponerlo en marcha (una vez)

Necesitas una cuenta de Cloudflare y [Node.js](https://nodejs.org) (versión LTS).

1. En el panel de Cloudflare, activa **R2** (menú *R2 Object Storage*). Puede pedirte un método de pago
   aunque no cobre nada dentro del plan gratuito.
2. Abre una terminal en esta carpeta (`servidor`) y ejecuta:

   ```
   npx wrangler login
   npx wrangler r2 bucket create auto-cdlc-envios
   npx wrangler secret put ADMIN_TOKEN
   npx wrangler deploy
   ```

   - `login` abre el navegador para dar acceso a tu cuenta.
   - `secret put` pide el token de administración. Pon una clave larga e inventada (por ejemplo, 40
     letras y números al azar) y **guárdala**: es la que te deja descargar los envíos.
   - `deploy` muestra al final la dirección del servidor, del estilo
     `https://auto-cdlc-envios.TU-SUBDOMINIO.workers.dev`.
3. Comprueba que funciona: al abrir esa dirección en el navegador debe salir
   "auto-cdlc: servidor de envíos en marcha".
4. Pon esa dirección en `ENVIOS_URL` dentro de `cdlc_bajo.py`, o en `servidor_envios` de
   `configuracion.txt` para probar. A partir de ahí, `procesar.bat` pregunta en cada tanda si enviar.

Si `deploy` da error por el límite de envíos por IP (`[[ratelimits]]` en `wrangler.toml`), borra ese bloque
y vuelve a desplegar.

## Descargar los envíos

```
python descargar_envios.py --url https://auto-cdlc-envios.TU-SUBDOMINIO.workers.dev --token TU_TOKEN
```

- Baja a la carpeta `envios` los que aún no tengas. También puedes poner la dirección y el token en las
  variables de entorno `AUTO_CDLC_ENVIOS_URL` y `AUTO_CDLC_ENVIOS_TOKEN`.
- Con `--borrar`, después los borra del servidor.

Cada archivo es un JSON comprimido con:

- versión, idioma y sistema;
- un identificador anónimo de la instalación;
- la configuración usada;
- por cada canción: nombre del archivo, estado, resumen, informe, diagnóstico completo y XML de los
  arreglos de bajo (y la traza del error, si falló).

## Otras rutas del servidor (con `Authorization: Bearer TOKEN`)

| Petición | Qué hace |
|---|---|
| `GET /envios` | Lista los envíos (clave, tamaño, fecha, versión, instalación, estado). |
| `GET /envios/AAAA-MM-DD/....json.gz` | Descarga uno. |
| `DELETE /envios/AAAA-MM-DD/....json.gz` | Lo borra. |
