// Card rendering + per-card preview/probe live in stream_card.js (loaded first).
let currentMode = 'camera';
let streamsPollInterval = null;
let tailscaleIp = null;
const STREAMS_POLL_MS = 3000;      // reconcile the active-stream grid

document.addEventListener('DOMContentLoaded', () => {
    loadCameras();
    loadFiles();
    loadNetworkInfo();
    startClock();
    refreshStreams();
    startStreamsPolling();

    document.getElementById('source-type').addEventListener('change', (e) => switchMode(e.target.value));
    document.getElementById('refresh-cameras').addEventListener('click', loadCameras);
    document.getElementById('upload-btn').addEventListener('click', uploadFile);
    document.getElementById('rtsp-port').addEventListener('input', updateEndpointPreview);
    document.getElementById('rtsp-mount').addEventListener('input', updateEndpointPreview);
    document.getElementById('add-btn').addEventListener('click', addStream);
    document.getElementById('stop-all-btn').addEventListener('click', stopAllStreams);

    switchMode(document.getElementById('source-type').value);
    updateEndpointPreview();
});

function startClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById('clock').innerText = now.toLocaleTimeString('en-US', {hour12: false});
        if (Math.random() > 0.7) {
            document.getElementById('cpu-load').innerText = Math.floor(Math.random() * 30 + 10) + '%';
        }
        if (Math.random() > 0.8) {
            document.getElementById('mem-load').innerText = (Math.random() * 0.5 + 3.8).toFixed(1) + 'GB';
        }
    }, 1000);
}

function switchMode(mode) {
    currentMode = mode;
    const secCamera = document.getElementById('camera-controls');
    const secFile = document.getElementById('file-controls');
    const secNetwork = document.getElementById('network-controls');

    secCamera.classList.add('hidden');
    secFile.classList.add('hidden');
    secNetwork.classList.add('hidden');

    if (mode === 'camera') {
        secCamera.classList.remove('hidden');
    } else if (mode === 'file') {
        secFile.classList.remove('hidden');
    } else if (mode === 'network') {
        secNetwork.classList.remove('hidden');
    }
}

// Custom RTSP output endpoint (port + mount path) chosen by the user.
function getEndpoint() {
    const port = parseInt(document.getElementById('rtsp-port').value, 10) || 8554;
    let mount = document.getElementById('rtsp-mount').value.trim() || '/stream';
    if (!mount.startsWith('/')) mount = '/' + mount;
    return { port, mount };
}

function updateEndpointPreview() {
    const { port, mount } = getEndpoint();
    document.getElementById('rtsp-preview').innerText = `rtsp://localhost:${port}${mount}`;
    const tsCont = document.getElementById('tailscale-preview-container');
    if (tailscaleIp) {
        document.getElementById('tailscale-preview').innerText = `rtsp://${tailscaleIp}:${port}${mount}`;
        tsCont.classList.remove('hidden');
    } else {
        tsCont.classList.add('hidden');
    }
}

async function loadNetworkInfo() {
    const badge = document.getElementById('tailscale-status');
    try {
        const res = await fetch('/api/network/info');
        const info = await res.json();
        if (info.tailscale_connected) {
            tailscaleIp = info.tailscale_ip;
            badge.innerText = info.tailscale_ip;
            badge.style.color = 'var(--neon-green)';
        } else {
            tailscaleIp = null;
            badge.innerText = 'OFFLINE';
            badge.style.color = 'var(--neon-red)';
        }
        updateEndpointPreview();
    } catch (e) {
        console.error("Failed to load network info", e);
        badge.innerText = 'ERR';
        badge.style.color = 'var(--neon-red)';
    }
}

async function loadCameras() {
    const select = document.getElementById('camera-select');
    select.innerHTML = '<option value="" disabled selected>SCANNING...</option>';
    try {
        const res = await fetch('/api/cameras');
        const cameras = await res.json();
        select.innerHTML = '';
        if (cameras.length === 0) {
            const option = document.createElement('option');
            option.text = "NO DEVICES FOUND";
            option.disabled = true;
            select.add(option);
            return;
        }
        cameras.forEach(cam => {
            const option = document.createElement('option');
            option.value = cam.id;
            option.text = cam.name.toUpperCase();
            select.add(option);
        });
    } catch (e) {
        console.error("Failed to load cameras", e);
        select.innerHTML = '<option value="" disabled>ERROR LOADING DEVICES</option>';
    }
}

async function loadFiles() {
    const select = document.getElementById('file-select');
    try {
        const res = await fetch('/api/files');
        const files = await res.json();
        select.innerHTML = '';
        if (files.length === 0) {
            const option = document.createElement('option');
            option.text = "ARCHIVE EMPTY";
            option.disabled = true;
            select.add(option);
            return;
        }
        files.forEach(f => {
            const option = document.createElement('option');
            option.value = f.path;
            option.text = f.name;
            select.add(option);
        });
    } catch (e) {
        console.error("Failed to load files", e);
    }
}

