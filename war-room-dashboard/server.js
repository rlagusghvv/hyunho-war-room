const express = require('express');
const Parser = require('rss-parser');
const { execFile } = require('child_process');
const path = require('path');

const app = express();
const parser = new Parser();
const PORT = process.env.PORT || 4177;
const KIS_DIR = process.env.KIS_DIR || __dirname;
const marketCache = new Map();
const liveRelays = new Map();
const YTDLP_BIN = process.env.YTDLP_BIN || '/Users/kimhyunhomacmini/Library/Python/3.9/bin/yt-dlp';
const liveChannels = {
  ytn: { id: 'ytn', name: 'YTN', url: 'https://www.youtube.com/@YTNnews24/live' },
  yonhap: { id: 'yonhap', name: '연합뉴스TV', url: 'https://www.youtube.com/@yonhapnewstv23/live' },
  hankyung: { id: 'hankyung', name: '한국경제TV', url: 'https://www.youtube.com/@hankyungtv/live' },
  reuters: { id: 'reuters', name: 'Reuters', url: 'https://www.youtube.com/@Reuters/live' },
  ap: { id: 'ap', name: 'AP News', url: 'https://www.youtube.com/@AssociatedPress/live' },
  sky: { id: 'sky', name: 'Sky News', url: 'https://www.youtube.com/@SkyNews/live' },
  dw: { id: 'dw', name: 'DW News', url: 'https://www.youtube.com/@dwnews/live' }
};

const liveIdCache = {
  updatedAt: 0,
  items: {
    ytn: '92feK1esksc',
    yonhap: 'LH77lflaM5w',
    hankyung: 'NJUjU9ALj4A',
    reuters: 'XYRdmw10RVw',
    ap: '45sRVqWwUIQ',
    sky: 'YDvsBbKfLPA',
    dw: 'LuKwFajn37U'
  },
  meta: {}
};

const gfMap = {
  '^spx': 'https://www.google.com/finance/quote/.INX:INDEXSP',
  '^ndq': 'https://www.google.com/finance/quote/NDX:INDEXNASDAQ',
  '^dji': 'https://www.google.com/finance/quote/.DJI:INDEXDJX',
  'usdkrw': 'https://www.google.com/finance/quote/USD-KRW',
  'cl.f': 'https://www.google.com/finance/quote/CLW00:NYMEX',
  'gc.f': 'https://www.google.com/finance/quote/GCW00:COMEX',
  'ng.f': 'https://www.google.com/finance/quote/NGW00:NYMEX',
  'si.f': 'https://www.google.com/finance/quote/SIW00:COMEX',
  'hg.f': 'https://www.google.com/finance/quote/HGW00:COMEX',
  'btcusd': 'https://www.google.com/finance/quote/BTC-USD'
};

async function fetchTextWithTimeout(url, ms = 5000, headers = { 'user-agent': 'Mozilla/5.0' }) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { headers, signal: ctrl.signal });
    return await r.text();
  } finally {
    clearTimeout(t);
  }
}

async function fetchGooglePrice(symbol) {
  const u = gfMap[symbol];
  if (!u) return null;
  try {
    const html = await fetchTextWithTimeout(u, 5000);
    const m = html.match(/data-last-price="([0-9.\-]+)"/);
    if (!m) return null;
    const v = Number(m[1]);
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

app.use(express.static(path.join(__dirname, 'public')));

function runNode(code, cwd, timeout = 15000) {
  return new Promise((resolve, reject) => {
    execFile('node', ['-e', code], { cwd, timeout }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout.toString().trim());
    });
  });
}

function stopRelay(id) {
  liveRelays.delete(id);
}

async function resolveYoutubeId(channelUrl) {
  return await new Promise((resolve, reject) => {
    execFile(YTDLP_BIN, ['--print', 'id', channelUrl], { timeout: 12000 }, (err, stdout, stderr) => {
      if (err) return reject(new Error((stderr || err.message).toString()));
      const id = (stdout || '').toString().trim().split('\n').filter(Boolean).pop();
      if (!id) return reject(new Error('id not found'));
      resolve(id);
    });
  });
}

