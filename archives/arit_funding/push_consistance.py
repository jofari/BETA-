import numpy as np, pandas as pd
from beta.lake.lecture import load

def sharpe(s):
    s=s.dropna()
    return s.mean()*np.sqrt(252)/s.std() if s.std()>0 else np.nan

CRYPTO=['BTC','ETH','SOL','BNB','LINK','XRP']
R=pd.DataFrame({a:load(a,'1d').set_index('date')['close'].pct_change() for a in CRYPTO}).dropna()

vol=R.rolling(180,min_periods=60).std()
w=(1.0/vol).div((1.0/vol).sum(axis=1),axis=0).shift(1)
rp=(R*w).sum(axis=1).dropna()

TAKER=0.0005  # 5 bps par cote

def voltarget(rp, target, lookback=30, freq='D'):
    rv=rp.rolling(lookback,min_periods=20).std()*np.sqrt(252)
    L=(target/rv).clip(0.33,2.0)
    if freq=='W':
        # levier mis a jour chaque vendredi, tenu la semaine
        L=L.where(rp.index.dayofweek==4)  # garder seulement les vendredis
        L=L.ffill()
    L=L.shift(1)              # levier de t-1 applique au rendement t (causal)
    gross=rp*L
    turn=L.diff().abs()       # |Delta L| : fraction du portefeuille a renouveler
    cost=turn*TAKER
    net=gross-cost
    return gross, net, L, turn

print("="*100)
print("PUSH 1 — CONSTANCE ANNEE PAR ANNEE  (Sharpe inverse-vol nu vs vol-target 25% : est-ce un +0.05 stable ou un coup de chance ?)")
print("="*100)
g25,n25,L25,t25 = voltarget(rp, 0.25)
df=pd.DataFrame({'rp':rp,'g25':g25})
yrs=df.index.year
print(f"{'annee':>6} {'invvol nu':>11} {'voltarget25':>12} {'diff':>7}  {'levier moy':>11} {'turn/j (%cap)':>14}")
for y in sorted(yrs.unique()):
    m=yrs==y
    s_rp=sharpe(rp[m]); s_g=sharpe(g25[m])
    print(f"{y:>6} {s_rp:>11.2f} {s_g:>12.2f} {s_g-s_rp:>+7.2f}  {L25[m].mean():>11.2f}x {t25[m].mean()*100:>14.2f}")

print()
print("="*100)
print("PUSH 2 — COUT DE TURNOVER (5 bps/cote) sur le levier variable, en quotidien et hebdo")
print("="*100)
for target in [0.25,0.45,0.70]:
    for freq in ['D','W']:
        g,n,L,t = voltarget(rp, target, 30, freq)
        tr_an=t.mean()*252          # turnover annuel (fraction)
        cost_an=tr_an*TAKER*2       # 2 cotes (approx conservatrice)
        sg=sharpe(g); sn=sharpe(n)
        # OOS
        msk=rp.index>pd.Timestamp('2024-06-30',tz='UTC')
        sgo, sno = sharpe(g[msk]), sharpe(n[msk])
        print(f"target {int(target*100):>2}%  freq {freq}: brut {sg:+.2f} -> net {sn:+.2f} | OOS {sgo:+.2f} -> {sno:+.2f} | turn/j {t.mean()*100:.3f}% | cout annuel ~{cost_an*100:.1f}% cap")

print()
print("reference: inv-vol nu Sharpe %.2f (OOS %.2f) | BTC hold Sharpe %.2f (OOS %.2f)"%(
    sharpe(rp), sharpe(rp[rp.index>pd.Timestamp('2024-06-30',tz='UTC')]),
    sharpe(R['BTC']), sharpe(R['BTC'][R['BTC'].index>pd.Timestamp('2024-06-30',tz='UTC')])))