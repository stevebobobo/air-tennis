# -*- coding: utf-8 -*-
"""Big-screen scoreboard for Air_Tennis_v4.

Run:  py tennis_screen.py      then open http://localhost:8000 on this computer (press F11 for full screen).
The phone and this computer must be on the same Wi-Fi (the phone's own hotspot works best).
Type the IP shown on the page into the app and tap Connect.

The app sends one web request per event:  /e?t=<event>&score=..&best=..&swings=..&side=..
events: hello, free, rally, swing, serve, hit, fast, slow, miss, stop, reset
"""
import json, socket, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
state = {'seq': 0, 't': 'none', 'score': 0, 'best': 0, 'swings': 0, 'side': 1, 'at': 0, 'via': ''}
lock = threading.Lock()


def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith('127.')) or ['127.0.0.1']


WIRELESS = ('wi-fi', 'wifi', 'wlan', 'wireless', '無線')
nets = [{'name': '', 'ip': ip, 'wifi': False} for ip in local_ips()]


def read_adapters():
    """Every network adapter with its name and IPv4 address, wireless ones first.
    A computer with both a cable and a Wi-Fi dongle has two addresses; the phone must use the Wi-Fi one."""
    command = ("Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and "
               "$_.IPAddress -notlike '169.254.*' } | ForEach-Object { $_.InterfaceAlias + '|' + $_.IPAddress }")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, timeout=20).stdout
        found = []
        for line in out.decode('mbcs', 'replace').splitlines():
            name, _, ip = line.strip().rpartition('|')
            if name and ip:
                found.append({'name': name, 'ip': ip, 'wifi': any(w in name.lower() for w in WIRELESS)})
        if found:
            return sorted(found, key=lambda n: (not n['wifi'], n['name']))
    except (OSError, subprocess.SubprocessError):
        pass
    return [{'name': '', 'ip': ip, 'wifi': False} for ip in local_ips()]


def watch_adapters():
    global nets
    while True:  # the address changes when the computer joins the phone's hotspot
        nets = read_adapters()
        time.sleep(5)


def number(query, key, default=0):
    try:
        return int(float(query.get(key, [default])[0]))
    except ValueError:
        return default


class Handler(BaseHTTPRequestHandler):
    def reply(self, body, ctype):
        data = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/e':
            q = parse_qs(url.query)
            with lock:
                state.update(seq=state['seq'] + 1, t=q.get('t', ['none'])[0][:10], score=number(q, 'score'),
                             best=number(q, 'best'), swings=number(q, 'swings'), side=number(q, 'side', 1),
                             at=time.time(), via=self.connection.getsockname()[0])
                print(time.strftime('%H:%M:%S'), state['t'], 'score', state['score'], 'swings', state['swings'])
            self.reply('ok', 'text/plain')
        elif url.path == '/state':
            with lock:
                self.reply(json.dumps(dict(state, nets=nets, port=PORT)), 'application/json')
        elif url.path == '/':
            self.reply(PAGE, 'text/html')
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


PAGE = r"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>體感網球 Air Tennis</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; background: #0b3d2e; color: #fff;
               font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif; }
  #court { position: absolute; inset: 0; background:
           linear-gradient(#0b3d2e 0 18%, #1f7a4d 18% 100%); }
  #net { position: absolute; left: 20%; right: 20%; top: 18%; height: 6px; background: #fff; opacity: .8; }
  .line { position: absolute; background: #fff; opacity: .55; }
  #top { position: absolute; top: 2vh; left: 0; right: 0; text-align: center; font-size: 4vh; letter-spacing: .2em; }
  #score { position: absolute; top: 20vh; left: 0; right: 0; text-align: center; font-size: 38vh; font-weight: 900;
           line-height: 1; text-shadow: 0 .6vh 0 rgba(0,0,0,.35); }
  #label { position: absolute; top: 12vh; left: 0; right: 0; text-align: center; font-size: 4vh; opacity: .85; }
  #status { position: absolute; top: 62vh; left: 22%; right: 22%; text-align: center; font-size: min(8vh, 3.6vw);
            font-weight: 700; white-space: nowrap; z-index: 2; }
  #bar { position: absolute; left: 20%; top: 77vh; width: 60%; height: 3vh; border: 3px solid #fff; border-radius: 2vh;
         overflow: hidden; visibility: hidden; }
  #fill { height: 100%; width: 100%; background: #ffd43b; }
  #info { position: absolute; bottom: 3vh; left: 2%; right: 2%; text-align: center; font-size: min(3.2vh, 1.7vw);
          opacity: .9; }
  #ball { position: absolute; width: 6vh; height: 6vh; border-radius: 50%; background: #d7f205;
          box-shadow: 0 0 2vh rgba(215,242,5,.8); left: 50%; top: 70vh; transform: translate(-50%, -50%);
          z-index: 1; visibility: hidden; }
  .miss #court { background: linear-gradient(#3d0b0b 0 18%, #7a1f1f 18% 100%); }
