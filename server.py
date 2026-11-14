"""
PAPOLTICA - Servidor (Python / Flask)

Sirve la página web y conecta con Grok (gratis vía OpenRouter, o xAI).
Ejecutar:  python server.py
"""

import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

# ======================================
# 1. CONFIGURACIÓN DEL SERVIDOR
# ======================================

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

PORT = int(os.environ.get("PORT", 3000))
# Por defecto usa Grok gratis a través de OpenRouter.
# Para usar la API oficial de xAI: API_URL=https://api.x.ai/v1 y MODELO=grok-4.7
API_URL = os.environ.get("API_URL", "https://openrouter.ai/api/v1").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")
MODELO = os.environ.get("MODELO", "x-ai/grok-4.1-fast:free")

# Solo se publica la carpeta "public"; el código del servidor y el .env quedan fuera.
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024  # 100 KB


# ======================================
# 2. PÁGINA PRINCIPAL
# ======================================

@app.get("/")
@app.get("/inicio")
def pagina_principal():
    return send_from_directory(PUBLIC_DIR, "index.html")


# ======================================
# 3. IDENTIDAD DE PAPOLTICA
# ======================================

INSTRUCCIONES_PAPOLTICA = """
Eres PAPOLTICA, una tutora inteligente de matemáticas
y ciencias.

Tu objetivo es ayudar al estudiante a comprender,
razonar y resolver problemas por sí mismo.

PERSONALIDAD:
- Paciente, amable y motivadora.
- Natural y cercana, sin exagerar.
- Nunca hagas sentir mal al estudiante.
- Utiliza palabras sencillas.
- Adapta tus explicaciones a su nivel.

REGLAS GENERALES:
1. No des respuestas innecesariamente largas.
2. Haz solamente una pregunta por respuesta.
3. Evita introducciones largas.
4. No utilices títulos innecesarios.
5. No repitas información que el estudiante ya conoce.
6. Utiliza el historial para continuar la conversación.
7. No reinicies un ejercicio que ya está en proceso.

MODO ASISTENTE IA:

Cuando el estudiante presente un ejercicio nuevo:
- Identifica qué necesita resolver.
- Dale una pista pequeña.
- Haz una pregunta que lo ayude a pensar.
- Espera su respuesta.

Cuando responda correctamente:
- Felicítalo brevemente.
- Explica por qué su respuesta es correcta.
- Continúa con el siguiente paso mediante otra pregunta.

Cuando se equivoque:
- No le des inmediatamente la respuesta.
- Explícale qué debe revisar.
- Proporciona una pista diferente.
- Vuelve a preguntarle.

Cuando no comprenda:
- Utiliza palabras más sencillas.
- Explica con un ejemplo cotidiano.
- Comprueba si entendió.

Si solicita la solución completa:
- Puedes mostrarla.
- Explica cada paso de manera sencilla.

MODO APRENDIZAJE:

Cuando el estudiante quiera aprender un tema desde cero:

1. Comienza con una explicación sencilla.
2. Presenta los conceptos importantes.
3. Explica las fórmulas necesarias, si existen.
4. Muestra un ejemplo resuelto paso a paso.
5. Haz una pregunta para comprobar su comprensión.
6. Después propón un ejercicio para practicar.

No presentes toda la información de golpe.
Avanza por pequeñas partes y espera la participación
del estudiante.

CONTINUIDAD:

- Recuerda el ejercicio actual.
- Utiliza las respuestas anteriores.
- Continúa desde el último paso.
- No confundas una respuesta nueva con un ejercicio anterior.

REGLA PRINCIPAL:

Tu función no es solamente resolver ejercicios.
Tu función es enseñar al estudiante a resolverlos.
"""

INSTRUCCIONES_APRENDIZAJE = """
MODO ACTIVO: APRENDIZAJE.

El estudiante quiere aprender el tema: {tema}.

Enséñale desde cero.
Comienza con una explicación sencilla y breve.
Avanza gradualmente por conceptos y ejemplos.
Comprueba su comprensión con preguntas.
No avances demasiado rápido.
"""

INSTRUCCIONES_ASISTENTE = """
MODO ACTIVO: ASISTENTE IA.

El tema seleccionado es: {tema}.

El estudiante puede presentar ejercicios o dudas.
Guíalo mediante preguntas y pistas.
No resuelvas todo de inmediato.
Continúa desde el último mensaje de la conversación.
"""


