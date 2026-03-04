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

async function chart(symbol){
  const r=await kisRequest({path:'/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice',tr_id:'FHKST03010200',params:{FID_ETC_CLS_CODE:'0',FID_COND_MRKT_DIV_CODE:'UN',FID_INPUT_ISCD:symbol,FID_INPUT_HOUR_1:'200000',FID_PW_DATA_INCU_YN:'Y'}});
  return (r.output2||[]).slice(0,120).reverse().map(x=>({t:x.stck_cntg_hour,p:Number(x.stck_prpr||0),v:Number(x.cntg_vol||0)}));
}

const mode = process.argv[2];
const symbol = (process.argv[3] || '0009K0').toUpperCase();
if (mode === 'snapshot') console.log(JSON.stringify(await snapshot(symbol)));
else if (mode === 'chart') console.log(JSON.stringify(await chart(symbol)));
else throw new Error('mode: snapshot|chart');
