# ROADMAP_IA.md — Instructions d'amélioration du moteur SignalMap

> **Destinataire : agent IA (Claude Code ou équivalent) travaillant dans ce repo.**
> Ce fichier est la source de vérité des travaux à réaliser. Exécute les tâches dans
> l'ordre, une par commit, en respectant les invariants ci-dessous. Chaque tâche a des
> critères d'acceptation vérifiables : ne passe à la suivante que quand ils sont verts.

---

## 0. Contexte (à lire avant toute action)

SignalMap prédit le RSRP 4G/5G par opérateur et par bande sur un hameau (Thodure, Isère)
via un modèle déterministe : FSPL + diffraction terrain (Deygout/P.526, cache d'arêtes K
indépendant de la fréquence) + ombres bâtiments (arête de couteau, BD TOPO) + végétation
(Weissberger) + perte d'entrée bâtiment (P.2109, appliquée côté client JS).

Structure :
- `engine/clutter_engine.py` — cœur physique (J(v), Deygout, géométrie 2D). ~70 lignes.
- `engine/params.json` — tous les paramètres du modèle.
- `engine/rebuild.py` — collecte ANFR (Cartoradio) + IGN (altimétrie).
- `engine/run_fine.py`, `run_garden.py`, `sim_all.py` — calculs grilles hameau/jardin.
- `engine/gen_fine_map.py`, `gen_all_map.py` — génération des pages HTML (Leaflet vendorisé).
- `engine/data/` — jeux d'entrée **figés** (22 sites, profils 50 pts, 165 bâtiments,
  73 polygones végétation, grilles). Permet de relancer sans re-frapper les API.
- `methode.html` — documentation publique du modèle. **Doc et code doivent rester synchrones.**

État vérifié (audit du 23/07/2026) : le pipeline se relance tel quel,
`python3 run_fine.py` → `DONE 2500` en ~25–35 s, zéro violation de monotonie fréquentielle.

### Invariants — ne JAMAIS enfreindre

1. **Moteur stdlib uniquement.** Aucune dépendance pip dans `clutter_engine.py` et les
   scripts `run_*`. Les outils de validation (tâche C) peuvent avoir leur propre venv
   dans `validation/`, jamais importé par le moteur.
2. **Doc ↔ code synchrones.** Toute modification du modèle ⇒ mise à jour de
   `methode.html` (et du README engine) dans le MÊME commit. C'est la valeur centrale
   du projet : ce qui est écrit est ce qui tourne.
3. **Données figées versionnées.** Tout nouveau fetch d'API produit de nouveaux fichiers
   dans `data/` (suffixés si le schéma change), commités. On ne modifie jamais un fichier
   de données à la main.
4. **Jamais de données inventées.** Si un champ manque dans une source (tilt, EIRP…),
   il devient un paramètre documenté avec sa valeur par défaut et son incertitude —
   pas une valeur silencieusement supposée.
5. **Reproductibilité.** Après chaque tâche modifiant le calcul :
   `cd engine && cp data/* . && python3 run_fine.py` doit finir par `DONE 2500`.
6. **Pas de régression silencieuse.** Avant une tâche qui NE doit PAS changer les
   résultats (refactor, robustesse), sauvegarde `fine_cov.json` et vérifie l'identité
   après (`diff` ou comparaison JSON). Pour une tâche qui DOIT les changer, produis un
   court rapport chiffré (moyenne/min/max des écarts par bande) dans le message de commit.
7. **Pages autonomes.** Les HTML restent self-contained (payload JSON embarqué,
   Leaflet vendorisé, pas de CDN).

---

## TÂCHE A — Données réelles ANFR : bandes par site + azimuts + secteurs
*Priorité 1. Supprime les deux plus grosses hypothèses du modèle.*

**Contexte.** Le modèle actuel suppose les antennes omnidirectionnelles et déduit les
bandes de "scénarios" nationaux. Or l'open data ANFR publie par support : les systèmes
réels (techno × bande × opérateur) et, par aérien, l'azimut et la hauteur.

**Sources** (Licence Ouverte v2.0) :
- Portail : https://data.anfr.fr — jeu « Observatoire / données sur les réseaux mobiles »
  (mise à jour hebdomadaire).
