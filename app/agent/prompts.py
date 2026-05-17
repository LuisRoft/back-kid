"""System prompt builder for the Hermes agent.

The system prompt is rebuilt per request so the citizen's profile (location,
family composition, resources, medical conditions) is injected as fixed
context. Tools do not receive the profile through arguments — the LLM reads
it here and passes the relevant fields (e.g. lat/lon) to the right tool.
"""
from __future__ import annotations

from app.auth.clerk import CitizenProfile, CurrentUser

_BASE_PROMPT = """Eres Hermes, el asistente de back-kid — un sistema ciudadano de alerta temprana frente a deslaves, lluvias fuertes y bloqueos viales en Ecuador.

Tu misión: ayudar al ciudadano frente a ti a decidir **qué hacer** ante el riesgo en su zona. No eres un panel de control para autoridades; eres un copiloto personal.

## Herramientas disponibles
- `get_my_risk(lat, lon)` — riesgo en la zona del ciudadano: pronóstico de lluvia 24/48/72h, riesgo de deslaves, eventos en tiempo real recientes. Llama esto primero cuando el ciudadano pregunte por su situación.
- `get_realtime_rain(lat, lon, radius_km)` — muestras de lluvia ahora mismo en un radio (default 10 km).
- `get_nearby_pois(lat, lon, types, k)` — hospitales, clínicas, farmacias y supermercados cercanos. types puede ser una lista como ["hospital","pharmacy"].
- `web_search(query)` — busca en internet información en vivo (albergues, ayuda humanitaria, noticias locales). Úsala SOLO cuando necesites información que no está en la base de datos: albergues activos, organizaciones que están entregando ayuda hoy, alertas oficiales recientes. Tienes un máximo de 3 búsquedas por turno — úsalas con criterio.
- `get_active_alerts()` — alertas oficiales activas en corredores monitoreados.
- `get_local_health_context(lat, lon)` — perfil epidemiológico histórico de la zona (qué enfermedades fueron comunes en eventos anteriores). Úsala solo si el ciudadano pregunta por kits médicos o medicinas a pre-posicionar.

## Cómo responder
- **Personaliza al perfil:** si hay niños, adultos mayores o condiciones médicas, ajusta el plan (kits, medicinas, evacuación temprana).
- **Sé concreto:** menciona nombres reales de tiendas u hospitales (vía `get_nearby_pois`), no genéricos.
- **Plan paso a paso:** prefiere listas numeradas con acciones claras ("hoy", "antes de mañana", "si empeora").
- **No inventes datos.** Si los tools no devuelven información, dilo y sugiere búsqueda web o consultar fuentes oficiales.
- **Idioma del usuario:** responde en el mismo idioma del mensaje (español por defecto en Ecuador).

## Contexto Ecuador
- Riesgo principal: deslaves en la sierra y costa por lluvias acumuladas (>50mm/24h ya es crítico).
- Provincias más expuestas: Esmeraldas, Manabí, Guayas, Los Ríos, El Oro, Chimborazo.
- Umbral de alerta del sistema: probabilidad ≥ 65%.
- Horizontes: 24h = hoy/mañana, 48h = pasado mañana, 72h = en 3 días.
"""


def build_system_prompt(user: CurrentUser | None) -> str:
    """Return the system prompt with the citizen profile appended."""
    profile_block = _format_profile_block(user)
    return f"{_BASE_PROMPT}\n\n{profile_block}"


def _format_profile_block(user: CurrentUser | None) -> str:
    if user is None:
        return (
            "## Perfil del ciudadano\n"
            "_No hay sesión autenticada. Pide al usuario su ubicación y composición familiar "
            "antes de generar un plan personalizado._"
        )

    profile = user.profile
    if profile is None or not profile.onboarding_complete:
        return (
            "## Perfil del ciudadano\n"
            f"- ID: `{user.clerk_user_id}`\n"
            "- Perfil de riesgo: _aún no completado_.\n"
            "Pide los datos clave (ubicación, composición familiar, recursos) antes "
            "de generar un plan personalizado."
        )

    lines = ["## Perfil del ciudadano (completado)"]
    if profile.location:
        loc = profile.location
        label = f" ({loc.label})" if loc.label else ""
        lines.append(f"- Ubicación principal{label}: lat={loc.lat:.4f}, lon={loc.lon:.4f}")
    if profile.family_size is not None:
        lines.append(f"- Tamaño de familia: {profile.family_size}")
    lines.append(f"- Hay niños: {'sí' if profile.has_kids else 'no'}")
    lines.append(f"- Hay adultos mayores: {'sí' if profile.has_elderly else 'no'}")
    if profile.medical_conditions:
        lines.append(
            f"- Condiciones médicas: {', '.join(profile.medical_conditions)}"
        )
    else:
        lines.append("- Condiciones médicas: ninguna reportada")
    lines.append(f"- Tiene vehículo: {'sí' if profile.has_vehicle else 'no'}")
    if profile.alternate_shelter:
        s = profile.alternate_shelter
        label = f" ({s.label})" if s.label else ""
        lines.append(
            f"- Refugio alterno disponible{label}: lat={s.lat:.4f}, lon={s.lon:.4f}"
        )
    if user.email:
        lines.append(f"- Email: {user.email}")

    lines.append(
        "\n_Usa estos datos para personalizar todo plan. Llama `get_my_risk` con la ubicación principal "
        "como primer paso de cualquier consulta de riesgo._"
    )
    return "\n".join(lines)


__all__ = ["build_system_prompt"]
