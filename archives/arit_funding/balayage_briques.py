import numpy as np, pandas as pd
from beta.lake.lecture import load, funding

PAIRES=("BTC","ETH","SOL","BNB","LINK","XRP")
BPS=5.0
FIN="2024-06-30"

# --- donnees ---
def calendrier_commun():
    c=None
    for p in PAIRES:
        d=pd.DatetimeIndex(load(p,'1d',colonnes=("close",))["date"])
        c=d if c is None else c.intersection(d)
    return c.sort_values()

def clotures(idx):
    return pd.DataFrame({p:load(p,'1d',colonnes=("close",)).set_index("date")["close"].astype(float).reindex(idx) for p in PAIRES}, index=idx)

def funding_quot(idx):
    return pd.DataFrame({p:funding(p).assign(j=lambda d:d["date"].dt.floor("D")).groupby("j")["funding_rate"].sum().reindex(idx) for p in PAIRES}, index=idx)

idx=calendrier_commun()
closes=clotures(idx)
r=closes.pct_change()
fj=funding_quot(idx)

# --- briques : poids cibles (causaux), rebalances a frequence donnee ---
def vol_inv(rend, fen=180):
    s=rend.rolling(fen,min_periods=fen).std(ddof=1)
    return (1.0/s.replace(0,np.nan))

def renorm(w):
    s=w.abs().sum(axis=1)
    return w.div(s.replace(0,np.nan),axis=0)

def cross_rank(rend, fen, signe=1):
    # signe +1 = momentum (long gagnants), -1 = reversal (long perdants)
    mom=signe*(closes/closes.shift(fen)-1)
    rk=mom.rank(axis=1)
    n=len(PAIRES); haut=n-3
    w=np.where(rk<=3, 1/6., np.where(rk>haut, -1/6., 0.))
    return pd.DataFrame(w,index=mom.index,columns=mom.columns).where(mom.notna().all(axis=1))

def carry(funding_j):
    rk=funding_j.rank(axis=1,method="first")
    n=funding_j.shape[1]; haut=n-3
    # long les funding BAS (moins cher a longer), short les HAUTS
    w=np.where(rk<=3, 1/6., np.where(rk>haut, -1/6., 0.))
    return pd.DataFrame(w,index=funding_j.index,columns=funding_j.columns).where(funding_j.notna().all(axis=1))

def tsmom(rend, fen):
    m=np.sign(closes/closes.shift(fen)-1)
    inv=vol_inv(rend)
    return renorm(inv*m)

def rebalancer(cible, pas):
    # ne garde la cible qu'aux jours de rebalancement, puis forward-fill
    keep = np.arange(len(cible)) % pas == 0
    full = np.repeat(keep[:, None], cible.shape[1], axis=1)
    return cible.where(full).ffill()

def mesurer(poids_tenus, rend, fund_j, bps=BPS):
    # poids_tenus[t] = position tenue pendant t (decidee au dernier rebalancement <= t)
    g=(poids_tenus*rend).sum(axis=1)
    turn=poids_tenus.diff().abs().sum(axis=1)
    cout=turn*bps/1e4
    fp=-(poids_tenus*fund_j).sum(axis=1)   # long paie le funding, short le recoit
    net=g-cout+fp
    return pd.DataFrame({"gross":g,"turn":turn,"cost":cout,"fund":fp,"net":net})

def perf(s):
    s=s.dropna(); n=len(s)
    if n<30 or s.std()==0: return (np.nan,)*4
    sh=s.mean()*np.sqrt(252)/s.std()
    v=s.std()*np.sqrt(252)
    eq=(1+s).cumprod(); md=(eq/eq.cummax()-1).min()
    cagr=eq.iloc[-1]**(252/n)-1
    return sh,v,md,cagr

# --- construire chaque brique ---
INV=vol_inv(r)
base=renorm(INV)

briques={}
briques["carry weekly"]   = rebalancer(carry(fj), 7)
briques["carry monthly"]  = rebalancer(carry(fj), 30)
briques["xsec mom 21d W"] = rebalancer(cross_rank(r,21,+1), 7)
briques["xsec mom 63d W"] = rebalancer(cross_rank(r,63,+1), 7)
briques["xsec rev 3d W"]  = rebalancer(cross_rank(r,3,-1), 7)
briques["tsmom 126d W"]   = rebalancer(tsmom(r,126), 7)
briques["tsmom 252d M"]   = rebalancer(tsmom(r,252), 30)

# references : inverse-vol continue (rebalance hebdo), BTC
refs={}
refs["inv-vol hebdo"]=rebalancer(base,7)
refs["BTC hold"]=None

# --- decalage causal : poids tenu au jour t decide <= t-1 ? ---
# Notre poids_tenus est DEJA causal si chaque brique n'est calculee que sur donnees <= t-1.
# verification : chaque brique utilise r.shift ou closes.shift en interne. On decale d'un jour
# par securite au moment de mesurer (position tenue en t = poids decide en t-1).

print("="*100)
print("BALAYAGE DES BRIQUES — 6 perps, net de frais (taker 5 bps), correlation avec l'existant")
print("="*100)

res={}
for nom,poids in list(briques.items())+list(refs.items()):
    if poids is None: continue
    tenu=poids.shift(1)                     # causal : position t = poids decide t-1
    m=mesurer(tenu, r, fj)
    oos=m.index>pd.Timestamp(FIN,tz="UTC")
    sh_f,v_f,md_f,cagr_f=perf(m["net"])
    sh_o,v_o,md_o,cagr_o=perf(m["net"][oos])
    turn_an=m["turn"].mean()*252
    res[nom]=m
    print(f"  {nom:<16}: Sharpe pleine {sh_f:+5.2f} | OOS {sh_o:+5.2f} | DD OOS {md_o*100:5.0f}% "
          f"| turn {turn_an:5.1f}x/an | corr(btc) {m['net'].corr(r['BTC'].reindex(m.index)):+.2f}")

# BTC reference
print(f"  {'BTC buy-hold':<16}: Sharpe pleine {perf(r['BTC'])[0]:+5.2f} | OOS {perf(r['BTC'][r.index>pd.Timestamp(FIN,tz='UTC')])[0]:+5.2f}")

# --- matrice de correlation des briques OOS (nettes) ---
print()
print("="*100)
print("CORRELATION DES BRIQUES entre elles (OOS, rendements nets)")
print("="*100)
noms=list(res.keys())
oos=r.index>pd.Timestamp(FIN,tz="UTC")
cols={}
for nom,m in res.items():
    cols[nom]=m["net"].reindex(r.index[oos])
cols["BTC"]=r["BTC"].reindex(r.index[oos])
C=pd.DataFrame(cols).corr()
C.index.name=None
for i in C.index:
    print("  " + "  ".join(f"{C.loc[i,j]:+.2f}" for j in C.columns))