- Export complet : data.gouv.fr, jeu « Données sur les installations radioélectriques
  de plus de 5 watts » — tables type `SUP_SUPPORT` (position), `SUP_ANTENNE` (azimut,
  hauteur, dimensions), `SUP_EMETTEUR` (système, ex. « LTE 800 », « 5G NR 3500 »),
  `SUP_BANDE` (fréquences début/fin).

**Étapes.**
1. Écrire `engine/fetch_anfr.py` (stdlib : urllib + csv/json) qui télécharge et filtre
   les enregistrements dans un rayon de 10 km autour de `FG['H']` (lat/lon maison,
   dans `data/finegrid.json`).
2. Apparier avec les 22 sites existants de `data/all_sites_elev.json` : par distance
   (< 60 m) + opérateur. Les IDs Cartoradio et ANFR peuvent différer — ne jamais
   apparier par ID seul. Logger les sites non appariés.
3. Produire `data/sites_anfr.json` : par site → liste de systèmes
   `{op, tech, band_mhz, statut}` et liste de secteurs `{azimut_deg, hauteur_m}`.
4. Dans `run_fine.py` / `run_garden.py` / `sim_all.py` : remplacer le test
   `op in s['ops'] and tech in s['ops'][op]` par la présence réelle du système
   (op, tech, bande) sur le site. Garder l'ancien mode derrière un flag
   `--scenarios` pour comparaison.
5. Ajouter le diagramme horizontal 3GPP dans `clutter_engine.py` :
   `A_h(dphi) = -min(12*(dphi/hpbw)**2, ftb)` avec `hpbw=65°`, `ftb=25 dB`
   (nouveaux champs `params.json`). Gain appliqué = max sur les secteurs du site
   (un mobile est servi par le meilleur secteur). Si un site n'a aucun azimut ANFR,
   fallback omni + log.
6. Mettre à jour `methode.html` : §2 (le tableau des données : bandes et azimuts
   deviennent « réels, open data ANFR »), supprimer/amender les limites n°2 et n°3
   du §7, décrire le diagramme sectoriel au §3.

**Acceptation.**
- `python3 fetch_anfr.py` produit `data/sites_anfr.json` avec ≥ 15 sites appariés
  sur 22 ; les non-appariés sont listés en sortie.
