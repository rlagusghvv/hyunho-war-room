const express = require('express');
const Parser = require('rss-parser');
const { execFile } = require('child_process');
const path = require('path');

const app = express();
const parser = new Parser();
const PORT = process.env.PORT || 4177;
const KIS_DIR = process.env.KIS_DIR || __dirname;
const marketCache = new Map();

app.use(express.static(path.join(__dirname, 'public')));

function runNode(code, cwd, timeout = 15000) {
  return new Promise((resolve, reject) => {
    execFile('node', ['-e', code], { cwd, timeout }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout.toString().trim());
    });
  });
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
    const q = `${symbol} 종토방`;
    const url = `https://news.google.com/rss/search?q=${encodeURIComponent(q)}&hl=ko&gl=KR&ceid=KR:ko`;
    const feed = await parser.parseURL(url);
    const items = (feed.items || []).slice(0, 8).map((it) => ({
      title: it.title,
      link: it.link,
      pubDate: it.pubDate,
      source: '미확인',
    }));
    res.json({ ok: true, updatedAt: new Date().toISOString(), items });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/markets', async (_req, res) => {
  try {
    const symbols = ['^kospi', '^spx', '^ndq', '^dji', 'usdkrw', 'cl.f', 'gc.f', 'ng.f', 'si.f', 'hg.f', 'btcusd'];
    const names = { '^kospi':'KOSPI', '^spx': 'S&P500', '^ndq': 'NASDAQ100', '^dji': 'DOW', 'usdkrw':'USDKRW', 'cl.f': 'WTI', 'gc.f': 'GOLD', 'ng.f':'NATGAS', 'si.f':'SILVER', 'hg.f':'COPPER', 'btcusd': 'BTC' };
    const out = [];
    for (const s of symbols) {
      const u = `https://stooq.com/q/l/?s=${encodeURIComponent(s)}&f=sd2t2ohlcv&h&e=csv`;
      const txt = await fetch(u, { headers: { 'user-agent': 'Mozilla/5.0' } }).then((r) => r.text());
      const lines = txt.trim().split('\n');
      const row = (lines[1] || '').split(',');
      const [symbol, date, time, open, high, low, close] = row;
      let o = Number(open), c = Number(close), h = Number(high), l = Number(low);
      const key = names[s] || symbol;
      const prev = marketCache.get(key);
      const valid = Number.isFinite(c) && c > 0;
      if (!valid && prev) {
        ({ open: o, close: c, high: h, low: l } = prev);
      } else if (!valid && !prev) {
        try {
          const hu = `https://stooq.com/q/d/l/?s=${encodeURIComponent(s)}&i=d`;
          const htxt = await fetch(hu, { headers: { 'user-agent': 'Mozilla/5.0' } }).then((r) => r.text());
          const hlines = htxt.trim().split('\n').slice(1).filter(Boolean);
          const last = (hlines[hlines.length - 1] || '').split(',');
          const [, ho, hh, hl, hc] = last;
          o = Number(ho); h = Number(hh); l = Number(hl); c = Number(hc);
        } catch {}
      }
      const chg = Number.isFinite(o) && Number.isFinite(c) ? c - o : null;
      const pct = Number.isFinite(o) && o !== 0 && Number.isFinite(c) ? (chg / o) * 100 : null;
      const item = { symbol: key, rawSymbol: s, date, time, open: Number.isFinite(o)?o:null, high: Number.isFinite(h)?h:null, low: Number.isFinite(l)?l:null, close: Number.isFinite(c)?c:null, chg, pct, stale: !valid };
      out.push(item);
      if (valid) marketCache.set(key, item);
    }

    // Prefer KIS for KR indexes (KOSPI/KOSDAQ) when available
    try {
      const kr = await new Promise((resolve, reject) => {
        execFile('node', ['kis_bridge.mjs', 'kr-indexes'], { cwd: KIS_DIR, timeout: 12000 }, (err, stdout, stderr) => {
          if (err) return reject(new Error(stderr || err.message));
          resolve(JSON.parse((stdout || '').toString().trim()));
        });
      });
      const map = new Map(out.map((x) => [x.symbol, x]));
      for (const it of kr) map.set(it.symbol, it);
      if (!map.has('KOSDAQ')) map.set('KOSDAQ', { symbol:'KOSDAQ', rawSymbol:'1001', open:null, high:null, low:null, close:null, chg:null, pct:null, stale:true });
      res.json({ ok: true, updatedAt: new Date().toISOString(), items: Array.from(map.values()) });
      return;
    } catch {}

    // fallback to free-source only
    if (!out.some((x) => x.symbol === 'KOSDAQ')) out.push({ symbol:'KOSDAQ', rawSymbol:'1001', open:null, high:null, low:null, close:null, chg:null, pct:null, stale:true });
    res.json({ ok: true, updatedAt: new Date().toISOString(), items: out });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/market-history', async (req, res) => {
  try {
    const symbol = (req.query.symbol || '^spx').toString().toLowerCase();
    const u = `https://stooq.com/q/d/l/?s=${encodeURIComponent(symbol)}&i=d`;
    const txt = await fetch(u, { headers: { 'user-agent': 'Mozilla/5.0' } }).then((r) => r.text());
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
    const targets = [
      { s: '^kospi', n: 'KOSPI' },
      { s: '^spx', n: 'S&P500' },
      { s: '^ndq', n: 'NASDAQ100' },
      { s: 'usdkrw', n: 'USDKRW' },
      { s: 'gc.f', n: 'GOLD' },
      { s: 'cl.f', n: 'WTI' },
      { s: 'ng.f', n: 'NATGAS' },
      { s: 'si.f', n: 'SILVER' },
      { s: 'hg.f', n: 'COPPER' }
    ];
    const series = {};
    for (const t of targets) {
      const u = `https://stooq.com/q/d/l/?s=${encodeURIComponent(t.s)}&i=d`;
      const txt = await fetch(u, { headers: { 'user-agent': 'Mozilla/5.0' } }).then((r) => r.text());
      const lines = txt.trim().split('\n').slice(1).filter(Boolean).slice(-90);
      series[t.n] = lines.map((ln) => {
        const [date, open, high, low, close, volume] = ln.split(',');
        return { date, open: Number(open || 0), high: Number(high || 0), low: Number(low || 0), close: Number(close || 0), volume: Number(volume || 0) };
      }).filter((x) => Number.isFinite(x.close) && x.close > 0);
    }

    // Prefer KIS history for KR indexes when available
    try {
      const krSeries = await new Promise((resolve, reject) => {
        execFile('node', ['kis_bridge.mjs', 'kr-history'], { cwd: KIS_DIR, timeout: 15000 }, (err, stdout, stderr) => {
          if (err) return reject(new Error(stderr || err.message));
          resolve(JSON.parse((stdout || '').toString().trim()));
        });
      });
      if (krSeries.KOSPI?.length) series.KOSPI = krSeries.KOSPI;
      if (krSeries.KOSDAQ?.length) series.KOSDAQ = krSeries.KOSDAQ;
      else if (!series.KOSDAQ) series.KOSDAQ = [];
    } catch {
      if (!series.KOSDAQ) series.KOSDAQ = [];
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

app.listen(PORT, () => {
  console.log(`war-room dashboard running: http://localhost:${PORT}`);
});
