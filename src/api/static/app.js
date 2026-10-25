/**
 * Company Brain on FalkorDB: Interactive Graph Web Application.
 * Handles chat streaming, Cytoscape.js graph rendering with Dagre branching layout,
 * node click inspection drawer, simultaneous live Cypher query trace viewer,
 * and separate slide-over Sources window.
 */

let cy = null;
let currentSubgraph = { nodes: [], edges: [] };

document.addEventListener("DOMContentLoaded", () => {
  initCytoscape();
  initSourcesDrawer();
  initChat();
  initQuickPills();
  initGraphControls();
  fetchGraphStats();
});

// =============================================================================
// CYTOSCAPE GRAPH INITIALIZATION & STYLING
// =============================================================================

function initCytoscape() {
  cy = cytoscape({
    container: document.getElementById("cy"),
    boxSelectionEnabled: false,
    autounselectify: false,
    style: [
      // Core Node Styling
      {
        selector: "node",
        style: {
          "label": "data(label)",
          "color": "#ffffff",
          "font-family": "Inter, sans-serif",
          "font-size": "10px",
          "font-weight": "600",
          "text-valign": "center",
          "text-halign": "center",
          "text-wrap": "wrap",
          "text-max-width": "75px",
          "width": "60px",
          "height": "60px",
          "border-width": "2px",
          "border-color": "rgba(255, 255, 255, 0.2)",
          "background-color": "#334155",
          "transition-property": "background-color, border-color, width, height",
          "transition-duration": "0.3s"
        }
      },
      // Status Color Overrides for PEPs
      {
        selector: 'node[status = "Final"]',
        style: {
          "background-color": "#10b981", // Emerald
          "border-color": "#34d399",
          "shape": "round-rectangle"
        }
      },
      {
        selector: 'node[status = "Superseded"]',
        style: {
          "background-color": "#f59e0b", // Amber
          "border-color": "#fbbf24",
          "shape": "round-rectangle"
        }
      },
      {
        selector: 'node[status = "Withdrawn"], node[status = "Rejected"]',
        style: {
          "background-color": "#ef4444", // Crimson
          "border-color": "#f87171",
          "shape": "round-rectangle"
        }
      },
      {
        selector: 'node[status = "Draft"], node[status = "Active"]',
        style: {
          "background-color": "#3b82f6", // Blue
          "border-color": "#60a5fa",
          "shape": "round-rectangle"
        }
      },
      // Person Nodes
      {
        selector: 'node[nodeType = "Person"]',
        style: {
          "background-color": "#8b5cf6", // Purple
          "border-color": "#a78bfa",
          "shape": "ellipse",
          "width": "50px",
          "height": "50px",
          "font-size": "9px"
        }
      },
      // Release Nodes
      {
        selector: 'node[nodeType = "Release"]',
        style: {
          "background-color": "#06b6d4", // Cyan
          "border-color": "#22d3ee",
          "shape": "hexagon",
          "width": "46px",
          "height": "46px"
        }
      },
      // Edge Styling
      {
        selector: "edge",
        style: {
          "width": 2,
          "line-color": "rgba(255, 255, 255, 0.25)",
          "target-arrow-color": "rgba(255, 255, 255, 0.4)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "label": "data(type)",
          "font-family": "Fira Code, monospace",
          "font-size": "8px",
          "color": "#94a3b8",
          "text-rotation": "autorotate",
          "text-background-opacity": 0.85,
          "text-background-color": "#070a12",
          "text-background-padding": "2px",
          "arrow-scale": 1.1
        }
      },
      // Specific Edge Colors
      {
        selector: 'edge[type = "REPLACES"]',
        style: {
          "line-color": "#f59e0b",
          "target-arrow-color": "#f59e0b",
          "width": 2.5
        }
      },
      {
        selector: 'edge[type = "CITES"]',
        style: {
          "line-color": "#38bdf8",
          "target-arrow-color": "#38bdf8"
        }
      },
      {
        selector: 'edge[type = "WROTE"]',
        style: {
          "line-color": "#a78bfa",
          "target-arrow-color": "#a78bfa",
          "line-style": "dashed"
        }
      },
      {
        selector: 'edge[type = "SIMILAR_TO"]',
        style: {
          "line-color": "#ec4899",
          "target-arrow-color": "#ec4899",
          "line-style": "dotted",
          "width": 2.5
        }
      },
      // Selected State
      {
        selector: ":selected",
        style: {
          "border-width": "3px",
          "border-color": "#38bdf8",
          "shadow-blur": 15,
          "shadow-color": "#38bdf8",
          "shadow-opacity": 0.8
        }
      }
    ],
    elements: []
  });

  // Node Click Listener: Show Metadata Drawer
  cy.on("tap", "node", (evt) => {
    const node = evt.target;
    openNodeDrawer(node.data());
  });

  // Background Tap: Close Drawer
  cy.on("tap", (evt) => {
    if (evt.target === cy) {
      closeNodeDrawer();
    }
  });

  // Drawer Close Button
  document.getElementById("drawer-close-btn").addEventListener("click", closeNodeDrawer);
}

