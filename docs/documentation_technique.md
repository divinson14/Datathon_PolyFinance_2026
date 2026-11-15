# Documentation technique — AlphaForge AI
Datathon PolyFinances 2026 · Banque Nationale × AWS · défi « AlphaForge AI »

> Simulation éducative sur des profils fictifs : aucune transaction réelle, aucun conseil financier personnalisé.
> Détail des choix au fil de l'eau : [`decisions.md`](decisions.md) · audit des données : [`audit_donnees.md`](audit_donnees.md).

## 1. Problème choisi
**Les investisseurs raisonnent en dollars ; leur portefeuille réagit au risque.** Une demande banale — « je pense
mettre 30 % dans Tesla » — peut faire porter à un seul titre l'essentiel des variations d'un portefeuille, sans que la
personne le voie, et sans qu'elle sache à partir de quand sa décision cesse d'être cohérente avec son profil.

**Question que l'outil éclaire :** *jusqu'où une demande d'investissement reste-t-elle cohérente avec le profil de la
personne, et quelle règle cède en premier ?* AlphaForge ne recommande aucun placement : il calcule la **part du risque**
portée par l'actif demandé et le **point de bascule** (part maximale compatible avec le profil), puis l'explique.

**Les trois personas de l'énoncé, traités sans code spécifique** (même moteur, autres limites) :

| Persona | Ce qu'il met à l'épreuve | Réponse du système (TSLA, données réelles) |
|---|---|---|
| Robert, faible à modéré, 3 à 5 ans | Remettre en question une demande médiatisée | 30 % demandés = **89,5 % du risque** ; point de bascule **3 %** ; tension avec « entreprises établies » |
| Amira, élevé, 15 ans et plus | « Risque élevé » ≠ « tout est permis » | Point de bascule **13 %** ; limites par titre et nombre de paris indépendants |
| Mateo, modéré, préférences ESG | Intégrer autre chose que rendement et risque | Point de bascule **6 %** ; exclusions ESG (Exxon : aucune part compatible) ; manques ESG signalés |

## 2. Architecture agentique
**Principe : le code juge et calcule, le LLM comprend et rédige, le code vérifie ce que le LLM a écrit.**
Schéma : [`architecture.svg`](architecture.svg). Un orchestrateur déterministe (`app/src/orchestrateur.py`) enchaîne :

| Étape | Rôle | Décide | Rôle du LLM |
|---|---|---|---|
| **Garde-fous d'entrée** | Refuser les ordres réels, détecter les sujets sensibles | Règle en code (ordres réels) + **Bedrock Guardrails** (détection) | — |
| **Agent Profil** | Construire le **mandat JSON** (profil, limites, contraintes, tensions, informations manquantes) et extraire la demande {actif, part} ; mémoire de conversation minimale (4 règles) | Code : la tolérance n'est jamais déduite ; la part est calculée par le code | Claude Haiku reconnaît l'actif (« nvdia », « le constructeur d'Elon Musk ») et **recopie** l'extrait « 30 % » ; le code vérifie qu'il figure dans le message |
| **Agent Analyste** | Mesurer le risque de la demande | Les **outils de calcul** produisent tous les chiffres (AWS Lambda) | Claude Sonnet, agent **Strands** : choisit ses outils (dont un stress-test sur 12 mois) ; son commentaire est vérifié avant affichage |
| **Agent Gouvernance** | Juger la demande contre le mandat : *conforme*, *corrigeable* ou *impossible* ; tensions avec le profil | **Moteur de règles** (code pur) ; le statut ne vient jamais du LLM | Claude Sonnet formule le verdict ; chiffres et formulations vérifiés, sinon texte déterministe |
| **Boucle de correction** | Si *corrigeable* : « teste au point de bascule » → l'Analyste recalcule → la Gouvernance revérifie (3 tentatives max) | Code | — |
| **Agent Explicabilité** | 4 à 6 affirmations étiquetées *Fait · Hypothèse · Scénario fictif*, chacune reliée à ses traces | — | Claude Sonnet rédige à partir des traces seulement |
| **Vérificateur de fidélité** + Guardrails de sortie | Chaque chiffre doit exister dans une trace ; aucune formulation de conseil ; Bedrock Guardrails sur le texte affiché | **Code pur** | — ; échec → régénération stricte, puis gabarit sûr |

**Pourquoi des agents et pas un seul prompt :** chaque étape a un contrat d'entrée-sortie vérifiable et une trace ; un
échec est localisé (et rattrapé) au lieu de contaminer toute la réponse. **Points de contrôle :** garde-fous d'entrée,
contrôle d'ancrage de la part, statut calculé par le code, vérification indépendante de chaque alternative,
vérificateur de fidélité, Guardrails de sortie. **Robustesse :** toute panne d'AWS (identifiants expirés, modèle
refusé, réponse tronquée) bascule sur un repli déterministe affiché ; une trace n'est jamais perdue.

