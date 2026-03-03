const express = require('express');
const Parser = require('rss-parser');
const { execFile } = require('child_process');
const path = require('path');

const app = express();
const parser = new Parser();
const PORT = process.env.PORT || 4177;
const KIS_DIR = '/Users/kimhyunhomacmini/.openclaw/workspace-tusasam';

app.use(express.static(path.join(__dirname, 'public')));

function runNode(code, cwd, timeout = 12000) {
  return new Promise((resolve, reject) => {
    execFile('node', ['-e', code], { cwd, timeout }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout.toString().trim());
    });
  });
}

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

app.get('/api/aimedbio', async (_req, res) => {
  try {
    const code = `
      import { kisRequest } from './kis_api.js';
      const s='0009K0';
      const q=await kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-price',method:'GET',tr_id:'FHKST01010100',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s}});
      const inv=await kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-investor',method:'GET',tr_id:'FHKST01010900',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s}});
      const o=q.output||{};
      const i=(inv.output||[])[0]||{};
      const p=Number(i.prsn_ntby_qty||0), f=Number(i.frgn_ntby_qty||0), g=Number(i.orgn_ntby_qty||0);
      const other=-(p+f+g);
      console.log(JSON.stringify({
        price:Number(o.stck_prpr||0),
        changePct:Number(o.prdy_ctrt||0),
        high:Number(o.stck_hgpr||0),
        low:Number(o.stck_lwpr||0),
        volume:Number(o.acml_vol||0),
        value:Number(o.acml_tr_pbmn||0),
        investor:{personal:p, foreign:f, inst:g, otherEst:other}
      }));
    `;

    const out = await runNode(code, KIS_DIR, 15000);
    res.json({ ok: true, updatedAt: new Date().toISOString(), data: JSON.parse(out) });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.listen(PORT, () => {
  console.log(`war-room dashboard running: http://localhost:${PORT}`);
});