function renderGraph(subgraph, layoutType = "dagre") {
  if (!cy) return;
  currentSubgraph = subgraph;

  cy.elements().remove();

  const elements = [];
  const nodeIds = new Set();

  // 1. Process Nodes
  if (subgraph && subgraph.nodes) {
    subgraph.nodes.forEach((n) => {
      const id = n.id;
      if (!nodeIds.has(id)) {
        nodeIds.add(id);

        let label = n.label || id;
        let nodeType = n.label || "PEP";
        let status = n.status || "";
        let title = n.title || n.name || id;

        // Clean PEP display label
        if (id.startsWith("PEP-")) {
          label = id;
          nodeType = "PEP";
        } else if (id.startsWith("Person-")) {
          label = n.name || id.replace("Person-", "");
          nodeType = "Person";
        }

        elements.push({
          group: "nodes",
          data: {
            id: id,
            label: label,
            nodeType: nodeType,
            status: status,
            title: title,
            url: n.url || (id.startsWith("PEP-") ? `https://peps.python.org/pep-${id.replace("PEP-", "").padStart(4, "0")}/` : null),
            authors: n.authors || [],
            created: n.created || ""
          }
        });
      }
    });
  }

  // 2. Process Edges
  if (subgraph && subgraph.edges) {
    subgraph.edges.forEach((e, idx) => {
      const src = e.source;
      const tgt = e.target;
      if (nodeIds.has(src) && nodeIds.has(tgt)) {
        elements.push({
          group: "edges",
          data: {
            id: `edge-${idx}-${src}-${tgt}`,
            source: src,
            target: tgt,
            type: e.type || "LINKS_TO",
            similarity: e.similarity || null
          }
        });
      }
    });
  }

  cy.add(elements);

  // Update Badge Count
  document.getElementById("graph-node-count").textContent = nodeIds.size;

  // Run Layout
  applyLayout(layoutType);
}

function applyLayout(layoutType = "dagre") {
  if (!cy || cy.nodes().length === 0) return;

  let layoutConfig = {};
  if (layoutType === "dagre") {
    layoutConfig = {
      name: "dagre",
      rankDir: "TB", // Top to Bottom DAG
      nodeSep: 45,
      rankSep: 60,
      animate: true,
      animationDuration: 400
    };
  } else {
    layoutConfig = {
      name: "cose",
      animate: true,
      animationDuration: 400,
      nodeRepulsion: 4000,
      idealEdgeLength: 65
    };
  }

  const layout = cy.layout(layoutConfig);
  layout.run();
  setTimeout(() => cy.fit(null, 30), 450);
}

// =============================================================================
// NODE INSPECTOR DRAWER
// =============================================================================

