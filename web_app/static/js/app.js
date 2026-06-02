let currentMode = 'camera';
let statusPollInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    // Initial Load
    loadCameras();
    loadFiles();
    checkStatus();
    startStatusPolling();
    startClock();

    // Event Listeners
    document.getElementById('source-type').addEventListener('change', (e) => {
        switchMode(e.target.value);
    });

    document.getElementById('refresh-cameras').addEventListener('click', loadCameras);
    document.getElementById('upload-btn').addEventListener('click', uploadFile);
    document.getElementById('connect-network-btn').addEventListener('click', () => {
        const btn = document.getElementById('connect-network-btn');
        const url = document.getElementById('network-url').value;
        if (url && url.startsWith('rtsp://')) {
            const originalText = btn.innerText;
            btn.innerText = "LINK ESTABLISHED";
            btn.classList.add('btn-primary');
            setTimeout(() => {
                btn.innerText = originalText;
                btn.classList.remove('btn-primary');
            }, 2000);
        } else {
            alert("INVALID NETWORK TARGET");
        }
    });
    document.getElementById('start-btn').addEventListener('click', startStream);
    document.getElementById('stop-btn').addEventListener('click', stopStream);
    document.getElementById('probe-btn').addEventListener('click', probeStream);
    
    // Auto-select based on initial dropdown state (usually 'camera')
    switchMode(document.getElementById('source-type').value);
});

function startClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById('clock').innerText = now.toLocaleTimeString('en-US', {hour12: false});
        // Simulate CPU/Mem fluctuation for effect
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

async function loadCameras() {
    const select = document.getElementById('camera-select');
    select.innerHTML = '<option value="" disabled selected>SCANNING...</option>';
    
    try {
        const res = await fetch('/api/cameras');
        const cameras = await res.json();
        select.innerHTML = ''; // Clear scanning text
        
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
    // Don't clear immediately to avoid flicker if just refreshing logic, but here we can
    // select.innerHTML = '<option value="" disabled selected>LOADING...</option>';

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
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        if (res.ok) {
            // alert("DATA UPLOAD COMPLETE");
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

async function startStream() {
    let type = currentMode;
    let path = '';
    
    if (type === 'camera') {
        path = document.getElementById('camera-select').value;
        if (!path || path.includes("NO DEVICES")) return alert("INVALID CAMERA FEED");
    } else if (type === 'file') {
        path = document.getElementById('file-select').value;
         if (!path || path.includes("ARCHIVE EMPTY")) return alert("INVALID FILE SOURCE");
    } else if (type === 'network') {
        path = document.getElementById('network-url').value;
        if (!path || !path.startsWith('rtsp://')) return alert("INVALID NETWORK TARGET");
    }

    const btnStart = document.getElementById('start-btn');
    btnStart.classList.add('btn-disabled');
    btnStart.innerText = "INITIALIZING...";

    try {
        const res = await fetch('/api/stream/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type, path })
        });
        
        if (res.ok) {
            checkStatus();
        } else {
            alert("STREAM INITIALIZATION FAILED");
            btnStart.classList.remove('btn-disabled');
            btnStart.innerText = "INITIATE STREAM";
        }
    } catch (e) {
        console.error(e);
        btnStart.classList.remove('btn-disabled');
        btnStart.innerText = "INITIATE STREAM";
    }
}

async function stopStream() {
    const btnStop = document.getElementById('stop-btn');
    btnStop.innerText = "TERMINATING...";
    
    try {
        await fetch('/api/stream/stop', { method: 'POST' });
        checkStatus();
    } catch (e) {
        console.error(e);
    } finally {
        btnStop.innerText = "TERMINATE";
    }
}

async function probeStream() {
    const btnProbe = document.getElementById('probe-btn');
    const hudOverlay = document.getElementById('hud-overlay');
    
    btnProbe.innerText = "PROBING...";
    btnProbe.classList.add('btn-disabled');

    try {
        const res = await fetch('/api/stream/probe');
        const data = await res.json();
        
        if (data.success) {
            document.getElementById('hud-res').innerText = data.resolution;
            document.getElementById('hud-codec').innerText = data.codec.toUpperCase();
            document.getElementById('hud-bitrate').innerText = (data.bitrate / 1000).toFixed(0) + " KBPS";
            
            if (data.simulated) {
                document.getElementById('hud-sim-tag').classList.remove('hidden');
            } else {
                document.getElementById('hud-sim-tag').classList.add('hidden');
            }
            
            hudOverlay.classList.remove('hidden');
            btnProbe.innerText = "HEALTH OK";
            
            setTimeout(() => {
                btnProbe.innerText = "HEALTH CHECK";
                btnProbe.classList.remove('btn-disabled');
            }, 3000);
        } else {
            alert("PROBE FAILED: UNABLE TO ANALYZE STREAM");
            btnProbe.innerText = "HEALTH CHECK";
            btnProbe.classList.remove('btn-disabled');
        }
    } catch (e) {
        console.error(e);
        btnProbe.innerText = "HEALTH CHECK";
        btnProbe.classList.remove('btn-disabled');
    }
}

async function checkStatus() {
    try {
        const res = await fetch('/api/stream/status');
        const data = await res.json();
        updateUI(data);
    } catch (e) {
        console.error(e);
        // Set offline status on error
        updateUI({ active: false, url: "CONNECTION LOST" });
    }
}

function updateUI(status) {
    const btnStart = document.getElementById('start-btn');
    const btnStop = document.getElementById('stop-btn');
    const btnProbe = document.getElementById('probe-btn');
    
    const viewportPlaceholder = document.getElementById('video-placeholder');
    const streamContainer = document.getElementById('stream-container');
    const hudOverlay = document.getElementById('hud-overlay');
    
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const rtspDisplay = document.getElementById('rtsp-url-display');

    if (status.active) {
        // Stream Running
        btnStart.classList.add('btn-disabled');
        btnStart.innerText = "STREAM ACTIVE";
        
        btnStop.classList.remove('btn-disabled');
        btnProbe.classList.remove('hidden');
        
        viewportPlaceholder.classList.add('hidden');
        streamContainer.classList.remove('hidden');
        
        statusDot.className = 'status-indicator active';
        statusText.innerText = "SYSTEM ACTIVE";
        statusText.style.color = "var(--neon-green)";
        
        rtspDisplay.innerText = status.url || "RTSP://UNKNOWN";
        rtspDisplay.style.color = "var(--neon-green)";

        if (hudOverlay.classList.contains('hidden')) {
            probeStream();
        }
    } else {
        // Stream Stopped
        btnStart.classList.remove('btn-disabled');
        btnStart.innerText = "INITIATE STREAM";
        
        btnStop.classList.add('btn-disabled');
        btnProbe.classList.add('hidden');
        hudOverlay.classList.add('hidden');
        
        viewportPlaceholder.classList.remove('hidden');
        streamContainer.classList.add('hidden');
        
        // If it was connection lost, keep it red
        if (status.url === "CONNECTION LOST") {
            statusDot.className = 'status-indicator offline';
            statusText.innerText = "CONNECTION LOST";
            statusText.style.color = "var(--neon-red)";
        } else {
            statusDot.className = 'status-indicator standby';
            statusText.innerText = "SYSTEM STANDBY";
            statusText.style.color = "var(--text-dim)";
            rtspDisplay.innerText = "RTSP://DISCONNECTED";
            rtspDisplay.style.color = "var(--text-dim)";
        }
    }
}

function startStatusPolling() {
    if (statusPollInterval) clearInterval(statusPollInterval);
    statusPollInterval = setInterval(checkStatus, 3000);
}
