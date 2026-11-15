# Audit des données · AlphaForge AI

Date : 2026-11-14 · Branche `main` · Audit en lecture seule (aucun fichier de `data/` ni de `app/` modifié).
Périmètre : `data/raw/`, `data/sources/`, `data/scripts/`, `data/processed/`, `app/src/donnees/`, `app/config/`,
`docs/decisions.md`. Les mesures ont été recalculées indépendamment, directement à partir de `data/raw/starter/`.

**Verdict global : aucun problème bloquant.**
- Les prix, la conversion en CAD et l'alignement des calendriers sont corrects.
- Les mesures sont cohérentes avec les ordres de grandeur connus.
- Les fichiers de `data/processed/` correspondent exactement à ce que produisent les scripts : l'écart relatif maximal est de 3·10⁻¹⁶.
- Les points à corriger sont surtout de la **documentation**, de la **signalisation dans l'interface** et la **robustesse de la source ESG**.

---

## 1. Tableau des vérifications

| # | Vérification | Résultat | Gravité | Correction proposée |
|---|---|---|---|---|
| 1.1 | `data/raw/` intact | ✅ `raw/starter/` est ajouté en un seul commit (`dfb1495`) et n'a jamais été modifié depuis. Aucun script n'écrit dans `raw/`. Les scripts lisent `RAW` et `AJOUTS` et écrivent seulement dans `processed/` et `reports/`. | — | — |
| 1.2 | Sources ajoutées documentées | ✅ Les 2 fichiers de `raw/added/` ont leurs 3 lignes dans `sources/sources_added.csv` : origine, URL, date des données, date de consultation, licence, traitement, limites. ⚠️ En revanche, `esg_etf_holdings.csv` n'a qu'une colonne `symbole` : on ne sait pas, ligne par ligne, si le titre vient d'ESGV ou de XESG, ni à quelle date. | mineur | Ajouter les colonnes `fnb` (ESGV/XESG) et `date_donnees` au fichier brut ajouté. Faire de même pour l'URL, par exemple avec un nouveau fichier versionné plutôt que réécrit. |
| 1.3 | `data/processed/` versionné | ✅ Il est **versionné** dans git (les 5 CSV sont suivis) et n'est pas ignoré. Le risque de retomber en données fictives sur un clone propre est donc faible. Ces fichiers sont à jour avec les scripts (reconstruction indépendante identique). ⚠️ Risque résiduel : si quelqu'un modifie un script sans relancer la chaîne, `processed/` sera périmé sans que rien ne le signale. | mineur | Ajouter un test pytest qui vérifie que `charger()[2]` ne contient pas « FICTIVES » quand `DONNEES=local`. Ajouter aussi un contrôle d'empreinte (date + nombre de lignes) dans `rapport_qualite.md`. |
| 1.4 | Données fictives signalées dans l'interface | ⚠️ Le repli est **silencieux**. `chargeur._sans_donnees_reelles()` bascule sur `_demo()` dès que `prix_cad_alignes.csv` est absent. Dans l'interface, seule une légende discrète le signale : `st.caption("Données : DONNÉES FICTIVES…")` en bas de page. Les traces portent aussi la source, mais il faut les ouvrir pour la voir. Un jury ou un utilisateur peut ne pas le voir. | **important** | Afficher un `st.warning` bien visible en haut de page quand la source contient « FICTIVES ». Ajouter aussi une mention dans l'explication finale. |
| 2.1 | `adj_close` partout | ✅ `01_nettoyer_prix.py` lit seulement `adj_close`. L'application ne lit jamais `raw/` et aucun `close` n'apparaît dans `app/src`. | — | — |
| 2.2 | Sens du taux USD→CAD | ✅ `usdcad` va de **1,2451 à 1,4603** (CAD pour 1 USD), et `usdcad × cadusd = 1,0000` sur toutes les lignes. Les prix en USD sont **multipliés** par `usdcad`. 23 734 lignes USD sont converties, 16 315 lignes CAD (tous les `.TO`) ne le sont pas. Les devises de l'univers et des prix concordent (0 écart). | — | Mettre à jour le commentaire de `01_nettoyer_prix.py`, qui dit encore « hypothèse … à vérifier ». |
| 2.3 | Taux reporté les jours sans taux | ✅ Le taux est reporté sur le calendrier civil complet **avant** la fusion, donc sans mélange entre symboles. La date du taux (16 h 30 HE, Banque du Canada) est cohérente avec la clôture américaine de 16 h HE. | — | — |
| 2.4 | Alignement des calendriers | ✅ Le calendrier de référence est l'union des jours TSX et NYSE : 1 282 jours, aucune fin de semaine. La crypto (1 827 lignes, 7 j/7) est ramenée à ces dates. Les calculs de risque utilisent des rendements **hebdomadaires** du vendredi, ce qui neutralise les fériés propres à chaque bourse. La pire fenêtre de 12 mois utilise des données quotidiennes en jours de semaine. | — | — |
| 2.5 | Report excessif de valeurs | ✅ 783 valeurs sont reportées en tout : 27 par titre non crypto, sur 29 titres, et aucune pour la crypto. Le plus long report consécutif est de **2 jours de bourse** (fériés TSX collés). Aucune valeur n'est inventée au-delà d'un congé. Il reste 0 valeur manquante après nettoyage. | — | — |
| 2.6 | Effet des fériés sur les calculs quotidiens | ⚠️ Un jour férié aux États-Unis mais ouvré à la TSX donne un rendement nul aux titres américains, et inversement. Cela n'a aucun effet sur les mesures hebdomadaires. Pour `pire_fenetre_12_mois` (quotidien), une fenêtre de 252 lignes couvre légèrement moins de 12 mois civils. | mineur | Le documenter (une phrase dans `decisions.md`). |
| 2.7 | Valeurs manquantes et anomalies brutes | ✅ 40 049 lignes, 31 symboles, 0 doublon (date, symbole), 0 `adj_close` manquant ou ≤ 0. Seule une ligne de ZST.TO a un volume nul (2022-07-06) ; son prix est cohérent et la ligne est conservée. | — | — |
| 2.8 | Faux « split » CNQ.TO 1,021 (2022-08-22) | ⚠️ Ce jour-là, `adj_close` affiche **+2,8 %** contre +0,6 % pour `close`. Le dividende de 0,75 $ explique environ 1 point de cet écart ; le reste vient probablement de l'artefact. Le point est déjà documenté dans `decisions.md` (« effet ≈ 2 %, non corrigé »). | mineur | Le laisser tel quel, mais préciser l'ampleur mesurée dans `decisions.md`. |
| 2.9 | Cohérence temporelle macro | ✅ `macro_quotidien.csv` ne contient que les séries **quotidiennes** : V39079, les rendements à 2 et 10 ans du Canada, DFF, DGS2 et DGS10. L'IPC et le chômage (mensuels, publiés en retard) sont **exclus**. Aucune information « du futur » n'entre donc dans les calculs. | — | — |
| 2.10 | `macro_rates.csv` réellement branché | ✅ Oui, mais **une seule série est utilisée** : V39079 (taux directeur de la Banque du Canada), via `contexte_macro` et l'outil Strands `contexte_taux_2022`. Les valeurs sont cohérentes : 0,25 % → 4,25 % en 2022, 7 hausses, la première le 2022-03-03 (réalité : 2 mars 2022, effective le 3). Les 5 autres séries sont copiées mais jamais lues. | mineur | Soit les utiliser (par exemple les taux à 10 ans du Canada et des États-Unis pour expliquer la baisse de XBB et TLT en 2022), soit les signaler comme non utilisées. |
| 2.11 | Valeurs FRED révisées | ℹ️ Les séries quotidiennes (DGS2, DGS10, DFF) ne sont quasiment pas révisées, donc l'impact est nul. | — | À citer dans les limites. |
| 2.12 | ESG : couverture | ⚠️ Les **20 actions sur 20** sont évaluées (4 `oui`, 16 `non`). Les **11 actifs sur 31** restants sont « non évalué » : 9 FNB et 2 cryptos. Le moteur traite « non évalué » comme une information manquante et non comme une conformité, ce qui est correct. | mineur | — |
| 2.13 | ESG : format des symboles | ✅ Les symboles sont harmonisés (`.TO` ajouté pour XESG, `-USD` pour la crypto). La jointure `esg_controverses` ↔ univers trouve les 20 actions sans orphelin. | — | — |
| 2.14 | ESG : robustesse de l'exclusion de JNJ | ⚠️ L'exclusion de JNJ d'ESGV est **déduite** de son absence du top 40 (poids < 0,35 %), sans vérification dans la liste complète des titres. C'est le seul `oui` hors énergie, et il pèse sur Mateo (JNJ est dans le portefeuille supposé d'Amira). | **important** | Vérifier JNJ dans le fichier **complet** des titres d'ESGV, puis confirmer ou corriger la ligne. Ajouter la preuve (date, URL) dans `sources_added.csv`. |
| 2.15 | ESG : méthodologies mélangées | ⚠️ `dans_fnb_esg` = « dans ESGV **ou** XESG ». Or ESGV exclut l'énergie alors que XESG pondère sans exclure (ENB et CNQ y sont). Le drapeau ne veut donc pas dire la même chose pour une action canadienne et pour une action américaine. C'est documenté dans `decisions.md`. | mineur | Dans l'interface, afficher le FNB de référence (ESGV ou XESG) à côté du drapeau. |
| 2.16 | ESG : biais d'anticipation | ℹ️ L'instantané de 2026 est appliqué à toute la période depuis 2021. C'est documenté. | — | À citer dans les limites. |
| 3.1 | Rendements 2022 | ✅ Voir le tableau §2 : TSLA −65,0 %, NVDA −50,3 %, SPY −18,2 %, BTC −64,3 % en devise d'origine, tous conformes aux repères. | — | — |
| 3.2 | Fractionnements | ✅ Aucune chute artificielle les jours de split (voir §2.2). Aucun « pire jour » d'un titre ne tombe sur une date de split. | — | — |
| 3.3 | Volatilités | ✅ Toutes sont plausibles (voir §2.1). BTC (51 %) est un peu sous le repère indicatif de 60 à 80 %, ce qui reste cohérent avec la volatilité réalisée de 2023 à 2026, plus calme. | — | — |
| 3.4 | Rendements exprimés en CAD | ⚠️ Toutes les mesures affichées sont **en CAD**. En 2022, la hausse du dollar américain (≈ +7 %) amortit les pertes : SPY fait −18,2 % en USD mais **−12,6 % en CAD**, et TSLA −65,0 % contre −62,6 %. Un utilisateur qui compare avec les chiffres « connus » pourrait croire à une erreur. | **important** | Écrire « en CAD » dans le libellé des traces de rejeu et de volatilité, et ajouter une phrase dans les limites. |
| 4.1 | Section « Limites » de la documentation technique | ⚠️ La section `## 7. Limites et améliorations` de `docs/documentation_technique.md` est **vide**. | **important** | La remplir avec la liste du §3 ci-dessous. |

---

## 2. Chiffres de vraisemblance calculés

### 2.1 Par actif

Sources des calculs :
- **2022 orig.** : `adj_close` brut, du dernier jour de 2021 au dernier jour de 2022, en devise d'origine.
- **2022 CAD** : même période, mais à partir de `prix_cad_alignes.csv`.
- **Vol. hebdo CAD** : méthode de l'application (vendredi, × √52).
- **Vol. quotid. orig.** : × √252, ou × √365 pour la crypto.

| Actif | Classe | Devise | 2022 orig. | Repère | 2022 CAD | Vol. hebdo CAD | Vol. quotid. orig. | Plage attendue |
|---|---|---|---|---|---|---|---|---|
| RY.TO | action | CAD | −1,5 % | | −1,5 % | 15,0 % | 15,5 % | |
| TD.TO | action | CAD | −6,0 % | | −6,0 % | 18,0 % | 17,7 % | |
| MFC.TO | action | CAD | +5,8 % | | +5,8 % | 20,5 % | 21,6 % | |
| ENB.TO | action | CAD | +14,0 % | | +14,0 % | 17,4 % | 16,1 % | |
| CNQ.TO | action | CAD | +52,9 % | | +52,9 % | 32,0 % | 30,7 % | |
| CNR.TO | action | CAD | +5,5 % | | +5,5 % | 17,6 % | 19,9 % | |
| FTS.TO | action | CAD | −7,9 % | | −7,9 % | 15,0 % | 14,7 % | |
| ATD.TO | action | CAD | +13,2 % | | +13,2 % | 25,0 % | 24,1 % | |
| SHOP.TO | action | CAD | −73,0 % | | −73,0 % | 65,1 % | 64,4 % | tech 40-70 % ✅ |
| CSU.TO | action | CAD | −9,7 % | | −9,7 % | 29,7 % | 30,5 % | |
| AAPL | action | USD | −26,4 % | | −21,4 % | 27,2 % | 28,2 % | |
| MSFT | action | USD | −28,0 % | | −23,1 % | 26,8 % | 28,5 % | |
| NVDA | action | USD | **−50,3 %** | ≈ −50 % ✅ | −46,9 % | 46,8 % | 51,9 % | tech 40-70 % ✅ |
| GOOGL | action | USD | −39,1 % | | −34,9 % | 32,4 % | 32,6 % | |
| AMZN | action | USD | −49,6 % | | −46,2 % | 33,4 % | 36,7 % | |
| TSLA | action | USD | **−65,0 %** | ≈ −65 % ✅ | −62,6 % | 55,7 % | 59,6 % | tech 40-70 % ✅ |
| JPM | action | USD | −12,6 % | | −6,7 % | 23,8 % | 24,4 % | |
| JNJ | action | USD | +6,0 % | | +13,2 % | 18,3 % | 18,1 % | |
| PG | action | USD | −5,0 % | | +1,4 % | 17,4 % | 18,5 % | |
| XOM | action | USD | +87,4 % | | +100,2 % | 27,5 % | 26,7 % | |
| XIU.TO | FNB actions | CAD | −6,3 % | | −6,3 % | 12,5 % | 13,1 % | indices 15-20 % (≈) |
| SPY | FNB actions | USD | **−18,2 %** | ≈ −18 % ✅ | −12,6 % | 14,9 % | 17,3 % | indices 15-20 % ✅ |
| QQQ | FNB actions | USD | −32,6 % | | −28,0 % | 20,6 % | 23,4 % | |
| ESGV | FNB actions | USD | −24,0 % | | −18,9 % | 16,4 % | 18,7 % | indices 15-20 % ✅ |
| XBB.TO | FNB oblig. | CAD | −11,7 % | | −11,7 % | 6,6 % | 6,6 % | oblig. 5-8 % ✅ |
| ZST.TO | FNB oblig. | CAD | +1,2 % | | +1,2 % | 0,5 % | 0,6 % | ultra-court ✅ |
| AGG | FNB oblig. | USD | −13,0 % | | −7,1 % | 7,1 % | 6,2 % | oblig. 5-8 % ✅ |
| TLT | FNB oblig. | USD | −31,2 % | | −26,5 % | 15,2 % | 15,6 % | oblig. longues (plausible) |
| GLD | FNB or | USD | −0,8 % | | +6,0 % | 16,2 % | 19,2 % | |
| BTC-USD | crypto | USD | **−64,3 %** | ≈ −64 % ✅ | −61,7 % | 50,7 % | 50,8 % | crypto 60-80 % (un peu bas, plausible) |
| ETH-USD | crypto | USD | −67,5 % | | −65,2 % | 65,5 % | 68,5 % | crypto 60-80 % ✅ |

Remarques :
- XIU.TO (12,5 %) est un peu sous la plage indicative, ce qui est normal pour le TSX 60 entre 2022 et 2026.
- Les volatilités hebdomadaires en CAD des actifs américains sont en général inférieures aux volatilités quotidiennes en USD : le change amortit les chocs.

### 2.2 Jours de fractionnement (variation du jour, `adj_close` brut et prix traités en CAD)

| Titre | Date | Ratio | `adj_close` | `close` | Prix traités (CAD) | Verdict |
|---|---|---|---|---|---|---|
| TSLA | 2022-08-25 | 3:1 | −0,3 % | −0,3 % | −0,7 % | ✅ pas de chute artificielle |
| SHOP.TO | 2022-06-29 | 10:1 | −5,6 % | −5,6 % | −5,6 % | ✅ mouvement de marché réel (pas −90 %) |
| NVDA | 2024-06-10 | 10:1 | +0,7 % | +0,7 % | +0,9 % | ✅ |
| AMZN | 2022-06-06 | 20:1 | +2,0 % | +2,0 % | +1,9 % | ✅ |
| GOOGL | 2022-07-18 | 20:1 | −2,5 % | −2,5 % | −3,1 % | ✅ |
| CNQ.TO | 2024-06-11 | 2:1 | +0,2 % | +0,2 % | +0,2 % | ✅ |
| CNQ.TO | 2022-08-22 | « 1,021 » | +2,8 % | +0,6 % | +2,8 % | ⚠️ artefact connu (voir 2.8) |

Les pires jours observés sont des événements réels et ne tombent sur aucune date de split :
- NVDA, −17,0 % le 2025-01-27 ;
- SHOP.TO, −19,6 % le 2025-04-03 ;
- TSLA, −15,4 % le 2025-03-10 ;
- BTC, −16,0 % le 2022-06-13.

### 2.3 Autres contrôles chiffrés

- **Change** : `usdcad` est compris entre 1,2451 et 1,4603. Le fichier compte 1 245 lignes, du 2021-11-12 au 2026-11-12.
- **Prix traités** : 1 282 jours × 31 actifs, du 2021-11-12 au 2026-11-12. Il n'y a aucune valeur manquante et aucune fin de semaine.
- **Reconstruction indépendante** : la conversion en CAD a été recalculée à partir de `raw/`. L'écart maximal avec `processed/` est de 3·10⁻¹⁶.
- **Taux directeur (V39079)** : il passe de 0,25 % à 4,25 % en 2022, avec 7 hausses, la première le 2022-03-03.

---

## 3. Limites à écrire dans la documentation technique (§7)

1. **Biais de survie.** L'univers a été choisi en 2026 parmi des titres importants aujourd'hui. Un rejeu depuis 2021 paraît donc meilleur que ce qu'aurait donné une sélection faite en 2021.
2. **Mesures en CAD.** Tous les rendements et toutes les volatilités incluent l'effet de change USD/CAD. En 2022, la hausse du dollar américain a réduit les pertes des actifs américains d'environ 5 à 6 points (SPY : −18,2 % en USD, −12,6 % en CAD).
3. **Rendement total brut.** `adj_close` réinvestit les dividendes à 100 %. On ne tient compte ni de la retenue à la source américaine (15 % pour un résident canadien hors REER), ni des frais de gestion des FNB, ni des frais de transaction ou de l'impôt.
4. **Données Yahoo Finance non certifiées.** Les valeurs ajustées changent si l'on retélécharge les données. Il existe aussi un artefact connu sur CNQ.TO le 2022-08-22 (environ 1 à 2 points).
5. **Calendriers.** Le calendrier retenu est l'union TSX + NYSE, avec report de la dernière valeur sur 2 jours au plus pendant les fériés. La crypto est ramenée aux jours de bourse : son prix est la clôture du jour UTC, alors que celui des actions est la clôture de 16 h HE, soit un décalage de quelques heures. Les mesures de risque sont hebdomadaires.
6. **Historique court.** Cinq ans (261 semaines) dominés par un seul régime de hausse des taux (2022). Les corrélations et les volatilités estimées sont instables, et la pire baisse dépend de cet échantillon.
7. **Macro.** Seul le taux directeur de la Banque du Canada est utilisé. L'IPC est exclu volontairement à cause de son délai de publication. Les séries FRED sont dans leur dernière version (révisées).
8. **Méthodologie ESG.**
   - Ce n'est pas une note ESG. C'est la présence dans un FNB ESG (ESGV pour les États-Unis, XESG pour le Canada, qui suivent des méthodes différentes) plus une règle sectorielle de l'équipe (énergie = controverse).
   - L'exclusion de JNJ est déduite du top 40 d'ESGV.
   - Il n'y a pas de revue des controverses sociales ou de gouvernance.
   - L'instantané de 2026 est appliqué à toute la période (biais d'anticipation).
   - Les FNB et la crypto sont « non évalué », ce qui est traité comme une information manquante, jamais comme une conformité.