## 3. Données
| Source | Contenu retenu | Traitement |
|---|---|---|
| Jeu de départ (Yahoo Finance via yfinance) | **31 actifs** : 10 actions canadiennes, 10 américaines, 9 FNB (actions, obligations, or, ESG), BTC, ETH ; 2021-11-12 → 2026-11-12 | Clôture **ajustée** (dividendes, fractionnements) ; calendrier TSX + NYSE ; crypto ramenée aux jours de bourse |
| Banque du Canada (Valet) | USD/CAD quotidien, taux directeur (V39079) | **Tout est converti en CAD** (taux du jour, reporté les jours fériés) |
| FRED, Banque du Canada | Taux et indicateurs | Séries **quotidiennes** seulement : IPC et chômage exclus (publiés après la date de référence) |
| Ajouts de l'équipe | Drapeaux ESG : règle sectorielle (énergie = controverse) + présence dans ESGV / XESG, avec motif, source et date | `data/sources/sources_added.csv` |

**Reproductibilité :** `data/scripts/01` à `04` régénèrent `data/processed/` ; un **manifeste** (empreintes SHA-256, version)
est vérifié à chaque lecture, et la version figure dans chaque trace. Les données sont lues depuis **Amazon S3** (bucket
privé et chiffré) ou en local. **Hypothèses affichées à l'utilisateur :** seuils des profils
(`app/config/gabarits_risque.yaml`), portefeuille de départ supposé de chaque persona, poids constants.

## 4. Méthodes et technologies
**Calculs (code pur, `app/src/outils/calculs.py`)** — rendements **hebdomadaires** en CAD (261 semaines, annualisation × 52) :
- **Volatilité annualisée** et **pire baisse** (du sommet au creux) d'un portefeuille à poids constants.
- **Part du risque** d'une ligne = contribution d'Euler à la variance : w_i·(Σw)_i / w′Σw (somme = 100 %).
- **Paris indépendants** = ratio de participation des valeurs propres de diag(w)·Σ·diag(w) : (Σλ)² / Σλ².
- **Point de bascule** : la part demandée balaie une grille de 0 à 100 % par pas de 0,5 point (le reste du portefeuille
  est réduit proportionnellement) ; à chaque pas, le moteur de règles évalue toutes les limites ; on retient la dernière
  part conforme et la première règle franchie. La même grille dessine la **courbe de bascule**.
- **Scénarios :** rejeu 2022 (achat-conservation, valeur mensuelle) ; pire fenêtre glissante de 12 mois ; contexte du
  taux directeur 2022 (7 hausses, de 0,25 % à 4,25 %).

**Moteur de règles (`app/src/regles/moteur.py`, sans LLM)** : poids max et part du risque max par titre (actions, crypto),
volatilité max, pire baisse max, obligations min, crypto max, paris indépendants min (profil élevé), exclusions ESG
(Mateo). Une donnée non évaluée est une **information manquante**, jamais une conformité.

**Technologies et justification**

| Choix | Pourquoi |
|---|---|
| **Amazon Bedrock** · Claude Haiku 5.5 (Profil) | Tâche courte (repérer un actif) : rapide et peu coûteux |
| Claude Sonnet 5.5 (Analyste, Gouvernance, Explicabilité) | Rédaction fidèle aux chiffres recopiés ; appel d'outils fiable |
| **Strands Agents** (SDK AWS) | L'Analyste choisit ses outils au lieu d'un plan figé, avec repli sur un plan fixe |
| **Bedrock Guardrails** | Filet AWS : détection en entrée, blocage en sortie (transactions réelles, promesses de rendement) |
| **AWS Lambda** (Function URL, IAM) | Outils de calcul isolés, appelés par requête signée |
| **Amazon S3** | Une source de données partagée, privée et chiffrée |
| **Amazon DynamoDB** | Journal d'audit : une trace par calcul, verdict et vérification, consultable après coup |
| **Streamlit** | Interface en Python : profils, conversation, coulisses des agents en direct, courbe de bascule |

## 5. Mécanisme d'explicabilité
Chaque étape écrit une **trace** `{id, session, horodatage, titre, agent, outil, entrées, sortie, source, période}` dans
DynamoDB. L'Agent Explicabilité ne peut citer que ces traces ; le **vérificateur** contrôle chaque chiffre et l'absence
de conseil ; l'interface affiche les étiquettes *Fait / Hypothèse / Scénario fictif*, les identifiants de trace, les
coulisses des agents, le journal complet et le mandat JSON.

