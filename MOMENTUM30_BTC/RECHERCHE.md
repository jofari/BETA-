# Momentum trente jours sur le BTC — note de recherche

**Statut : proposition de Claude, écrite le 10/11/2026 à la demande de Jonas** (« à l'aide de
toutes les données et de tous les tests effectués dans BETA, théorise et teste une stratégie
rentable sur le BTC, et fais-la passer dans BETA »). Rien ici n'est une « décision de Jonas »
sauf mention explicite. Le skill de recherche demande que Jonas écrive lui-même l'hypothèse et
la synthèse de littérature ; à sa demande, Claude les a rédigées, et elles restent à relire par lui.

Deux entorses au skill de recherche, nommées une fois :
1. l'hypothèse et le mécanisme sont écrits par Claude, pas par Jonas ;
2. la nuit entre le gel du préenregistrement et le lancement est sautée (Jonas veut le
   résultat aujourd'hui). La mesure est déterministe : relancer demain donnerait le même
   chiffre. Ce que la nuit protège, c'est la relecture du préenregistrement ; Claude l'a
   relu une fois avant de lancer, mais ce n'est pas la relecture de Jonas. Au sens strict du
   skill, le résultat est donc **« exploration, pas recherche »** tant que Jonas n'a pas relu
   et validé le préenregistrement. Un résultat d'exploration inspire une question, il ne
   prouve rien.

---

## 1. Question

**Sur le perpétuel BTC/USDT de Binance, en quotidien, une exposition long-only décidée à la
clôture et appliquée le lendemain — 100 % investi quand le rendement des 30 derniers jours est
positif, 0 % sinon — bat-elle le buy-and-hold du même contrat, sur la même période
(2019-10 → 2024-12), en rendement annualisé ET en Sharpe, tous coûts déduits (frais, funding),
sans que ce résultat soit reproductible par un placement aléatoire des mêmes périodes
d'exposition ?**

Référence de comparaison : le buy-and-hold du perpétuel BTC, qui paie le même funding.

## 2. Littérature (vérifiée le 10/11/2026 par recherche web ; synthèse de Jonas : à écrire)

| Source | Actif, période | Méthode | Résultat | Limites |
|---|---|---|---|---|
| Moskowitz, Ooi, Pedersen, « Time series momentum », *Journal of Financial Economics* 104(2), 2012, 228-250 | 58 contrats à terme (indices, devises, matières premières, taux), 1985-2009 | signe du rendement passé 1 à 12 mois, position le mois suivant | persistance des rendements de 1 à 12 mois, positive sur chacun des 58 contrats ; renversement partiel au-delà ; expliqué par sous-réaction puis sur-réaction retardée | pas de crypto ; horizon mensuel ; données jusqu'en 2009 |
| Liu, Tsyvinski, « Risks and Returns of Cryptocurrency », *Review of Financial Studies* 34(6), 2021, 2689-2727 (NBER w24877) | BTC, ETH, XRP, 2011-2018 selon l'actif | momentum en série temporelle, fréquences quotidienne et hebdomadaire | effet de momentum en série temporelle significatif aux fréquences quotidienne et hebdomadaire sur les trois actifs | période antérieure à 2019 (avant tout le train de BETA) ; pas de coûts de perpétuel ; l'horizon de 4 semaines n'a pas été vérifié dans le texte intégral |
| Grobys, Sapkota, « Cryptocurrencies and momentum », *Economics Letters* 180, 2019, 6-10 | 143 cryptos, 2014-2018 | momentum en coupe (gagnants moins perdants, 12-1-1) et test du momentum en série temporelle | **aucun profit de momentum** ; certaines variantes négatives ; pas de soutien net au momentum en série temporelle de Moskowitz et al. ; marché « plus efficient qu'annoncé » | coupe transversale surtout ; petites capitalisations ; période courte |
| ARIT, `research/pertinence_donnees_2026-09-05/RAPPORT.md` (Jonas et Claude, 05/09/2026) | BTC, ETH, SOL, BNB perpétuels Binance, 2019-09 → 2026-09 | long-only quotidien, signe du rendement sur L jours (L = 7, 14, 30, 60, 90), frais 5 pb par changement, **sans funding** | Sharpe BTC : 0,44 / 1,01 / 1,00 / 0,88 / 0,48 contre 0,55 pour le hold ; plateau entre 14 et 60 jours ; train < 2023 : 1,03, 2023+ : 0,98 | **inclut le hold-out de BETA (2025+)** ; balayage de 5 fenêtres ; pas de funding ; pas de test contre un placement aléatoire |

La source qui contredit l'idée est Grobys et Sapkota (2019). Elle porte surtout sur le momentum en
coupe transversale entre cryptos, pas sur la série temporelle du seul BTC, mais elle rappelle que
le momentum crypto n'est pas acquis.

## 3. Mécanisme (proposition de Claude)

- **Pourquoi l'effet existerait.** Sous-réaction à l'information et flux par vagues (particuliers,
  effet de levier et funding qui s'auto-entretiennent, entrées par paliers des institutionnels) :
  les tendances du BTC durent des semaines, pas des heures. Un signal lent (30 jours) ignore le
  bruit intra-semaine et ne bascule qu'après un vrai changement de régime.
- **Qui prend l'autre côté.** Les contrariens et les teneurs de marché qui vendent la hausse et
  achètent la baisse. C'est exactement ce que BETA a mesuré depuis août : toutes les hypothèses
  **contrariennes** sur ces paires sont INFIRMÉES avec un R moyen négatif — R2 (retour à la
  moyenne), R7 (mèches de liquidation), R9 (funding extrême), R4 (Fear & Greed), R10 (conjonction),
  R11 (crédit), R8/R13/R14 (fade de l'open). Si fader perd, la continuation a au moins une chance.
- **Pourquoi il ne disparaît pas.** La contrepartie est structurelle (teneurs de marché,
  arbitragistes de funding, particuliers qui « achètent le creux ») ; et le coût de l'effet est le
  retard : le signal rate le premier mois de chaque hausse et subit le premier mois de chaque
  baisse. Ce retard est ce qui le rend tenable : il n'est rentable que si les tendances durent
  plus que leur délai de détection.
- **Quand il devrait cesser.** Marché en range (va-et-vient de 30 jours : chaque bascule coûte
  frais + mouvement adverse), retournements brusques (krach de mars 2020 : le signal 30 j reste
  long jusqu'à 20 jours après le sommet), et institutionnalisation (ETF au comptant depuis janvier
  2024) si elle rend le marché plus efficient. Le funding positif en bull (coût du long perpétuel)
  érode l'effet par rapport au comptant.

## 4. Données

| Besoin | Disponible | Profondeur | Biais / remarque |
|---|---|---|---|
| Clôtures quotidiennes BTC perpétuel | lake BETA `BTC 1d` (freqtrade, Binance USDⓈ-M), couverture 100 %, 0 trou | 2019-09-08 → 2026-11-09 ; train jusqu'au 2024-12-31 (hold-out scellé) | bougie datée par son ouverture ; clôture = 00:00 UTC du lendemain |
| Funding 8 h | `lecture.funding("BTC")`, horodaté au règlement | même période | moyenne 0,0134 % par 8 h sur le train (≈ 14,6 %/an pour un long) |
| Taux sans risque (cash) | FRED `DFF` (`fedfunds`, séries macro du lake) | 2019+ | décalé d'un jour (publication), convention du pipeline |
| Spread | tick BTC ≈ 0,01 pb du prix | — | négligeable devant 6 pb de frais : ignoré, dit ici |

Rien ne manque. Hold-out 2025+ : jamais lu. Les clôtures 2019-2024 ont déjà servi à toutes les
R et aux voies C (voir « déjà connu » du préenregistrement).

## 5. Prédiction réfutable (écrite avant tout résultat)

Si l'idée est vraie, on devrait observer sur 2019-10 → 2024-12, tous coûts déduits :
- Sharpe de la stratégie ≥ Sharpe du buy-and-hold + 0,20 ;
- drawdown maximal de la stratégie moins profond d'au moins 15 points que celui du hold ;
- CAGR de la stratégie ≥ CAGR du hold ;
- p retenue des deux nulls (décalage circulaire, mélange des segments) < 0,05.

L'idée tombe si : Sharpe ≤ celui du hold, ou CAGR < celui du hold (la stratégie mesure alors le
marché en moins bien), ou p retenue ≥ 0,20 (le placement des périodes d'exposition ne vaut pas
mieux qu'un tirage au hasard de même agitation).

Issue attendue : **infirmée** — prior fondé sur l'historique du banc (14 hypothèses de trading,
aucune confirmée), sur le funding (absent des chiffres d'ARIT, ~15 %/an contre le long) et sur
la condition « CAGR ≥ hold » que les chiffres d'ARIT ne documentent pas (ils ne donnent que le
Sharpe).

## 6. Préenregistrement

`MOMENTUM30_BTC/PREENREGISTREMENT.md`, id `MOMENTUM30_BTC` au registre, famille invest.
