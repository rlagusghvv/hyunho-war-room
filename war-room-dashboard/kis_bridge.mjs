import fs from 'fs';

function loadDotEnv() {
  if (!fs.existsSync('.env')) return;
  const lines = fs.readFileSync('.env', 'utf-8').split(/\r?\n/);
  for (const line of lines) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    const k = m[1];
    let v = (m[2] ?? '').trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    if (!process.env[k]) process.env[k] = v;
  }
}
loadDotEnv();

const BASE_URL = process.env.KIS_BASE_URL || 'https://openapi.koreainvestment.com:9443';
const APP_KEY = process.env.KIS_APP_KEY;
const APP_SECRET = process.env.KIS_APP_SECRET;
if (!APP_KEY || !APP_SECRET) throw new Error('Missing KIS_APP_KEY/KIS_APP_SECRET (.env)');

function readJsonSafe(path) {
  try { return JSON.parse(fs.readFileSync(path, 'utf-8')); } catch { return null; }
}
function tokenIsFresh(tok) {
  if (!tok?.access_token || !tok?.issuedAt || !tok?.expires_in) return false;
  const issued = Date.parse(tok.issuedAt);
  return Number.isFinite(issued) && Date.now() < issued + Number(tok.expires_in) * 1000 - 5 * 60 * 1000;
}

async function ensureToken() {
  const tok = readJsonSafe('.kis_token.json');
  if (tokenIsFresh(tok)) return tok;
  const res = await fetch(`${BASE_URL}/oauth2/tokenP`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ grant_type: 'client_credentials', appkey: APP_KEY, appsecret: APP_SECRET }),
  });
  const json = await res.json();
  if (!res.ok || !json?.access_token) throw new Error(`token error: ${JSON.stringify(json)}`);
  const out = { issuedAt: new Date().toISOString(), ...json };
  fs.writeFileSync('.kis_token.json', JSON.stringify(out, null, 2));
  return out;
}

async function kisRequest({ path, tr_id, params }) {
  const tok = await ensureToken();
  const u = new URL(`${BASE_URL}${path}`);
  for (const [k, v] of Object.entries(params || {})) u.searchParams.set(k, String(v));
  const res = await fetch(u, {
    headers: {
      'Content-Type': 'application/json',
      authorization: `${tok.token_type || 'Bearer'} ${tok.access_token}`,
      appkey: APP_KEY,
      appsecret: APP_SECRET,
      tr_id,
      custtype: 'P',
    },
  });
  const txt = await res.text();
  let json; try { json = JSON.parse(txt); } catch { json = { raw: txt }; }
  if (!res.ok) throw new Error(`KIS ${path} ${res.status}: ${json?.msg1 || txt}`);
  return json;
}

async function snapshot(symbol){
  const [q,ob,inv,prg]=await Promise.all([
    kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-price',tr_id:'FHKST01010100',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:symbol}}),
    kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn',tr_id:'FHKST01010200',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:symbol}}),
    kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-investor',tr_id:'FHKST01010900',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:symbol}}),
    kisRequest({path:'/uapi/domestic-stock/v1/quotations/program-trade-by-stock',tr_id:'FHPPG04650101',params:{FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:symbol}}),
  ]);
  const o=q.output||{}, b=ob.output1||{}, i=(inv.output||[])[0]||{}, p=(prg.output||[])[0]||{};
  const personal=Number(i.prsn_ntby_qty||0), foreign=Number(i.frgn_ntby_qty||0), inst=Number(i.orgn_ntby_qty||0);
  const levels=[]; for(let n=1;n<=10;n++) levels.push({n,ask:Number(b['askp'+n]||0),askQty:Number(b['askp_rsqn'+n]||0),bid:Number(b['bidp'+n]||0),bidQty:Number(b['bidp_rsqn'+n]||0)});
  return {
    symbol,
    name:o.hts_kor_isnm || symbol,
    price:Number(o.stck_prpr||0), change:Number(o.prdy_vrss||0), changePct:Number(o.prdy_ctrt||0), high:Number(o.stck_hgpr||0), low:Number(o.stck_lwpr||0), volume:Number(o.acml_vol||0), value:Number(o.acml_tr_pbmn||0),
    investor:{ personal, foreign, inst, otherEst:-(personal+foreign+inst) },
    orderbook:{ totalAsk:Number(b.total_askp_rsqn||0), totalBid:Number(b.total_bidp_rsqn||0), levels },
    program:{ netQty:Number(p.whol_smtn_ntby_qty||0), netAmt:Number(p.whol_smtn_ntby_tr_pbmn||0) },
    asOf:o.stck_cntg_hour || b.aspr_acpt_hour || null,
  };
}