let _liveRefreshRunning = false;
async function refreshLiveIds() {
  if (_liveRefreshRunning) return;
  _liveRefreshRunning = true;
  try {
    const entries = await Promise.all(Object.values(liveChannels).map(async (c) => {
      try {
        const id = await resolveYoutubeId(c.url);
        return [c.id, id, true];
      } catch {
        return [c.id, liveIdCache.items[c.id] || null, false];
      }
    }));
    const now = Date.now();
    for (const [k, v, ok] of entries) {
      if (v) liveIdCache.items[k] = v;
      const prev = liveIdCache.meta[k] || { failCount: 0 };
      liveIdCache.meta[k] = ok
        ? { ok: true, failCount: 0, lastSuccessAt: now }
        : { ok: false, failCount: (prev.failCount || 0) + 1, lastSuccessAt: prev.lastSuccessAt || 0 };
    }
    liveIdCache.updatedAt = now;
  } finally {
    _liveRefreshRunning = false;
  }
}

app.get('/api/search', async (req, res) => {
  try {
    const q = (req.query.q || '').toString().trim();
    if (!q) return res.json({ ok: true, items: [] });
    const url = `https://ac.stock.naver.com/ac?q=${encodeURIComponent(q)}&target=stock`;
    const r = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0' } });
    const j = await r.json();
    const items = (j.items || []).map((x) => ({
      code: x.code,
      name: x.name,
      market: x.typeCode,
    }));
    res.json({ ok: true, items });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/snapshot', async (req, res) => {
  try {
    const symbol = (req.query.symbol || '0009K0').toString().toUpperCase();
    execFile('node', ['kis_bridge.mjs', 'snapshot', symbol], { cwd: KIS_DIR, timeout: 18000 }, (err, stdout, stderr) => {
      if (err) return res.status(500).json({ ok: false, error: (stderr || err.message).toString() });
      try {
        const data = JSON.parse((stdout || '').toString().trim());
        return res.json({ ok: true, updatedAt: new Date().toISOString(), data });
      } catch (e) {
        return res.status(500).json({ ok: false, error: e.message });
      }
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/chart', async (req, res) => {
  try {
    const symbol = (req.query.symbol || '0009K0').toString().toUpperCase();
    execFile('node', ['kis_bridge.mjs', 'chart', symbol], { cwd: KIS_DIR, timeout: 18000 }, (err, stdout, stderr) => {
      if (err) return res.status(500).json({ ok: false, error: (stderr || err.message).toString() });
      try {
        const data = JSON.parse((stdout || '').toString().trim());
        return res.json({ ok: true, data });
      } catch (e) {
        return res.status(500).json({ ok: false, error: e.message });
      }
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/portfolio', async (_req, res) => {
  try {
    execFile('node', ['kis_bridge.mjs', 'portfolio'], { cwd: KIS_DIR, timeout: 18000 }, (err, stdout, stderr) => {
      if (err) return res.status(500).json({ ok: false, error: (stderr || err.message).toString() });
      try {
        const data = JSON.parse((stdout || '').toString().trim());
        return res.json({ ok: true, updatedAt: new Date().toISOString(), data });
      } catch (e) {
        return res.status(500).json({ ok: false, error: e.message });
      }
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/geopolitics', async (_req, res) => {
  try {
    const queries = [
      'Reuters Iran US Strait of Hormuz latest',
      'AP News Iran US latest',
      'Ukraine Russia Reuters latest',
    ];
    const all = [];
    for (const q of queries) {
      const url = `https://news.google.com/rss/search?q=${encodeURIComponent(q)}&hl=en-US&gl=US&ceid=US:en`;
      const feed = await parser.parseURL(url);
      for (const item of (feed.items || []).slice(0, 4)) {
        all.push({
          title: item.title,
          link: item.link,
          pubDate: item.pubDate,
          source: q.includes('Reuters') ? 'Reuters' : q.includes('AP') ? 'AP' : 'Mixed',
        });
      }
    }
    all.sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));
    res.json({ ok: true, updatedAt: new Date().toISOString(), items: all.slice(0, 12) });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/community', async (req, res) => {
  try {
    const symbol = (req.query.symbol || '0009K0').toString().toUpperCase();
    const name = (req.query.name || '').toString().trim();

    // Try to resolve Naver stock code (digits or alnum like 0009K0)
    let naverCode = /^[0-9A-Z]{4,8}$/.test(symbol) ? symbol : null;
    if (!naverCode) {
      const q1 = symbol;
      const r1 = await fetch(`https://ac.stock.naver.com/ac?q=${encodeURIComponent(q1)}&target=stock`, { headers: { 'user-agent': 'Mozilla/5.0' } });
      const j1 = await r1.json().catch(() => ({}));
      naverCode = (j1.items || [])[0]?.code || null;
    }
    if (!naverCode && name) {
      const r2 = await fetch(`https://ac.stock.naver.com/ac?q=${encodeURIComponent(name)}&target=stock`, { headers: { 'user-agent': 'Mozilla/5.0' } });
      const j2 = await r2.json().catch(() => ({}));
      naverCode = (j2.items || [])[0]?.code || null;
    }

    const naverBoardUrl = naverCode ? `https://finance.naver.com/item/board.naver?code=${naverCode}` : null;

    const q = `${name || symbol} 종토방`;
    const url = `https://news.google.com/rss/search?q=${encodeURIComponent(q)}&hl=ko&gl=KR&ceid=KR:ko`;
    const feed = await parser.parseURL(url);
    const items = (feed.items || []).slice(0, 8).map((it) => ({
      title: it.title,
      link: it.link,
      pubDate: it.pubDate,
      source: '미확인',
    }));
    res.json({ ok: true, updatedAt: new Date().toISOString(), naverCode, naverBoardUrl, items });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/markets', async (_req, res) => {
  try {
    const pairs = [
      ['S&P500','^spx'], ['NASDAQ100','^ndq'], ['DOW','^dji'], ['USDKRW','usdkrw'],
      ['WTI','cl.f'], ['GOLD','gc.f'], ['NATGAS','ng.f'], ['SILVER','si.f'], ['COPPER','hg.f'], ['BTC','btcusd']
    ];

    const globals = await Promise.all(pairs.map(async ([label, code]) => {
      const prev = marketCache.get(label);
      const c = await fetchGooglePrice(code);
      const close = Number.isFinite(c) ? c : (prev?.close ?? null);
      const open = prev?.open ?? close;
      const chg = Number.isFinite(open) && Number.isFinite(close) ? close - open : null;
      const pct = Number.isFinite(open) && open !== 0 && Number.isFinite(close) ? (chg / open) * 100 : null;
      const item = { symbol: label, rawSymbol: code, open, high: prev?.high ?? close, low: prev?.low ?? close, close, chg, pct, stale: !Number.isFinite(c) };
      if (Number.isFinite(close)) marketCache.set(label, item);
      return item;
    }));

    const map = new Map(globals.map((x) => [x.symbol, x]));
    try {
      const kr = await new Promise((resolve, reject) => {
        execFile('node', ['kis_bridge.mjs', 'kr-indexes'], { cwd: KIS_DIR, timeout: 5000 }, (err, stdout, stderr) => {
          if (err) return reject(new Error(stderr || err.message));
          resolve(JSON.parse((stdout || '').toString().trim()));
        });
      });
      for (const it of kr) map.set(it.symbol, it);
    } catch {}

    if (!map.has('KOSPI')) map.set('KOSPI', marketCache.get('KOSPI') || { symbol:'KOSPI', rawSymbol:'0001', close:null, stale:true });
    if (!map.has('KOSDAQ')) map.set('KOSDAQ', marketCache.get('KOSDAQ') || { symbol:'KOSDAQ', rawSymbol:'1001', close:null, stale:true });

    return res.json({ ok: true, updatedAt: new Date().toISOString(), items: Array.from(map.values()) });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/market-history', async (req, res) => {
  try {
    const symbol = (req.query.symbol || '^spx').toString().toLowerCase();
    const u = `https://stooq.com/q/d/l/?s=${encodeURIComponent(symbol)}&i=d`;
    const txt = await fetchTextWithTimeout(u, 5000);
    const lines = txt.trim().split('\n').slice(1).filter(Boolean);
    const rows = lines.slice(-120).map((ln) => {
      const [date, open, high, low, close, volume] = ln.split(',');
      return { date, open: Number(open || 0), high: Number(high || 0), low: Number(low || 0), close: Number(close || 0), volume: Number(volume || 0) };
    });
    res.json({ ok: true, updatedAt: new Date().toISOString(), symbol, data: rows });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/macro-history', async (_req, res) => {
  try {
    const series = { 'S&P500': [], 'NASDAQ100': [], 'USDKRW': [], 'GOLD': [], 'WTI': [], 'NATGAS': [], 'SILVER': [], 'COPPER': [] };

    // KR history from KIS first (fast + reliable)
    try {
      const krSeries = await new Promise((resolve, reject) => {
        execFile('node', ['kis_bridge.mjs', 'kr-history'], { cwd: KIS_DIR, timeout: 8000 }, (err, stdout, stderr) => {
          if (err) return reject(new Error(stderr || err.message));
          resolve(JSON.parse((stdout || '').toString().trim()));
        });
      });
      series.KOSPI = krSeries.KOSPI || [];
      series.KOSDAQ = krSeries.KOSDAQ || [];
    } catch {
      series.KOSPI = [];
      series.KOSDAQ = [];
    }

    // lightweight fallback series from current market cache (repeat point so chart never blanks)
    const now = new Date().toISOString().slice(0,10).replace(/-/g,'');
    for (const [label, key] of [['S&P500','S&P500'],['NASDAQ100','NASDAQ100'],['USDKRW','USDKRW'],['GOLD','GOLD'],['WTI','WTI'],['NATGAS','NATGAS'],['SILVER','SILVER'],['COPPER','COPPER']]) {
      const v = marketCache.get(key)?.close;
      if (Number.isFinite(v)) series[label] = [{ date: now, open: v, high: v, low: v, close: v, volume: 0 }];
    }

    res.json({ ok: true, updatedAt: new Date().toISOString(), series });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/intel', async (_req, res) => {
  try {
    const feeds = [
      // KR
      { url: 'https://www.yna.co.kr/rss/economy.xml', tag: 'KR-연합경제' },
      { url: 'https://www.mk.co.kr/rss/30000001/', tag: 'KR-매경' },
      // global wire/media (worldmonitor style)
      { url: 'https://feeds.bbci.co.uk/news/world/rss.xml', tag: 'BBC-World' },
      { url: 'https://www.theguardian.com/world/rss', tag: 'Guardian-World' },
      { url: 'https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en', tag: 'AP' },
      { url: 'https://news.google.com/rss/search?q=site:reuters.com+world&hl=en-US&gl=US&ceid=US:en', tag: 'Reuters' },
      { url: 'https://www.cnbc.com/id/100003114/device/rss/rss.html', tag: 'CNBC' },
      { url: 'https://finance.yahoo.com/rss/topstories', tag: 'YahooFinance' },
      // alerts
      { url: 'https://www.who.int/rss-feeds/news-english.xml', tag: 'WHO' },
      { url: 'https://travel.state.gov/_res/rss/TAsTWs.xml', tag: 'US-Travel' },
      { url: 'https://www.safetravel.govt.nz/news/feed', tag: 'NZ-Travel' }
    ];
    const items = [];
    for (const f of feeds) {
      try {
        const feed = await parser.parseURL(f.url);
        for (const it of (feed.items || []).slice(0, 4)) {
          items.push({ title: it.title, link: it.link, pubDate: it.pubDate, source: f.tag });
        }
      } catch {}
    }
    items.sort((a, b) => new Date(b.pubDate || 0) - new Date(a.pubDate || 0));
    res.json({ ok: true, updatedAt: new Date().toISOString(), items: items.slice(0, 20) });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/live/channels', (_req, res) => {
  const now = Date.now();
  const items = Object.values(liveChannels).map((c) => {
    const meta = liveIdCache.meta[c.id] || {};
    const fresh = meta.lastSuccessAt ? ((now - meta.lastSuccessAt) < 40 * 60 * 1000) : true;
    return {
      id: c.id,
      name: c.name,
      url: c.url,
      videoId: liveIdCache.items[c.id] || null,
      embed: liveIdCache.items[c.id] ? `https://www.youtube.com/embed/${liveIdCache.items[c.id]}` : null,
      available: !!liveIdCache.items[c.id] && fresh,
      failCount: meta.failCount || 0
    };
  });
  res.json({ ok: true, updatedAt: liveIdCache.updatedAt, items });
});

app.post('/api/live/refresh', express.json(), async (_req, res) => {
  await refreshLiveIds();
  res.json({ ok: true, updatedAt: liveIdCache.updatedAt, items: liveIdCache.items });
});

app.get('/api/naver-board', async (req, res) => {
  try {
    const code = (req.query.code || '').toString().trim();
    if (!code) return res.json({ ok: true, items: [] });
    const u = `https://finance.naver.com/item/board.naver?code=${encodeURIComponent(code)}&page=1`;
    const html = await fetchTextWithTimeout(u, 5000);
    const re = /href="\/(item\/board_read\.naver\?[^"]+)"[^>]*title="([^"]+)"/g;
    const out = [];
    let m;
    while ((m = re.exec(html)) && out.length < 12) {
      out.push({ title: m[2].trim(), link: `https://finance.naver.com/${m[1]}`, source: '네이버 종토방' });
    }
    res.json({ ok: true, items: out });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.listen(PORT, () => {
  console.log(`war-room dashboard running: http://localhost:${PORT}`);
  refreshLiveIds().catch(() => {});
  setInterval(() => refreshLiveIds().catch(() => {}), 10 * 60 * 1000);
});
