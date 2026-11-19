"""SmartEdu AI: backend Python con Gemini/Gemma, Groq y actividad de Filosofía."""
import os
import re
from dotenv import load_dotenv
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
for env_candidate in [
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
    BASE_DIR / ".env.txt",
    BASE_DIR.parent / ".env.txt",
]:
    if env_candidate.is_file():
        load_dotenv(env_candidate, override=True)
load_dotenv(override=True)


def get_clean_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip().strip('"').strip("'")


app = FastAPI(title="SmartEdu AI", version="2.9.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
PROMPTS = BASE_DIR / "prompts"
CONTEXTS = BASE_DIR / "contexts"


class StudyRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    sourceText: str = Field(default="", max_length=12000)
    workType: Literal["summary", "assignment"] = "summary"
    mode: Literal["simple", "context"] = "simple"
    activity: str = "resumen"
    customInstructions: str = Field(default="", max_length=4000)


class GradeRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    studentText: str = Field(min_length=1, max_length=12000)
    instructions: str = Field(default="", max_length=3000)
    mode: Literal["simple", "context"] = "simple"
    activity: str = "evaluacion-resumen"
    customInstructions: str = Field(default="", max_length=4000)


class AIResponse(BaseModel):
    mode: str
    provider: str
    result: str
    promptUsed: str


def render(template: str, **fields: str) -> str:
    file = PROMPTS / template
    if not file.is_file():
        return (
            f"Tema: {fields.get('TOPIC', '')}\n"
            f"Material: {fields.get('SOURCE', '')}\n"
            f"Contenido: {fields.get('STUDENT_TEXT', fields.get('DESCRIPTION', ''))}"
        )
    text = file.read_text(encoding="utf-8")
    for key, value in fields.items():
        text = text.replace("{{" + key + "}}", value)
    return text


ACTIVITY_NAMES = {
    "alumno": {
        "resumen": "Resumen",
        "ensayo": "Ensayo",
        "cuestionario": "Cuestionario",
        "guia-estudio": "Guía de estudio",
        "filosofia": "Filosofía",
        "personalizada": "Tarea personalizada",
    },
    "docente": {
        "evaluacion-resumen": "Evaluar resumen",
        "rubrica": "Evaluación con rúbrica",
        "retroalimentacion": "Retroalimentación",
        "personalizada": "Tarea personalizada",
    },
}


def list_activities(module: str):
    if module not in ACTIVITY_NAMES:
        raise HTTPException(404, detail="Módulo desconocido")
    return [
        {"id": key, "name": name}
        for key, name in ACTIVITY_NAMES[module].items()
        if (CONTEXTS / module / f"{key}.md").is_file()
    ]


def context_from_md(module: str, activity: str, fields: dict[str, str]) -> str:
    if module not in ACTIVITY_NAMES or activity not in ACTIVITY_NAMES[module]:
        raise HTTPException(400, detail="Actividad no permitida")
    file = CONTEXTS / module / f"{activity}.md"
    if not file.is_file():
        return (
            f"Elabora una actividad de tipo {activity} sobre {fields.get('TOPIC', '')}.\n"
            f"Material de apoyo: {fields.get('SOURCE', '')}\n"
            f"Instrucciones: {fields.get('CUSTOM', '')}"
        )
    template = file.read_text(encoding="utf-8")

    def replace(match):
        return fields.get(match.group(1), "")

    return re.sub(r"\{\{([A-Z_]+)\}\}", replace, template)


@app.get("/api/activities/{module}")
def activities(module: str):
    return list_activities(module)


def has_valid_gemini() -> bool:
    key = get_clean_env("GEMINI_API_KEY")
    return bool(key) and "PEGA_AQUI" not in key and "TU_CLAVE" not in key


def has_valid_groq() -> bool:
    key = get_clean_env("GROQ_API_KEY")
    return bool(key) and "PEGA_AQUI" not in key and "TU_CLAVE" not in key and "..." not in key


def has_any_ai_key() -> bool:
    return has_valid_gemini() or has_valid_groq()


async def call_gemini(client: httpx.AsyncClient, prompt: str, max_tokens: int) -> str:
    api_key = get_clean_env("GEMINI_API_KEY")
    if not has_valid_gemini():
        raise RuntimeError("Falta GEMINI_API_KEY válida")

    primary_model = get_clean_env("GEMINI_MODEL", "gemini-3.5-flash-lite").removeprefix("models/")
    thinking_level = get_clean_env("GEMINI_THINKING_LEVEL", "MINIMAL").upper()
    try:
        temperature = float(get_clean_env("GEMINI_TEMPERATURE", "0.4"))
    except ValueError:
        temperature = 0.4

    models_to_try = list(dict.fromkeys([primary_model, "gemma-4-26b-a4b-it"]))[:2]
    last_error = "Sin respuesta de Gemini"

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        base_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max(max_tokens, 2048),
        }
        gen_config = dict(base_config)
        if thinking_level in {"MINIMAL", "LOW", "MEDIUM", "HIGH"} and "gemma" not in model.lower():
            gen_config["thinkingConfig"] = {"thinkingLevel": thinking_level}

        for attempt in range(2):
            current_config = gen_config if attempt == 0 else base_config
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": current_config,
            }
            try:
                response = await client.post(url, headers={"x-goog-api-key": api_key}, json=payload)
                if response.status_code == 400 and "thinkingConfig" in current_config and attempt == 0:
                    continue
                if response.status_code >= 400:
                    last_error = f"Gemini ({model}) HTTP {response.status_code}: {response.text[:150]}"
                    print(f"[ERROR GEMINI] {last_error}")
                    break

                data = response.json()
                parts = data["candidates"][0]["content"]["parts"]
                result = "\n".join(
                    part["text"] for part in parts if "text" in part and not part.get("thought", False)
                ).strip()
                if not result:
                    last_error = f"Gemini ({model}) devolvió texto vacío"
                    print(f"[ERROR GEMINI] {last_error}")
                    break

                print(f"[OK GEMINI] Respondido con {model}")
                return result
            except Exception as exc:
                last_error = f"Gemini ({model}) {type(exc).__name__}: {exc}"
                print(f"[ERROR GEMINI] {last_error}")
                break

    raise RuntimeError(last_error)


