// Where the screens find the two local services. Both run on the demo laptop (see apps/agent/scripts/demo.sh).
export const EVENTS_URL = process.env.NEXT_PUBLIC_EVENTS_URL ?? "http://127.0.0.1:7870";
export const CALL_WS_URL = process.env.NEXT_PUBLIC_CALL_WS_URL ?? "ws://127.0.0.1:7861/ws";
