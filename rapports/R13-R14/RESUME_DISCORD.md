# 🟢 Fade open NY sur l'or (5m) · Fade open NY sur le Nasdaq-100 (1h) — rapport du programme — 2026-11-04

**Verdicts au registre : R13 INFIRMÉE · R14 INFIRMÉE.**
État du calcul : verdict au registre et 42 contrôles sur 42 passés (pastille = état du calcul, pas jugement du résultat).

## Fade open NY sur l'or (5m) — R13 — INFIRMÉE
- Préenregistrée le 04/11/2026 (N = 94) ; close le 04/11/2026 ; conforme à l'issue attendue : oui
- Série : XAU_SPOT 5m, du 21/06/2023 au 31/12/2024, 108 528 bougies (empreinte 2b385177304526f9)
```
variante             issue           n   R net  R brut  coûts    MDE  échouées
stop 0,5x amplitude  infirmée      395   −0,57   +0,09   0,66   0,24  8/10
stop 1,0x amplitude  infirmée      395   −0,27   +0,06   0,33   0,15  8/10
stop 1,5x amplitude  infirmée      395   −0,19   +0,03   0,22   0,11  8/10
```
R net, R brut et coûts : moyennes par trade, en R (R brut et coûts recalculés depuis les trades ; la règle ne porte que sur le R net).
- Buy-and-hold du même actif sur la même période (S8) : +35,59 % ; S8 franchie par 0 variante(s) sur 3
- Épreuve de causalité sur la série mesurée : non enregistrée avec les runs ; relancée par le programme : OK pour 3 variante(s) sur 3, 395 signaux (même code que les runs)

## Fade open NY sur le Nasdaq-100 (1h) — R14 — INFIRMÉE
- Préenregistrée le 04/11/2026 (N = 95) ; close le 04/11/2026 ; conforme à l'issue attendue : oui
- Série : NDX 1h, du 22/11/2023 au 31/12/2024, 1 930 bougies (empreinte 2ce1d08485626763)
```
variante             issue           n   R net  R brut  coûts    MDE  échouées
stop 0,5x amplitude  infirmée      277   −0,60   −0,13   0,47   0,25  9/10
stop 1,0x amplitude  infirmée      276   −0,34   −0,10   0,24   0,19  10/10
stop 1,5x amplitude  infirmée      276   −0,25   −0,09   0,16   0,14  10/10
```
R net, R brut et coûts : moyennes par trade, en R (R brut et coûts recalculés depuis les trades ; la règle ne porte que sur le R net).
- Buy-and-hold du même actif sur la même période (S8) : +31,23 % ; S8 franchie par 0 variante(s) sur 3
- Épreuve de causalité sur la série mesurée : non enregistrée avec les runs ; relancée par le programme : OK pour 3 variante(s) sur 3, 278 signaux (même code que les runs)

## Compteur d'essais
- R13 (trading) : N = 94 au préenregistrement, lot jugé à N = 98
- R14 (trading) : N = 95 au préenregistrement, lot jugé à N = 100
- Aujourd'hui : trading 99

## Fichiers
- `rapports/R13-R14/RAPPORT.md` (joint) : préenregistrement mot pour mot, batterie porte par porte, sorties, sens, années, contrôles de cohérence
- Code `b962b07` ; runs 8bfb719165c8, 53aae4e0be16, f621f8eb0240, 544b3cd8a3bf, eaa351a4c37a, 03d6d0620341

Message écrit par le programme (`beta/rapport/experience.py`), sans interprétation.
