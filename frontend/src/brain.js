/**
 * agentwatch/frontend/src/brain.js
 *
 * Three.js force-directed brain graph.
 * - Nodes = reasoning steps / tool calls
 * - Edges = execution flow between steps
 * - Color = trust score (green → yellow → orange → red)
 * - Size = token count / importance
 * - Pulse animation = currently active node
 * - Red flash = anomaly detected
 */

// ─────────────────────────────────────────────
// Scene Setup
// ─────────────────────────────────────────────

const canvas = document.getElementById('brain-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x050810, 1);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 45);

// Fog for depth
scene.fog = new THREE.FogExp2(0x050810, 0.018);

// Ambient + directional light
scene.add(new THREE.AmbientLight(0x4060a0, 0.5));
const dirLight = new THREE.DirectionalLight(0x80b0ff, 1.0);
dirLight.position.set(10, 20, 10);
scene.add(dirLight);

// ─────────────────────────────────────────────
// Background starfield
// ─────────────────────────────────────────────

const starGeo = new THREE.BufferGeometry();
const starCount = 800;
const starPositions = new Float32Array(starCount * 3);
for (let i = 0; i < starCount * 3; i++) {
  starPositions[i] = (Math.random() - 0.5) * 200;
}
starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
const starMat = new THREE.PointsMaterial({ color: 0x334466, size: 0.15, sizeAttenuation: true });
scene.add(new THREE.Points(starGeo, starMat));

// ─────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────

function trustToColor(trust) {
  // 1.0 → green, 0.5 → yellow, 0.2 → orange, 0.0 → red
  if (trust > 0.7) return new THREE.Color(0x00ff88);
  if (trust > 0.5) return new THREE.Color(0x88ff44);
  if (trust > 0.3) return new THREE.Color(0xffcc00);
  if (trust > 0.15) return new THREE.Color(0xff8800);
  return new THREE.Color(0xff3355);
}

function eventTypeToColor(eventType) {
  const map = {
    llm_call:   new THREE.Color(0x4f8fff),
    tool_call:  new THREE.Color(0x00e5ff),
    step_start: new THREE.Color(0x5a7090),
    step_end:   new THREE.Color(0x00ff88),
    anomaly:    new THREE.Color(0xff3355),
    error:      new THREE.Color(0xff8800),
  };
  return map[eventType] || new THREE.Color(0x7090b0);
}

// ─────────────────────────────────────────────
// Node & Edge State
// ─────────────────────────────────────────────

export const nodes = new Map();    // step_id → { mesh, data, velocity, position }
export const edges = [];            // { line, fromId, toId }

let lastStepId = null;
let totalEvents = 0;
let totalAnomalies = 0;
let trustSum = 0;
const agentIds = new Set();

// ─────────────────────────────────────────────
// Create / Update Nodes
// ─────────────────────────────────────────────

export function addOrUpdateNode(event) {
  const { step_id, event_type, trust_score = 1.0, step_name, agent_id } = event;
  if (!step_id) return;

  totalEvents++;
  if (agent_id) agentIds.add(agent_id);
  trustSum += trust_score;

  updateStats(event);

  if (nodes.has(step_id)) {
    updateNode(step_id, event);
    return;
  }

  // New node — pick a spawn position with slight randomness
  const angle = Math.random() * Math.PI * 2;
  const radius = 5 + Math.random() * 12;
  const position = new THREE.Vector3(
    Math.cos(angle) * radius,
    (Math.random() - 0.5) * 10,
    Math.sin(angle) * radius,
  );

  // Node size based on token count or default
  const tokens = event.llm_total_tokens || 0;
  const baseSize = event_type === 'anomaly' ? 0.9 : 0.4 + Math.min(tokens / 8000, 0.5);

  // Geometry
  const geo = event_type === 'tool_call'
    ? new THREE.OctahedronGeometry(baseSize)
    : new THREE.SphereGeometry(baseSize, 16, 16);

  const color = trustToColor(trust_score);

  // Core mesh
  const mat = new THREE.MeshPhongMaterial({
    color,
    emissive: color.clone().multiplyScalar(0.3),
    shininess: 80,
    transparent: true,
    opacity: 0.9,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.copy(position);
  mesh.userData = { step_id, event_type, step_name, trust_score };
  scene.add(mesh);

  // Glow halo
  const haloGeo = new THREE.SphereGeometry(baseSize * 2.5, 12, 12);
  const haloMat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.06,
    side: THREE.BackSide,
  });
  const halo = new THREE.Mesh(haloGeo, haloMat);
  mesh.add(halo);

  // Anomaly ring
  let ring = null;
  if (event_type === 'anomaly') {
    const ringGeo = new THREE.TorusGeometry(baseSize * 1.8, 0.05, 8, 32);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xff3355 });
    ring = new THREE.Mesh(ringGeo, ringMat);
    mesh.add(ring);
    triggerAnomalyFlash();
  }

  const nodeData = {
    mesh,
    halo,
    ring,
    data: event,
    position: position.clone(),
    velocity: new THREE.Vector3(
      (Math.random() - 0.5) * 0.02,
      (Math.random() - 0.5) * 0.02,
      (Math.random() - 0.5) * 0.02,
    ),
    baseSize,
    trust: trust_score,
    active: true,
    birthTime: Date.now(),
  };
  nodes.set(step_id, node => node, nodeData);
  nodes.set(step_id, nodeData);

  // Draw edge from last step
  if (lastStepId && nodes.has(lastStepId)) {
    addEdge(lastStepId, step_id, trust_score);
  }
  lastStepId = step_id;

  // Pulse flash on new node
  pulseNode(step_id);
}