- `run_fine.py` tourne dans les deux modes ; le rapport de commit chiffre l'écart
  omni vs sectoriel (attendu : jusqu'à ~25 dB sur les cellules hors-axe).
- Le cas test du doc : le site de Marnans (7,3 km) — vérifier si un secteur pointe
  vers Thodure et le noter dans le commit.
- `methode.html` ne contient plus l'affirmation « azimuts non publics ».

---

## TÂCHE B — Corrections moteur (audit du 23/07/2026)
*Priorité 2. Quatre points relevés par audit externe du code.*

**B1. Profils par cellule (remplace l'étirement).** Aujourd'hui `terrain_K` réutilise le
profil maison→antenne avec `z[0]=pe` ET un `step=dm/(n-1)` qui l'étire à la distance de
la cellule. Correctif : dans `finegrid.py`/`rebuild.py`, récupérer un vrai profil IGN
par (cellule, site) est trop coûteux (2500×22 appels) ⇒ télécharger UNE FOIS la dalle
RGE ALTI 5 m de la zone (Géoplateforme, WMS/WCS ou dalle ASC), la stocker dans
`data/dem_5m.json` (ou .npz-like maison en JSON compact), et échantillonner les profils
localement, sans API, pour chaque (cellule, site). Supprimer la limite n°4 du doc.
*Acceptation :* profils exacts par cellule ; écart avant/après chiffré ; temps de calcul
< 3 min pour le hameau ; plus aucun appel réseau dans `run_*`.

**B2. Weissberger : trancher et documenter.** Le code applique la formule à la longueur
totale sommée (concave ⇒ optimiste). Décision retenue : **par tronçon** (chaque polygone
traversé = un volume de feuillage distinct, cas réel de haies séparées), somme des pertes,
caps inchangés. Implémenter, mesurer l'écart, documenter le choix dans `methode.html` §3.4.

**B3. Robustesse `ray_clutter`.** Gérer le nombre impair d'intersections (rayon tangent) :
si `len(ts)` impair et point de départ hors polygone, ignorer la dernière valeur + compter
l'occurrence dans un compteur de warnings. *Acceptation :* `fine_cov.json` identique
avant/après (cas dégénéré absent des données actuelles) ; test unitaire ajouté dans
`engine/tests.py` (nouveau, stdlib `assert`, lancé par `python3 tests.py`).

**B4. Doc intérieur.** Préciser dans `engine/README.md` et `methode.html` §3.6 que la
perte P.2109 est appliquée côté client (payload `ind` de `gen_fine_map.py`), pas dans
le moteur Python.

---

## TÂCHE C — Nouveaux paramètres physiques
*Priorité 3. Chaque sous-tâche = un commit, params.json + moteur + doc ensemble.*

**C1. Diagramme vertical + tilt (remplace `range_km`).**
`A_v(theta) = -min(12*((theta-tilt)/6.5)**2, 20)` ; `tilt_deg` par défaut 4° (non public
⇒ invariant n°4 : paramètre documenté, bouton de calibration). Une fois en place,
supprimer les caps `range_km` et vérifier que les sites lointains s'éteignent
naturellement sur les bandes hautes. Doc : §3.5.

**C2. Variabilité de localisation (σ_L).**
Nouveau champ `sigma_L_dB: 6`. `run_fine.py` exporte médiane + p10 + p90
(`RSRP ± 1.28·σ_L`). `gen_fine_map.py` : sélecteur médiane/pessimiste/optimiste.
Doc : §7 — l'incertitude devient une couche affichée, plus seulement une phrase.

**C3. Obstacle arrondi (P.526 §4.2).**
Dans `deygout_K`, après identification de l'arête dominante : ajuster une parabole sur
±3 échantillons autour du sommet pour estimer le rayon de courbure ; si r > seuil,
ajouter le terme de correction obstacle arrondi de P.526. Lève la limite n°5. Chiffrer
l'effet sur les trajets concernés.

**C4. Étage / hauteur récepteur.**
`rx_height_m` devient fonction du contexte : vue intérieur avec sélecteur d'étage
(`floor_height_m: 2.8`). Recalcul de la géométrie clutter avec la hauteur effective —
un étage suffit souvent à dégager un bâtiment masquant.

**C5. Bilan uplink.**
`ue_power_dbm: 23`, `enb_sensitivity_dbm: -101` (approx. 10 MHz). Nouvelle couche
« uplink OK ? » = EIRP_UE − pertes(trajet, mêmes termes) > sensibilité. Doc : nouveau
§. C'est souvent l'uplink qui limite en rural, pas le RSRP descendant.

**C6. Pertes terminal.**
`body_loss_dB: 3` appliqué à l'affichage « conditions réelles » (toggle), pas au RSRP
physique. Rapproche la prédiction de ce qu'affiche un téléphone tenu en main.

**C7. Végétation saisonnière (option).**
`winter_bonus_dB: 4` (feuillus). Si faisable simplement : croiser `clutter_veg.json`
avec BD Forêt v2 (essence) pour ne l'appliquer qu'aux feuillus. Sinon toggle global.

**C8. Mix P.2109.**
`indoor_class` par défaut `traditional` ; paramètre `thermally_efficient_entry_loss_dB`
(~28 dB) + possibilité d'override par bâtiment dans `clutter_bld.json` (`"cls":"te"`).

---

## TÂCHE D — Validation croisée par les standards
*Priorité 4. Environnement séparé `validation/` (venv autorisé ici, cf. invariant n°1).*

**D1. Py1812.** `pip install "git+https://github.com/eeveetza/Py1812"`.
⚠ **ACTION HUMAINE REQUISE** : les cartes numériques ITU doivent être téléchargées
manuellement depuis le site de l'ITU (voir README de Py1812) — si absentes, marquer la
tâche `BLOQUÉ:cartes-ITU` dans ce fichier et passer à D2, ne pas contourner.
Script `validation/compare_p1812.py` : pour les 22 trajets maison→antenne, calculer la
perte P.1812-8 (p=50 %, pL=50 %) vs FSPL+Deygout du moteur. Sortie : tableau + écart
moyen/max. Critère de succès : |écart| ≤ 8 dB sur les trajets obstrués (les trajets
en vue peuvent diverger, attendu).

**D2. Delta-Bullington.** Implémenter P.526 §4.5 dans `validation/` (pas dans le moteur),
comparer aux K de Deygout sur les mêmes profils. Publier l'encadrement
Bullington ≤ réalité ≤ Deygout dans une nouvelle page `validation.html` (générée,
autonome, même style que les autres pages).

**D3 (option). Signal-Server/ITM** sur les mêmes sites comme troisième avis
(lignée Longley-Rice indépendante). Uniquement si D1+D2 terminés.

---

## TÂCHE E — Chaîne de calibration terrain
*Priorité 5 côté code — mais à préparer AVANT la sortie terrain.*

**Contexte.** La collecte se fera **en marchant le long d'un chemin**, pas point par
point : l'app Android **G-NetTrack Lite** (gratuite, sans root) logge en continu
RSRP + PCI + EARFCN + GPS et exporte en CSV/KML. C'est la source primaire.
`mesures.html` (saisie manuelle ponctuelle, schéma `measures.json` v1) reste utile
pour les mesures intérieures ; le déposer à la racine du site s'il ne l'est pas.

**E1. Importeur.** `engine/import_gnettrack.py` : CSV G-NetTrack → `data/measures.json`
(schéma v1 : ts, lat, lon, acc_m, op, tech, rsrp_dbm, pci, arfcn, band, freq_mhz,
indoor, floor, note). Décodage EARFCN/NR-ARFCN → bande (reprendre le mapping de
`mesures.html` : B1/B3/B7/B20/B28/B38, n1/n28/n78). Filtres : vitesse < 8 km/h,
précision GPS ≤ 20 m, agrégation par médiane sur segments de 10 m (le RSRP fluctue
de ±3 dB en fast fading — c'est la médiane locale que le modèle prédit).

**E2. Prédicteur ponctuel.** `engine/predict_at.py` : réutilise `clutter_engine` +
dalle DEM (B1) pour prédire le RSRP en un (lat, lon, bande, op) arbitraire — même
chaîne que `run_fine.py` mais pour une liste de points.

**E3. Calibration.** `engine/calibrate.py` : lit `data/measures.json`, prédit via E2,
ajuste par moindres carrés un `eirp_offset_db` par (site × bande) — borné à ±8 dB
(au-delà = problème de modèle, pas d'EIRP : logger, ne pas absorber). Sorties :
`data/calibration.json` + rapport (RMSE avant/après, scatter en ASCII ou page HTML).
Les `run_*` appliquent les offsets si `calibration.json` existe.
**Identification du site servant :** apparier le PCI mesuré est impossible sans base
PCI ; apparier par (bande, meilleur serveur prédit) et signaler les points où le
2e serveur prédit est à < 3 dB (ambigus, exclus du fit).

**Acceptation E :** avec un CSV G-NetTrack fourni, `import → calibrate` tourne de bout
en bout et publie le RMSE. Tant qu'aucune mesure réelle n'existe, tester avec un CSV
synthétique généré depuis `fine_cov.json` + bruit gaussien σ=6 dB (le fit doit
retrouver des offsets injectés à ±1 dB près).

---

## TÂCHE F — Consolidation
1. `validation.html` : rassembler D1/D2/D3 + le rapport de calibration E3
   (scatter prédit/mesuré, RMSE) — c'est la page qui rend le projet opposable.
2. Fourchettes affichées partout (C2) ; mention de ce qui est mesuré vs supposé
   dans un encadré en tête de chaque carte.
3. Paramétrer l'adresse (lat0/lon0 + géocodage BAN + fetch BD TOPO/ALTI auto) pour
   généraliser à n'importe quel hameau — SEULEMENT quand A→E sont stables.

---

## Journal (à tenir par l'agent)

| Date | Tâche | Commit | Résultat / écarts chiffrés | Blocages |
|---|---|---|---|---|
| 2026-07-23 | A | (ce commit) | 21/22 sites appariés (1584007 → repli scénario, loggé). Écarts réel-sectorisé vs omni-scénarios (hameau) : SFR/Bouygues 1800/2100 −16/−17 dB moy (max −60, Chambaran hors-axe) ; Free B20 supprimée (bande fantôme, −72 dB) ; Orange B7 et n1 locales supprimées ; Orange n78 gagnée (Beaufort 2,94 km, secteur 160° = 27° hors-axe → couverture n78 réelle). Cas test Marnans : secteur 290° vs cap requis 280° → dans l'axe (−0,3 dB), confirmé. Cap 3500 porté à 5 km (sites n78 réels à 2,9 et 4,7 km), suppression prévue en C1. LTE 900 (Free B8) présent dans les données, non simulé (pas de scénario 4G900) — proxy 4G700 dans l'outil bandes, à traiter en C. | — |
