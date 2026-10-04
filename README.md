# Integrador Frappe → PostgreSQL

La aplicación consulta tickets `HD Ticket` de Frappe. Un proceso separado
revisa periódicamente los tickets nuevos o modificados y crea o actualiza su
orden correspondiente en PostgreSQL. No es necesario configurar Webhooks en
Frappe.

## Configuración

Define estas variables en un archivo `.env` en la carpeta del proyecto o en el
entorno donde se ejecuta la aplicación. La aplicación carga `.env` al iniciar:

- `FRAPPE_URL`, `FRAPPE_API_KEY` y `FRAPPE_API_SECRET`: acceso de lectura a Frappe.
- `DATABASE_URL`: conexión PostgreSQL, por ejemplo
  `postgresql://usuario:clave@host:5432/base_de_datos`.
- `FRAPPE_POLL_INTERVAL`: intervalo de sondeo en segundos (predeterminado: `60`).
- `FRAPPE_OT_SERVICE_FIELD`: nombre del campo Frappe para el tipo de servicio
  (predeterminado: `subject`).
- `FRAPPE_OT_DESCRIPTION_FIELD`: nombre del campo de descripción
  (predeterminado: `description`).
- `FRAPPE_OT_ADDRESS_FIELD`: nombre del campo de dirección
  (predeterminado: `address`).

Los nombres de campo deben ser los **fieldname** existentes en `HD Ticket`, no
sus etiquetas visibles. `subject`, `description` y `priority` son campos
estándar; dirección normalmente requiere que exista un campo personalizado.
Verifica y configura ese fieldname en `.env` antes de iniciar el sondeo.

El archivo debe incluir las cuatro variables de conexión. Ejemplo (reemplaza los valores;
no subas credenciales reales al control de versiones):

```dotenv
FRAPPE_URL=https://tu-sitio-frappe
FRAPPE_API_KEY=tu-api-key
FRAPPE_API_SECRET=tu-api-secret
DATABASE_URL=postgresql://usuario:clave@host:5432/base_de_datos
FRAPPE_POLL_INTERVAL=60
FRAPPE_OT_SERVICE_FIELD=subject
FRAPPE_OT_DESCRIPTION_FIELD=description
FRAPPE_OT_ADDRESS_FIELD=address
```

Instala las dependencias con `pip install -r requirements.txt`. Para iniciar la
interfaz web, ejecuta `python app.py`. En otra ventana de terminal, inicia el
sondeador con `python poller.py`. Ambos procesos leen `.env`; deja los dos
ejecutándose. En producción, configura ambos procesos como servicios
independientes para que se inicien automáticamente.

## Preparar PostgreSQL

`id_pqr` identifica de forma única la PQR y evita duplicados. El sondeador crea
el índice único automáticamente al iniciar. También crea la tabla
`integrador_sync_state` para recordar el último cambio procesado y reintentar
sin perder tickets cuando se reinicia. La primera ejecución comienza desde el
inicio y sincroniza los tickets históricos que Frappe devuelva.

```sql
CREATE UNIQUE INDEX IF NOT EXISTS ordenes_trabajo_id_pqr_uidx
    ON ordenes_trabajo (id_pqr);
```

Si ya existen varias órdenes con el mismo `id_pqr`, primero resuelve esos
duplicados; PostgreSQL no permitirá crear el índice mientras existan.

Las órdenes comienzan con estado `PENDIENTE`. Al sincronizar actualizaciones,
Frappe normaliza sus estados así:

| Estado Frappe | Estado en `ordenes_trabajo` |
| --- | --- |
| `Open` | `PENDIENTE` |
| `Replied` | `EN_ATENCION` |
| `Resolved` | `FINALIZADA` |
| `Closed` | `FINALIZADA` |

Cuando el ticket cambia de estado en Frappe, el sondeador actualiza también
`ordenes_trabajo.estado`. Por lo tanto, el estado de Frappe prevalece sobre
cambios manuales hechos directamente en PostgreSQL. Se conservan el técnico y
las fechas de atención.