async def call_groq(client: httpx.AsyncClient, prompt: str, max_tokens: int) -> str:
    api_key = get_clean_env("GROQ_API_KEY")
    if not has_valid_groq():
        raise RuntimeError("Falta GROQ_API_KEY válida en .env")

    primary_model = get_clean_env("GROQ_MODEL", "openai/gpt-oss-20b")
    base_url = get_clean_env("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    try:
        temperature = float(get_clean_env("GROQ_TEMPERATURE", "0.4"))
    except ValueError:
        temperature = 0.4

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SmartEduAI/2.9",
    }

    models_to_try = list(dict.fromkeys([primary_model, "openai/gpt-oss-120b"]))[:2]
    last_error = "Sin respuesta de Groq"

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max(max_tokens, 2048),
        }
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            if response.status_code >= 400:
                last_error = f"Groq ({model}) HTTP {response.status_code}: {response.text[:150]}"
                print(f"[ERROR GROQ] {last_error}")
                continue

            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            if not result:
                last_error = f"Groq ({model}) devolvió texto vacío"
                continue

            print(f"[OK GROQ] Respondido con {model}")
            return result
        except Exception as exc:
            last_error = f"Groq ({model}) {type(exc).__name__}: {exc}"
            print(f"[ERROR GROQ] {last_error}")

    raise RuntimeError(last_error)


async def generate(prompt: str, max_tokens: int) -> tuple[str, str]:
    default_primary = get_clean_env("AI_PROVIDER", "gemini").lower()
    raw_order = get_clean_env("AI_PROVIDER_ORDER", f"{default_primary},groq,gemini").lower()
    providers = [p.strip() for p in raw_order.split(",") if p.strip() in {"gemini", "groq"}]
    if not providers:
        providers = ["gemini", "groq"]

    errors: list[str] = []
    timeout_cfg = httpx.Timeout(35.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout_cfg, verify=False) as client:
        for provider in dict.fromkeys(providers):
            try:
                if provider == "gemini":
                    if not has_valid_gemini():
                        print("[AVISO] GEMINI_API_KEY no configurada correctamente en .env")
                        continue
                    return await call_gemini(client, prompt, max_tokens), "gemini"
                if provider == "groq":
                    if not has_valid_groq():
                        print("[AVISO] GROQ_API_KEY no configurada correctamente en .env")
                        continue
                    return await call_groq(client, prompt, max_tokens), "groq"
            except Exception as exc:
                errors.append(str(exc))
                print(f"[FALLBACK] {provider} falló -> pasando al siguiente proveedor...")

    detail = " | ".join(errors) if errors else "No hay claves válidas configuradas en .env"
    raise HTTPException(status_code=502, detail=detail)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": "real" if has_any_ai_key() else "demo",
        "providerOrder": get_clean_env("AI_PROVIDER_ORDER", "gemini,groq"),
        "gemini": {
            "active": has_valid_gemini(),
            "models": list(dict.fromkeys([get_clean_env("GEMINI_MODEL", "gemini-3.5-flash-lite"), "gemma-4-26b-a4b-it"]))[:2],
        },
        "groq": {
            "active": has_valid_groq(),
            "model": get_clean_env("GROQ_MODEL", "openai/gpt-oss-20b"),
        },
    }