**Exemple réel, de la conclusion aux données** (Robert : « Tout le monde parle de Tesla, je pense mettre 30 % dedans »)

1. **La phrase affichée** — *Fait* : « Point de bascule : jusqu'à 3 % de TSLA, toutes les règles sont respectées ;
   à 3,5 %, la première règle franchie est « part du risque max par titre ». » → trace **T-07**
2. **La trace T-07** — outil `point_de_bascule(base, "TSLA", gabarit)` · agent : Analyste
   - entrées : base XBB.TO 30 % · ZST.TO 30 % · XIU.TO 15 % · SPY 15 % · FTS.TO 5 % · GLD 5 % ; grille de 0 à 100 % par
     pas de 0,5 % ; gabarit « Faible à modéré »
   - sortie : point de bascule 3 % ; première règle franchie à 3,5 % (part du risque max par titre) ; autres seuils :
     volatilité à 9 %, pire baisse à 9 %, poids max à 10,5 %, obligations min à 33,5 % ; 201 points calculés
   - période : 2021-11-19 → 2026-11-13, 261 semaines
3. **Les données** — `prix_cad_alignes.csv` (clôture ajustée, en CAD), **version ae9492861959, empreintes vérifiées**,
   et la limite de 20 % lue dans `config/gabarits_risque.yaml`.
4. **Le contrôle** — trace « Vérification de fidélité » : **53/53 chiffres retrouvés dans les traces · 0 formulation
   de conseil**.

Même chaîne pour « TSLA représenterait 30 % du capital mais **89,5 % du risque** » → trace T-03,
`analyse_portefeuille(poids)` : TSLA 89,5 %, SPY 5,3 %, XIU.TO 3,3 %… ; volatilité 18,4 % ; pire baisse −28,1 %.
Une analyse complète produit 14 traces (mandat, extraction, mesures, point de bascule, rejeux, verdicts, alternative,
vérification), toutes visibles dans l'interface.

## 6. Validation
- **Tests unitaires** : `cd app && pytest tests/` → **180 tests** (calculs, règles, Profil, mémoire, Analyste,
  Gouvernance, Explicabilité, Guardrails, journal, Lambda, données). Ils vérifient notamment que la part du risque somme
  à 100 %, qu'à la part du point de bascule toutes les règles passent et qu'un pas plus loin l'une d'elles casse, qu'un
  chiffre inventé ou une formulation de conseil est rejeté, et que chaque portefeuille supposé respecte son propre profil.
- **Scénarios piégés** (`python tests/lancer_scenarios.py`) : **14/14 conformes**.

  | Scénario | Comportement attendu et obtenu |
  |---|---|
  | Robert / Amira veulent 30 % dans Tesla | 4 / 3 règles violées, correction au point de bascule |
  | Robert veut 3 % dans Tesla (sous le point de bascule) | 0 règle violée |
  | Robert veut 5 % de Bitcoin | crypto interdite : aucune part compatible, dit honnêtement |
  | Mateo : 10 % de Tesla / 5 % d'Exxon | part du risque bloquante / controverse ESG, aucune part compatible |
  | « 50 000 $ dans Tesla » (Robert, 200 000 $) | converti en 25 % par le code |
  | Demande de transaction réelle | bloquée par le garde-fou |
  | Part manquante, actif inconnu, deux actifs, 150 % | l'agent pose une question au lieu de deviner |
  | Profil saisi sans tolérance / élevé avec 3 ans d'horizon | tolérance demandée / tension signalée |

