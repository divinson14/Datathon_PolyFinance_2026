# InvestIA
**On ne vous dit pas quoi acheter. On vous montre jusqu'où votre décision reste cohérente avec vous.**

**Le problème.** On pense en dollars, mais un portefeuille réagit au risque. Mettre une part de son argent dans un
titre très volatil, c'est souvent lui confier la plus grande partie des hauts et des bas de tout son portefeuille :
pour un investisseur prudent, **30 % en Tesla, c'est près de 90 % du risque**. Prudent, équilibré ou audacieux,
personne ne voit cet écart, ni le moment où sa décision ne lui correspond plus.

**Notre solution.** On pose sa question comme à une personne : « Je pense mettre 30 % dans Tesla ». InvestIA répond
en quelques secondes : est-ce cohérent avec mon profil ? Sinon, **jusqu'où ça le serait** (le *point de bascule*) et
quelle limite casse en premier. Même question, trois profils : prudent **3 %**, équilibré **6 %**, audacieux **13 %**.

**Comment ça marche : 4 agents IA et un vérificateur.**
- **Profil** : comprend la question et le profil ; ne devine jamais une information manquante, il la demande.
- **Analyste** : fait les calculs. Les chiffres viennent toujours des calculs, jamais de l'IA.
- **Gouvernance** : compare la demande aux limites du profil et ose dire non, même à un profil audacieux.
- **Explicabilité** : explique en langage simple, en séparant les faits, les hypothèses et les scénarios.
- **Vérificateur** : relit chaque réponse. Un chiffre qui ne vient pas d'un calcul, ou un conseil déguisé, et la
  réponse est réécrite.

**Ce qui est original.**
- On mesure **la part du risque**, pas la part des dollars, et on la montre en une image : la courbe de bascule.
- **Aucun chiffre inventé, aucun conseil** : ce n'est pas une promesse, c'est vérifié automatiquement à chaque réponse.
- Un assistant qui sait **dire non** et explique pourquoi, au lieu d'approuver la demande.

**Les données.** 31 placements (actions canadiennes et américaines, fonds indiciels, obligations, or,
cryptomonnaies), 5 ans de prix réels (Yahoo Finance), tout converti en **dollars canadiens** au taux de la Banque du
Canada, sans jamais utiliser une information publiée plus tard. **ESG : version partielle**, assumée : une règle
simple (secteur de l'énergie) et les fonds ESG ; ce qui n'est pas évalué est marqué « à vérifier », jamais
« conforme ». Les limites de chaque profil sont des hypothèses de l'équipe, affichées comme telles.

**Chaque réponse se justifie.** Chaque chiffre a sa preuve : un clic montre le calcul, les données utilisées et leur
source. Tout est enregistré sur AWS (Amazon DynamoDB), consultable après coup.

**Sur AWS.** Amazon Bedrock (modèles Claude) pour les agents · Bedrock Guardrails pour bloquer les transactions
réelles et les promesses de rendement · AWS Lambda pour les calculs · Amazon S3 pour les données · Amazon DynamoDB
pour l'historique des preuves.

**Le bénéfice.** Pour l'investisseur : comprendre en dix secondes **pourquoi** une idée ne lui convient pas, et
**jusqu'où** elle lui conviendrait. Pour la banque : une vérification de convenance expliquée et traçable, qu'un
conseiller peut partager telle quelle.

**Et ensuite ?** Plusieurs placements dans une même question, un horizon de placement qui ajuste les limites
(« et sur 10 ans ? »), un agent qui relit le sens des réponses, un mode conseiller… La suite, nous aimerions la
construire avec vous.

<sub>Simulation éducative sur des profils fictifs : aucune transaction réelle, aucun conseil financier personnalisé.
Les performances passées ne prédisent pas les résultats futurs.</sub>