@app.get("/api/test")
async def test_providers():
    """Prueba en vivo Gemini/Gemma y Groq."""
    report = {}
    timeout_cfg = httpx.Timeout(35.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout_cfg, verify=False) as client:
        try:
            res = await call_gemini(client, "Responde solo: OK Gemini", 50)
            report["gemini"] = {"ok": True, "response": res}
        except Exception as exc:
            report["gemini"] = {"ok": False, "error": str(exc)}

        try:
            res = await call_groq(client, "Responde solo: OK Groq", 50)
            report["groq"] = {"ok": True, "response": res}
        except Exception as exc:
            report["groq"] = {"ok": False, "error": str(exc)}
    return report


@app.post("/api/study/generate", response_model=AIResponse)
async def study(input: StudyRequest):
    if input.mode == "context":
        prompt = context_from_md(
            "alumno",
            input.activity,
            {
                "TOPIC": input.topic,
                "SOURCE": input.sourceText or "Sin material de apoyo",
                "CUSTOM": input.customInstructions or "Sin instrucciones adicionales",
            },
        )
    else:
        prompt = f"Elabora una actividad académica ({input.activity}) sobre: {input.topic}."

    if not has_any_ai_key():
        result = (
            f"SIMULACIÓN SIN IA REAL — {input.topic}\n\nIdea principal: define el concepto y explica sus aplicaciones."
            if input.mode == "context"
            else f"SIMULACIÓN SIN IA REAL — {input.topic} es un tema importante."
        )
        return AIResponse(mode=input.mode, provider="demo", result=result, promptUsed=prompt)

    result, used_provider = await generate(prompt, 1100)
    return AIResponse(mode=input.mode, provider=used_provider, result=result, promptUsed=prompt)


@app.post("/api/grade/evaluate", response_model=AIResponse)
async def grade(input: GradeRequest):
    if input.mode == "context":
        prompt = context_from_md(
            "docente",
            input.activity,
            {
                "TOPIC": input.topic,
                "STUDENT_TEXT": input.studentText,
                "INSTRUCTIONS": input.instructions or "Sin instrucciones originales",
                "CUSTOM": input.customInstructions or "Sin instrucciones adicionales",
            },
        )
    else:
        prompt = f"Evalúa de forma general el siguiente trabajo sobre {input.topic}:\n{input.studentText}"

    if not has_any_ai_key():
        return AIResponse(mode=input.mode, provider="demo", result="SIMULACIÓN SIN IA REAL", promptUsed=prompt)

    result, used_provider = await generate(prompt, 1600)
    return AIResponse(mode=input.mode, provider=used_provider, result=result, promptUsed=prompt)


class IncidentRequest(BaseModel):
    description: str = Field(min_length=5, max_length=6000)
    mode: Literal["simple", "context"] = "simple"


INCIDENT_RULES = {
    "seguridad": ["phishing", "contraseña robada", "acceso no autorizado", "malware", "virus", "ransomware", "cuenta comprometida"],
    "red": ["wifi", "wi-fi", "internet", "vpn", "conexión", "red", "latencia"],
    "hardware": ["impresora", "pantalla", "teclado", "disco duro", "batería", "monitor", "laptop"],
    "software": ["aplicación", "sistema", "error", "login", "inicio de sesión", "software", "actualización"],
}


def demo_incident(description: str, mode: str) -> str:
    import unicodedata

    def normalize(value: str) -> str:
        return "".join(ch for ch in unicodedata.normalize("NFD", value.lower()) if unicodedata.category(ch) != "Mn")

    text = normalize(description)
    matches = {category: sum(normalize(word) in text for word in words) for category, words in INCIDENT_RULES.items()}
    category = max(matches, key=matches.get) if any(matches.values()) else "sin clasificar"
    return f"SIMULACIÓN LOCAL (reglas, no IA)\nCategoría probable: {category}"


@app.post("/api/incidents/classify", response_model=AIResponse)
async def classify_incident(input: IncidentRequest):
    prompt = render("incident-with-context.txt" if input.mode == "context" else "incident-without-context.txt", DESCRIPTION=input.description)
    if not has_any_ai_key():
        return AIResponse(mode=input.mode, provider="demo-reglas", result=demo_incident(input.description, input.mode), promptUsed=prompt)
    result, used_provider = await generate(prompt, 1100)
    return AIResponse(mode=input.mode, provider=used_provider, result=result, promptUsed=prompt)