# ======================================
# 4. ESTADO DEL SERVIDOR
# ======================================

@app.get("/api/estado")
def estado():
    return jsonify(
        funcionando=True,
        mensaje="PAPOLTICA está conectada.",
        modelo=MODELO,
    )


# ======================================
# 5. VALIDACIONES
# ======================================

def error(mensaje, codigo=400):
    return jsonify(error=mensaje), codigo


def validar_historial(historial):
    """Devuelve un mensaje de error, o None si el historial es válido."""
    if not isinstance(historial, list) or not 0 < len(historial) <= 20:
        return "La conversación no es válida."

    for mensaje in historial:
        if (
            not isinstance(mensaje, dict)
            or mensaje.get("role") not in ("user", "assistant")
            or not isinstance(mensaje.get("content"), str)
            or not mensaje["content"].strip()
            or len(mensaje["content"]) > 4000
        ):
            return "Uno de los mensajes no es válido."

    # Los roles deben alternar: user, assistant, user, ...
    for i, mensaje in enumerate(historial):
        esperado = "user" if i % 2 == 0 else "assistant"
        if mensaje["role"] != esperado:
            return "El orden de la conversación no es válido."

    if historial[-1]["role"] != "user":
        return "Se esperaba un mensaje del estudiante."

    return None


# ======================================
# 6. CONEXIÓN CON LA INTELIGENCIA ARTIFICIAL
# ======================================

@app.post("/api/tutor")
def tutor():
    try:
        datos = request.get_json(silent=True) or {}

        tema = datos.get("tema")
        historial = datos.get("historial")
        modo = datos.get("modo") or "asistente"

        if not isinstance(tema, str) or not tema.strip() or len(tema) > 100:
            return error("Selecciona un tema válido.")

        if modo not in ("aprendizaje", "asistente"):
            return error("El modo seleccionado no es válido.")

        problema = validar_historial(historial)
        if problema:
            return error(problema)

        plantilla = (
            INSTRUCCIONES_APRENDIZAJE
            if modo == "aprendizaje"
            else INSTRUCCIONES_ASISTENTE
        )

        mensajes = [
            {
                "role": "system",
                "content": INSTRUCCIONES_PAPOLTICA + plantilla.format(tema=tema),
            },
            *[
                {"role": m["role"], "content": m["content"]}
                for m in historial
            ],
        ]

        # ----- Enviar a Grok -----

        if not API_KEY:
            return error(
                "Falta la clave de la API. Agrega API_KEY en el archivo .env.",
                500,
            )

        respuesta = requests.post(
            f"{API_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
                "X-Title": "PAPOLTICA",
            },
            timeout=120,
            json={
                "model": MODELO,
                "messages": mensajes,
                "temperature": 0.3,
                "max_tokens": 1000,
            },
        )

        if respuesta.status_code == 429:
            return error(
                "Se alcanzó el límite gratuito de uso. "
                "Espera un momento e inténtalo de nuevo.",
                429,
            )

        if not respuesta.ok:
            raise RuntimeError(
                f"La API respondió con el estado {respuesta.status_code}: "
                f"{respuesta.text[:200]}"
            )

        opciones = respuesta.json().get("choices") or []
        contenido = ((opciones[0] if opciones else {}).get("message") or {}).get(
            "content"
        )

        if not isinstance(contenido, str) or not contenido.strip():
            raise RuntimeError("Grok no devolvió una respuesta válida.")

        return jsonify(respuesta=contenido, modo=modo, tema=tema)

    except requests.Timeout:
        print("Error en PAPOLTICA: tiempo de espera agotado.")
        return error("La respuesta tardó demasiado. Inténtalo nuevamente.", 500)

    except Exception as e:  # noqa: BLE001
        print(f"Error en PAPOLTICA: {e}")
        return error(
            "No se pudo conectar con PAPOLTICA. Comprueba tu conexión, "
            "tu clave API_KEY y el nombre del modelo.",
            500,
        )


@app.errorhandler(413)
def demasiado_grande(_):
    return error("El mensaje es demasiado grande.", 413)


# ======================================
# 7. INICIAR SERVIDOR
# ======================================

if __name__ == "__main__":
    print("----------------------------------")
    print(" PAPOLTICA está funcionando")
    print(f" http://localhost:{PORT}")
    print(f" Modelo: {MODELO}")
    print("----------------------------------")
    app.run(host="0.0.0.0", port=PORT)
