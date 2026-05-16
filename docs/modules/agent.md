# Módulo: Agent (`app/agent/`) — Post-MVP

## Qué hace

Chatbot conversacional embebido en la aplicación. Permite a cualquier actor consultar el estado del sistema en lenguaje natural. Implementado con Claude Agent SDK — maneja el loop del agente, tool-calling y sesión de forma automática.

## Estado

**Post-MVP.** No se construye en el hackathon. Se implementa una vez que la base funcional (pipeline + dashboards) esté estable.

---

## Diseño técnico

### Stack
- **Claude Agent SDK** (`claude-agent-sdk`) — `query()` + `create_sdk_mcp_server`
- In-process: las tools corren dentro del proceso FastAPI, sin subprocess separado
- Streaming: el endpoint responde con SSE / chunked response

### Estructura prevista

```
app/agent/
├── tools.py        # @tool definitions + create_sdk_mcp_server
└── handler.py      # Endpoint POST /api/v1/agent/chat
```

### Endpoint

```
POST /api/v1/agent/chat
Body: { "message": string, "session_id": string | null }
Response: streaming text (SSE)
```

### Tools (in-process, llaman directamente al repo layer)

| Tool | Descripción |
|---|---|
| `get_corridor_risks(horizon_hours)` | Corredores en riesgo con forecasts 24/48/72h |
| `get_rerouting_plan(corridor_id)` | Rutas alternativas para un corredor específico |
| `get_health_risk(min_probability)` | Municipios en riesgo de aislamiento con perfil epidemiológico |
| `get_active_alerts()` | Alertas activas en este momento |

### Sesión

- Memoria **por sesión** via `resume=session_id` built-in del SDK
- Al cerrar el chat, la sesión se descarta (sin persistencia cross-session)
- `session_id` generado por el frontend, pasado en cada request

### Comportamiento acordado

- **Read-only** — el agente solo consulta datos, no modifica estado
- **Reactivo** — solo responde cuando el usuario pregunta
- **Agnóstico al actor** — responde con todos los datos disponibles sin filtrar por rol

### Built-in tools del SDK

Los built-in tools de Claude Code (Read, Write, Bash) se deshabilitan explícitamente:

```python
options=ClaudeAgentOptions(
    mcp_servers={"kidbot": kidbot_server},
    allowed_tools=["mcp__kidbot__*"],
    tools=[],  # elimina Read, Write, Bash del contexto
    resume=session_id,
)
```

---

## Variable de entorno requerida

```
ANTHROPIC_API_KEY   — API key de Anthropic para el Agent SDK
```

---

## Queries de ejemplo que el agente puede responder

- *"¿Cuáles corredores tienen más del 80% de probabilidad de cierre en las próximas 48h?"*
- *"¿Qué hospitales quedan aislados si cierra la vía Quito-Guayaquil?"*
- *"Dame las rutas alternativas para el corredor Babahoyo-Guayaquil."*
- *"¿Qué municipios tienen historial de dengue y están en riesgo de aislamiento esta semana?"*
