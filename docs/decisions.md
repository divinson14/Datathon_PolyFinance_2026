# Décisions et hypothèses

Notez ici chaque choix au fil de l'eau : c'est la moitié de la documentation technique.

## Formats d'échange (figés à H0)
- **Mandat** : persona (`app/config/personas/*.json`) + gabarit (`app/config/gabarits_risque.yaml`) + demande extraite `{symbole, part}`.
- **Trace** : `{id, session, horodatage, titre, agent, outil, entrees, sortie, source, periode}`.
- **Verdict** : `{trace, regles: [{regle, limite, valeur, ok}], violees, consigne}`.
- **Réponse** : `{intro, lignes: [{tag: Fait|Hypothèse|Scénario fictif, texte, traces}], limites, style}`.

## Méthode de calcul (app/config/calcul.yaml, app/src/outils/calculs.py)
- Prix : `adj_close` (dividendes et fractionnements déjà intégrés, ne rien réappliquer), convertis en CAD
  avec le taux Banque du Canada reporté sur les jours sans taux (fériés, fins de semaine crypto).
- Rendements **hebdomadaires** (clôture du vendredi), 261 semaines du 2021-11-19 au 2026-11-13 : neutralise
  les calendriers TSX / NYSE / crypto 7 j/7. Annualisation × 52.
- Portefeuille à **poids constants** (rééquilibré chaque semaine) pour volatilité, pire baisse et part du risque ;
  le rejeu 2022 est en achat-conservation (plus parlant en dollars). Les deux hypothèses sont affichées.
- **Part du risque** = contribution d'Euler à la variance : w_i·(Σw)_i / w'Σw (somme = 100 %).
- **Paris indépendants** = ratio de participation des valeurs propres de diag(w)·Σ·diag(w) : (Σλ)²/Σλ².
  N lignes indépendantes de même risque → N ; un seul facteur dominant → 1.
  ⚠️ Cette définition ne redonne pas le « 1,9 » de l'exploration (portefeuille Amira à parts égales : 2,6) : citer 2,6.
- **Point de bascule** : grille de 0 à 100 % par pas de 0,5 point ; part maximale de l'actif demandé (le reste
  du portefeuille est réduit proportionnellement) qui respecte toutes les règles, et première règle franchie.
- Macro : seules les séries **quotidiennes** sont copiées dans `processed/macro_quotidien.csv`. IPC et chômage
  (datés au mois de référence, publiés des semaines plus tard) sont exclus pour ne pas « voir le futur ».
- Correction des données : le report du taux de change se faisait sur la table longue (mélange possible entre symboles) ;
  il est maintenant fait sur le calendrier civil complet avant la fusion.
- CNQ.TO : faux « split » 1,021 le 2022-08-22 (probable distribution spéciale) déjà intégré par Yahoo dans `adj_close`. Effet ≈ 2 %, non corrigé, documenté.

## Seuils des gabarits (hypothèses de l'équipe, app/config/gabarits_risque.yaml)
« Titre » = action individuelle ou crypto. Les FNB diversifiés ne sont pas soumis aux limites par titre.

| Gabarit | Poids max/titre | Part du risque max/titre | Vol. max | Pire baisse max | Oblig. min | Crypto max | Paris min |
|---|---|---|---|---|---|---|---|
| Faible à modéré (Robert) | 10 % | 20 % | 8 % | -12 % | 40 % | 0 % | — |
| Modéré (Mateo) | 15 % | 25 % | 12 % | -20 % | 20 % | 0 % | — |
| Élevé (Amira) | 25 % | 30 % | 25 % | -45 % | 0 % | 10 % | 2,0 |

Justification à compléter (NT). Contrainte vérifiée par un test : chaque portefeuille supposé respecte son propre gabarit.

## Portefeuilles supposés (hypothèses affichées à l'utilisateur, mesures sur données réelles)
| Persona | Portefeuille | Vol. | Pire baisse | Paris indép. |
|---|---|---|---|---|
| Robert | XBB 30, ZST 30, XIU 15, SPY 15, FTS 5, GLD 5 | 5,2 % | -9,2 % | 2,5 |
| Mateo | ESGV 30, XIU 25, XBB 30, ZST 5, FTS 5, GLD 5 | 8,4 % | -14,3 % | 1,7 |
| Amira | XIU 15, SPY 20, QQQ 20, XBB 10, GLD 5, NVDA/SHOP/MSFT/JNJ 5 chacun, BTC 5, ETH 5 | 16,2 % | -30,2 % | 2,6 |

Points de bascule obtenus (TSLA) : Robert 3 %, Mateo 6 %, Amira 13 %. Règle limitante dans les trois cas : part du risque par titre.
Robert à 30 % TSLA : TSLA porte 89,5 % du risque. Crypto : bascule à 0 % pour Robert et Mateo (interdite) et pour Amira (déjà au plafond de 10 %).

## ESG (Mateo)
Sortie : `data/processed/esg_drapeaux.csv` (via `02_construire_esg.py`). Sources détaillées dans `data/sources/sources_added.csv`.

