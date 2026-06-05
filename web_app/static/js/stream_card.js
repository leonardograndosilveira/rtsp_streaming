// Per-card live preview + probe. One card per active RTSP stream.
// Globals shared with app.js (both loaded as plain scripts): cardPollers is
// read by stopAllStreams; addCard/removeCard are called by reconcileGrid.
const cardPollers = new Map();     // port -> setInterval id for that card's preview
const PREVIEW_INTERVAL_MS = 1000;  // per-card snapshot poll (~1 fps)

function addCard(stream) {
    const tpl = document.getElementById('stream-card-template');
    const card = tpl.content.firstElementChild.cloneNode(true);
    card.dataset.port = stream.port;
    card.querySelector('.card-title').innerText = stream.mount;
    card.querySelector('.card-port').innerText = ':' + stream.port;
    card.querySelector('.card-url').innerText = stream.url;
    const tsUrlEl = card.querySelector('.card-tailscale-url');
    if (stream.tailscale_url) {
        tsUrlEl.innerText = '↗ VPN: ' + stream.tailscale_url;
        tsUrlEl.classList.remove('hidden');
    }
    card.querySelector('.card-test').addEventListener('click', () => probeCard(stream.port, card));
    card.querySelector('.card-stop').addEventListener('click', () => stopStream(stream.port));
    document.getElementById('stream-grid').appendChild(card);
    startCardPreview(stream.port, card);
}

function removeCard(port) {
    stopCardPreview(port);
    const card = document.querySelector(`.stream-card[data-port="${port}"]`);
    if (card) card.remove();
}

// Each card polls its own live JPEG frame; a frame that loads == source works.
// Chained (not setInterval): the next request fires only AFTER the current
// frame settles. A slow/dead source's snapshot can take up to the server's 8s
// ffmpeg timeout, so a fixed 1s interval would pile requests up and exhaust the
// browser's per-host connection pool -- which then blocks adding new streams.
// Chaining caps in-flight snapshots at one per card.
function startCardPreview(port, card) {
    const img = card.querySelector('.card-frame');
    const tick = () => { img.src = `/api/streams/${port}/snapshot?t=${Date.now()}`; };
    const again = () => {
        if (!cardPollers.has(port)) return;  // card was stopped mid-request
        cardPollers.set(port, setTimeout(tick, PREVIEW_INTERVAL_MS));
    };
    img.onload = () => { setCardLiveness(card, 'live', 'LIVE'); again(); };
    img.onerror = () => { setCardLiveness(card, 'dead', 'NO SIGNAL'); again(); };
    cardPollers.set(port, null);  // mark active (no timer pending yet)
    tick();
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
