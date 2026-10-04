import os
import requests
import psycopg
from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

FRAPPE_URL = os.getenv("FRAPPE_URL", "").rstrip("/")
FRAPPE_API_KEY = os.getenv("FRAPPE_API_KEY", "")
FRAPPE_API_SECRET = os.getenv("FRAPPE_API_SECRET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

PRIORIDADES = {
    "BAJA": "BAJA",
    "LOW": "BAJA",
    "MEDIA": "MEDIA",
    "MEDIUM": "MEDIA",
    "ALTA": "ALTA",
    "HIGH": "ALTA",
    "URGENTE": "URGENTE",
    "URGENT": "URGENTE",
}

ESTADOS_FRAPPE = {
    "OPEN": "PENDIENTE",
    "REPLIED": "EN_ATENCION",
    "RESOLVED": "FINALIZADA",
    "CLOSED": "FINALIZADA",
}


def normalizar_orden(payload):
    campos = {
        "id_pqr": payload.get("name"),
        "tipo_servicio": payload.get("tipo_servicio"),
        "descripcion": payload.get("descripcion"),
        "direccion": payload.get("direccion"),
        "prioridad": payload.get("prioridad", "MEDIA"),
        "estado": normalizar_estado_frappe(payload.get("estado_frappe")),
    }

    for campo in ("id_pqr", "tipo_servicio", "descripcion", "direccion"):
        valor = campos[campo]
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(f"El campo '{campo}' es obligatorio y debe ser texto.")
        campos[campo] = valor.strip()

    limites = {"id_pqr": 30, "tipo_servicio": 100, "direccion": 200}
    for campo, limite in limites.items():
        if len(campos[campo]) > limite:
            raise ValueError(f"El campo '{campo}' no puede superar {limite} caracteres.")

    prioridad = campos["prioridad"]
    if not isinstance(prioridad, str) or prioridad.strip().upper() not in PRIORIDADES:
        raise ValueError("La prioridad debe ser BAJA, MEDIA, ALTA o URGENTE.")
    campos["prioridad"] = PRIORIDADES[prioridad.strip().upper()]
    return campos


def normalizar_estado_frappe(estado):
    if not isinstance(estado, str) or estado.strip().upper() not in ESTADOS_FRAPPE:
        raise ValueError(
            "El estado de Frappe debe ser Open, Replied, Resolved o Closed."
        )
    return ESTADOS_FRAPPE[estado.strip().upper()]


def guardar_ordenes(ordenes):
    if not DATABASE_URL:
        raise RuntimeError("La variable DATABASE_URL no está configurada.")
    if not ordenes:
        return

    with psycopg.connect(DATABASE_URL) as conexion:
        with conexion.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO ordenes_trabajo
                    (id_pqr, tipo_servicio, descripcion, direccion, prioridad, estado)
                VALUES
                    (%(id_pqr)s, %(tipo_servicio)s, %(descripcion)s,
                     %(direccion)s, %(prioridad)s, %(estado)s)
                ON CONFLICT (id_pqr) DO UPDATE SET
                    tipo_servicio = EXCLUDED.tipo_servicio,
                    descripcion = EXCLUDED.descripcion,
                    direccion = EXCLUDED.direccion,
                    prioridad = EXCLUDED.prioridad,
                    estado = EXCLUDED.estado
                """,
                ordenes,
            )


def obtener_pqrs():
    if not FRAPPE_URL or not FRAPPE_API_KEY or not FRAPPE_API_SECRET:
        raise RuntimeError("Faltan variables de entorno de Frappe.")

    r = requests.get(
        f"{FRAPPE_URL}/api/resource/HD%20Ticket",
        headers={"Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}"},
        params={
            "fields": '["name","subject","status","priority","creation"]',
            "order_by": "creation desc",
            "limit_page_length": 100
        },
        timeout=20
    )
    r.raise_for_status()
    return r.json().get("data", [])

@app.route("/")
def inicio():
    try:
        return render_template("index.html", pqrs=obtener_pqrs(), error=None)
    except Exception as e:
        return render_template("index.html", pqrs=[], error=str(e))

@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