- **Titres détenus par des FNB ESG** (`raw/added/esg_etf_holdings.csv`) :
  - ESGV (Vanguard, données au 2026-11-12) pour les 10 actions américaines : relevé manuel des 40 premiers titres ;
    un titre absent de ce top 40 (poids < 0,35 %) est considéré comme exclu.
  - XESG (iShares, fichier de l'émetteur au 2026-10-02) pour les 10 actions canadiennes, car ESGV ne détient que des
    actions américaines. XESG n'est pas dans l'univers ; il sert seulement de référence. `dans_fnb_esg` = « dans ESGV ou XESG ».
- **Règle de controverse de l'équipe** (`raw/added/esg_controverses.csv`) : `oui` si secteur énergie (ENB.TO, CNQ.TO, XOM)
  ou exclusion observée d'ESGV hors énergie (JNJ) ; `non` sinon. Résultat : 4 `oui`, 16 `non`.
- **Ce qui n'est pas affirmé** : la raison de l'exclusion de JNJ n'est pas publiée par Vanguard et n'est pas devinée ;
  l'exclusion elle-même est déduite du top 40, pas vérifiée dans la liste complète.
- **Limites** :
  - règle simplifiée, sans revue détaillée par entreprise : elle ne capte pas les controverses sociales
    ou de gouvernance que les filtres ESGV/XESG ne reflètent pas ;
  - méthodologies d'émetteurs différentes : XESG pondère selon les notes MSCI sans exclure l'énergie ; ESGV exclut ;
  - instantané 2026 appliqué à toute la période (biais d'anticipation).
- **Conséquence pour Mateo** : TSLA est `non` (détenue par ESGV, hors énergie). Une évaluation ciblée de TSLA avec une
  source officielle datée reste une amélioration possible.
- Le moteur ne vérifie l'ESG que pour les titres individuels (actions, crypto). Les FNB et la crypto restent « non évalué » dans
  `esg_drapeaux.csv`. Un titre non évalué n'est **pas** déclaré conforme : il est signalé comme information manquante.

## Agent Profil (app/src/agents/profil.py, config/profil.yaml, config/alias_actifs.yaml)
- **Mandat JSON** = profil + gabarit + contraintes + horizon en années + informations manquantes + tensions + hypothèses + demande.
  Le profil vient d'un persona de référence OU de 5 champs saisis (âge, tolérance, horizon, objectif, ESG ; capital facultatif).
- **La tolérance au risque n'est jamais déduite** : si elle manque, l'agent s'arrête et la demande.
- **Tensions** entre champs (ex. tolérance élevée + horizon < 7 ans, seuils dans config/profil.yaml) : signalées dans
  l'interface et l'explication, jamais corrigées à la place de l'utilisateur. L'âge n'est volontairement pas utilisé dans une règle.
- Profil saisi : capital fictif par défaut et portefeuille supposé selon la tolérance, affichés comme hypothèses.
- **Extraction de la demande** : le LLM choisit l'actif et recopie l'extrait (« 30 % », « 50 000 $ ») ; le code vérifie que
  l'extrait est dans le message (contrôle d'ancrage) puis calcule la part. Un montant ≥ capital n'est pas une part.
  Plusieurs actifs cités ou part hors de 0–100 % → question à l'utilisateur. Deux traces : « Construction du mandat », « Extraction de la demande ».

## Agent Explicabilité (app/src/agents/explicabilite.py, prompts/explicabilite.md, config/garde_fous.yaml)
- **On décrit des limites, jamais de conseil** (énoncé : « ne pas se présenter comme fournissant un conseil
  financier personnalisé »). Ex. : « le point de bascule se situe à 3 % », jamais « mettez 3 % ».
- **Vérificateur de fidélité, deux contrôles en code pur** : (1) chaque chiffre du texte existe dans les traces ;
  (2) aucune expression de conseil (liste dans config/garde_fous.yaml). Échec → régénération stricte, puis gabarit sûr.
  Le contrôle s'applique aussi aux reformulations (« plus simple / plus technique »).
- **Synthétique** : 4 à 6 affirmations, dans l'ordre part des dollars vs part du risque, règles violées, point de bascule,
  rejeu 2022, hypothèse clé. « Fait » = ce qu'une trace dit explicitement ; aucun lien de cause inventé.
- **Courbe de bascule** : part du risque portée par l'actif selon son poids (grille de l'outil point_de_bascule, trace citée),
  limite du profil, point de bascule et demande. Image descriptive, aucune recommandation.
- Rédaction : Claude Sonnet 5.5 sur Bedrock, 4 000 jetons max (1 500 tronquait la réponse JSON). Tout échec Bedrock
  (identifiants expirés, réponse tronquée ou illisible) bascule sur le gabarit, avec le motif affiché.
- Testé sur Bedrock (Robert, TSLA 30 %) : 6 affirmations, 33/33 chiffres vérifiés, aucune formulation de conseil, ~24 s.

## Services AWS
| Service | Pourquoi |
|---|---|
| Bedrock | LLM des agents ; petit modèle pour l'extraction, modèle plus capable pour la rédaction |
| Bedrock Guardrails | Bloque transactions réelles et conseil personnalisé |
| S3 | Données propres produites par data/ |
| Lambda | Outils de calcul isolés, rôle IAM en lecture seule |
| DynamoDB | Journal d'audit des traces |

## Journal des choix
- AAAA-MM-JJ — choix — raison — qui
- 2026-11-14 — Sens du taux USD/CAD vérifié : `usdcad` varie de 1,245 à 1,460, donc CAD pour 1 USD ; les prix en USD
  sont multipliés par ce taux, sans inversion — conforme à `sources_metadata.csv` (série FXUSDCAD de la Banque du Canada) — P1
- 2026-11-14 — Trous dans les séries : report de la dernière valeur sur 3 jours de bourse au plus — les trous viennent
  des fériés propres à la TSX ou aux bourses américaines (27 jours par titre sur 5 ans) ; aucun trou plus long n'existe,
  donc aucune valeur inventée au-delà d'un congé — P1
- 2026-11-14 — Correction de `01_nettoyer_prix.py` : le report se fait maintenant APRÈS la réduction aux jours de bourse —
  avant, les fins de semaine (lignes crypto) comptaient dans la limite de 3 et les 13 titres `.TO` gardaient 3 trous
  (2021-12-28, 2022-12-27, 2023-12-26 : Noël TSX collé à un week-end). Résultat : 0 valeur manquante sur les 31 actifs — P1