function updateNode(step_id, event) {
  const node = nodes.get(step_id);
  if (!node) return;
  node.trust = event.trust_score ?? node.trust;
  node.data = { ...node.data, ...event };
  const color = trustToColor(node.trust);
  node.mesh.material.color.set(color);
  node.mesh.material.emissive.set(color.clone().multiplyScalar(0.3));
  node.halo.material.color.set(color);

  if (event.event_type === 'anomaly') {
    node.mesh.material.emissive.set(new THREE.Color(0xff3355).multiplyScalar(0.6));
    triggerAnomalyFlash();
  }
}

// ─────────────────────────────────────────────
// Edges
// ─────────────────────────────────────────────

function addEdge(fromId, toId, trust) {
  const from = nodes.get(fromId);
  const to = nodes.get(toId);
  if (!from || !to) return;

  const points = [from.mesh.position.clone(), to.mesh.position.clone()];
  const geo = new THREE.BufferGeometry().setFromPoints(points);
  const color = trustToColor(trust);
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: 0.25,
  });
  const line = new THREE.Line(geo, mat);
  scene.add(line);
  edges.push({ line, fromId, toId, geo });
}

function updateEdgePositions() {
  for (const edge of edges) {
    const from = nodes.get(edge.fromId);
    const to = nodes.get(edge.toId);
    if (!from || !to) continue;
    const positions = edge.geo.attributes.position;
    const fp = from.mesh.position;
    const tp = to.mesh.position;
    positions.setXYZ(0, fp.x, fp.y, fp.z);
    positions.setXYZ(1, tp.x, tp.y, tp.z);
    positions.needsUpdate = true;
  }
}

// ─────────────────────────────────────────────
// Force-Directed Layout (simplified)
// ─────────────────────────────────────────────

const REPEL = 0.8;
const ATTRACT = 0.005;
const DAMPING = 0.92;
const CENTER_PULL = 0.001;

function applyForces() {
  const nodeList = Array.from(nodes.values());

  for (let i = 0; i < nodeList.length; i++) {
    const a = nodeList[i];

    // Center gravity
    a.velocity.addScaledVector(a.mesh.position.clone().negate(), CENTER_PULL);

    for (let j = i + 1; j < nodeList.length; j++) {
      const b = nodeList[j];
      const diff = a.mesh.position.clone().sub(b.mesh.position);
      const dist = Math.max(diff.length(), 0.5);

      // Repulsion
      const repel = REPEL / (dist * dist);
      const dir = diff.normalize();
      a.velocity.addScaledVector(dir, repel);
      b.velocity.addScaledVector(dir, -repel);
    }
  }

  // Edge attraction
  for (const edge of edges) {
    const a = nodes.get(edge.fromId);
    const b = nodes.get(edge.toId);
    if (!a || !b) continue;
    const diff = b.mesh.position.clone().sub(a.mesh.position);
    const dist = diff.length();
    const ideal = 6;
    const force = (dist - ideal) * ATTRACT;
    const dir = diff.normalize();
    a.velocity.addScaledVector(dir, force);
    b.velocity.addScaledVector(dir, -force);
  }

  // Apply velocities
  for (const node of nodeList) {
    node.velocity.multiplyScalar(DAMPING);
    node.mesh.position.add(node.velocity);
    // Clamp to sphere
    if (node.mesh.position.length() > 22) {
      node.mesh.position.setLength(22);
    }
  }
}

// ─────────────────────────────────────────────
// Pulse Animation
// ─────────────────────────────────────────────

const pulsingNodes = new Map();  // step_id → { start, duration }

export function pulseNode(step_id) {
  pulsingNodes.set(step_id, { start: Date.now(), duration: 1200 });
}

function animatePulses(t) {
  for (const [id, pulse] of pulsingNodes) {
    const node = nodes.get(id);
    if (!node) { pulsingNodes.delete(id); continue; }

    const elapsed = t - pulse.start;
    const progress = elapsed / pulse.duration;
    if (progress > 1) { pulsingNodes.delete(id); continue; }

    const scale = 1 + Math.sin(progress * Math.PI) * 0.6;
    node.halo.scale.setScalar(scale);
    node.halo.material.opacity = 0.12 * (1 - progress);
  }
}

// ─────────────────────────────────────────────
// Anomaly Flash
// ─────────────────────────────────────────────

