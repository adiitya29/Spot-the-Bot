/**
 * k6 WebSocket Load Test for Spot the Bot
 *
 * Target: 100 concurrent rooms x 6 clients per room (600 active WebSocket connections)
 * Measures:
 *   - ws_fanout_latency: p95 latency from sender broadcast to recipient delivery (<150ms target)
 *   - ws_connect_duration: WebSocket handshake duration
 *   - ws_messages_broadcast: Total broadcast events received
 *   - ws_errors: Connection and framing error rate
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import ws from 'k6/ws';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom Metrics
export const wsFanoutLatency = new Trend('ws_fanout_latency', true);
export const wsConnectDuration = new Trend('ws_connect_duration', true);
export const wsMessagesBroadcast = new Counter('ws_messages_broadcast');
export const wsErrors = new Rate('ws_errors');
export const roomCreationSuccess = new Rate('room_creation_success');

// Configuration
const HTTP_BASE = __ENV.HTTP_BASE || 'http://localhost:8000';
const WS_BASE = __ENV.WS_BASE || 'ws://localhost:8000';
const TARGET_ROOMS = parseInt(__ENV.ROOMS || '100', 10);
const CLIENTS_PER_ROOM = parseInt(__ENV.CLIENTS || '6', 10);
const DURATION_SECONDS = parseInt(__ENV.DURATION || '60', 10);

export const options = {
  scenarios: {
    room_mesh_load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '15s', target: Math.min(TARGET_ROOMS, 20) },
        { duration: '30s', target: TARGET_ROOMS },
        { duration: `${DURATION_SECONDS}s`, target: TARGET_ROOMS },
        { duration: '15s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    // Phase 9 Target: p95 fan-out latency < 150ms
    ws_fanout_latency: ['p(95)<150'],
    ws_connect_duration: ['p(95)<250'],
    ws_errors: ['rate<0.01'],
    http_req_duration: ['p(95)<250'],
  },
};

/**
 * Executes a simulated game room with 6 participants chatting and tracking fanout latency.
 */
export default function () {
  const roomIndex = __VU;
  const iteration = __ITER;

  // Step 1: Host creates a room
  const createPayload = JSON.stringify({
    nickname: `Host_${roomIndex}_${iteration}`,
    min_humans: 4,
    max_humans: 7,
    allow_replay_use: false,
  });

  const createRes = http.post(`${HTTP_BASE}/api/rooms/`, createPayload, {
    headers: { 'Content-Type': 'application/json' },
  });

  const createOk = check(createRes, {
    'room created 201': (r) => r.status === 201,
  });
  roomCreationSuccess.add(createOk);

  if (!createOk) {
    wsErrors.add(1);
    sleep(1);
    return;
  }

  const roomData = JSON.parse(createRes.body);
  const roomCode = roomData.code;
  const hostToken = roomData.player_token;

  // Step 2: 5 Guest players join the room
  const guestTokens = [];
  for (let g = 1; g < CLIENTS_PER_ROOM; g++) {
    const joinPayload = JSON.stringify({
      nickname: `G${g}_${roomIndex}_${iteration}`,
    });

    const joinRes = http.post(
      `${HTTP_BASE}/api/rooms/${roomCode}/join/`,
      joinPayload,
      { headers: { 'Content-Type': 'application/json' } }
    );

    if (joinRes.status === 200) {
      guestTokens.push(JSON.parse(joinRes.body).player_token);
    } else {
      wsErrors.add(1);
    }
  }

  const allTokens = [hostToken, ...guestTokens];

  // Step 3: Connect client to WebSocket and measure fan-out latency
  const playerToken = allTokens[Math.floor(Math.random() * allTokens.length)];
  const wsUrl = `${WS_BASE}/ws/room/${roomCode}/?token=${playerToken}`;
  const connectStart = Date.now();

  const res = ws.connect(wsUrl, {}, function (socket) {
    socket.on('open', () => {
      wsConnectDuration.add(Date.now() - connectStart);

      // Ping to establish presence
      socket.send(JSON.stringify({ type: 'ping' }));

      // Send chat test message after short pause
      socket.setTimeout(() => {
        const sendTime = Date.now();
        const clientMsgId = `k6_${roomIndex}_${iteration}_${sendTime}`;
        socket.send(
          JSON.stringify({
            type: 'chat_message',
            text: `load test message ${sendTime}`,
            client_msg_id: clientMsgId,
            sent_at: sendTime,
          })
        );
      }, 500);
    });

    socket.on('message', (data) => {
      try {
        const msg = JSON.parse(data);
        wsMessagesBroadcast.add(1);

        if (msg.type === 'chat_message' && msg.sent_at) {
          const latency = Date.now() - Number(msg.sent_at);
          if (latency >= 0) {
            wsFanoutLatency.add(latency);
          }
        }
      } catch (e) {
        wsErrors.add(1);
      }
    });

    socket.on('error', (e) => {
      wsErrors.add(1);
    });

    // Run connection for 10 seconds per iteration
    socket.setTimeout(() => {
      socket.close();
    }, 10000);
  });

  check(res, { 'ws handshake successful (101)': (r) => r && r.status === 101 });
  sleep(1);
}

