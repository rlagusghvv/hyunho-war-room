const express = require('express');
const Parser = require('rss-parser');
const { execFile } = require('child_process');
const path = require('path');

const app = express();
const parser = new Parser();
const PORT = process.env.PORT || 4177;
const KIS_DIR = '/Users/kimhyunhomacmini/.openclaw/workspace-tusasam';

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
    const code = `
      import { kisRequest } from './kis_api.js';
      const s='${symbol}';
      const [q,ob,inv,prg] = await Promise.all([
        kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-price',method:'GET',tr_id:'FHKST01010100',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s}}),
        kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn',method:'GET',tr_id:'FHKST01010200',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s}}),
        kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-investor',method:'GET',tr_id:'FHKST01010900',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s}}),
        kisRequest({path:'/uapi/domestic-stock/v1/quotations/program-trade-by-stock',method:'GET',tr_id:'FHPPG04650101',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s}}),
      ]);
      const o=q.output||{}; const i=(inv.output||[])[0]||{}; const b=ob.output1||{}; const p=(prg.output||[])[0]||{};
      const personal=Number(i.prsn_ntby_qty||0), foreign=Number(i.frgn_ntby_qty||0), inst=Number(i.orgn_ntby_qty||0);
      const otherEst=-(personal+foreign+inst);
      const levels=[];
      for (let n=1;n<=10;n++) levels.push({
        n,
        ask: Number(b['askp'+n]||0), askQty: Number(b['askp_rsqn'+n]||0),
        bid: Number(b['bidp'+n]||0), bidQty: Number(b['bidp_rsqn'+n]||0),
      });
      console.log(JSON.stringify({
        symbol:s,
        name:o.hts_kor_isnm || s,
        price:Number(o.stck_prpr||0),
        change:Number(o.prdy_vrss||0),
        changePct:Number(o.prdy_ctrt||0),
        high:Number(o.stck_hgpr||0),
        low:Number(o.stck_lwpr||0),
        volume:Number(o.acml_vol||0),
        value:Number(o.acml_tr_pbmn||0),
        investor:{ personal, foreign, inst, otherEst },
        orderbook:{
          totalAsk:Number(b.total_askp_rsqn||0),
          totalBid:Number(b.total_bidp_rsqn||0),
          levels
        },
        program:{
          netQty:Number(p.whol_smtn_ntby_qty||0),
          netAmt:Number(p.whol_smtn_ntby_tr_pbmn||0)
        },
        asOf:o.stck_cntg_hour || b.aspr_acpt_hour || null
      }));
    `;
    const out = await runNode(code, KIS_DIR, 18000);
    res.json({ ok: true, updatedAt: new Date().toISOString(), data: JSON.parse(out) });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/chart', async (req, res) => {
  try {
    const symbol = (req.query.symbol || '0009K0').toString().toUpperCase();
    const code = `
      import { kisRequest } from './kis_api.js';
      const s='${symbol}';
      const r=await kisRequest({
        path:'/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice',
        method:'GET',
        tr_id:'FHKST03010200',
        params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:s,FID_INPUT_HOUR_1:'200000',FID_PW_DATA_INCU_YN:'Y',FID_ETC_CLS_CODE:'0'}
      });
      const rows=(r.output2||[]).slice(0,120).reverse().map(x=>({
        t:x.stck_cntg_hour,
        p:Number(x.stck_prpr||0),
        v:Number(x.cntg_vol||0)
      }));
      console.log(JSON.stringify(rows));
    `;
    const out = await runNode(code, KIS_DIR, 18000);
    res.json({ ok: true, data: JSON.parse(out) });
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