async function uploadFile() {
    const input = document.getElementById('file-input');
    const btn = document.getElementById('upload-btn');
    if (!input.files[0]) return alert("SELECT DATA SOURCE FIRST");

    const formData = new FormData();
    formData.append('file', input.files[0]);
    btn.innerText = "UPLOADING...";
    btn.classList.add('btn-disabled');
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        if (res.ok) {
            input.value = '';
            loadFiles();
        } else {
            alert("UPLOAD FAILED - CORRUPT DATA?");
        }
    } catch (e) {
        alert("CRITICAL ERROR DURING UPLOAD");
    } finally {
        btn.innerText = "UPLOAD ARCHIVE";
        btn.classList.remove('btn-disabled');
    }
}

// Resolve the source path for the active sidebar mode, or null if invalid.
function resolveSourcePath() {
    if (currentMode === 'camera') {
        const v = document.getElementById('camera-select').value;
        return (!v || v.includes("NO DEVICES")) ? null : v;
    }
    if (currentMode === 'file') {
        const v = document.getElementById('file-select').value;
        return (!v || v.includes("ARCHIVE EMPTY")) ? null : v;
    }
    const v = document.getElementById('network-url').value;
    return (!v || !v.startsWith('rtsp://')) ? null : v;
}

async function addStream() {
    const path = resolveSourcePath();
    if (!path) return alert("INVALID SOURCE FOR " + currentMode.toUpperCase());

    const { port, mount } = getEndpoint();
    const btn = document.getElementById('add-btn');
    btn.classList.add('btn-disabled');
    btn.innerText = "ADDING...";
    try {
        const res = await fetch('/api/streams/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type: currentMode, path, port, mount })
        });
        if (res.ok) {
            // Suggest the next free port so adding several streams is quick.
            document.getElementById('rtsp-port').value = String(port + 1);
            updateEndpointPreview();
            refreshStreams();
        } else {
            const err = await res.json().catch(() => ({}));
            const msg = res.status === 409 ? "PORT BUSY: " : "STREAM INIT FAILED: ";
            alert(msg + (err.detail || "unknown error"));
        }
    } catch (e) {
        console.error(e);
        alert("STREAM INIT ERROR: could not reach server");
    } finally {
        btn.classList.remove('btn-disabled');
        btn.innerText = "ADD STREAM";
    }
}

async function stopStream(port) {
    try {
        await fetch(`/api/streams/${port}/stop`, { method: 'POST' });
    } catch (e) {
        console.error(e);
    }
    removeCard(port);
    refreshStreams();
}

async function stopAllStreams() {
    if (cardPollers.size === 0) return;
    if (!confirm("Terminate ALL active streams?")) return;
    try {
        await fetch('/api/streams/stop_all', { method: 'POST' });
    } catch (e) {
        console.error(e);
    }
    refreshStreams();
}

// --- Grid reconcile -------------------------------------------------------

async function refreshStreams() {
    try {
        const res = await fetch('/api/streams');
        const streams = await res.json();
        reconcileGrid(streams);
        updateFooter(streams.length);
    } catch (e) {
        console.error(e);
        updateFooter(0, true);
    }
}

function reconcileGrid(streams) {
    const grid = document.getElementById('stream-grid');
    const activePorts = new Set(streams.map(s => s.port));

    // Drop cards whose stream is gone (stopped or died).
    grid.querySelectorAll('.stream-card').forEach(card => {
        const port = parseInt(card.dataset.port, 10);
        if (!activePorts.has(port)) removeCard(port);
    });

    // Add cards for newly-seen streams.
    streams.forEach(s => {
        if (!grid.querySelector(`.stream-card[data-port="${s.port}"]`)) addCard(s);
    });
}

function updateFooter(count, lost = false) {
    document.getElementById('empty-placeholder').classList.toggle('hidden', count > 0);
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const countDisplay = document.getElementById('stream-count-display');
    countDisplay.innerText = `${count} STREAMS ACTIVE`;

    if (lost) {
        dot.className = 'status-indicator offline';
        text.innerText = "CONNECTION LOST";
        text.style.color = "var(--neon-red)";
    } else if (count > 0) {
        dot.className = 'status-indicator active';
        text.innerText = "SYSTEM ACTIVE";
        text.style.color = "var(--neon-green)";
    } else {
        dot.className = 'status-indicator standby';
        text.innerText = "SYSTEM STANDBY";
        text.style.color = "var(--text-dim)";
    }
}

function startStreamsPolling() {
    if (streamsPollInterval) clearInterval(streamsPollInterval);
    streamsPollInterval = setInterval(refreshStreams, STREAMS_POLL_MS);
}
