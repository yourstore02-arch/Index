#!/usr/bin/env python3
import concurrent.futures as cf
import datetime as dt
import json
import math
import re
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screener-data.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36 HalifaxTradeEngine/13.3"
MIN_PRICE = 2.0
MAX_PRICE = 100.0
MIN_VOLUME = 100_000
MIN_DOLLAR_VOLUME = 5_000_000
HORIZON = 20
HISTORY_POOL = 180
MAX_RESULTS = 20


def request_json(url, timeout=20, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*", "Accept-Language": "en-US,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"request failed: {last}")


def num(v):
    try:
        s = re.sub(r"[$,%+\s,]", "", str(v or ""))
        return float(s)
    except Exception:
        return None


def allowed_name(name):
    n = str(name or "").lower()
    blocked = r"\b(warrant|warrants|right|rights|unit|units|preferred|preference|senior notes?|notes? due|debenture|bond|depositary shares.*preferred)\b"
    return not re.search(blocked, n, re.I)


def fetch_exchange(exchange):
    url = f"https://api.nasdaq.com/api/screener/stocks?exchange={urllib.parse.quote(exchange)}&download=true"
    raw = request_json(url)
    rows = (((raw or {}).get("data") or {}).get("rows") or [])
    out = []
    for r in rows:
        sym = re.sub(r"[^A-Z0-9.\-]", "", str(r.get("symbol") or "").upper())
        if not sym or len(sym) > 12 or not allowed_name(r.get("name")):
            continue
        price, volume = num(r.get("lastsale")), num(r.get("volume"))
        out.append({
            "symbol": sym,
            "name": str(r.get("name") or sym),
            "market": exchange.upper(),
            "price": price,
            "volume": volume,
            "pct1d": num(r.get("pctchange")) or 0.0,
            "market_cap": num(r.get("marketCap")) or 0.0,
            "sector": str(r.get("sector") or ""),
            "industry": str(r.get("industry") or ""),
        })
    return out


def ema(values, period):
    if len(values) < period:
        return [None] * len(values)
    out = [None] * len(values)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    k = 2 / (period + 1)
    for i in range(period, len(values)):
        seed = (values[i] - seed) * k + seed
        out[i] = seed
    return out