let flashTimer = 0;

function triggerAnomalyFlash() {
  flashTimer = 600;
}

function animateFlash(delta) {
  if (flashTimer > 0) {
    flashTimer -= delta;
    const intensity = (flashTimer / 600) * 0.15;
    renderer.setClearColor(new THREE.Color(0xff3355).lerp(new THREE.Color(0x050810), 1 - intensity), 1);
  } else {
    renderer.setClearColor(0x050810, 1);
  }
}

// ─────────────────────────────────────────────
// Rotation
// ─────────────────────────────────────────────

let autoRotate = true;
let rotY = 0;

document.addEventListener('keydown', e => { if (e.key === 'r') autoRotate = !autoRotate; });

// ─────────────────────────────────────────────
// Mouse Interaction (raycasting)
// ─────────────────────────────────────────────

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

canvas.addEventListener('mousemove', e => {
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
});

canvas.addEventListener('click', () => {
  raycaster.setFromCamera(mouse, camera);
  const meshes = Array.from(nodes.values()).map(n => n.mesh);
  const hits = raycaster.intersectObjects(meshes);
  if (hits.length > 0) {
    const hit = hits[0].object;
    const step_id = hit.userData.step_id;
    const node = nodes.get(step_id);
    if (node) {
      showInspector(node.data);
      pulseNode(step_id);
    }
  }
});

function showInspector(event) {
  const panel = document.getElementById('inspector-content');
  const trust = parseFloat(event.trust_score ?? 1.0);
  const trustPct = Math.round(trust * 100);
  const trustColor = trust > 0.7 ? '#00ff88' : trust > 0.4 ? '#ffcc00' : '#ff3355';

  panel.innerHTML = `
    <div class="inspector-field">
      <label>Step Name</label>
      <value>${event.step_name || '—'}</value>
    </div>
    <div class="inspector-field">
      <label>Event Type</label>
      <value>${event.event_type || '—'}</value>
    </div>
    <div class="inspector-field">
      <label>Trust Score</label>
      <value style="color:${trustColor}">${trustPct}%</value>
      <div class="trust-bar">
        <div class="trust-fill" style="width:${trustPct}%;background:${trustColor}"></div>
      </div>
    </div>
    ${event.llm_total_tokens ? `
    <div class="inspector-field">
      <label>Tokens</label>
      <value>${event.llm_total_tokens.toLocaleString()}</value>
    </div>` : ''}
    ${event.tool_name ? `
    <div class="inspector-field">
      <label>Tool</label>
      <value>${event.tool_name}</value>
    </div>` : ''}
    ${event.duration_ms ? `
    <div class="inspector-field">
      <label>Duration</label>
      <value>${Math.round(event.duration_ms)}ms</value>
    </div>` : ''}
    ${event.reasoning_content ? `
    <div class="inspector-field">
      <label>Reasoning</label>
      <value style="font-size:10px;opacity:0.8">${event.reasoning_content.substring(0, 200)}...</value>
    </div>` : ''}
    ${event.error ? `
    <div class="inspector-field">
      <label>Error</label>
      <value style="color:var(--red);font-size:10px">${event.error}</value>
    </div>` : ''}
    <div class="inspector-field">
      <label>Trace ID</label>
      <value style="font-size:9px;color:var(--text-dim)">${(event.trace_id || '').substring(0, 16)}...</value>
    </div>
  `;
}

// ─────────────────────────────────────────────
// Stats Update
// ─────────────────────────────────────────────

function updateStats(event) {
  document.getElementById('stat-events').textContent = totalEvents;
  if (event.event_type === 'anomaly') {
    totalAnomalies++;
    document.getElementById('stat-anomalies').textContent = totalAnomalies;
  }
  const avgTrust = totalEvents > 0 ? (trustSum / totalEvents).toFixed(2) : '1.00';
  document.getElementById('stat-trust').textContent = avgTrust;
  document.getElementById('stat-agents').textContent = agentIds.size;
}

// ─────────────────────────────────────────────
// Resize
// ─────────────────────────────────────────────

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ─────────────────────────────────────────────
// Render Loop
// ─────────────────────────────────────────────

let lastTime = 0;

function animate(t) {
  requestAnimationFrame(animate);
  const delta = t - lastTime;
  lastTime = t;

  if (autoRotate) {
    rotY += 0.001;
    scene.rotation.y = rotY;
  }

  // Animate active node rings
  for (const node of nodes.values()) {
    if (node.ring) {
      node.ring.rotation.x += 0.02;
      node.ring.rotation.z += 0.01;
    }
    // Subtle breathing on all nodes
    const age = (t - node.birthTime) / 1000;
    const breathe = 1 + Math.sin(age * 1.5 + node.birthTime * 0.001) * 0.04;
    node.mesh.scale.setScalar(breathe);
  }

  applyForces();
  updateEdgePositions();
  animatePulses(t);
  animateFlash(delta);

  renderer.render(scene, camera);
}

animate(0);

// Export for other modules
export { scene, camera, renderer };
