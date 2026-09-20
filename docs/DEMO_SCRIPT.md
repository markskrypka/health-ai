# Clínica Arenal — Guía de Despliegue y Ejecución para la Demo

> **Guía operativa paso a paso para arrancar, desplegar y presentar el proyecto ante el jurado.**  
> Equipo: **GING** (Javier, Samer, Mark) · HackSpain 2026 (Prosper Track)

---

## 🗺️ Mapa de Puertos y Servicios

El sistema se compone de 4 servicios coordinados:

| Puerto | Servicio | Rol | Comando |
|---|---|---|---|
| **7860** | `clinic_agent.server:app` | Línea telefónica real (Twilio / Cloudflare Tunnel) | `apps/agent/scripts/restart.sh` |
| **7861** | `clinic_agent.server:app` | Servidor de llamadas web (Dry-Run seguro) | `apps/agent/scripts/demo.sh` |
| **7870** | `clinic_agent.console:app` | Servicio de eventos en tiempo real (SSE) | `apps/agent/scripts/demo.sh` |
| **3100** | Next.js Frontend | Interfaz de operadora (`/desk`) y teléfono web (`/call`) | `apps/agent/scripts/demo.sh` |

---

## 🚀 Despliegue Rápido (Recomendado para la Demo)

### Paso 1: Comprobar Variables de Entorno (`.env`)
Asegúrate de que existe el archivo `.env` en la raíz del repositorio con las claves activas:
```bash
GOOGLE_API_KEY="AIzaSy..."          # Para Gemini Flash
DEEPGRAM_API_KEY="b68b..."          # Para transcripción STT Nova-3 y Aura-2
ELEVENLABS_API_KEY="sk_..."         # Para TTS natural (Pipeline A)
PROSPER_API_KEY="app_..."           # Token del track Prosper
PROSPER_BASE_URL="https://..."      # Endpoint de la API de la clínica
```

---

### Paso 2: Arrancar la Suite de Demo (Un Solo Comando)
Este script levanta en paralelo el servidor web de llamadas (7861), el gestor de eventos SSE (7870) y la aplicación web Next.js (3100):

```bash
apps/agent/scripts/demo.sh
```

**Salida esperada en terminal:**
```text
up: 7861
up: 7870
up: 3100
phone line (7860): {"status":"ok","active_calls":0}

  the caller's screen   http://localhost:3100/call
  the front desk        http://localhost:3100/desk
```

---

### Paso 3: Arrancar / Comprobar la Línea Telefónica Real (Puerto 7860)
Si el jurado va a llamar por teléfono real (Twilio / número público):

1. **Levantar el servidor telefónico:**
   ```bash
   apps/agent/scripts/restart.sh
   ```
2. **Comprobar salud:**
   ```bash
   curl -s http://localhost:7860/health
   # Respuesta: {"status":"ok","active_calls":0}
   ```
3. **Exponer con Cloudflare Tunnel (si no está activo):**
   ```bash
   cloudflared tunnel --url http://localhost:7860
   ```
   *(Copia la URL `https://xxxx.trycloudflare.com` y configúrala en el Webhook de Twilio).*

---

## 💻 Configuración de Pantallas para la Presentación

Para una demo impactante ante el jurado, utiliza **dos pantallas o pestañas**:

1. **Pantalla Principal (Proyector para el Jurado):**
   * URL: `http://localhost:3100/desk`
   * Muestra:
     * Logo oficial de Prosper con el distintivo **Prosper — GING**.
     * Tarjetas de acción en vivo (paciente identificado, seguro, ofertas de huecos).
     * Transcripción en tiempo real y análisis de sentimiento turno a turno.
     * Coste en céntimos acumulado de la llamada.

2. **Segunda Pantalla / Móvil (Dispositivo que llama):**
   * URL: `http://localhost:3100/call`
   * Muestra:
     * Botón de llamada con audio de navegador (WebRTC/micrófono).
     * Formulario que se rellena solo con IA conforme el paciente habla.
     * Calendario interactivo con los huecos disponibles del doctor.

---

## 🧪 Pruebas de Humo (Smoke Test) Antes de Subir al Escenario

Ejecuta estas comprobaciones 5 minutos antes de la presentación:

### 1. Test de Servicios Activos
```bash
curl -s http://localhost:7860/health && echo ""
curl -s http://localhost:7861/health && echo ""
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3100/desk
```
*Los tres deben responder código 200.*

### 2. Test de Llamada Sintética Local (Sin hablar por micro)
Para verificar que el pipeline completo (Gemini + STT + Tools) funciona sin tocar el navegador:
```bash
PYTHONPATH=apps/agent/src .venv/bin/python apps/agent/scripts/local_call.py
```

### 3. Test de Benchmark de Latencia
Si el jurado pregunta por el rendimiento o queréis mostrar datos empíricos:
```bash
PYTHONPATH=apps/agent/src .venv/bin/python scripts/measure_latency.py
```
*Muestra latencia mediana de **2.79s** y mínima de **2.12s**.*

---

## 🛠️ Resolución Rápida de Incidencias (Cheat Sheet)

### Caso 1: Un puerto está ocupado (EADDRINUSE / 7860 / 7861 / 3100)
Si algún proceso anterior quedó colgado en segundo plano:
```bash
# Matar procesos en los puertos de la demo:
lsof -ti:7860,7861,7870,3100 | xargs kill -9 2>/dev/null || true

# Reejecutar el arranque:
apps/agent/scripts/demo.sh
```

### Caso 2: El navegador no captura el micrófono en `/call`
* Asegúrate de abrir `http://localhost:3100/call` (los navegadores bloquean el micrófono en IPs que no sean `localhost` a menos que tengan HTTPS).
* Revisa los permisos de micrófono en la barra de direcciones (icono del candado).

### Caso 3: Reiniciar el servidor telefónico limpio
```bash
apps/agent/scripts/restart.sh
```
*(Espera de forma segura a que no haya llamadas activas antes de reiniciar).*

---

## 📞 Casos de Prueba Recomendados para la Demo

1. **Cita estándar con cambio de opinión:**
   * *"Hola, soy Josefa Domínguez Navarro. Necesito cita con el médico de cabecera lo antes posible."*
   * *El bot ofrece cita el lunes por la mañana.*
   * *"Uy, por la mañana no puedo, ¿tienes por la tarde? Y por cierto, tengo Mapfre."*
   * *El bot cambia atómicamente la cita a la tarde verificando la cobertura.*

2. **Desambiguación de médicos homónimos:**
   * *"Quiero cita con el doctor Iglesias."*
   * *El bot detecta la ambigüedad (Dra. Carmen Iglesias en Dermatología vs. Dr. Marcos Iglesia en Traumatología) y pregunta cuál busca.*

3. **Parada de emergencia (Triaje 112 Hard-Lock):**
   * *"Tengo una opresión muy fuerte en el pecho y me cuesta respirar..."*
   * *El bot corta en seco cualquier gestión de cita, ordena con voz firme llamar de inmediato al 112 y cuelga registrando el evento de auditoría.*

---

## 👥 Equipo GING

* **Javier**, **Samer**, y **Mark**
* HackSpain 2026 · Prosper Track
* Arquitectura: [docs/architecture_diagram.jpg](architecture_diagram.jpg)
* Latencia: [docs/LATENCY_BENCHMARK.json](LATENCY_BENCHMARK.json)