def rsi(values, period=14):
    out = [None] * len(values)
    if len(values) <= period:
        return out
    gain = loss = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gain += max(d, 0); loss += max(-d, 0)
    ag, al = gain / period, loss / period
    out[period] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(period + 1, len(values)):
        d = values[i] - values[i - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        out[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def atr_series(high, low, close, period=14):
    tr = [None] * len(close)
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = [None] * len(close)
    if len(close) <= period:
        return out
    v = sum(x for x in tr[1:period + 1] if x is not None) / period
    out[period] = v
    for i in range(period + 1, len(close)):
        v = (v * (period - 1) + tr[i]) / period
        out[i] = v
    return out


def adx_value(high, low, close, period=14):
    if len(close) < period * 2 + 1:
        return None
    tr=[]; plus=[]; minus=[]
    for i in range(1, len(close)):
        tr.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
        up=high[i]-high[i-1]; down=low[i-1]-low[i]
        plus.append(up if up>down and up>0 else 0.0)
        minus.append(down if down>up and down>0 else 0.0)
    trn=sum(tr[:period]); pn=sum(plus[:period]); mn=sum(minus[:period]); dx=[]
    for i in range(period, len(tr)):
        if i>period:
            trn=trn-trn/period+tr[i]; pn=pn-pn/period+plus[i]; mn=mn-mn/period+minus[i]
        p=100*pn/trn if trn else 0; m=100*mn/trn if trn else 0
        dx.append(100*abs(p-m)/(p+m) if p+m else 0)
    if not dx:
        return None
    if len(dx)<period:
        return sum(dx)/len(dx)
    a=sum(dx[:period])/period
    for x in dx[period:]: a=(a*(period-1)+x)/period
    return a


def fetch_history(symbol):
    sym = urllib.parse.quote(symbol)
    hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
    last = None
    for host in hosts:
        try:
            url=f"https://{host}/v8/finance/chart/{sym}?interval=1d&range=5y&includePrePost=false&events=div%2Csplits"
            raw=request_json(url, timeout=18, retries=2)
            res=((raw.get("chart") or {}).get("result") or [None])[0]
            if not res: raise RuntimeError("no result")
            q=((res.get("indicators") or {}).get("quote") or [None])[0]
            ts=res.get("timestamp") or []
            rows=[]
            for i,t in enumerate(ts):
                try:
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    v=(q.get("volume") or [0]*len(ts))[i] or 0
                    if all(isinstance(x,(int,float)) and math.isfinite(x) for x in [t,o,h,l,c]):
                        rows.append((int(t),float(o),float(h),float(l),float(c),float(v or 0)))
                except Exception:
                    pass
            if len(rows)<100: raise RuntimeError("not enough history")
            return rows
        except Exception as e:
            last=e
    raise RuntimeError(str(last))


def simple_atr(high, low, close, idx, period=14):
    if idx<period: return None
    vals=[]
    for i in range(idx-period+1,idx+1):
        if i<=0: continue
        vals.append(max(high[i]-low[i],abs(high[i]-close[i-1]),abs(low[i]-close[i-1])))
    return sum(vals)/len(vals) if vals else None


def analyze(symbol, source):
    rows=fetch_history(symbol)
    close=[r[4] for r in rows]; high=[r[2] for r in rows]; low=[r[3] for r in rows]; vol=[r[5] for r in rows]
    e9=ema(close,9); e21=ema(close,21); rsi_arr=rsi(close,14); atrs=atr_series(high,low,close,14)
    price=close[-1]; e9v=e9[-1]; e21v=e21[-1]; sma50=sum(close[-50:])/50 if len(close)>=50 else None
    rsiv=rsi_arr[-1] if rsi_arr[-1] is not None else 50.0; atr=atrs[-1] if atrs[-1] is not None else price*.02
    roc20=((price/close[-21])-1)*100 if len(close)>20 and close[-21] else 0.0
    avgvol=sum(vol[-20:])/min(20,len(vol)); vr=vol[-1]/avgvol if avgvol else 0.0
    adx=adx_value(high,low,close,14)
    if not (e9v and e21v and sma50): return None
    if not (price>e9v>e21v and e21v>sma50 and roc20>0 and rsiv<76): return None

    samples=hits=stops=unresolved=0
    for i in range(70,len(close)-HORIZON-1):
        p=close[i]; a9=e9[i]; a21=e21[i]; r=rsi_arr[i]
        if None in (a9,a21,r): continue
        s50=sum(close[i-49:i+1])/50
        a=simple_atr(high,low,close,i,14)
        if not a: continue
        r20=((p/close[i-20])-1)*100 if close[i-20] else 0
        av=sum(vol[max(0,i-19):i+1])/len(vol[max(0,i-19):i+1]); vratio=vol[i]/av if av else 1
        if not (p>a9>a21>s50 and 50<=r<=73 and r20>=1 and vratio>=.65): continue
        sd=min(p*.08,max(a*1.7,p*.02)); stop=p-sd; target=p+5*sd; samples+=1; outcome="open"
        for j in range(i+1,min(len(close),i+HORIZON+1)):
            stop_hit=low[j]<=stop; target_hit=high[j]>=target
            if stop_hit: outcome="stop"; break
            if target_hit: outcome="hit"; break
        if outcome=="hit": hits+=1
        elif outcome=="stop": stops+=1
        else: unresolved+=1
    hit_rate=(hits/samples*100) if samples else None
    stop_dist=min(price*.08,max(atr*1.7,price*.02)); stop=max(.01,price-stop_dist); target=price+5*stop_dist
    score=50.0
    score += 10 if price>e9v else -10
    score += 12 if e9v>e21v else -12
    score += 10 if e21v>sma50 else -10
    score += max(-10,min(18,roc20*.55))
    if 52<=rsiv<=68: score+=8
    elif rsiv>74: score-=10
    score += max(0,min(10,((adx or 18)-10)/30*10))
    score += max(0,min(8,vr/2*8))
    score += (max(0,min(50,hit_rate))*0.48) if samples>=8 and hit_rate is not None else 8
    score=max(0,min(100,round(score)))
    parts=["price is above EMA9, EMA21 and the 50-day trend"]
    if roc20>5: parts.append(f"20-day momentum is +{roc20:.1f}%")
    elif roc20>0: parts.append("20-day momentum is positive")
    if 52<=rsiv<=68: parts.append(f"RSI {rsiv:.0f} is constructive without being extremely stretched")
    if vr>=1.1: parts.append(f"volume is {vr:.1f}× its 20-day average")
    if samples>=8 and hit_rate is not None: parts.append(f"{hit_rate:.1f}% of {samples} similar historical setups reached 5R inside {HORIZON} days")
    else: parts.append(f"only {samples} comparable historical setups were found")
    return {
        "ticker":symbol,"market":source.get("market",""),"score":score,"hit_rate":hit_rate,"samples":samples,"hits":hits,"stops":stops,"unresolved":unresolved,
        "price":price,"stop":stop,"target":target,"roc20":roc20,"rsi":rsiv,"adx":adx,"volume_ratio":vr,"why":"; ".join(parts[:5])+"."
    }


def main():
    notes=[]; allrows=[]
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(fetch_exchange,e):e for e in ("nasdaq","nyse","amex")}
        for f,e in futs.items():
            try: allrows.extend(f.result())
            except Exception as err: notes.append(f"{e.upper()} source failed: {err}")
    dedup={}
    for r in allrows:
        old=dedup.get(r["symbol"])
        if old is None or ((old.get("price") is None or old.get("volume") is None) and r.get("price") is not None and r.get("volume") is not None): dedup[r["symbol"]]=r
    universe=list(dedup.values())
    eligible=[r for r in universe if r.get("price") is not None and r.get("volume") is not None and MIN_PRICE<=r["price"]<=MAX_PRICE and r["volume"]>=MIN_VOLUME and r["price"]*r["volume"]>=MIN_DOLLAR_VOLUME]

    by_liq=sorted(eligible,key=lambda r:r["price"]*r["volume"],reverse=True)[:90]
    by_move=sorted(eligible,key=lambda r:r.get("pct1d",-999),reverse=True)[:90]
    by_cap=sorted(eligible,key=lambda r:r.get("market_cap",0),reverse=True)[:60]
    pool=[]; seen=set()
    for r in by_liq+by_move+by_cap:
        if r["symbol"] not in seen:
            seen.add(r["symbol"]); pool.append(r)
        if len(pool)>=HISTORY_POOL: break

    results=[]; failures=0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(analyze,r["symbol"],r):r for r in pool}
        for f,r in futs.items():
            try:
                x=f.result()
                if x: results.append(x)
            except Exception:
                failures+=1
    results.sort(key=lambda r:((r["hit_rate"] if r["samples"]>=8 and r["hit_rate"] is not None else -1),r["score"]),reverse=True)
    qualified=[r for r in results if (r["samples"]>=8 and r["hit_rate"] is not None and r["hit_rate"]>=16.7) or r["score"]>=78][:MAX_RESULTS]
    if failures: notes.append(f"Historical data failed for {failures} of {len(pool)} finalists.")
    payload={
        "meta":{
            "status":"ok","generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z"),
            "universe_checked":len(universe),"eligible_count":len(eligible),"history_pool_count":len(pool),"qualified_count":len(qualified),
            "min_price":MIN_PRICE,"max_price":MAX_PRICE,"min_volume":MIN_VOLUME,"min_dollar_volume":MIN_DOLLAR_VOLUME,"horizon_days":HORIZON,
            "notes":notes,
        },
        "results":qualified,
    }
    OUT.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(f"wrote {OUT}: universe={len(universe)} eligible={len(eligible)} pool={len(pool)} results={len(qualified)}")

if __name__=="__main__":
    main()