function kstHHMMSS(){
  const d = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const hh = String(d.getUTCHours()).padStart(2,'0');
  const mm = String(d.getUTCMinutes()).padStart(2,'0');
  return `${hh}${mm}00`;
}

async function chart(symbol){
  const hour = kstHHMMSS();
  const r=await kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice',tr_id:'FHKST03010200',params:{FID_ETC_CLS_CODE:'0',FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:symbol,FID_INPUT_HOUR_1:hour,FID_PW_DATA_INCU_YN:'Y'}});
  let rows=(r.output2||[]).slice(0,240).reverse().map(x=>({
    t:x.stck_cntg_hour,
    o:Number(x.stck_oprc||x.stck_prpr||0),
    h:Number(x.stck_hgpr||x.stck_prpr||0),
    l:Number(x.stck_lwpr||x.stck_prpr||0),
    c:Number(x.stck_prpr||0),
    v:Number(x.cntg_vol||0)
  }));
  // keep meaningful candles first; if too few, return raw rows
  const meaningful = rows.filter(x => x.v > 0 || x.h !== x.l);
  if (meaningful.length >= 20) rows = meaningful;
  return rows.slice(-120);
}

async function krIndexes(){
  const pairs = [
    { code: '0001', name: 'KOSPI' },
    { code: '1001', name: 'KOSDAQ' }
  ];
  const out = [];
  for (const p of pairs) {
    const r = await kisRequest({
      path:'/uapi/domestic-stock/v1/quotations/inquire-index-tickprice',
      tr_id:'FHPUP02100000',
      params:{ FID_COND_MRKT_DIV_CODE:'U', FID_INPUT_ISCD:p.code }
    });
    const o = r.output || {};
    const close = Number(o.bstp_nmix_prpr||0);
    const open = Number(o.bstp_nmix_oprc||0);
    const high = Number(o.bstp_nmix_hgpr||0);
    const low = Number(o.bstp_nmix_lwpr||0);
    const chg = Number(o.bstp_nmix_prdy_vrss||0);
    const pct = Number(o.bstp_nmix_prdy_ctrt||0);
    out.push({ symbol:p.name, rawSymbol:p.code, open, high, low, close, chg, pct, stale:false, source:'KIS' });
  }
  return out;
}

async function krIndexHistory(){
  const d = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const dt = `${d.getUTCFullYear()}${String(d.getUTCMonth()+1).padStart(2,'0')}${String(d.getUTCDate()).padStart(2,'0')}`;
  const pairs = [
    { code: '0001', name: 'KOSPI' },
    { code: '1001', name: 'KOSDAQ' }
  ];
  const series = {};
  for (const p of pairs) {
    const r = await kisRequest({
      path:'/uapi/domestic-stock/v1/quotations/inquire-index-timeprice',
      tr_id:'FHPUP02120000',
      params:{ FID_COND_MRKT_DIV_CODE:'U', FID_INPUT_ISCD:p.code, FID_INPUT_HOUR_1:'1200', FID_INPUT_DATE_1:dt, FID_PERIOD_DIV_CODE:'1' }
    });
    series[p.name] = (r.output2 || []).slice(0, 100).reverse().map(x => ({
      date: x.stck_bsop_date,
      open: Number(x.bstp_nmix_oprc||0),
      high: Number(x.bstp_nmix_hgpr||0),
      low: Number(x.bstp_nmix_lwpr||0),
      close: Number(x.bstp_nmix_prpr||0),
      volume: Number(x.acml_vol||0)
    })).filter(x=>x.close>0);
  }
  return series;
}

