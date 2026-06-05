// Per-card live preview + probe. One card per active RTSP stream.
// Globals shared with app.js (both loaded as plain scripts): cardPollers is
// read by stopAllStreams; addCard/removeCard are called by reconcileGrid.
const cardPollers = new Map();     // port -> null; tracks which cards are active

function addCard(stream) {
    const tpl = document.getElementById('stream-card-template');
    const card = tpl.content.firstElementChild.cloneNode(true);
    card.dataset.port = stream.port;
    card.querySelector('.card-title').innerText = stream.mount;
    card.querySelector('.card-port').innerText = ':' + stream.port;
    card.querySelector('.card-url').innerText = stream.url;
    const tsUrlEl = card.querySelector('.card-tailscale-url');
    if (stream.tailscale_url) {
        card.querySelector('.card-tailscale-text').innerText = '↗ VPN: ' + stream.tailscale_url;
        const copyBtn = card.querySelector('.card-copy');
        copyBtn.addEventListener('click', () => copyVpnUrl(stream.tailscale_url, copyBtn));
        tsUrlEl.classList.remove('hidden');
    }
    card.querySelector('.card-test').addEventListener('click', () => probeCard(stream.port, card));
    card.querySelector('.card-stop').addEventListener('click', () => stopStream(stream.port));
    document.getElementById('stream-grid').appendChild(card);
    startCardPreview(stream.port, card);
}

// Copy the raw VPN URL (no '↗ VPN:' prefix) to clipboard. clipboard API needs a
// secure context (https or localhost); fall back to a hidden textarea + execCommand
// so copy still works when the dashboard is served over plain-HTTP LAN.
async function copyVpnUrl(url, btn) {
    const original = btn.innerText;
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(url);
        } else {
            const ta = document.createElement('textarea');
            ta.value = url;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            ta.remove();
        }
        btn.innerText = 'COPIED';
    } catch (e) {
        console.error('copy failed', e);
        btn.innerText = 'FAILED';
    }
    setTimeout(() => { btn.innerText = original; }, 1500);
}

function removeCard(port) {
    stopCardPreview(port);
    const card = document.querySelector(`.stream-card[data-port="${port}"]`);
    if (card) card.remove();
}

// Grab ONE preview frame per card, then keep it static. Each snapshot spawns a
// fresh `ffmpeg -rtsp_transport tcp` RTSP client: connect, wait for a keyframe,
// decode, tear down. Polling that once per second per card produced a SETUP/
// TEARDOWN storm against the GStreamer rtsp-server's shared pipeline that
// stuttered real viewers (VLC). A single grab gives the card a thumbnail without
// competing with the live stream. Liveness reflects that one grab.
function startCardPreview(port, card) {
    const img = card.querySelector('.card-frame');
    img.onload = () => setCardLiveness(card, 'live', 'LIVE');
    img.onerror = () => setCardLiveness(card, 'dead', 'NO SIGNAL');
    cardPollers.set(port, null);  // mark active so stopCardPreview/stopAll still track it
    img.src = `/api/streams/${port}/snapshot?t=${Date.now()}`;
}

function stopCardPreview(port) {
    if (cardPollers.get(port)) clearTimeout(cardPollers.get(port));
    cardPollers.delete(port);
}

function setCardLiveness(card, state, text) {
    const banner = card.querySelector('.card-liveness');
    banner.className = `card-liveness liveness-${state}`;
    const dot = banner.querySelector('.status-indicator');
    dot.className = `status-indicator ${state === 'live' ? 'active' : state === 'dead' ? 'offline' : 'standby'}`;
    card.querySelector('.card-liveness-text').innerText = text;
}

async function probeCard(port, card) {
    const btn = card.querySelector('.card-test');
    btn.innerText = "TESTING...";
    btn.classList.add('btn-disabled');
    try {
        const res = await fetch(`/api/streams/${port}/probe`);
        const data = await res.json();
        if (data.success) {
            card.querySelector('.stat-res').innerText = data.resolution;
            card.querySelector('.stat-codec').innerText = (data.codec || 'N/A').toUpperCase();
            card.querySelector('.stat-bitrate').innerText = data.bitrate ? (data.bitrate / 1000).toFixed(0) + " KBPS" : "N/A";
            card.querySelector('.card-stats').classList.remove('hidden');
            btn.innerText = "SOURCE OK";
        } else {
            setCardLiveness(card, 'dead', 'TEST FAILED');
            alert("TEST FAILED: " + (data.error || "source not producing a valid stream"));
            btn.innerText = "TEST";
        }
    } catch (e) {
        console.error(e);
        alert("TEST ERROR: could not reach probe endpoint");
        btn.innerText = "TEST";
    } finally {
        setTimeout(() => { btn.innerText = "TEST"; btn.classList.remove('btn-disabled'); }, 3000);
    }
}
