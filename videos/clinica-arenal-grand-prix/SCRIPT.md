# SCRIPT — clinica-arenal-grand-prix (European Spanish Edition)

**Voice:** Onyx (OpenAI)
**Voice settings:** model tts-1-hd · speed 1.12
**Language:** European Spanish (es-ES)
**Voice direction:** Natural, seguro, cinematográfico, técnico y profundamente humano.
**Mantra:** "Un vídeo de 3 minutos. Contad el proyecto a fondo, para que puedan juzgar creatividad, problem solving y craftsmanship."

---

## Line 1 — El Dilema Clínico y la Arquitectura en Cascada (Frame 1)

**Time:** 0.0 – 22.5s
**Delivery:** Empático, riguroso, planteando el problema y la decisión arquitectónica fundamental.

    Cada mañana, los centros de salud sufren esperas interminables y citas perdidas. Frente a modelos Speech-to-Speech nativos, cuya precisión cae al cuarenta por ciento en tareas clínicas, Clínica Arenal eligió una arquitectura en cascada: transcripción, razonamiento estructurado y síntesis. En sanidad, alucinar citas o coberturas es inadmisible: la cascada garantiza determinismo, auditabilidad y cero alucinaciones en base de datos.

## Line 2 — La Experiencia Dual-Surface y la Latencia Humana (Frame 2)

**Time:** 22.5 – 45.0s
**Delivery:** Dinámico, explicando la pantalla del paciente, PatientTurnStop y Deepgram Nova.

    Diseñamos la experiencia de doble superficie: la pantalla del paciente. Mientras Josefa habla con naturalidad, Deepgram Nova-3 transcribe cada ciento veinte milisegundos y conmuta a Nova-2 ca si detecta catalán. La latencia de dos coma siete segundos es deliberada: PatientTurnStop no corta a pacientes mayores al dictar su DNI, y una frase de espera neutraliza el silencio si una consulta supera segundo y medio.

## Line 3 — Front-Desk Mission Control y Privacidad por Diseño (Frame 3)

**Time:** 45.0 – 66.0s
**Delivery:** Conciso y profesional, demostrando supervisión y protección estricta de datos.

    Al otro lado de la línea, el Front-Desk de recepción no ve una simple transcripción. Observa en tiempo real la verificación del paciente contra el historial clínico, con enmascaramiento estricto grado HIPAA de DNI y teléfono aplicado directamente en el cable. La recepcionista mantiene supervisión continua mientras la agenda se sincroniza al segundo.

## Line 4 — Explicabilidad Total y Selección del LLM (Frame 4)

**Time:** 66.0 – 88.5s
**Delivery:** Técnico y convincente, justificando Gemini 3.8 Flash frente a Groq y modelos pesados.

    En medicina, la inteligencia artificial de caja negra es inaceptable. Elegimos Gemini 3.8 Flash con razonamiento mínimo: frente a Groq, que falla un catorce por ciento en pólizas, o Claude y GPT-4o, con colas de tres segundos, Gemini logra un noventa y siete por ciento de éxito en herramientas con un primer token en quinientos milisegundos. Cada acción es trazable antes de hablar.

## Line 5 — Inteligencia Post-Llamada y Estado Atómico (Frame 5)

**Time:** 88.5 – 110.0s
**Delivery:** Analítico y resolutivo, explicando el commit atómico en el cuelgue y la analítica clínica.

    Al finalizar, el modelo de análisis evalúa la fricción, el coste y la satisfacción. Para evitar dobles reservas si el usuario cuelga o duda, el agente jamás muta la base de datos a mitad de llamada: mantiene un estado atómico en memoria y consolida todas las citas en un único commit durante el cuelgue, con reintentos automáticos si la API hospitalaria se retrasa.

## Line 6 — Resiliencia con Gemelos Digitales: Pipeline A y B (Frame 6)

**Time:** 110.0 – 132.0s
**Delivery:** Experto y artesanal, detallando el testing A/B en pipelines.py y la conmutación instantánea.

    La fiabilidad clínica exige redundancia arquitectónica. En pipelines.py implementamos pruebas A/B en vivo: el Pipeline A ofrece voz bilingüe natural con ElevenLabs Flash v2.5, mientras que el Pipeline B aporta contingencia instantánea con Deepgram Aura-2. Los operadores comparan latencia y sentimiento en tiempo real, con una conmutación transparente en menos de catorce milisegundos.

## Line 7 — Concurrencia Masiva a Escala (Frame 7)

**Time:** 132.0 – 154.0s
**Delivery:** Enérgico y contundente, demostrando robustez bajo carga simultánea.

    En horas punta, Clínica Arenal no deja pacientes en espera. Aquí vemos diez llamadas concurrentes reproduciéndose a velocidad real de producción. Gracias al aislamiento de transacciones SQLite WAL y arquitecturas orientadas a eventos, el sistema gestiona reservas simultáneas de agenda y bloqueos de slots con cero colisiones y una latencia constante de setecientos cuarenta milisegundos.

## Line 8 — Rigor de Ingeniería y Grand Prix (Frame 8)

**Time:** 154.0 – 180.0s
**Delivery:** Solemne, inspirador y concluyente para el jurado del Grand Prix.

    Detrás de esta interfaz late un rigor técnico absoluto: ciento veintisiete tests de agente, setenta y tres evaluaciones de benchmark con ensayos repetidos y compuertas de seguridad en código que derivan emergencias al instante. Creatividad, resolución de problemas y artesanía técnica unidas en salud. Diseñado para clínicos, construido para pacientes y preparado para el Grand Prix.