</style></head>
<body><div id="court"><div id="net"></div>
<div class="line" style="left:20%;top:18%;bottom:0;width:4px"></div>
<div class="line" style="right:20%;top:18%;bottom:0;width:4px"></div></div>
<div id="top">體感網球　AIR TENNIS</div>
<div id="label">得分 SCORE</div><div id="score">0</div>
<div id="status">等待手機連線…</div>
<div id="bar"><div id="fill"></div></div>
<div id="ball"></div>
<div id="info"></div>
<script>
const $ = id => document.getElementById(id);
let seq = -1, anim = null;
function fly(x0, y0, s0, x1, y1, s1, ms) {            // move the ball; s = size in vh
  cancelAnimationFrame(anim);
  const t0 = performance.now(), ball = $('ball');
  ball.style.visibility = 'visible';
  (function step(now) {
    const k = Math.min(1, (now - t0) / ms), arc = Math.sin(Math.PI * k) * 12;
    ball.style.left = (x0 + (x1 - x0) * k) + '%';
    ball.style.top = (y0 + (y1 - y0) * k - arc) + 'vh';
    const s = s0 + (s1 - s0) * k;
    ball.style.width = ball.style.height = s + 'vh';
    if (k < 1) anim = requestAnimationFrame(step);
  })(t0);
}
function countdown(ms) {
  const fill = $('fill');
  $('bar').style.visibility = 'visible';
  fill.style.transition = 'none'; fill.style.width = '100%';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    fill.style.transition = 'width ' + ms + 'ms linear'; fill.style.width = '0%';
  }));
}
function show(s) {
  const side = s.side == 1 ? '左邊 LEFT' : '右邊 RIGHT', x = s.side == 1 ? 30 : 70;
  document.body.className = '';
  cancelAnimationFrame(anim); $('ball').style.visibility = 'hidden';   // only shown while a ball is in play
  $('bar').style.visibility = 'hidden';
  $('label').textContent = '得分 SCORE'; $('score').textContent = s.score;
  switch (s.t) {
    case 'hello': $('status').textContent = '📱 手機已連線 Phone connected'; break;
    case 'free': $('status').textContent = '自由揮拍 Free swing'; $('label').textContent = '揮拍 SWINGS';
                 $('score').textContent = s.swings; break;
    case 'swing': $('status').textContent = '啵！'; $('label').textContent = '揮拍 SWINGS';
                  $('score').textContent = s.swings; fly(50, 70, 6, 50, 24, 2, 500); break;
    case 'rally': $('status').textContent = '對打模式：揮拍發球 Swing to serve'; break;
    case 'serve': $('status').textContent = '發球！ Serve!'; fly(50, 70, 6, 50, 24, 2, 900); break;
    case 'hit': $('status').textContent = '好球！ Nice!'; fly(50, 70, 6, 50, 24, 2, 900); break;
    case 'fast': $('status').textContent = '⚡ 快球 FAST　' + side; fly(50, 24, 2, x, 70, 7, 1800); countdown(1800); break;
    case 'slow': $('status').textContent = '🎾 慢球 SLOW　' + side; fly(50, 24, 2, x, 70, 7, 3000); countdown(3000); break;
    case 'miss': $('status').textContent = '❌ MISS！遊戲結束 Game over'; document.body.className = 'miss'; break;
    case 'stop': $('status').textContent = '✋ 遊戲結束 Game over'; break;
    case 'reset': $('status').textContent = '已歸零 Reset'; break;
  }
}
async function poll() {
  try {
    const s = await (await fetch('/state')).json();
    const port = s.port == 8000 ? '' : '（埠號 ' + s.port + '）';
    // The phone has connected: show the one address it really used. Before that, list every adapter by name.
    $('info').textContent = s.via && s.via != '127.0.0.1'
      ? '最高 BEST ' + s.best + '　｜　✅ 手機已連線，使用的 IP： ' + s.via + port
      : '在 App 輸入這台電腦的 IP：　' + s.nets.map(n => (n.wifi ? '📶 ' : '🔌 ') + n.name + ' ' + n.ip +
          (n.wifi ? '（手機熱點用這個）' : '')).join('　｜　') + port;
    if (s.seq !== seq) { if (seq !== -1 || s.seq) show(s); seq = s.seq; }
  } catch (e) { $('info').textContent = '伺服器沒有回應'; }
  setTimeout(poll, 120);
}
poll();
</script></body></html>
"""

if __name__ == '__main__':
    print('Air Tennis big screen: open  http://localhost:%d  on this computer' % PORT)
    nets = read_adapters()
    for n in nets:
        print('  %s %-28s %s' % ('Wi-Fi' if n['wifi'] else 'cable', n['name'], n['ip']))
    print('Type the Wi-Fi address into the app (the page shows it too).')
    threading.Thread(target=watch_adapters, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
