# Moteur de propagation SignalMap

Moteur Python (stdlib uniquement, pas de dépendances) qui calcule les cartes de couverture
servies par ce site. Méthode complète : [methode.html](../methode.html) /
https://lab.bourdat.fr/signalmap/methode.html

## Fichiers

| Fichier | Rôle |
|---|---|
| `clutter_engine.py` | **Cœur du modèle.** J(v) ITU-R P.526, récursion de Deygout (cache d'arêtes `K` indépendant de la fréquence, courbure terrestre k=4/3), projection locale lat/lon→mètres (équirectangulaire `to_xy`), intersections segment-polygone, point-in-polygon, Weissberger végétation. ~60 lignes. |
| `params.json` | Paramètres : EIRP/N_RB/portée max par scénario de bande, fenêtre clutter 400 m, caps bâtiments 25/30 dB, caps végétation 300 m/30 dB, pertes d'entrée bâti P.2109-2, hauteur récepteur 1,5 m. |
| `fetch_anfr.py` | **Tâche A.** Télécharge l'export open data ANFR (~66 Mo, data.gouv), filtre à 10 km, décode les positions DMS, apparie aux sites Cartoradio (<60 m + opérateur) et produit `data/sites_anfr.json` : systèmes réels (op × techno × bande) + azimuts des secteurs par site. |
| `rebuild.py` | Collecte des données : sites ANFR (API Cartoradio), altitudes + profils terrain (API altimétrie IGN, 50 échantillons/profil). Produit `data/all_sites_elev.json`, `data/profiles.json`, `data/tool_data.json`. |
| `finegrid.py` | Génère la grille du hameau (50×50 = 2500 cellules à 18 m) + altitudes IGN par lots de 120. |
| `run_fine.py` | **Calcul principal** sur la grille hameau : par cellule × 22 antennes × 4 opérateurs × 8 bandes → RSRP. Géométrie clutter (bâtiments/végétation traversés) calculée une fois par (cellule, antenne), pertes réévaluées par bande via `v = K/√λ`. Sortie `fine_cov.json`. |
| `run_garden.py` | Idem sur la grille fine du jardin (cellules de 3 m, zone tracée + 9 rangs). |
| `sim_all.py` | Variante « bandes seulement » du hameau (sans clutter bâtiments/végétation) pour la carte hameau.html. |
| `gen_fine_map.py`, `gen_all_map.py` | Générateurs des pages HTML : payload JSON embarqué + Leaflet (vendorisé, cf. CSP). |
| `data/` | Jeux de données d'entrée figés (antennes, profils, bâtiments BD TOPO avec hauteurs, végétation, grilles+altitudes) — permet de relancer les calculs sans re-frapper les API. |

## Secteurs (Tâche A)

Les runners lisent `data/sites_anfr.json` (mode nominal) : un site n'est éligible pour
(opérateur, techno, bande) que si le système existe réellement, et le gain horizontal
3GPP `A_h = −min(12(Δφ/65°)², 25 dB)` est appliqué au meilleur secteur. `--scenarios`
restaure l'ancien mode (présence Cartoradio + omni) pour comparaison.

## Les « tuiles »

Les cellules colorées des cartes ne sont **pas** des tuiles raster : ce sont les cellules de la
grille de calcul, embarquées en JSON dans chaque page HTML et dessinées côté client par Leaflet
(`L.rectangle`, rendu canvas). Les fonds de carte (satellite/plan) sont les tuiles WMTS de l'IGN
(`data.geopf.fr`) et d'OpenStreetMap.

## La projection

Deux systèmes :
- **Affichage** : Leaflet en Web Mercator (EPSG:3857), fonds WMTS IGN `TILEMATRIXSET=PM`.
- **Calcul** : projection locale équirectangulaire centrée sur la maison
  (`x = Δlon·111320·cos(lat₀)`, `y = Δlat·110540`, en mètres) — largement suffisante à l'échelle
  de quelques km (erreur < 0,1 %). Les distances antennes utilisent le haversine.

## Relancer

```bash
python3 rebuild.py     # re-fetch ANFR + IGN (ou utiliser data/ figé)
python3 finegrid.py    # grille hameau + altitudes
python3 run_fine.py    # calcul hameau  (~25 s)
python3 run_garden.py  # calcul jardin  (~15 s)
python3 gen_fine_map.py # régénère les pages
```

Les scripts lisent/écrivent dans le répertoire courant (copier `data/*` à côté d'eux, les noms
de fichiers sont relatifs).

## Historique de vérification

Le moteur a été soumis à une relecture adversariale (formules vs standards ITU/3GPP, doc vs code) —
corrections notables : signe du bombement terrestre (le bombement s'**ajoute** à la hauteur du
terrain), offset RE n78 = 35,2 dB, pertes P.2109 recalées (~14–16 dB, quasi plates en fréquence).