function openNodeDrawer(data) {
  const drawer = document.getElementById("node-drawer");
  const labelBadge = document.getElementById("drawer-label");
  const titleEl = document.getElementById("drawer-title");
  const subtitleEl = document.getElementById("drawer-subtitle");
  const statusEl = document.getElementById("drawer-status");
  const authorsEl = document.getElementById("drawer-authors");
  const createdEl = document.getElementById("drawer-created");
  const linkBtn = document.getElementById("drawer-pep-link");

  labelBadge.textContent = data.nodeType || "Entity";
  titleEl.textContent = data.label || data.id;
  subtitleEl.textContent = data.title || "";

  statusEl.textContent = data.status || "N/A";
  authorsEl.textContent = Array.isArray(data.authors) && data.authors.length ? data.authors.join(", ") : (data.nodeType === "Person" ? data.title : "N/A");
  createdEl.textContent = data.created || "Historical Record";

  if (data.url) {
    linkBtn.href = data.url;
    linkBtn.style.display = "block";
    linkBtn.textContent = `🔗 Open ${data.label} on peps.python.org`;
  } else if (data.id.startsWith("PEP-")) {
    const num = data.id.replace("PEP-", "").padStart(4, "0");
    linkBtn.href = `https://peps.python.org/pep-${num}/`;
    linkBtn.style.display = "block";
    linkBtn.textContent = `🔗 Open ${data.label} on peps.python.org`;
  } else {
    linkBtn.style.display = "none";
  }

  drawer.style.display = "block";
}

function closeNodeDrawer() {
  const drawer = document.getElementById("node-drawer");
  drawer.style.display = "none";
  if (cy) cy.$(":selected").unselect();
}

// =============================================================================
// GRAPH CONTROLS
// =============================================================================

function initGraphControls() {
  document.getElementById("btn-fit").addEventListener("click", () => {
    if (cy) cy.fit(null, 30);
  });

  const btnDag = document.getElementById("btn-layout-dag");
  const btnForce = document.getElementById("btn-layout-force");

  btnDag.addEventListener("click", () => {
    btnDag.classList.add("active");
    btnForce.classList.remove("active");
    applyLayout("dagre");
  });

  btnForce.addEventListener("click", () => {
    btnForce.classList.add("active");
    btnDag.classList.remove("active");
    applyLayout("cose");
  });
}

// =============================================================================
// SOURCES SLIDE-OVER DRAWER
// =============================================================================

function initSourcesDrawer() {
  const openBtn = document.getElementById("btn-open-sources");
  const closeBtn = document.getElementById("sources-close-btn");
  const drawer = document.getElementById("sources-drawer");
  const backdrop = document.getElementById("drawer-backdrop");

  openBtn.addEventListener("click", () => {
    drawer.classList.add("open");
    backdrop.classList.add("active");
  });

  closeBtn.addEventListener("click", () => {
    drawer.classList.remove("open");
    backdrop.classList.remove("active");
  });

  backdrop.addEventListener("click", () => {
    drawer.classList.remove("open");
    backdrop.classList.remove("active");
  });
}

// =============================================================================
// CHAT & REASONING STREAM
// =============================================================================

function initChat() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const clearBtn = document.getElementById("clear-chat-btn");

  // Auto-resize input
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  });

  // Enter to send (Shift+Enter for newline)
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Form Submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    input.value = "";
    input.style.height = "auto";
    await sendQuery(query);
  });

  // Clear Chat
  clearBtn.addEventListener("click", () => {
    const messages = document.getElementById("chat-messages");
    messages.innerHTML = `
      <div class="message message-agent">
        <div class="message-avatar">🧠</div>
        <div class="message-content">
          <p>Conversation cleared. Ask any question to query the knowledge graph.</p>
        </div>
      </div>
    `;
  });
}

function initQuickPills() {
  document.querySelectorAll(".pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const query = pill.getAttribute("data-query");
      if (query) {
        sendQuery(query);
      }
    });
  });
}

