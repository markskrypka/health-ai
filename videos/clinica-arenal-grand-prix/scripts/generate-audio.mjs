import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync, copyFileSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

let apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) {
  try {
    const envStr = readFileSync("/home/Shodan/teacher/.env", "utf8");
    const m = envStr.match(/^OPENAI_API_KEY=(.+)$/m);
    if (m) apiKey = m[1].trim();
  } catch (e) {}
}
if (!apiKey) {
  console.error("Missing OPENAI_API_KEY for Whisper word alignment");
  process.exit(1);
}

let geminiApiKey = process.env.GEMINI_API_KEY;
if (!geminiApiKey) {
  try {
    const envStr = readFileSync("/home/Shodan/strangemed/.env.local", "utf8");
    const m = envStr.match(/^GEMINI_API_KEY=(.+)$/m);
    if (m) geminiApiKey = m[1].trim();
  } catch (e) {}
}
if (!geminiApiKey) {
  console.error("Missing GEMINI_API_KEY for Google Gemini TTS");
  process.exit(1);
}

const projectDir = resolve(import.meta.dirname, "..");
const audioDir = join(projectDir, "audio");
await mkdir(audioDir, { recursive: true });

const FRAME_STARTS = {
  1: 0.0,
  2: 24.5,
  3: 48.0,
  4: 68.5,
  5: 91.0,
  6: 112.5,
  7: 135.5,
  8: 158.0,
};

const FRAME_MAX_DURS = {
  1: 24.0,
  2: 23.0,
  3: 20.0,
  4: 22.0,
  5: 21.0,
  6: 22.5,
  7: 22.0,
  8: 21.5,
};

function parseScript(md) {
  const lines = [];
  let current = null;
  for (const line of md.split(/\r?\n/)) {
    const h = line.match(/^##\s+Line\s+(\d+)\s+—\s+(.*?)\s+\(Frame\s+(\d+)\)/i);
    if (h) {
      if (current) lines.push(current);
      current = { line: Number(h[1]), title: h[2], frame: Number(h[3]), text: "" };
      continue;
    }
    if (!current) continue;
    if (/^\s*\*\*/.test(line)) continue;
    const m = line.match(/^(?: {4,}|\t)(.+)$/);
    if (m) {
      current.text += (current.text ? " " : "") + m[1].trim();
    }
  }
  if (current) lines.push(current);
  return lines;
}

async function synthesize(text, voicePath, targetMaxDur) {
  console.log(`Synthesizing with Google Gemini TTS (Puck): "${text.slice(0, 50)}..." -> ${voicePath}`);
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key=${geminiApiKey}`;
  
  const payload = {
    contents: [
      {
        parts: [
          {
            text: `Por favor, lee el siguiente texto en voz alta con entonación natural, ritmo fluido y acento de español europeo de España, sin añadir comentarios ni preámbulos:\n\n${text}`
          }
        ]
      }
    ],
    generationConfig: {
      responseModalities: ["AUDIO"],
      speechConfig: {
        voiceConfig: {
          prebuiltVoiceConfig: {
            voiceName: "Puck"
          }
        }
      }
    }
  };

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Gemini TTS failed with status ${res.status}: ${await res.text()}`);
  }

  const json = await res.json();
  const cand = json.candidates?.[0]?.content?.parts?.[0];
  if (!cand || !cand.inlineData?.data) {
    throw new Error(`Gemini TTS returned no audio: ${JSON.stringify(json)}`);
  }

  const rawPcm = Buffer.from(cand.inlineData.data, "base64");
  const rawPath = voicePath + ".raw";
  await writeFile(rawPath, rawPcm);

  const tmpMp3 = voicePath + ".tmp.mp3";
  await execFileAsync("ffmpeg", [
    "-y",
    "-f", "s16le",
    "-ar", "24000",
    "-ac", "1",
    "-i", rawPath,
    tmpMp3
  ]);

  const { stdout: probeOut } = await execFileAsync("ffprobe", [
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1",
    tmpMp3
  ]);
  const rawDur = parseFloat(probeOut.trim());

  let tempo = 1.0;
  if (targetMaxDur && rawDur > targetMaxDur - 0.5) {
    tempo = rawDur / (targetMaxDur - 0.8);
    tempo = Math.max(1.05, Math.min(tempo, 1.30));
  }

  if (Math.abs(tempo - 1.0) > 0.02) {
    console.log(`Adjusting tempo by x${tempo.toFixed(2)} (raw: ${rawDur.toFixed(2)}s -> target: ~${(rawDur / tempo).toFixed(2)}s)`);
    await execFileAsync("ffmpeg", [
      "-y",
      "-i", tmpMp3,
      "-filter:a", `atempo=${tempo.toFixed(3)}`,
      voicePath
    ]);
  } else {
    copyFileSync(tmpMp3, voicePath);
  }
}

async function transcribe(voicePath) {
  console.log(`Transcribing with Whisper (es): ${voicePath}`);
  const fileBuffer = await readFile(voicePath);
  const formData = new FormData();
  formData.append("file", new Blob([fileBuffer], { type: "audio/mpeg" }), "audio.mp3");
  formData.append("model", "whisper-1");
  formData.append("language", "es");
  formData.append("response_format", "verbose_json");
  formData.append("timestamp_granularities[]", "word");

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`Whisper failed with status ${res.status}: ${await res.text()}`);
  }
  const data = await res.json();
  return {
    duration_s: data.duration,
    words: (data.words || []).map((w, i) => ({
      id: `w${i}`,
      text: w.word,
      start: Number(w.start.toFixed(3)),
      end: Number(w.end.toFixed(3)),
    })),
  };
}

