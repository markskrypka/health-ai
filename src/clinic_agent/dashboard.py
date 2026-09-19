"""Live Console & Observability Dashboard for Clínica Arenal Voice Agent.

Provides a real-time visual control room for jury demonstrations and live monitoring:
- Live call audio/pipeline status and duration counter
- Turn-by-turn live transcript (caller vs agent)
- Live tool calls timeline with execution latency and payloads
- Identified patient card with chart notes and previous history
- Submitted decisions and actions
- Post-call audit log inspector
"""

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from . import config, session

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clínica Arenal — Voice Agent Live Control Room</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --surface: #111827;
      --surface-border: #1f293d;
      --surface-hover: #172136;
      --primary: #0ea5e9;
      --primary-glow: rgba(14, 165, 233, 0.18);
      --secondary: #6366f1;
      --accent-green: #10b981;
      --accent-green-bg: rgba(16, 185, 129, 0.12);
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --font: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      height: 100vh;
      max-height: 100vh;
      overflow: hidden;
      background-color: var(--bg);
      color: var(--text-main);
      font-family: var(--font);
    }
    body {
      display: flex;
      flex-direction: column;
    }

    /* Top Navigation Bar */
    header {
      flex-shrink: 0;
      height: 70px;
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--surface-border);
      padding: 0.85rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 50;
      box-sizing: border-box;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }

    .logo-badge {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--primary), var(--secondary));
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.25rem;
      box-shadow: 0 0 20px var(--primary-glow);
    }

    .brand-title {
      font-size: 1.2rem;
      font-weight: 600;
      letter-spacing: -0.01em;
    }

    .brand-sub {
      font-size: 0.78rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.35rem 0.85rem;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 500;
      background: var(--surface);
      border: 1px solid var(--surface-border);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--text-dim);
    }

    .status-dot.active {
      background: var(--accent-green);
      box-shadow: 0 0 10px var(--accent-green);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.25); opacity: 0.7; }
      100% { transform: scale(1); opacity: 1; }
    }

    /* Main Grid Layout - Fixed to Viewport */
    main {
      flex: 1 1 0;
      min-height: 0;
      max-height: calc(100vh - 70px);
      display: grid;
      grid-template-columns: 320px 1fr 380px;
      grid-template-rows: 100%;
      gap: 1.25rem;
      padding: 1.25rem 2rem;
      overflow: hidden;
      box-sizing: border-box;
    }

    @media (max-width: 1200px) {
      html, body {
        overflow: auto;
        height: auto;
        max-height: none;
      }
      main {
        grid-template-columns: 1fr;
        grid-template-rows: auto;
        height: auto;
        max-height: none;
        overflow-y: visible;
      }
      .panel {
        height: 550px !important;
      }
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 14px;
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 0;
      max-height: 100%;
      min-width: 0;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }

    .panel-header {
      flex-shrink: 0;
      padding: 0.9rem 1.15rem;
      border-bottom: 1px solid var(--surface-border);
      font-size: 0.88rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(255,255,255,0.015);
    }

    .panel-body {
      flex: 1 1 0;
      min-height: 0;
      min-width: 0;
      padding: 1.15rem;
      overflow-y: auto;
      overflow-x: hidden;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    /* Clean Dark Scrollbars */
    .panel-body::-webkit-scrollbar {
      width: 6px;
    }
    .panel-body::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.1);
    }
    .panel-body::-webkit-scrollbar-thumb {
      background: var(--surface-border);
      border-radius: 4px;
    }
    .panel-body::-webkit-scrollbar-thumb:hover {
      background: var(--text-dim);
    }

    /* Left Panel Cards */
    .card {
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--surface-border);
      border-radius: 10px;
      padding: 0.9rem;
      transition: all 0.2s ease;
      min-width: 0;
      word-break: break-word;
    }

    .card:hover {
      border-color: rgba(14, 165, 233, 0.4);
      background: rgba(255,255,255,0.03);
    }

    .card-label {
      font-size: 0.72rem;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 0.25rem;
    }

    .card-val {
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-main);
    }

    .badge {
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }

    .badge-blue { background: rgba(14, 165, 233, 0.15); color: #38bdf8; border: 1px solid rgba(14, 165, 233, 0.3); }
    .badge-green { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-rose { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }

    /* Center Panel: Transcript */
    .transcript-container {
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
      min-width: 0;
      padding-bottom: 0.5rem;
    }

    .message-bubble {
      display: flex;
      flex-direction: column;
      max-width: 85%;
      min-width: 0;
      animation: fadeIn 0.15s ease-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .message-bubble.caller {
      align-self: flex-start;
    }

    .message-bubble.agent {
      align-self: flex-end;
    }

    .message-meta {
      font-size: 0.7rem;
      color: var(--text-dim);
      margin-bottom: 0.25rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }

    .message-bubble.agent .message-meta {
      justify-content: flex-end;
    }

    .message-content {
      padding: 0.75rem 1rem;
      border-radius: 12px;
      font-size: 0.95rem;
      line-height: 1.45;
      word-break: break-word;
      overflow-wrap: break-word;
    }

    .message-bubble.caller .message-content {
      background: #1e293b;
      border: 1px solid #334155;
      color: #f1f5f9;
      border-bottom-left-radius: 4px;
    }

    .message-bubble.agent .message-content {
      background: linear-gradient(135deg, rgba(14, 165, 233, 0.25), rgba(99, 102, 241, 0.25));
      border: 1px solid rgba(14, 165, 233, 0.4);
      color: #ffffff;
      border-bottom-right-radius: 4px;
    }

    /* Right Panel: Tool calls & Orchestration */
    .timeline {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      min-width: 0;
      padding-bottom: 0.5rem;
    }

    .timeline-item {
      background: rgba(255,255,255,0.015);
      border: 1px solid var(--surface-border);
      border-left: 3px solid var(--primary);
      border-radius: 8px;
      padding: 0.7rem 0.85rem;
      font-family: var(--font-mono);
      font-size: 0.78rem;
      animation: fadeIn 0.15s ease-out;
      min-width: 0;
      word-break: break-word;
      overflow-wrap: break-word;
    }

    .timeline-item.error {
      border-left-color: var(--accent-rose);
    }

    .timeline-item.success {
      border-left-color: var(--accent-green);
    }

    .timeline-header {
      display: flex;
      justify-content: space-between;
      color: var(--text-muted);
      margin-bottom: 0.35rem;
      font-weight: 500;
    }

    .timeline-body {
      color: #e2e8f0;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: break-word;
    }

    /* Empty state */
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: var(--text-dim);
      gap: 0.75rem;
      text-align: center;
      padding: 2rem;
    }

    .empty-icon {
      font-size: 2.2rem;
      opacity: 0.5;
    }

    /* Tabs */
    .tabs {
      display: flex;
      gap: 0.5rem;
    }

    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 0.3rem 0.6rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 600;
      transition: all 0.15s ease;
    }

    .tab-btn.active {
      background: var(--surface-hover);
      color: var(--primary);
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="logo-badge">CA</div>
      <div>
        <div class="brand-title">Clínica Arenal · Voice Console</div>
        <div class="brand-sub">HackSpain Prosper Track · Live Orchestration & Jury Console</div>
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 1rem;">
      <div class="status-pill" id="call-status-pill">
        <span class="status-dot" id="call-status-dot"></span>
        <span id="call-status-text">Esperando llamada...</span>
      </div>
      <div class="status-pill">
        <span style="color: var(--text-dim);">Madrid:</span>
        <span id="clock-madrid" style="font-family: var(--font-mono); font-weight: 600;">--:--</span>
      </div>
    </div>
  </header>

  <main>
    <!-- Left Column: Patient & Call State -->
    <div class="panel">
      <div class="panel-header">
        <span>Estado & Paciente</span>
        <span class="badge badge-blue" id="call-id-badge">Sin llamada</span>
      </div>
      <div class="panel-body">
        <div class="card">
          <div class="card-label">Tiempo de llamada</div>
          <div class="card-val" id="call-timer" style="font-family: var(--font-mono); font-size: 1.35rem; color: var(--primary);">00:00</div>
        </div>

        <div class="card">
          <div class="card-label">Llamante (Caller ID)</div>
          <div class="card-val" id="caller-number" style="font-family: var(--font-mono); font-size: 0.95rem;">Desconocido</div>
        </div>

        <div class="card">
          <div class="card-label">Paciente Identificado</div>
          <div class="card-val" id="patient-name">No identificado</div>
          <div id="patient-meta" style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; display: none;">
            <div>DNI: <span id="patient-dni" style="font-family: var(--font-mono); color: var(--text-main);"></span></div>
            <div>Seguro: <span id="patient-insurer" class="badge badge-green" style="margin-top: 0.2rem;"></span></div>
          </div>
        </div>

        <div class="card" id="patient-note-card" style="display: none;">
          <div class="card-label">Nota de Recepción / Historial</div>
          <div id="patient-note-text" style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.45; font-style: italic;"></div>
        </div>

        <div class="card" id="decision-card" style="display: none;">
          <div class="card-label">Acción Final Registrada</div>
          <div id="decision-badge" class="badge badge-green" style="font-size: 0.85rem; margin-top: 0.2rem;"></div>
          <div id="decision-details" style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted); margin-top: 0.4rem;"></div>
        </div>
      </div>
    </div>

    <!-- Center Column: Real-time Transcript -->
    <div class="panel">
      <div class="panel-header">
        <span>Transcripción en Directo</span>
        <span class="badge badge-green" id="voice-badge">Deepgram Nova-3 & Aura-2</span>
      </div>
      <div class="panel-body" id="transcript-body">
        <div class="empty-state" id="transcript-empty">
          <div class="empty-icon">🎙️</div>
          <div>Conecte una llamada a través del WebPhone o el evaluador para ver la conversación en tiempo real.</div>
        </div>
        <div class="transcript-container" id="transcript-list" style="display: none;">
          <div id="transcript-anchor"></div>
        </div>
      </div>
    </div>

    <!-- Right Column: Tool Calls & Orchestration -->
    <div class="panel">
      <div class="panel-header">
        <span>Orquestación & Tools</span>
        <div class="tabs">
          <button class="tab-btn active" id="tab-tools-btn" onclick="switchTab('tools')">En Vivo</button>
          <button class="tab-btn" id="tab-history-btn" onclick="switchTab('history')">Historial</button>
        </div>
      </div>
      <div class="panel-body" id="tools-panel-body">
        <div class="empty-state" id="tools-empty">
          <div class="empty-icon">⚡</div>
          <div>Las herramientas ejecutadas por Gemini y la latencia aparecerán aquí.</div>
        </div>
        <div class="timeline" id="tools-list" style="display: none;">
          <div id="tools-anchor"></div>
        </div>

        <!-- History view (hidden by default) -->
        <div id="history-list" style="display: none; flex-direction: column; gap: 0.6rem;"></div>
      </div>
    </div>
  </main>

  <script>
    // Live Clock in Europe/Madrid
    function updateClock() {
      const now = new Date();
      const options = { timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
      document.getElementById('clock-madrid').textContent = new Intl.DateTimeFormat('es-ES', options).format(now);
    }
    setInterval(updateClock, 1000);
    updateClock();

    let activeCallId = null;
    let callStartTime = null;
    let timerInterval = null;

    function formatTime(secs) {
      const m = Math.floor(secs / 60).toString().padStart(2, '0');
      const s = Math.floor(secs % 60).toString().padStart(2, '0');
      return `${m}:${s}`;
    }

    function scrollTranscriptToBottom() {
      const panel = document.getElementById('transcript-body');
      if (!panel) return;
      panel.scrollTop = panel.scrollHeight;
      requestAnimationFrame(() => {
        panel.scrollTop = panel.scrollHeight;
        const anchor = document.getElementById('transcript-anchor');
        if (anchor) {
          anchor.scrollIntoView({ behavior: 'auto', block: 'end' });
        }
      });
    }

    function scrollToolsToBottom() {
      const panel = document.getElementById('tools-panel-body');
      if (!panel) return;
      panel.scrollTop = panel.scrollHeight;
      requestAnimationFrame(() => {
        panel.scrollTop = panel.scrollHeight;
        const anchor = document.getElementById('tools-anchor');
        if (anchor) {
          anchor.scrollIntoView({ behavior: 'auto', block: 'end' });
        }
      });
    }

    function appendMessage(role, text, timeSec) {
      document.getElementById('transcript-empty').style.display = 'none';
      const container = document.getElementById('transcript-list');
      container.style.display = 'flex';

      const bubble = document.createElement('div');
      bubble.className = `message-bubble ${role}`;
      bubble.innerHTML = `
        <div class="message-meta">
          <span>${role === 'caller' ? '👤 Paciente' : '🤖 Clínica Arenal'}</span>
          <span>·</span>
          <span>${timeSec ? timeSec + 's' : ''}</span>
        </div>
        <div class="message-content">${escapeHtml(text)}</div>
      `;
      const anchor = document.getElementById('transcript-anchor');
      if (anchor) {
        container.insertBefore(bubble, anchor);
      } else {
        container.appendChild(bubble);
      }

      scrollTranscriptToBottom();
    }

    function appendTool(name, args, result, timeSec) {
      document.getElementById('tools-empty').style.display = 'none';
      const container = document.getElementById('tools-list');
      container.style.display = 'flex';

      const isError = result && (result.status === 'error' || result.status === 'provider_not_found');
      const item = document.createElement('div');
      item.className = `timeline-item ${isError ? 'error' : 'success'}`;
      item.innerHTML = `
        <div class="timeline-header">
          <span>🔧 ${escapeHtml(name)}</span>
          <span>${timeSec ? timeSec + 's' : ''}</span>
        </div>
        <div class="timeline-body" style="color: var(--text-dim); margin-bottom: 0.25rem;">
          ${escapeHtml(JSON.stringify(args || {}))}
        </div>
        ${result ? `<div class="timeline-body" style="color: ${isError ? '#fb7185' : '#34d399'}; font-size: 0.74rem;">➜ ${escapeHtml(JSON.stringify(result))}</div>` : ''}
      `;
      const anchor = document.getElementById('tools-anchor');
      if (anchor) {
        container.insertBefore(item, anchor);
      } else {
        container.appendChild(item);
      }

      scrollToolsToBottom();
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Connect Server-Sent Events (SSE)
    function connectSSE() {
      const sse = new EventSource('/api/live');

      sse.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          handleLiveEvent(data);
        } catch (err) {
          console.error("SSE parse error", err);
        }
      };

      sse.onerror = () => {
        document.getElementById('call-status-dot').className = 'status-dot';
        document.getElementById('call-status-text').textContent = 'Reconectando...';
        setTimeout(connectSSE, 3000);
      };
    }

    function handleLiveEvent(evt) {
      const callId = evt.call_id;
      const data = evt.event;

      if (data.kind === 'call_started') {
        activeCallId = callId;
        callStartTime = Date.now();
        document.getElementById('call-id-badge').textContent = callId.slice(0, 8);
        document.getElementById('call-status-dot').className = 'status-dot active';
        document.getElementById('call-status-text').textContent = 'Llamada en curso';
        document.getElementById('caller-number').textContent = data.has_caller_id ? 'Identificado en red' : 'Número oculto';

        // Clear containers and re-insert bottom anchors
        const tList = document.getElementById('transcript-list');
        tList.innerHTML = '<div id="transcript-anchor"></div>';
        tList.style.display = 'none';
        document.getElementById('transcript-empty').style.display = 'flex';

        const toolsList = document.getElementById('tools-list');
        toolsList.innerHTML = '<div id="tools-anchor"></div>';
        toolsList.style.display = 'none';
        document.getElementById('tools-empty').style.display = 'flex';

        document.getElementById('patient-name').textContent = 'No identificado';
        document.getElementById('patient-meta').style.display = 'none';
        document.getElementById('patient-note-card').style.display = 'none';
        document.getElementById('decision-card').style.display = 'none';

        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
          const elapsed = (Date.now() - callStartTime) / 1000;
          document.getElementById('call-timer').textContent = formatTime(elapsed);
        }, 1000);
      }

      if (data.kind === 'caller') {
        appendMessage('caller', data.text, data.t);
      }

      if (data.kind === 'agent') {
        appendMessage('agent', data.text, data.t);
      }

      if (data.kind === 'tool_call') {
        appendTool(data.name, data.args, null, data.t);
      }

      if (data.kind === 'tool_result') {
        appendTool(data.name, null, data.result, data.t);

        // Update Patient Card if find_patient matched
        if (data.name === 'find_patient' && data.result && data.result.status === 'identified') {
          document.getElementById('patient-name').textContent = data.result.full_name;
          document.getElementById('patient-dni').textContent = data.result.date_of_birth || '';
          document.getElementById('patient-insurer').textContent = data.result.insurer_on_file || '';
          document.getElementById('patient-meta').style.display = 'block';

          if (data.result.note) {
            document.getElementById('patient-note-text').textContent = data.result.note;
            document.getElementById('patient-note-card').style.display = 'block';
          }
        }
      }

      if (data.kind === 'recorded') {
        document.getElementById('decision-card').style.display = 'block';
        document.getElementById('decision-badge').textContent = data.action.toUpperCase();
        document.getElementById('decision-details').textContent = JSON.stringify(data.payload || {});
      }

      if (data.kind === 'call_ended') {
        clearInterval(timerInterval);
        document.getElementById('call-status-dot').className = 'status-dot';
        document.getElementById('call-status-text').textContent = 'Llamada finalizada';
      }
    }

    function switchTab(tab) {
      const isTools = tab === 'tools';
      document.getElementById('tab-tools-btn').className = `tab-btn ${isTools ? 'active' : ''}`;
      document.getElementById('tab-history-btn').className = `tab-btn ${!isTools ? 'active' : ''}`;

      if (isTools) {
        document.getElementById('history-list').style.display = 'none';
        if (document.getElementById('tools-list').children.length > 0) {
          document.getElementById('tools-list').style.display = 'flex';
          document.getElementById('tools-empty').style.display = 'none';
        } else {
          document.getElementById('tools-empty').style.display = 'flex';
        }
      } else {
        document.getElementById('tools-list').style.display = 'none';
        document.getElementById('tools-empty').style.display = 'none';
        loadCallHistory();
      }
    }

    async function loadCallHistory() {
      const container = document.getElementById('history-list');
      container.style.display = 'flex';
      container.innerHTML = '<div style="color: var(--text-dim); font-size: 0.8rem;">Cargando llamadas anteriores...</div>';

      try {
        const res = await fetch('/api/calls');
        const calls = await res.json();
        if (!calls || calls.length === 0) {
          container.innerHTML = '<div style="color: var(--text-dim); font-size: 0.8rem;">Aún no hay llamadas registradas en disco.</div>';
          return;
        }

        container.innerHTML = '';
        calls.slice(0, 15).forEach(c => {
          const item = document.createElement('div');
          item.className = 'card';
          item.style.cursor = 'pointer';
          item.innerHTML = `
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem;">
              <span style="font-family: var(--font-mono); font-weight: 600;">ID: ${c.call_id.slice(0, 8)}</span>
              <span class="badge badge-blue">${c.actions.length ? c.actions.join(', ') : 'SIN ACCIÓN'}</span>
            </div>
            <div style="font-size: 0.72rem; color: var(--text-dim); margin-top: 0.25rem;">
              ${c.turns} turnos · ${c.duration_secs}s
            </div>
          `;
          container.appendChild(item);
        });
      } catch (err) {
        container.innerHTML = '<div style="color: var(--accent-rose); font-size: 0.8rem;">Error al cargar historial.</div>';
      }
    }

    // Auto-scroll observer to guarantee bottom pinning on any dynamic DOM update
    const transcriptObserver = new MutationObserver(() => {
      scrollTranscriptToBottom();
    });
    const tListInit = document.getElementById('transcript-list');
    if (tListInit) {
      transcriptObserver.observe(tListInit, { childList: true, subtree: true, characterData: true });
    }

    const toolsObserver = new MutationObserver(() => {
      scrollToolsToBottom();
    });
    const toolsListInit = document.getElementById('tools-list');
    if (toolsListInit) {
      toolsObserver.observe(toolsListInit, { childList: true, subtree: true, characterData: true });
    }

    connectSSE();
  </script>
