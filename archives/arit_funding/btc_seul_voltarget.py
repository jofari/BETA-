import numpy as np, pandas as pd
from beta.lake.lecture import load

def metrics(s):
    s=s.dropna(); n=len(s)
    cagr=(1+s).prod()**(252/n)-1
    v=s.std()*np.sqrt(252); sh=s.mean()*np.sqrt(252)/s.std()
    cum=(1+s).cumprod(); md=(cum/cum.cummax()-1).min()
    return cagr,v,sh,md

btc=load('BTC','1d').set_index('date')['close'].pct_change().dropna()
TAKER=0.0005

print("="*92)
print("BTC SEUL — vol-targeting, levier borne [0,33 ; 2,0], tout l'historique ({}-{})".format(
    btc.index[0].date(), btc.index[-1].date()))
print("="*92)
c,v,sh,md=metrics(btc)
print(f"  BTC buy-and-hold : Sharpe {sh:+.2f} | vol {v*100:.0f}% | DD {md*100:.0f}% | CAGR {c*100:.0f}%")
print("-"*92)

for lookback in [30,60]:
    rv=btc.rolling(lookback,min_periods=20).std()*np.sqrt(252)
    for target in [0.25,0.45,0.70]:
        L=(target/rv).clip(0.33,2.0).shift(1)
        gross=btc*L
        cost=L.diff().abs()*TAKER
        net=gross-cost
        c,v,sh,md=metrics(net)
        Lm=L.mean()
        print(f"  vt {int(target*100):>2}% / {lookback}j : Sharpe {sh:+.2f} | vol {v*100:.0f}% | "
              f"DD {md*100:.0f}% | CAGR {c*100:.0f}% | levier moy {Lm:.2f}x | cout {cost.mean()*252*100:.1f}%/an")

print("="*92)
print("CONSTANCE ANNEE PAR ANNEE — BTC vol-target 25% / 30j (net)")
print("="*92)
rv=btc.rolling(30,min_periods=20).std()*np.sqrt(252)
L=(0.25/rv).clip(0.33,2.0).shift(1)
net=btc*L - L.diff().abs()*TAKER
df=pd.DataFrame({'bh':btc,'vt':net})
print(f"  {'annee':>6} {'buy-hold':>10} {'voltarget':>10} {'diff':>7}")
for y in sorted(df.index.year.unique()):
    m=df.index.year==y
    sb=df['bh'][m].mean()*np.sqrt(252)/df['bh'][m].std()
    sv=df['vt'][m].mean()*np.sqrt(252)/df['vt'][m].std()
    print(f"  {y:>6} {sb:>10.2f} {sv:>10.2f} {sv-sb:>+7.2f}")

print("="*92)
print("OU EST LA VALEUR ? — le vol-targeting sur BTC seul level-up (cible>vol) ou de-lever (cible<vol) ?")
print("="*92)
# vol moyenne de BTC seule
print(f"  vol realisee BTC (pleine periode, ~30j): {btc.rolling(30,min_periods=20).std().mean()*np.sqrt(252)*100:.0f}%")
print("  cible 25% < vol BTC ~48%  -> on DE-LEVER (assurance crash)")
print("  cible 70% > vol BTC ~48%  -> on LEVER (prime de vol, mais plus de risque)")