async function sendQuery(promptText) {
  const chatMessages = document.getElementById("chat-messages");
  const sendBtn = document.getElementById("send-btn");

  // 1. Append User Message
  const userMsg = document.createElement("div");
  userMsg.className = "message message-user";
  userMsg.innerHTML = `
    <div class="message-avatar">👤</div>
    <div class="message-content"><p>${escapeHtml(promptText)}</p></div>
  `;
  chatMessages.appendChild(userMsg);

  // 2. Append Loading Indicator
  const loadingMsg = document.createElement("div");
  loadingMsg.className = "message message-agent loading-msg";
  loadingMsg.innerHTML = `
    <div class="message-avatar">🧠</div>
    <div class="message-content">
      <div class="loading-indicator">
        <span>Traversing FalkorDB Knowledge Graph...</span>
        <div class="loading-dots">
          <div class="dot"></div>
          <div class="dot"></div>
          <div class="dot"></div>
        </div>
      </div>
    </div>
  `;
  chatMessages.appendChild(loadingMsg);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  sendBtn.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptText })
    });

    const data = await response.json();
    loadingMsg.remove();

    // 3. Render Agent Response in Chat
    const agentMsg = document.createElement("div");
    agentMsg.className = "message message-agent";
    
    // Markdown parse response answer
    const formattedHtml = typeof marked !== "undefined" ? marked.parse(data.answer) : `<p>${data.answer}</p>`;
    
    agentMsg.innerHTML = `
      <div class="message-avatar">🧠</div>
      <div class="message-content">
        ${formattedHtml}
      </div>
    `;
    chatMessages.appendChild(agentMsg);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // 4. Update Graph Canvas (Top Right)
    if (data.subgraph && data.subgraph.nodes && data.subgraph.nodes.length > 0) {
      renderGraph(data.subgraph, "dagre");
    }

    // 5. Update Live Cypher Query Trace Inspector (Bottom Right)
    updateCypherInspector(data.cypher_queries, data.total_latency_ms, data.trace_id);

    // 6. Update Sources Drawer
    updateSourcesTab(data.sources);

  } catch (err) {
    loadingMsg.remove();
    const errorMsg = document.createElement("div");
    errorMsg.className = "message message-agent";
    errorMsg.innerHTML = `
      <div class="message-avatar">⚠️</div>
      <div class="message-content" style="border-color: var(--crimson);">
        <p style="color: var(--crimson);"><strong>Error executing query:</strong> ${escapeHtml(err.message)}</p>
      </div>
    `;
    chatMessages.appendChild(errorMsg);
  } finally {
    sendBtn.disabled = false;
  }
}

// =============================================================================
// INSPECTOR UPDATERS
// =============================================================================

function updateCypherInspector(queries, totalLatency, traceId) {
  const container = document.getElementById("trace-container");
  const countBadge = document.getElementById("cypher-query-count");
  const latencyPill = document.getElementById("trace-latency-pill");

  countBadge.textContent = queries ? queries.length : 0;
  if (totalLatency) {
    latencyPill.textContent = `${totalLatency} ms`;
    latencyPill.style.display = "inline-flex";
  }

  if (!queries || queries.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>⚡ No Cypher queries were needed for this turn (synthesized from verified knowledge).</p>
      </div>
    `;
    return;
  }

  let html = `
    <div style="margin-bottom: 0.65rem; font-size: 0.76rem; color: var(--text-muted); display: flex; justify-content: space-between;">
      <span>Trace ID: <code>${traceId}</code></span>
      <span>Engine Latency: <strong style="color: var(--emerald);">${totalLatency}ms</strong></span>
    </div>
  `;

  queries.forEach((q, idx) => {
    html += `
      <div class="trace-card">
        <div class="trace-card-header">
          <span>Query #${idx + 1} (${q.row_count || 0} rows)</span>
          <span class="trace-latency">⚡ ${q.latency_ms} ms</span>
        </div>
        <pre class="trace-query"><code>${escapeHtml(q.query)}</code></pre>
      </div>
    `;
  });

  container.innerHTML = html;
}

function updateSourcesTab(sources) {
  const container = document.getElementById("sources-container");
  const countBadge = document.getElementById("sources-count");

  countBadge.textContent = sources ? sources.length : 0;

  if (!sources || sources.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>📚 No canonical sources cited in this response.</p>
      </div>
    `;
    return;
  }

  let html = `<div style="margin-bottom: 0.85rem; font-size: 0.8rem; color: var(--text-muted);">Cited Official Specifications & Heading Anchors:</div>`;
  sources.forEach((src) => {
    html += `
      <div class="source-item">
        <a href="${src}" target="_blank" rel="noopener noreferrer" class="source-link">
          🔗 ${escapeHtml(src)}
        </a>
      </div>
    `;
  });

  container.innerHTML = html;
}

// =============================================================================
// LIVE GRAPH STATS
// =============================================================================

async function fetchGraphStats() {
  try {
    const res = await fetch("/api/graph/stats");
    if (!res.ok) return;
    const data = await res.json();
    if (data.total_entities) {
      document.getElementById("entity-count-badge").textContent = `${data.total_entities.toLocaleString()} Graph Elements`;
    }
  } catch (e) {
    console.warn("Could not fetch graph stats:", e);
  }
}

function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
