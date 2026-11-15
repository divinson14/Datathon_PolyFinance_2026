# AlphaForge AI
**On ne vous dit pas quoi acheter. On vous montre où votre décision cesse d'être cohérente avec vous.**

**Le problème.** Prudent, équilibré ou audacieux, tout investisseur raisonne en **dollars** : « je mets 30 % de mon
argent ici ». Or son portefeuille réagit au **risque**, et quelques lignes volatiles peuvent en porter l'essentiel.
Un retraité prudent qui cède à un titre médiatisé, un profil audacieux qui croit que « risque élevé » veut dire
« tout est permis », une personne attachée à l'ESG à qui l'on ne montre que le rendement : tous ont accès à l'information, mais
personne ne leur montre **l'écart entre la part de leurs dollars et la part de leur risque**, ni le point où leur
décision cesse d'être cohérente avec leur profil. Exemple : 30 % en Tesla dans un portefeuille prudent, c'est
**89,5 % du risque**.

**Notre réponse : le point de bascule.** Pour toute demande en langage courant (« je pense mettre 30 % dans
Tesla »), AlphaForge calcule **la part maximale compatible avec le profil** et la règle qui casse en premier.
Même question pour trois profils de l'énoncé : prudent (Robert) **3 %**, équilibré avec ESG (Mateo) **6 %**,
audacieux (Amira) **13 %**. Même moteur, trois limites, et jamais « tout est permis ».

**L'approche agentique (le code juge, le LLM comprend et rédige, le code vérifie).**
- **Agent Profil** (Claude Haiku) : construit le mandat ; ne déduit jamais la tolérance au risque ; signale ce qui manque.
- **Agent Analyste** (Claude Sonnet, agent Strands) : choisit ses outils de calcul ; tous les chiffres viennent des outils.
- **Agent Gouvernance** : le moteur de règles (code) juge le mandat ; le LLM formule le verdict et les tensions avec le profil.
- **Agent Explicabilité** (Claude Sonnet) : 4 à 6 affirmations étiquetées *Fait · Hypothèse · Scénario fictif*.
- **Vérificateur de fidélité** (code pur) : chaque chiffre du texte doit exister dans une trace, et aucune formulation
  de conseil n'est tolérée ; sinon la réponse est régénérée.

**Ce qui est original.** (1) Mesurer **la part du risque**, pas la part des dollars, et la montrer en une image : la
*courbe de bascule*. (2) **Zéro chiffre inventé, zéro conseil déguisé**, garantis par du code, pas par une consigne
au LLM. (3) **Un système qui ose dire non** : il nuance, il refuse, il relève les tensions (« entreprises établies »
contre une volatilité de 55,7 %), sans jamais céder à une hypothèse plus favorable.

**Données.** 31 actifs (actions canadiennes et américaines, FNB, obligations, or, cryptoactifs), 5 ans de prix
quotidiens (Yahoo Finance, prix ajustés), **tout en CAD** au taux de la Banque du Canada ; taux directeur
(Banque du Canada), sans jamais utiliser une donnée publiée après la date simulée. **ESG : version partielle**,
assumée : règle sectorielle et fonds ESG (ESGV, XESG), sans revue des controverses sociales ; ce qui n'est pas
évalué est signalé « à vérifier », jamais déclaré conforme.
Seuils des profils : hypothèses de l'équipe, affichées comme telles.

**Explicabilité vérifiable.** Chaque étape écrit une trace horodatée (entrées, sortie, source), stockée dans
**Amazon DynamoDB** : chaque chiffre de la réponse renvoie à son calcul, consultable en un clic.

**Sur AWS.** Amazon Bedrock (Claude Haiku et Sonnet, Strands) · **Bedrock Guardrails** (aucune transaction réelle,
aucun conseil personnalisé, en entrée et en sortie) · Amazon S3 (données) · Amazon DynamoDB (journal d'audit) ·
AWS Lambda (outils de calcul). <!-- ÉQUIPE : confirmer que la fonction Lambda est déployée, sinon retirer. -->

**Le bénéfice.** Pour l'investisseur : comprendre en dix secondes *pourquoi* une idée ne lui convient pas, et
jusqu'où elle lui conviendrait. Pour la banque : une analyse de **convenance** expliquée, tracée et auditable,
prête à être partagée par un conseiller.

**Et ensuite ?** Plusieurs portefeuilles et plusieurs actifs dans une même demande, un horizon qui ajuste les limites
(« et si mon horizon était de 10 ans ? »), une marge d'incertitude sur le point de bascule, un mode conseiller…
La suite, nous aimerions la construire avec vous.

<sub>Simulation éducative sur des profils fictifs ; aucune transaction réelle, aucun conseil financier personnalisé.
Les performances passées ne prédisent pas les résultats futurs.</sub>