9. **Portefeuilles supposés.** Les compositions par persona sont des hypothèses de l'équipe et non des données réelles de clients.
10. **Données fictives de démonstration.** Si `data/processed/` est absent, l'application utilise une série simulée (`chargeur._demo`). Ces données ne servent qu'au développement.

---

## 4. Corrections proposées (par ordre de priorité)

| Priorité | Correction | Fichiers touchés | Effort |
|---|---|---|---|
| 1 | **Bandeau visible quand les données sont fictives** : un `st.warning` en haut de page si `res["source_donnees"]` contient « FICTIVES », avec la même mention dans l'explication. | `app/ui/streamlit_app.py` (+ éventuellement `app/src/agents/explicabilite.py`) | 10 min |
| 2 | **Test anti-repli** : un test pytest qui échoue si `charger()` renvoie des données fictives alors que `DONNEES=local`. | `app/tests/test_donnees.py` (nouveau) | 10 min |
| 3 | **Remplir la section « 7. Limites »** de la documentation technique avec les 10 points du §3. | `docs/documentation_technique.md` | 20 min |
| 4 | **Écrire « en CAD »** dans les libellés de sortie des traces de rejeu, de volatilité et de pire fenêtre, et dans l'interface. | `app/src/outils/calculs.py` (texte des traces uniquement) | 15 min |
| 5 | **Vérifier l'exclusion de JNJ d'ESGV dans la liste complète** des titres, puis confirmer ou corriger `esg_controverses.csv` et `sources_added.csv`. Relancer ensuite `02_construire_esg.py`. | `data/raw/added/` (nouvelle version), `data/sources/sources_added.csv` | 20 min (manuel) |
| 6 | **Traçabilité par ligne d'`esg_etf_holdings.csv`** : ajouter les colonnes `fnb` et `date_donnees`. | `data/raw/added/esg_etf_holdings.csv`, `02_construire_esg.py` (lecture inchangée) | 10 min |
| 7 | **Compléter `decisions.md`** : l'ampleur mesurée de l'artefact CNQ, l'effet des fériés sur les calculs quotidiens, les séries macro copiées mais non utilisées. Mettre aussi à jour le commentaire « à vérifier » de `01_nettoyer_prix.py`. | `docs/decisions.md`, `data/scripts/01_nettoyer_prix.py` (commentaire seulement) | 10 min |
| 8 | *(Optionnel)* **Utiliser les taux à 10 ans** (BD.CDN.10YR, DGS10) dans le contexte de 2022 pour expliquer la baisse simultanée des obligations, ou retirer ces séries de `macro_quotidien.csv`. | `app/src/outils/calculs.py`, `app/config/calcul.yaml` | 30 min |

Aucune correction ne touche aux seuils, aux règles ni aux fichiers de `data/raw/starter/`.
**En attente de votre accord** avant toute modification.
