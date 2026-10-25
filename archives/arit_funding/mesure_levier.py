import numpy as np, pandas as pd
from beta.lake.lecture import load

def metrics(s):
    s=s.dropna(); n=len(s)
    cagr=(1+s).prod()**(252/n)-1
    v=s.std()*np.sqrt(252)
    sh=s.mean()*np.sqrt(252)/s.std()
    cum=(1+s).cumprod(); md=(cum/cum.cummax()-1).min()
    return cagr, v, sh, md

CRYPTO=['BTC','ETH','SOL','BNB','LINK','XRP']
R=pd.DataFrame({a:load(a,'1d').set_index('date')['close'].pct_change() for a in CRYPTO}).dropna()

# portefeuille inverse-vol (causal : poids a t utilisent la vol jusqu'a t-1)
vol=R.rolling(180,min_periods=60).std()
w=(1.0/vol).div((1.0/vol).sum(axis=1),axis=0).shift(1)
rp=(R*w).sum(axis=1).dropna()

# vol realisee du portefeuille, fenetre 30j annualisee
rpvol=rp.rolling(30,min_periods=20).std()*np.sqrt(252)

def lev(target):
    return (target/rpvol).clip(0.33,2.0).shift(1)   # levier decide en t-1, applique au rendement t

sp = rp.index>pd.Timestamp('2024-06-30',tz='UTC')

def ligne(name,r,L=None):
    c,v,sh,md=metrics(r)
    levm = L.mean() if L is not None else float('nan')
    print(f"{name:>22}: Sharpe {sh:+.2f} | vol {v*100:5.1f}% | DD {md*100:6.1f}% | CAGR {c*100:5.1f}% | levier moy {levm:.2f}x")

print("="*90)
print("THEORIQUE, BRUT (sans frais de rebalancement)")
print("="*90)
# reference BTC
btc=R['BTC']
ligne("BTC seul OOS", btc[sp].dropna())
ligne("BTC seul pleine", btc.dropna())
print("-"*90)
ligne("inv-vol unlevered pleine", rp)
ligne("inv-vol unlevered OOS  ", rp[sp])
print("-"*90)
# levier CONSTANT (demonstration : Sharpe invariant)
for L in [0.33, 0.6, 1.0, 1.5, 2.0]:
    rcon=(rp*L).dropna()
    if L==1.0: continue
    ligne(f"levier constant {L}x pleine", rcon)
print("  (levier constant : Sharpe IDENTIQUE a l'unlevered, seul vol/DD/CAGR bougent)")
print("-"*90)
for target in [0.25, 0.45, 0.70]:
    L=lev(target)
    vt=rp*L
    msk = vt.index>pd.Timestamp('2024-06-30',tz='UTC')
    ligne("voltarget %d%% pleine"%(target*100), vt, L)
    ligne("voltarget %d%% OOS  "%(target*100), vt[msk], L[msk])
print("-"*90)
print("CONTROLE : l'unlevered 0.45 OOS vs voltarget 40% OOS — meme niveau de vol, Sharpe different ?")