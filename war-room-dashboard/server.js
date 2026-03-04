const express = require('express');
const Parser = require('rss-parser');
const { execFile } = require('child_process');
const path = require('path');

const app = express();
const parser = new Parser();
const PORT = process.env.PORT || 4177;
const KIS_DIR = process.env.KIS_DIR || __dirname;

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

app.listen(PORT, () => {
  console.log(`war-room dashboard running: http://localhost:${PORT}`);
});
