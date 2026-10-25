import numpy as np, pandas as pd
from beta.lake.lecture import load, funding

PAIRES=("BTC","ETH","SOL","BNB","LINK","XRP")
BPS=5.0; FIN="2024-06-30"

def cal():
    c=None
    for p in PAIRES:
        d=pd.DatetimeIndex(load(p,'1d',colonnes=("close",))["date"]); c=d if c is None else c.intersection(d)
    return c.sort_values()

def clash(idx): return pd.DataFrame({p:load(p,'1d',colonnes=("close",)).set_index("date")["close"].astype(float).reindex(idx) for p in PAIRES},index=idx)
def fq(idx): return pd.DataFrame({p:funding(p).assign(j=lambda d:d["date"].dt.floor("D")).groupby("j")["funding_rate"].sum().reindex(idx) for p in PAIRES},index=idx)

idx=cal(); closes=clash(idx); r=closes.pct_change(); fj=fq(idx)

def carry(funding_j):
    rk=funding_j.rank(axis=1,method="first"); n=funding_j.shape[1]; haut=n-3
    w=np.where(rk<=3,1/6.,np.where(rk>haut,-1/6.,0.))
    return pd.DataFrame(w,index=funding_j.index,columns=funding_j.columns).where(funding_j.notna().all(axis=1))

def rebal(cible,pas):
    keep=np.arange(len(cible))%pas==0
    return cible.where(np.repeat(keep[:,None],cible.shape[1],axis=1)).ffill()

tenu=rebal(carry(fj),7).shift(1)
gross=(tenu*r).sum(axis=1)
fund_pnl=-(tenu*fj).sum(axis=1)
cost=tenu.diff().abs().sum(axis=1)*BPS/1e4
net=gross-cost+fund_pnl
df=pd.DataFrame({"gross":gross,"fund":fund_pnl,"cost":cost,"net":net})

def ann(s): return s.mean()*252

oos=df.index>pd.Timestamp(FIN,tz="UTC")
print("="*80)
print("DECOMPOSITION DU CARRY HEBDOMADAIRE (annualise)")
print("="*80)
for nom,m in [("pleine",df),("OOS",df[oos])]:
    print(f"  {nom:>6}: rev prix {ann(m['gross'])*100:+6.1f}%/an | funding {ann(m['fund'])*100:+6.1f}%/an "
          f"| cout {ann(m['cost'])*100:+5.1f}%/an | NET {ann(m['net'])*100:+6.1f}%/an")

print()
print("="*80)
print("CONSTANCE ANNEE PAR ANNEE (Sharpe net du carry hebdo)")
print("="*80)
print(f"  {'annee':>6} {'Sharpe':>8} {'fund%/an':>9} {'rev prix%/an':>12}")
for y in sorted(df.index.year.unique()):
    m=df.index.year==y
    s=df['net'][m]
    sh=s.mean()*np.sqrt(252)/s.std() if s.std()>0 else np.nan
    print(f"  {y:>6} {sh:>8.2f} {ann(df['fund'][m])*100:>9.1f} {ann(df['gross'][m])*100:>12.1f}")

print()
print("="*80)
print("QUEL EST LE NIVEAU DU FUNDING QUI NOURRIT LE CARRY ? (spread long/short)")
print("="*80)
rk=fj.rank(axis=1,method="first")
spread=(fj.where(rk>3).mean(axis=1)-fj.where(rk<=3).mean(axis=1))  # moyen short - moyen long
print(f"  spread funding (moy short - moy long), 8h somme quotidienne :")
print(f"    pleine : {spread.mean()*100:.4f}%/j  ->  {spread.mean()*365*100:.1f}%/an")
print(f"    OOS    : {spread[oos].mean()*100:.4f}%/j  ->  {spread[oos].mean()*365*100:.1f}%/an")
print(f"  funding BRUT par paire (moyenne annuelle, somme 8h x 365) :")
for p in PAIRES:
    print(f"    {p:>6}: {fj[p].mean()*365*100:+.1f}%/an")