</body>
</html>
"""


async def live_events_generator() -> AsyncGenerator[str, None]:
    """Stream live call events to connected browsers over Server-Sent Events."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    def on_event(call_id: str, event: dict) -> None:
        try:
            queue.put_nowait({"call_id": call_id, "event": event})
        except asyncio.QueueFull:
            pass

    unsubscribe = session.subscribe(on_event)
    try:
        # Initial greeting event
        yield f"data: {json.dumps({'call_id': 'system', 'event': {'kind': 'connected'}})}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(msg, ensure_ascii=False, default=str)}\n\n"
            except asyncio.TimeoutError:
                # Keepalive ping
                yield ": keepalive\n\n"
    finally:
        unsubscribe()


def get_call_history() -> list[dict]:
    """Summarize recent calls stored in logs/calls/*.jsonl."""
    log_dir = config.CALL_LOG_DIR
    if not log_dir.exists():
        return []

    calls = []
    for path in sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
        events = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        except Exception:
            continue

        if not events:
            continue

        call_id = path.stem
        turns = sum(1 for e in events if e.get("kind") in ("caller", "agent"))
        actions = [e["action"].upper() for e in events if e.get("kind") == "submit" and "action" in e]
        duration = events[-1].get("t", 0.0) if events else 0.0

        calls.append({
            "call_id": call_id,
            "turns": turns,
            "actions": actions,
            "duration_secs": round(duration, 1),
        })

    return calls