- **Sur Amazon Bedrock** : `tests/tester_profil.py --bedrock` → **9/9** (dont « le constructeur de voitures électriques
  d'Elon Musk » → TSLA) ; parcours complet Robert/TSLA → **6 affirmations, 33/33 chiffres vérifiés, aucun conseil**.
- **Guardrails** : `tests/test_guardrails.py` (15 ordres réels bloqués, 9 simulations admises) et
  `tests/verifier_guardrail.py` (faux positifs mesurés sur le vrai guardrail, puis corrigés).
- **Données** : `tests/verifier_donnees.py` et l'audit du 2026-11-14 (aucun point bloquant, 0 valeur manquante).

## 7. Limites et améliorations

Détail et chiffres de contrôle : `docs/audit_donnees.md` (audit du 2026-11-14).

### Limites des données
1. **Biais de survie.** L'univers a été choisi en 2026 parmi des titres importants aujourd'hui : un rejeu depuis 2021 paraît
   meilleur que ce qu'aurait donné une sélection faite en 2021.
2. **Mesures en dollars canadiens (CAD).** Tous les montants, rendements et volatilités incluent l'effet de change USD/CAD
   (taux quotidien de la Banque du Canada). En 2022, la hausse du dollar américain a réduit d'environ 5 à 6 points les pertes
   des actifs américains (SPY : −18,2 % en USD, −12,6 % en CAD). Les traces, l'explication et l'interface le précisent.
3. **Rendement total brut.** `adj_close` réinvestit 100 % des dividendes : ni retenue à la source américaine (15 % pour un
   résident canadien hors REER), ni frais de gestion des FNB, ni frais de transaction, ni impôt.
4. **Données Yahoo Finance non certifiées.** Les valeurs ajustées changent si l'on retélécharge. Artefact connu : faux
   « split » 1,021 de CNQ.TO le 2022-08-22 (≈ 1 point de rendement sur ce jour), non corrigé.
5. **Calendriers.** Union TSX + NYSE, report de la dernière valeur sur 2 jours de bourse au plus (fériés). La crypto est
   ramenée aux jours de bourse ; son prix est la clôture du jour UTC, celui des actions la clôture de 16 h HE (décalage de
   quelques heures). Les mesures de risque sont hebdomadaires (vendredi), ce qui neutralise les fériés.
6. **Historique court.** Cinq ans (261 semaines) dominés par un seul cycle de hausse des taux (2022) : corrélations et
   volatilités estimées instables ; la pire baisse dépend de cet échantillon.
7. **Macro.** Seul le taux directeur de la Banque du Canada (V39079) est utilisé. L'IPC et le chômage sont exclus à cause de
   leur délai de publication. Les taux à 2 et 10 ans (Canada, É.-U.) et le taux des fonds fédéraux sont préparés mais pas
   encore exploités (amélioration possible : expliquer la baisse simultanée des obligations en 2022). Les séries FRED sont
   dans leur dernière version (révisées).
8. **Méthodologie ESG.** Ce n'est pas une note ESG : présence dans un FNB ESG (ESGV pour les É.-U., XESG pour le Canada,
   méthodes différentes : ESGV exclut l'énergie, XESG pondère sans exclure) + règle sectorielle de l'équipe (énergie =
   controverse). JNJ est « non évalué » : son exclusion d'ESGV n'a pas pu être vérifiée dans la liste complète du fonds. Pas de revue des
   controverses sociales ou de gouvernance. Instantané 2026 appliqué à toute la période (biais d'anticipation). FNB et
   crypto : statuts `conforme` (ESGV), `non applicable` (obligations, or, neutre) ou `non évalué` (traité comme
   information manquante, jamais comme conformité). La règle couvre tous les actifs détenus, FNB compris : pour Mateo,
   XIU.TO (portefeuille supposé, contient de l'énergie) apparaît toujours en information manquante.
9. **Portefeuilles supposés.** Les compositions par persona sont des hypothèses de l'équipe, pas des données de clients.
10. **Données fictives de démonstration.** Si `data/processed/` est absent, l'application utilise une série simulée
    (`chargeur._demo`), réservée au développement : un bandeau rouge l'annonce dans l'interface, l'explication le répète
    et `tests/test_donnees.py` échoue en mode `DONNEES=local`.

### Améliorations possibles
- Exploiter les taux à 10 ans (BD.CDN.10YR.DQ.YLD, DGS10) dans le contexte 2022.
- Vérifier JNJ dans la liste complète des titres d'ESGV ; évaluer TSLA avec une source ESG officielle datée.
- Évaluer les FNB (composition) pour la règle ESG plutôt que « non évalué ».

### Limites de la solution
- **Une demande, un actif à la fois** ; la mémoire de conversation complète une demande à moitié donnée, sans plus.
- **L'horizon n'ajuste pas encore les limites** : il sert aux tensions et aux explications.
- **Latence** : environ 25 s pour un parcours complet sur Bedrock (agents successifs).
- **Le vérificateur contrôle les chiffres et les formulations, pas le sens** : une interprétation reste possible ;
  le prompt l'interdit et les étiquettes la rendent visible.

### Améliorations envisagées
- **Agent Auditeur** : relire la réponse finale (cohérence du verdict, « Fait » réellement dit par sa trace, aucun lien
  de cause inventé). Le code continue de bloquer ; l'Auditeur signale.
- Horizon qui ajuste la pire baisse tolérée, avec un sélecteur « Et si… » ; plusieurs actifs dans une même demande.
- Marge d'incertitude du point de bascule (recalculé sur plusieurs sous-périodes).
- ESG : évaluation des FNB titre par titre et source de controverses datée.