async function marketFlow(){
  const d = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const dt = `${d.getUTCFullYear()}${String(d.getUTCMonth()+1).padStart(2,'0')}${String(d.getUTCDate()).padStart(2,'0')}`;
  const out = { updatedAt: new Date().toISOString() };

  try {
    const k = await kisRequest({
      path:'/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market',
      tr_id:'FHPTJ04040000',
      params:{ FID_COND_MRKT_DIV_CODE:'U', FID_INPUT_ISCD:'0001', FID_INPUT_DATE_1:dt, FID_INPUT_ISCD_1:'KSP' }
    });
    out.kospi = (k.output2||[])[0] || (k.output1||[])[0] || {};
  } catch { out.kospi = {}; }

  try {
    const q = await kisRequest({
      path:'/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market',
      tr_id:'FHPTJ04040000',
      params:{ FID_COND_MRKT_DIV_CODE:'U', FID_INPUT_ISCD:'1001', FID_INPUT_DATE_1:dt, FID_INPUT_ISCD_1:'KSQ' }
    });
    out.kosdaq = (q.output2||[])[0] || (q.output1||[])[0] || {};
  } catch { out.kosdaq = {}; }

  try {
    const p = await kisRequest({
      path:'/uapi/domestic-stock/v1/quotations/investor-program-trade-today',
      tr_id:'HHPPG046600C0',
      params:{ MRKT_DIV_CLS_CODE:'1' }
    });
    out.program = p.output || p.output1 || p.output2 || {};
  } catch { out.program = {}; }

  try {
    const f = await kisRequest({
      path:'/uapi/domestic-futureoption/v1/quotations/display-board-futures',
      tr_id:'FHPIF05030200',
      params:{ FID_COND_MRKT_DIV_CODE:'F', FID_COND_SCR_DIV_CODE:'20503', FID_COND_MRKT_CLS_CODE:'MKI' }
    });
    out.futures = f.output || f.output1 || f.output2 || {};
  } catch { out.futures = {}; }

  try {
    const o = await kisRequest({
      path:'/uapi/domestic-futureoption/v1/quotations/display-board-callput',
      tr_id:'FHPIF05030100',
      params:{ FID_COND_MRKT_DIV_CODE:'O', FID_COND_SCR_DIV_CODE:'20503', FID_MRKT_CLS_CODE:'CO', FID_MTRT_CNT:'202407', FID_COND_MRKT_CLS_CODE:'', FID_MRKT_CLS_CODE1:'PO' }
    });
    out.options = o.output || o.output1 || o.output2 || {};
  } catch { out.options = {}; }

  return out;
}

async function portfolio(){
  const CANO = process.env.KIS_CANO;
  const ACNT_PRDT_CD = process.env.KIS_ACNT_PRDT_CD || '01';
  if (!CANO) throw new Error('Missing KIS_CANO in .env');
  const r = await kisRequest({
    path:'/uapi/domestic-stock/v1/trading/inquire-balance',
    tr_id:'TTTC8434R',
    params:{ CANO, ACNT_PRDT_CD, AFHR_FLPR_YN:'N', OFL_YN:'', INQR_DVSN:'02', UNPR_DVSN:'01', FUND_STTL_ICLD_YN:'N', FNCG_AMT_AUTO_RDPT_YN:'N', PRCS_DVSN:'00', CTX_AREA_FK100:'', CTX_AREA_NK100:'' }
  });
  const rows=(r.output1||[]).filter(x=>Number(x.hldg_qty||0)>0).map(x=>({
    code:x.pdno,
    name:x.prdt_name,
    qty:Number(x.hldg_qty||0),
    avg:Number(x.pchs_avg_pric||0),
    now:Number(x.prpr||0),
    pnl:Number(x.evlu_pfls_amt||0),
    pnlPct:Number(x.evlu_pfls_rt||0)
  }));
  const sum=(r.output2||[])[0]||{};
  return { holdings: rows, account: { nassAmt: Number(sum.nass_amt||0), dncaTotAmt: Number(sum.dnca_tot_amt||0), evluAmtSmtl: Number(sum.evlu_amt_smtl_amt||0) } };
}

const mode = process.argv[2];
const symbol = (process.argv[3] || '0009K0').toUpperCase();
if (mode === 'snapshot') console.log(JSON.stringify(await snapshot(symbol)));
else if (mode === 'chart') console.log(JSON.stringify(await chart(symbol)));
else if (mode === 'portfolio') console.log(JSON.stringify(await portfolio()));
else if (mode === 'kr-indexes') console.log(JSON.stringify(await krIndexes()));
else if (mode === 'kr-history') console.log(JSON.stringify(await krIndexHistory()));
else if (mode === 'market-flow') console.log(JSON.stringify(await marketFlow()));
else throw new Error('mode: snapshot|chart|portfolio|kr-indexes|kr-history|market-flow');