function chunkIntoGroups(voices) {
  const groups = [];
  let groupIdx = 0;

  for (const v of voices) {
    const frameStart = FRAME_STARTS[v.frame] || 0;
    const words = v.words;
    if (!words || words.length === 0) continue;

    let currentGroupWords = [];
    
    for (let i = 0; i < words.length; i++) {
      const w = words[i];
      const absStart = Number((frameStart + w.start).toFixed(2));
      const absEnd = Number((frameStart + w.end).toFixed(2));
      
      currentGroupWords.push({
        id: `caption-word-${groupIdx}-${currentGroupWords.length}`,
        text: w.text,
        start: absStart,
        end: absEnd,
      });

      const hasPunctuation = /[,.:;—!?]$/.test(w.text.trim());
      const isLastWord = i === words.length - 1;
      const reachedWordLimit = currentGroupWords.length >= 3;
      const groupDuration = currentGroupWords[currentGroupWords.length - 1].end - currentGroupWords[0].start;

      if (isLastWord || hasPunctuation || (reachedWordLimit && groupDuration >= 1.2)) {
        const gStart = currentGroupWords[0].start;
        const gEnd = currentGroupWords[currentGroupWords.length - 1].end;
        const gText = currentGroupWords.map((cw) => cw.text).join(" ");
        
        groups.push({
          id: `caption-group-${groupIdx}`,
          frame: v.frame,
          start: gStart,
          end: gEnd,
          text: gText,
          words: currentGroupWords,
        });

        groupIdx++;
        currentGroupWords = [];
      }
    }
  }

  return groups;
}

async function updateCaptionsHtml(groups) {
  const captionsPath = join(projectDir, "compositions", "captions.html");
  let content = await readFile(captionsPath, "utf8");

  const groupsJson = JSON.stringify(groups);
  const regex = /var GROUPS\s*=\s*\[[\s\S]*?\];/;
  if (!regex.test(content)) {
    throw new Error("Could not find var GROUPS in captions.html");
  }

  content = content.replace(regex, `var GROUPS = ${groupsJson};`);
  content = content.replace(/data-duration=".*?"/, `data-duration="180"`);
  content = content.replace(/var DURATION\s*=\s*\d+;/, `var DURATION = 180;`);
  await writeFile(captionsPath, content, "utf8");
  console.log(`Updated compositions/captions.html with ${groups.length} caption groups (180s total).`);
}

async function main() {
  const scriptContent = await readFile(join(projectDir, "SCRIPT.md"), "utf8");
  const scriptLines = parseScript(scriptContent);
  console.log(`Parsed ${scriptLines.length} lines from SCRIPT.md`);

  const voices = [];
  for (const item of scriptLines) {
    const filename = `voice-${String(item.frame).padStart(2, "0")}.mp3`;
    const relPath = `audio/${filename}`;
    const absPath = join(audioDir, filename);

    const maxDur = FRAME_MAX_DURS[item.frame] || 22.0;
    await synthesize(item.text, absPath, maxDur);
    const trans = await transcribe(absPath);

    console.log(`Frame ${item.frame}: generated ${trans.duration_s}s (max target: ${maxDur}s)`);

    voices.push({
      frame: item.frame,
      path: relPath,
      duration_s: Number(trans.duration_s.toFixed(3)),
      words: trans.words,
    });
  }

  // Audio metadata
  const sfxList = [
    { frame: 1, file: "audio/whoosh-cinematic.mp3", offset_s: 0.1, duration_s: 2.0, volume: 0.35 },
    { frame: 2, file: "audio/sparkle.mp3", offset_s: 0.5, duration_s: 1.0, volume: 0.25 },
    { frame: 3, file: "audio/notification.mp3", offset_s: 0.3, duration_s: 1.0, volume: 0.25 },
    { frame: 4, file: "audio/click.mp3", offset_s: 0.2, duration_s: 0.5, volume: 0.2 },
    { frame: 5, file: "audio/chime.mp3", offset_s: 0.2, duration_s: 1.0, volume: 0.25 },
    { frame: 6, file: "audio/click.mp3", offset_s: 0.2, duration_s: 0.5, volume: 0.2 },
    { frame: 7, file: "audio/whoosh-cinematic.mp3", offset_s: 0.1, duration_s: 2.0, volume: 0.3 },
    { frame: 8, file: "audio/chime.mp3", offset_s: 0.5, duration_s: 1.5, volume: 0.35 },
  ];

  const audioMeta = {
    bgm: { path: "audio/bgm.loop.mp3", volume: 0.07, query: "ambient cinematic piano", duration_s: 180 },
    bgm_pending: false,
    voices,
    sfx: sfxList,
  };

  await writeFile(join(projectDir, "audio_meta.json"), JSON.stringify(audioMeta, null, 2));
  console.log("Wrote audio_meta.json successfully!");

  // Build and save caption groups
  const groups = chunkIntoGroups(voices);
  const captionGroupsData = {
    total_duration_s: 180,
    width: 1920,
    height: 1080,
    groups,
  };
  await writeFile(join(projectDir, "caption_groups.json"), JSON.stringify(captionGroupsData, null, 2));
  console.log(`Wrote caption_groups.json (${groups.length} groups)`);

  // Update captions.html
  await updateCaptionsHtml(groups);

  console.log("\n=== Narration Timings Summary ===");
  for (const v of voices) {
    console.log(`Frame ${v.frame}: voice duration = ${v.duration_s}s, words = ${v.words.length}`);
  }
}

main().catch((err) => {
  console.error("Audio generation failed:", err);
  process.exit(1);
});
