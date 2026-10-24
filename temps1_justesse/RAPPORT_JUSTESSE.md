# Temps 1 — test de justesse des détecteurs de régime (T1J)

## Clarifications avant calcul

Décidées par Jonas le **24/10/2026**, après la découverte (`temps1_justesse/DISCOVERY.md`, commit
`7be0fe1`), **avant tout calcul de détecteur, de juge ou de mesure**.

**A. Les ratés dans la médiane de f_entrée.** Un bear raté (aucune bascule bear avant le creux)
compte **f = 1** dans la médiane et dans le pire cas. Le nombre de ratés reste rapporté à part.

**B. Un épisode à cheval sur deux périodes.** Le juge tourne sur tout l'historique. Un épisode
n'appartient à une période que si **ses deux bornes** (pic et creux) y sont toutes les deux. Les
épisodes à cheval sont listés, et aucune mesure ne les utilise.

**C. Épisodes neutres.** P début = **clôture de la veille du premier jour neutre**, P fin =
clôture du dernier jour neutre (n rendements pour √n).

**D. Le gagnant principal.** Si plusieurs candidats sont retenus, le gagnant principal est celui
qui a **la plus petite moyenne des médianes de f_entrée sur le témoin actions et sur l'or**. À
égalité, c'est le meilleur pire cas moyen qui l'emporte. **Tous les candidats retenus à l'étape A
passent quand même à l'étape B (BTC).**

**E. USD/JPY (DEXJPUS) : vrai calendrier de parution.** ALFRED est indisponible, et le H.10 paraît
une fois par semaine. Une valeur de la semaine S devient utilisable à la clôture du **mardi
suivant**, c'est-à-dire le 2e jour ouvré Fed après le vendredi de S. Si le lundi est férié, c'est
le mercredi.

**F. Essais informatifs.** Les variantes du juge (15 %, 25 %, σ unique) **ne sont pas des
essais** : ce sont les mêmes détecteurs mesurés autrement. Elles sont rapportées, sans être
comptées. Essais informatifs = bande SMA (4 fenêtres × 3 actifs = 12) + fenêtres σ 21 et 126 de
C1_V1 (2 × 3 actifs = 6) = **18**, sur une ligne à part.

### Compteur et essais du verdict (24/10/2026)

- **Les deux valeurs ne se remplacent pas.** Le préenregistrement gelé dit **117** : c'est le
  compteur **global** au gel. BETA a aujourd'hui deux compteurs, et ce rapport donne les deux avec
  leur nom exact :
  - **global** (`experiences.compteur_total`, trading + invest) : 131 avant ce test, parce que T1A
    l'a porté de 117 à 131 le 21/10 ;
  - **invest** (`experiences.compteur(famille="invest")`) : 38 avant ce test. C'est celui qui
    correspond aux tests de détecteurs (T1A y est), donc celui qui est incrémenté.
- **Essais du verdict : 16.** SMA200 compte aussi, et le BTC aussi : 4 détecteurs (SMA200,
  MOM126, C1_V1, C1_V2) × 3 actifs labo (S&P 500, Nasdaq-100, or) = 12, plus les 4 détecteurs
  sur le BTC = 4.
- **Détail affiché avant le lancement** : global 131 → 147, invest 38 → 54, trading actif 93
  inchangé.

### Précisions complémentaires (24/10/2026, demandées avant le gel)

- **Variantes σ 21 et σ 126 de C1_V1.** Pour V, la moyenne du VIX change de fenêtre **avec** σ :
  VIX > moyenne 21 + 2 × σ21, ou moyenne 126 + 2 × σ126. Pour Y, T et G, σ63 devient σ21 ou σ126.
- **« Résultat solide » (règle 5).** Il faut **le même gagnant principal ET la même liste de
  candidats retenus** sous les 3 variantes du juge.
- **Ratés de sortie.** Même règle que A : un raté de sortie compte **f = 1** dans la médiane et le
  pire cas de f_sortie, et le nombre de ratés est rapporté à part.

<!-- FIN DES CLARIFICATIONS : tout ce qui suit est ecrit par le programme (scripts/temps1_justesse.py) -->

*Le reste de ce rapport sera écrit par le programme après la mesure. Aucun chiffre n'a encore été
calculé.*
