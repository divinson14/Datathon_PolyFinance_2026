import React, { useEffect, useMemo, useRef, useState } from "react";

/* =====================================================================
   AlphaForge AI — prototype React (données FICTIVES de démonstration)
   Le pipeline reproduit l'architecture :
   Guardrails → Agent Profil → Agent Analyste (outils) → Agent Gouvernance
   (moteur de règles + boucle, max 3 tentatives) → Agent Explicabilité
   → Vérificateur de fidélité. Chaque appel d'outil écrit une trace.
   Les "agents" sont simulés par du code ; dans le vrai projet, ils
   appellent Amazon Bedrock et les outils tournent dans Lambda.
   ===================================================================== */

/* ---------- 1. Données de démonstration (remplacer par prices_daily.csv) ---------- */
const MOIS = ["début", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

// Indices de prix fictifs 2022, déjà convertis en CAD (1 = valeur au 1er janvier)
const SERIES_2022 = {
  TSLA: [1, 0.8, 0.92, 0.78, 0.62, 0.56, 0.7, 0.74, 0.62, 0.55, 0.47, 0.42, 0.36],
  XIU: [1, 1.0, 1.02, 0.97, 0.98, 0.89, 0.94, 0.92, 0.88, 0.93, 0.98, 0.97, 0.94],
  XBB: [1, 0.97, 0.94, 0.91, 0.91, 0.89, 0.92, 0.89, 0.86, 0.85, 0.88, 0.89, 0.88],
};

const ACTIFS = {
  TSLA: { nom: "Tesla", classe: "Action américaine", vol: 0.55, crypto: false },
  XIU: { nom: "FNB actions canadiennes (ex.)", classe: "FNB actions", vol: 0.12, crypto: false },
  XBB: { nom: "FNB obligations canadiennes (ex.)", classe: "FNB obligations", vol: 0.06, crypto: false },
};

const CORRELATIONS = { "TSLA|XIU": 0.45, "TSLA|XBB": 0.1, "XIU|XBB": 0.3 };

/* ---------- 2. Configuration fixée par l'équipe (jamais par le LLM) ---------- */
const GABARITS = {
  faible_a_modere: { label: "Faible à modéré", poidsMax: 0.05, volMax: 0.1, perteMax: -0.15, cryptoMax: 0 },
  modere: { label: "Modéré", poidsMax: 0.1, volMax: 0.15, perteMax: -0.25, cryptoMax: 0 },
  eleve: { label: "Élevé", poidsMax: 0.15, volMax: 0.25, perteMax: -0.35, cryptoMax: 0.1 },
};

const PERSONAS = {
  robert: {
    id: "robert", nom: "Robert", age: 59, risque: "faible_a_modere", horizon: "3 à 5 ans",
    capital: 200000, experience: "Avancée", style: "avance", metier: "Professionnel de la santé",
    objectif: "Préserver son capital tout en gardant un potentiel de croissance",
    preferences: ["Entreprises établies et bien comprises", "Stabilité et qualité", "Peu intéressé par les cryptoactifs"],
    base: { XIU: 0.6, XBB: 0.4 }, baseLabel: "60 % actions / 40 % obligations",
    resume: "Faible à modéré · 3 à 5 ans · retraite proche",
    message: "J'ai 200 000 $ de côté pour ma retraite. Tout le monde parle de Tesla, je pense mettre 30 % dedans. Bonne idée ?",
    contexte: {
      avance: (perte) => `Les seuils viennent du gabarit fixé par l'équipe. Avec un horizon de 3 à 5 ans, une perte de ${perte} laisse peu de temps pour récupérer avant la retraite.`,
      inter: () => "Tu prévois ta retraite dans 3 à 5 ans : après une grosse baisse, tu aurais peu de temps pour te refaire. Les limites de ton profil sont un choix documenté de l'équipe.",
    },
  },
  amira: {
    id: "amira", nom: "Amira", age: 26, risque: "eleve", horizon: "15 ans et plus",
    capital: 50000, experience: "Intermédiaire", style: "inter", metier: "Ingénieure logicielle",
    objectif: "Faire croître son capital à long terme",
    preferences: ["IA et technologies émergentes", "Ouverte à une forte volatilité", "Veut rester diversifiée"],
    base: { XIU: 0.8, XBB: 0.2 }, baseLabel: "80 % actions / 20 % obligations",
    resume: "Risque élevé · 15 ans et plus",
    message: "Je crois beaucoup à Tesla et aux technologies émergentes. Je pense mettre 30 % de mon portefeuille dedans.",
    contexte: {
      avance: () => "Les seuils viennent du gabarit fixé par l'équipe. Un horizon de 15 ans et plus tolère la volatilité, mais concentrer une grande part sur un seul titre réduit la diversification.",
      inter: () => "Avec 15 ans devant toi, tu peux encaisser des hauts et des bas. Mais mettre une grosse part sur une seule entreprise, c'est miser beaucoup sur un seul cheval : « risque élevé » ne veut pas dire « tout est acceptable ».",
    },
  },
  mateo: {
    id: "mateo", nom: "Mateo", age: 41, resume: "Risque modéré · 8 à 12 ans · ESG", disabled: true,
    metier: "Gestionnaire des opérations", horizon: "8 à 12 ans", objectif: "Croissance équilibrée à moyen et long terme",
    preferences: ["Critères ESG importants", "Évite les controverses", "Peu de placements spéculatifs"],
  },
};

/* ---------- 3. Formatage et utilitaires ---------- */
const sep = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const money = (x) => (x < 0 ? "-" : "") + sep(Math.abs(Math.round(x / 100) * 100)) + " $";
const pct = (x, d = 1) => {
  let s = (x * 100).toFixed(d).replace(".", ",");
  if (s.endsWith(",0")) s = s.slice(0, -2);
  if (s === "-0") s = "0";
  return s + " %";
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- 4. Journal d'audit (DynamoDB dans le vrai projet) ---------- */
function creerJournal() {
  const traces = [];
  return {
    traces,
    log(t) {
      const id = "T-" + String(traces.length + 1).padStart(2, "0");
      traces.push({ id, ...t });
      return id;
    },
  };
}

/* ---------- 5. Outils déterministes (Lambda dans le vrai projet) ---------- */
function poidsAvecPosition(base, actif, w) {
  const out = {};
  Object.entries(base).forEach(([k, v]) => (out[k] = v * (1 - w)));
  out[actif] = (out[actif] || 0) + w;
  return out;
}
const poidsTexte = (p) => Object.entries(p).filter(([, v]) => v > 0.0001).map(([k, v]) => `${k} ${pct(v)}`).join(" · ");

function outilStatistiques(journal, actif) {
  const s = SERIES_2022[actif];
  let pic = s[0], pire = 0;
  s.forEach((v) => { pic = Math.max(pic, v); pire = Math.min(pire, v / pic - 1); });
  const res = { vol: ACTIFS[actif].vol, pireBaisse: pire };
  const id = journal.log({
    titre: `Profil de risque · ${actif}`, agent: "Agent Analyste", outil: `statistiques(actif="${actif}")`,
    entrees: `actif : ${actif} · devise : CAD`,
    sortie: `volatilité annualisée : ${pct(res.vol)} · pire baisse 2022 : ${pct(res.pireBaisse)}`,
    source: "prices_daily.csv (clôture ajustée) · fx_usdcad_daily.csv", periode: "2022 (données de démonstration)",
  });
  return { id, ...res };
}

function outilContexteMacro(journal) {
  const id = journal.log({
    titre: "Contexte des taux en 2022", agent: "Agent Analyste", outil: 'contexte_macro(serie="taux_directeur_canada")',
    entrees: "série : taux directeur de la Banque du Canada",
    sortie: "1re hausse le 2022-03-02 : 0,25 % → 0,50 %",
    source: "macro_rates.csv (Banque du Canada)", periode: "2022-01-01 → 2022-12-31",
  });
  return { id };
}

function outilRejeu2022(journal, poids, capital, libelle, agent) {
  const valeurs = MOIS.map((_, i) => Object.entries(poids).reduce((acc, [k, w]) => acc + w * SERIES_2022[k][i] * capital, 0));
  const final = valeurs[valeurs.length - 1];
  const rend = final / capital - 1;
  const id = journal.log({
    titre: `Rejeu 2022 · ${libelle}`, agent, outil: "rejeu_2022(poids, capital)",
    entrees: `${poidsTexte(poids)} · capital ${money(capital)}`,
    sortie: `rendement ${pct(rend)} · perte ${money(final - capital)} · valeur finale ${money(final)}`,
    source: "prices_daily.csv (clôture ajustée) · fx_usdcad_daily.csv", periode: "2022-01-03 → 2022-12-30",
  });
  return { id, valeurs, final, rend, perte: final - capital };
}

function outilVolatilite(journal, poids, libelle, agent) {
  const k = Object.keys(poids);
  let variance = 0;
  k.forEach((a) => k.forEach((b) => {
    const rho = a === b ? 1 : CORRELATIONS[`${a}|${b}`] ?? CORRELATIONS[`${b}|${a}`] ?? 0;
    variance += poids[a] * poids[b] * ACTIFS[a].vol * ACTIFS[b].vol * rho;
  }));
  const vol = Math.sqrt(variance);
  const id = journal.log({
    titre: `Volatilité · ${libelle}`, agent, outil: "volatilite_portefeuille(poids)",
    entrees: poidsTexte(poids), sortie: `volatilité annualisée : ${pct(vol)}`,
    source: "prices_daily.csv (rendements quotidiens)", periode: "5 ans (données de démonstration)",
  });
  return { id, vol };
}

/* ---------- 6. Moteur de règles (Python déterministe dans le vrai projet) ---------- */
function moteurDeRegles(journal, poids, actif, rejeu, tVol, g, libelle) {
  const vol = tVol.vol;
  const crypto = Object.entries(poids).filter(([a]) => ACTIFS[a].crypto).reduce((s, [, w]) => s + w, 0);
  const regles = [
    { regle: "Poids max par titre", limite: pct(g.poidsMax), valeur: pct(poids[actif]), ok: poids[actif] <= g.poidsMax + 1e-9 },
    { regle: "Volatilité du portefeuille", limite: "≤ " + pct(g.volMax), valeur: pct(vol), ok: vol <= g.volMax + 1e-9 },
    { regle: "Perte en 2022", limite: "≥ " + pct(g.perteMax), valeur: pct(rejeu.rend), ok: rejeu.rend >= g.perteMax - 1e-9 },
    { regle: "Cryptoactifs", limite: "≤ " + pct(g.cryptoMax), valeur: pct(crypto), ok: crypto <= g.cryptoMax + 1e-9 },
  ];
  const violees = regles.filter((r) => !r.ok);
  const id = journal.log({
    titre: `Verdicts · ${libelle}`, agent: "Agent Gouvernance (moteur de règles, sans LLM)", outil: "verifier_mandat(allocation, gabarit)",
    entrees: `${poidsTexte(poids)} · gabarit « ${g.label} »`,
    sortie: violees.length ? `${violees.length} règle(s) violée(s) : ${violees.map((r) => `${r.regle} (${r.valeur} vs ${r.limite})`).join(", ")}` : `${regles.length} règles sur ${regles.length} respectées`,
    source: "config/gabarits_risque.yaml", periode: "exécution courante",
  });
  return { id, regles, violees };
}

/* ---------- 7. Vérificateur de fidélité ---------- */
const NUM_RE = /\d{1,3}(?: \d{3})+(?:,\d+)?|\d+(?:,\d+)?/g;
const normNum = (s) => String(Math.abs(parseFloat(s.replace(/\s/g, "").replace(",", "."))).toFixed(2) * 1);

function verifierFidelite(journal, fiche, mandat, traces, tentative) {
  const autorises = new Set();
  const corpus = traces.map((t) => `${t.entrees} ${t.sortie}`).join(" ") +
    ` ${mandat.capital} ${mandat.horizon} 2022 ${pct(mandat.gabarit.poidsMax)} ${pct(mandat.gabarit.volMax)} ${pct(mandat.gabarit.perteMax)} ${mandat.baseLabel}`;
  (corpus.match(NUM_RE) || []).forEach((n) => autorises.add(normNum(n)));
  const texte = fiche.intro + " " + fiche.lignes.map((l) => l.texte).join(" ") + " " + fiche.limites;
  const trouves = texte.match(NUM_RE) || [];
  const rejets = trouves.filter((n) => !autorises.has(normNum(n)));
  const id = journal.log({
    titre: `Vérification de fidélité · version ${tentative}`, agent: "Vérificateur (code, sans LLM)", outil: "verifier_fidelite(fiche, traces)",
    entrees: `${trouves.length} chiffres extraits de la fiche`,
    sortie: rejets.length ? `${rejets.length} chiffre(s) introuvable(s) dans les traces : ${rejets.join(", ")} → fiche rejetée` : `${trouves.length}/${trouves.length} chiffres retrouvés dans les traces · 0 rejet`,
    source: "journal d'audit (Amazon DynamoDB)", periode: "exécution courante",
  });
  return { id, ok: rejets.length === 0, total: trouves.length, rejets };
}

/* ---------- 8. Agent Explicabilité (le LLM sur Bedrock, simulé par des gabarits de texte) ---------- */
function agentExplicabilite({ mandat, persona, actif, demande, alt, tMacro, style, halluciner }) {
  const g = mandat.gabarit, nom = ACTIFS[actif].nom;
  const r = demande.rejeu, b = demande.base, v = demande.vol, verd = demande.verdicts;
  const rendAffiche = halluciner ? r.rend - 0.031 : r.rend; // erreur volontaire pour la démo
  const lignes = [];
  const n = verd.violees.length;
  const intro = style === "avance"
    ? (n === 0 ? `Demande analysée : ${pct(demande.w, 0)} en ${actif}. Elle respecte les ${verd.regles.length} règles de ton mandat.`
      : alt ? `Demande analysée : ${pct(demande.w, 0)} en ${actif}. ${n} règle(s) de ton mandat ne sont pas respectées ; voici le détail et une alternative conforme.`
      : `Demande analysée : ${pct(demande.w, 0)} en ${actif}. ${n} règle(s) de ton mandat ne sont pas respectées, et aucune alternative conforme n'a été trouvée.`)
    : (n === 0 ? `Bonne nouvelle : ${pct(demande.w, 0)} en ${nom}, ça reste dans les limites de ton profil. Voici pourquoi.`
      : alt ? `En bref : ${pct(demande.w, 0)} en ${nom}, c'est plus de risque que ton profil ne le permet. Je t'explique pourquoi, et je te propose une option plus équilibrée.`
      : `En bref : ${pct(demande.w, 0)} en ${nom} dépasse ton profil, et je n'ai pas trouvé d'option conforme.`);
  if (style === "avance") {
    lignes.push({ tag: "Fait", texte: `Rejeu 2022 : ${pct(rendAffiche)} (${money(r.perte)}) avec ${pct(demande.w, 0)} de ${actif}, contre ${pct(b.rend)} (${money(b.perte)}) pour le portefeuille actuel.`, traces: [r.id, b.id] });
    lignes.push({ tag: "Fait", texte: `Volatilité annualisée du portefeuille demandé : ${pct(v.vol)}, pour une limite de ${pct(g.volMax)} dans le gabarit « ${g.label} ».`, traces: [v.id] });
    if (verd.violees.length) lignes.push({ tag: "Fait", texte: `Règles non respectées : ${verd.violees.map((x) => `${x.regle.toLowerCase()} (${x.valeur} pour une limite de ${x.limite.replace("≤ ", "").replace("≥ ", "")})`).join(" ; ")}.`, traces: [verd.id] });
    lignes.push({ tag: "Fait", texte: "Contexte : la Banque du Canada relève son taux directeur à partir du 2 mars 2022 (0,25 % → 0,50 %).", traces: [tMacro.id] });
    lignes.push({ tag: "Hypothèse", texte: persona.contexte.avance(pct(r.rend)), traces: [] });
    if (alt) lignes.push({ tag: "Scénario fictif", texte: `Alternative conforme : une poche satellite de ${pct(alt.w, 0)} en ${actif} donne ${pct(alt.rejeu.rend)} (${money(alt.rejeu.perte)}) en 2022 et une volatilité de ${pct(alt.vol.vol)}.`, traces: [alt.rejeu.id, alt.vol.id, alt.verdicts.id] });
  } else {
    lignes.push({ tag: "Fait", texte: `Si tu avais mis ${pct(demande.w, 0)} en ${nom} début 2022, tes ${money(mandat.capital)} seraient devenus environ ${money(r.final)} en fin d'année (${pct(rendAffiche)}). Sans ${nom}, ils seraient à ${money(b.final)}.`, traces: [r.id, b.id] });
    const volOk = v.vol <= g.volMax;
    lignes.push({ tag: "Fait", texte: volOk
      ? `La volatilité (l'ampleur des hausses et des baisses) serait de ${pct(v.vol)} : ça reste sous le maximum de ${pct(g.volMax)} de ton profil.`
      : `Ton portefeuille ferait de plus grosses montagnes russes que prévu : sa volatilité (l'ampleur des hausses et des baisses) serait de ${pct(v.vol)}, alors que ton profil fixe un maximum de ${pct(g.volMax)}.`, traces: [v.id] });
    if (verd.violees.length) lignes.push({ tag: "Fait", texte: `Ce qui coince : ${verd.violees.map((x) => x.regle.toLowerCase()).join(", ")}.`, traces: [verd.id] });
    lignes.push({ tag: "Hypothèse", texte: persona.contexte.inter(), traces: [] });
    if (alt) lignes.push({ tag: "Scénario fictif", texte: `Une option plus équilibrée : une part de ${pct(alt.w, 0)} en ${nom}. En 2022, ton portefeuille serait passé à environ ${money(alt.rejeu.final)}, et ça respecte ton profil.`, traces: [alt.rejeu.id, alt.vol.id, alt.verdicts.id] });
  }
  const limites = style === "avance"
    ? `Un seul scénario historique (2022) : les performances passées ne prédisent pas les résultats futurs. La volatilité n'est qu'un indicateur de risque parmi d'autres. Portefeuille actuel supposé (${mandat.baseLabel}), faute d'information.`
    : `2022 n'est qu'un exemple du passé : ça ne dit pas ce qui arrivera demain. On a aussi supposé que ton portefeuille actuel est ${mandat.baseLabel}.`;
  return { intro, lignes, limites, style };
}

/* ---------- 9. Orchestrateur déterministe ---------- */
const MAX_TENTATIVES = 3;

async function orchestrer({ personaId, message, style, halluciner, onEtape }) {
  const persona = PERSONAS[personaId];
  const journal = creerJournal();
  const etape = async (e) => { onEtape({ ...e }); await sleep(520); };

  // Guardrails
  if (/\b(ach[eè]te[- ]?(le|la|les)?|passe (l'|un )?ordre|ex[ée]cute|vends)\b/i.test(message)) {
    await etape({ agent: "Bedrock Guardrails", statut: "fail", texte: "Demande bloquée : aucune transaction réelle n'est possible. Reformule ta question pour une analyse en simulation." });
    return { arret: true, journal };
  }
  await etape({ agent: "Bedrock Guardrails", statut: "ok", texte: "Demande admise · analyse en mode simulation" });

  // Agent Profil : extraction + gabarit (les seuils viennent de la config)
  const g = GABARITS[persona.risque];
  const mPct = message.match(/(\d{1,3}(?:[.,]\d+)?)\s*%/);
  const actif = /tesla|tsla/i.test(message) ? "TSLA" : null;
  if (!actif) {
    await etape({ agent: "Agent Profil", statut: "warn", texte: "Actif non reconnu. L'univers de démonstration ne couvre que Tesla (TSLA) : précise l'actif visé." });
    return { arret: true, journal };
  }
  if (!mPct) {
    await etape({ agent: "Agent Profil", statut: "warn", texte: "Information manquante : quelle part du portefeuille souhaites-tu y mettre ? Je ne la devine pas à ta place." });
    return { arret: true, journal };
  }
  const w = Math.min(1, parseFloat(mPct[1].replace(",", ".")) / 100);
  const mandat = { persona: persona.nom, gabarit: g, capital: persona.capital, horizon: persona.horizon, baseLabel: persona.baseLabel, demande: { actif, w } };
  await etape({ agent: "Agent Profil", statut: "warn", texte: "Demande comprise · 1 information manquante remplacée par une hypothèse affichée",
    details: { type: "mandat", lignes: [["Actif demandé", `${actif} (${ACTIFS[actif].nom})`], ["Part demandée", pct(w, 0)], ["Gabarit appliqué", `« ${g.label} » (config/)`], ["Seuils", `poids max ${pct(g.poidsMax)} · vol. max ${pct(g.volMax)} · perte max ${pct(g.perteMax)}`], ["Hypothèse", `portefeuille actuel ${persona.baseLabel}`]] } });

  // Agent Analyste — tentative 1
  const tStats = outilStatistiques(journal, actif);
  const tMacro = outilContexteMacro(journal);
  const poidsDemande = poidsAvecPosition(persona.base, actif, w);
  const base = outilRejeu2022(journal, persona.base, persona.capital, "portefeuille actuel", "Agent Analyste · tentative 1");
  const rejeu = outilRejeu2022(journal, poidsDemande, persona.capital, `demande ${pct(w, 0)} ${actif}`, "Agent Analyste · tentative 1");
  const vol = outilVolatilite(journal, poidsDemande, `demande ${pct(w, 0)} ${actif}`, "Agent Analyste · tentative 1");
  await etape({ agent: "Agent Analyste · tentative 1", statut: "ok", texte: "5 appels d'outils de calcul",
    details: { type: "calculs", lignes: [
      { lib: `Volatilité de ${actif}`, val: pct(tStats.vol), trace: tStats.id },
      { lib: "Contexte des taux 2022", val: "1re hausse le 2 mars", trace: tMacro.id },
      { lib: "Rejeu 2022 · portefeuille actuel", val: pct(base.rend), trace: base.id },
      { lib: `Rejeu 2022 · demande ${pct(w, 0)}`, val: pct(rejeu.rend), trace: rejeu.id },
      { lib: `Volatilité · demande ${pct(w, 0)}`, val: pct(vol.vol), trace: vol.id },
    ] } });

  // Agent Gouvernance + boucle
  const verdicts = moteurDeRegles(journal, poidsDemande, actif, rejeu, vol, g, `demande ${pct(w, 0)} ${actif}`);
  const demande = { w, poids: poidsDemande, base, rejeu, vol, verdicts };
  let alt = null;
  if (verdicts.violees.length) {
    await etape({ agent: "Agent Gouvernance", statut: "fail", texte: `${verdicts.violees.length} règle(s) violée(s) → correction demandée à l'Analyste`,
      details: { type: "regles", regles: verdicts.regles, trace: verdicts.id, consigne: `« Trouve la plus grande position en ${actif} conforme au mandat. »` } });
    let candidat = Math.min(w, g.poidsMax);
    for (let t = 2; t <= MAX_TENTATIVES; t++) {
      const p = poidsAvecPosition(persona.base, actif, candidat);
      const lib = `alternative ${pct(candidat, 0)} ${actif}`;
      const r2 = outilRejeu2022(journal, p, persona.capital, lib, `Agent Analyste · tentative ${t}`);
      const v2 = outilVolatilite(journal, p, lib, `Agent Analyste · tentative ${t}`);
      await etape({ agent: `Agent Analyste · tentative ${t}`, statut: "ok", texte: `Alternative testée : ${pct(candidat, 0)} en ${actif}`,
        details: { type: "calculs", lignes: [
          { lib: `Rejeu 2022 · ${pct(candidat, 0)} ${actif}`, val: pct(r2.rend), trace: r2.id },
          { lib: `Volatilité · ${pct(candidat, 0)} ${actif}`, val: pct(v2.vol), trace: v2.id },
        ] } });
      const vd2 = moteurDeRegles(journal, p, actif, r2, v2, g, lib);
      if (!vd2.violees.length) {
        alt = { w: candidat, poids: p, rejeu: r2, vol: v2, verdicts: vd2 };
        await etape({ agent: "Agent Gouvernance", statut: "ok", texte: `${vd2.regles.length} règles sur ${vd2.regles.length} respectées`,
          details: { type: "regles", regles: vd2.regles, trace: vd2.id } });
        break;
      }
      await etape({ agent: "Agent Gouvernance", statut: "fail", texte: `Toujours ${vd2.violees.length} règle(s) violée(s) → nouvelle correction`,
        details: { type: "regles", regles: vd2.regles, trace: vd2.id } });
      candidat = Math.max(0, candidat - 0.02);
    }
    if (!alt) await etape({ agent: "Orchestrateur", statut: "warn", texte: `Aucune alternative conforme trouvée en ${MAX_TENTATIVES} tentatives : le système le dit honnêtement.` });
  } else {
    await etape({ agent: "Agent Gouvernance", statut: "ok", texte: "La demande respecte toutes les règles du mandat",
      details: { type: "regles", regles: verdicts.regles, trace: verdicts.id } });
  }

  // Agent Explicabilité + vérificateur de fidélité
  let fiche = agentExplicabilite({ mandat, persona, actif, demande, alt, tMacro, style, halluciner });
  let verif = verifierFidelite(journal, fiche, mandat, journal.traces, 1);
  await etape({ agent: "Agent Explicabilité", statut: "ok", texte: `Réponse rédigée au niveau « ${style === "avance" ? "avancé" : "intermédiaire"} »`,
    details: { type: "texte", texte: `${fiche.lignes.length} affirmations, chacune étiquetée (Fait / Hypothèse / Scénario fictif) et reliée à ses traces. Aucun chiffre n'est produit par le LLM.` } });
  if (!verif.ok) {
    await etape({ agent: "Vérificateur de fidélité", statut: "fail", texte: "Réponse rejetée → régénération en mode strict",
      details: { type: "verif", ok: false, rejets: verif.rejets, total: verif.total, trace: verif.id } });
    fiche = agentExplicabilite({ mandat, persona, actif, demande, alt, tMacro, style, halluciner: false });
    verif = verifierFidelite(journal, fiche, mandat, journal.traces, 2);
  }
  await etape({ agent: "Vérificateur de fidélité", statut: "ok", texte: "Réponse validée",
    details: { type: "verif", ok: true, total: verif.total, trace: verif.id } });

  return { arret: false, journal, mandat, persona, actif, demande, alt, tMacro, fiche, verif };
}

/* ---------- 10. Interface ---------- */
const COULEURS = { base: "#6B778C", demande: "#B42318", alt: "#1F4FD1" };

const AGENTS_META = [
  { prefixe: "Bedrock Guardrails", role: "Filtre de sécurité (entrées et sorties)", couleur: "#8C5A00", fond: "#FFF4D6", lettre: "G" },
  { prefixe: "Agent Profil", role: "Comprend la demande · applique le gabarit", couleur: "#4B2C9E", fond: "#EEE8FB", lettre: "1" },
  { prefixe: "Agent Analyste", role: "Appelle les outils de calcul", couleur: "#1A3E9E", fond: "#E6EEFC", lettre: "2" },
  { prefixe: "Agent Gouvernance", role: "Vérifie le mandat · moteur de règles sans LLM", couleur: "#8A1C12", fond: "#FDECEA", lettre: "3" },
  { prefixe: "Agent Explicabilité", role: "Rédige la réponse à partir des traces", couleur: "#14532D", fond: "#E7F4EC", lettre: "4" },
  { prefixe: "Vérificateur de fidélité", role: "Contrôle chaque chiffre · code sans LLM", couleur: "#14532D", fond: "#E7F4EC", lettre: "✓" },
  { prefixe: "Orchestrateur", role: "Coordonne les agents · max. 3 tentatives", couleur: "#3B4556", fond: "#EEF0F3", lettre: "O" },
];
const metaAgent = (nom) => AGENTS_META.find((m) => nom.startsWith(m.prefixe)) || AGENTS_META[AGENTS_META.length - 1];

function Icone({ statut }) {
  const props = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", strokeWidth: 2.4, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, style: { flex: "none" } };
  if (statut === "ok") return <svg {...props} stroke="#1E7B4C"><path d="M20 6 9 17l-5-5" /></svg>;
  if (statut === "warn") return <svg {...props} stroke="#B54708"><path d="M12 3 2 21h20L12 3z" /><path d="M12 10v4" /><path d="M12 17.5h.01" /></svg>;
  if (statut === "fail") return <svg {...props} stroke="#B42318"><circle cx="12" cy="12" r="9" /><path d="M15 9l-6 6" /><path d="M9 9l6 6" /></svg>;
  return <span className="spinner" aria-hidden="true" />;
}

function Puce({ id, onOpen }) {
  return <button type="button" className="puce" onClick={() => onOpen(id)} aria-label={`Ouvrir la trace ${id}`}>{id}</button>;
}

function Etiquette({ tag }) {
  const cls = tag === "Fait" ? "tag fait" : tag === "Hypothèse" ? "tag hyp" : "tag scen";
  return <span className={cls}>{tag}</span>;
}

function Statut({ ok }) {
  return ok ? <span className="pill ok">Respecté</span> : <span className="pill ko">Violé</span>;
}

function Graphique({ series }) {
  const W = 640, H = 260, x0 = 58, x1 = 560, y0 = 26, y1 = 220;
  const tous = series.flatMap((s) => s.valeurs);
  const max = Math.max(...tous), min = Math.min(...tous);
  const pad = (max - min) * 0.08 || 1;
  const vmax = max + pad, vmin = min - pad;
  const X = (i) => x0 + (i * (x1 - x0)) / (MOIS.length - 1);
  const Y = (v) => y0 + ((vmax - v) * (y1 - y0)) / (vmax - vmin);
  const ticks = [0, 1, 2, 3].map((k) => vmin + ((vmax - vmin) * k) / 3);
  const finals = series.map((s) => ({ ...s, yf: Y(s.valeurs[s.valeurs.length - 1]) })).sort((a, b) => a.yf - b.yf);
  for (let i = 1; i < finals.length; i++) if (finals[i].yf - finals[i - 1].yf < 15) finals[i].yf = finals[i - 1].yf + 15;
  const desc = series.map((s) => `${s.label} : ${money(s.valeurs[s.valeurs.length - 1])} en fin d'année`).join(" ; ");
  return (
    <figure className="graph">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Valeur mensuelle du portefeuille en 2022. ${desc}`}>
        {ticks.map((t, k) => (
          <g key={k}>
            <line x1={x0} x2={x1 + 8} y1={Y(t)} y2={Y(t)} stroke="#E2E5EA" />
            <text x={x0 - 8} y={Y(t) + 4} textAnchor="end" fontSize="11" fill="#5A6372">{sep(Math.round(t / 1000))} k$</text>
          </g>
        ))}
        {MOIS.map((m, i) => (i % 2 === 0 ? null : <text key={m} x={X(i)} y={H - 12} textAnchor="middle" fontSize="11" fill="#5A6372">{m}</text>))}
        <line x1={X(3)} x2={X(3)} y1={y0 - 8} y2={y1} stroke="#8C95A3" strokeDasharray="4 4" />
        <text x={X(3) + 6} y={y0 - 10} fontSize="11" fontWeight="600" fill="#3B4556">2 mars : hausse des taux</text>
        {series.map((s) => (
          <polyline key={s.cle} points={s.valeurs.map((v, i) => `${X(i)},${Y(v)}`).join(" ")} fill="none" stroke={COULEURS[s.cle]} strokeWidth={s.cle === "demande" ? 3.2 : 2.8} strokeDasharray={s.cle === "base" ? "7 5" : undefined} strokeLinejoin="round" />
        ))}
        {finals.map((s) => (
          <g key={s.cle}>
            <circle cx={x1} cy={Y(s.valeurs[s.valeurs.length - 1])} r="4" fill={COULEURS[s.cle]} />
            <text x={x1 + 10} y={s.yf + 4} fontSize="12" fontWeight="700" fill={COULEURS[s.cle]}>{sep(Math.round(s.valeurs[s.valeurs.length - 1] / 1000))} k$</text>
          </g>
        ))}
      </svg>
      <figcaption className="legende">
        {series.map((s) => (
          <span key={s.cle}>
            <svg width="24" height="6" aria-hidden="true"><line x1="0" x2="24" y1="3" y2="3" stroke={COULEURS[s.cle]} strokeWidth="3" strokeDasharray={s.cle === "base" ? "6 4" : undefined} /></svg>
            {s.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

/* ----- Écran 1 : choix du profil ----- */
function EcranProfil({ onChoisir }) {
  return (
    <main className="wrap accueil">
      <div className="accueil-tete">
        <div className="surtitre">Étape 1 sur 2</div>
        <h1>Choisis ton profil d'investisseur</h1>
        <p className="gris">Chaque profil est fictif. Le même système répondra différemment selon le risque, l'horizon et les préférences de chacun.</p>
      </div>
      <div className="cartes-profil">
        {Object.values(PERSONAS).map((p) => {
          const g = p.risque ? GABARITS[p.risque] : null;
          return (
            <section key={p.id} className={"carte-profil" + (p.disabled ? " inactif" : "")}>
              <div className="avatar" aria-hidden="true">{p.nom[0]}</div>
              <h2>{p.nom}, {p.age} ans</h2>
              <div className="gris">{p.metier}</div>
              <div className="jetons">
                <span className="jeton">Risque : {g ? g.label.toLowerCase() : "modéré"}</span>
                <span className="jeton">Horizon : {p.horizon}</span>
              </div>
              <h3 className="h-mini">Objectif</h3>
              <p className="objectif">{p.objectif}</p>
              <h3 className="h-mini">Préférences</h3>
              <ul className="prefs">{p.preferences.map((x) => <li key={x}>{x}</li>)}</ul>
              <button type="button" className="bouton large" disabled={p.disabled} onClick={() => onChoisir(p.id)}>
                {p.disabled ? "Bientôt disponible (ESG)" : `Continuer avec ${p.nom}`}
              </button>
            </section>
          );
        })}
      </div>
    </main>
  );
}

/* ----- Panneau droit : une carte par étape d'agent ----- */
function CarteAgent({ e, onOpen, derniere }) {
  const m = metaAgent(e.agent);
  const d = e.details;
  return (
    <li className={"agent" + (e.statut === "fail" ? " agent-echec" : "")}>
      <div className="agent-rail" aria-hidden="true"><span className="agent-pastille" style={{ background: m.fond, color: m.couleur }}>{m.lettre}</span>{!derniere && <span className="agent-ligne" />}</div>
      <div className="agent-corps">
        <div className="agent-tete">
          <div><strong>{e.agent}</strong><div className="agent-role">{m.role}</div></div>
          <Icone statut={e.statut} />
        </div>
        <p className="agent-texte">{e.texte}</p>
        {d?.type === "mandat" && (
          <dl className="mini-kv">{d.lignes.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
        )}
        {d?.type === "calculs" && (
          <ul className="mini-calc">{d.lignes.map((l) => <li key={l.trace}><span>{l.lib}</span><span className="calc-droite"><strong>{l.val}</strong><Puce id={l.trace} onOpen={onOpen} /></span></li>)}</ul>
        )}
        {d?.type === "regles" && (
          <>
            <ul className="mini-calc">{d.regles.map((r) => <li key={r.regle}><span>{r.regle} <span className="gris">({r.limite})</span></span><span className="calc-droite"><strong>{r.valeur}</strong><Statut ok={r.ok} /></span></li>)}</ul>
            {d.consigne && <p className="consigne">Correction envoyée à l'Analyste : {d.consigne}</p>}
            <div className="puces"><Puce id={d.trace} onOpen={onOpen} /></div>
          </>
        )}
        {d?.type === "texte" && <p className="agent-note">{d.texte}</p>}
        {d?.type === "verif" && (
          <>
            <p className="agent-note">{d.ok ? `${d.total}/${d.total} chiffres de la réponse retrouvés dans les traces.` : `Chiffre(s) introuvable(s) dans les traces : ${d.rejets.join(", ")}. La réponse n'est pas envoyée.`}</p>
            <div className="puces"><Puce id={d.trace} onOpen={onOpen} /></div>
          </>
        )}
      </div>
    </li>
  );
}

/* ----- Message de réponse dans le chat ----- */
function Reponse({ res, onOpen, onStyle }) {
  if (res.arret) {
    const derniere = res.etapes[res.etapes.length - 1];
    return <div className="bulle bot"><p className="intro">{derniere?.texte}</p></div>;
  }
  const { fiche, demande, alt, actif, persona } = res;
  const series = [
    { cle: "base", label: "Portefeuille actuel", valeurs: demande.base.valeurs },
    { cle: "demande", label: `Demande ${pct(demande.w, 0)}`, valeurs: demande.rejeu.valeurs },
  ];
  if (alt) series.push({ cle: "alt", label: `Alternative ${pct(alt.w, 0)}`, valeurs: alt.rejeu.valeurs });
  return (
    <div className="bulle bot">
      <p className="intro">{fiche.intro}</p>
      <div className="fiche">
        {fiche.lignes.map((l, i) => (
          <div key={i} className="fiche-ligne">
            <Etiquette tag={l.tag} />
            <div>{l.texte} {l.traces.map((t) => <Puce key={t} id={t} onOpen={onOpen} />)}</div>
          </div>
        ))}
      </div>
      <div className="encart">
        <div className="encart-titre">Ce que 2022 aurait fait à {money(persona.capital)}</div>
        <div className="stats">
          <div className="stat"><span>Actuel</span><strong>{pct(demande.base.rend)}</strong></div>
          <div className="stat rouge"><span>Demande {pct(demande.w, 0)} {actif}</span><strong>{pct(demande.rejeu.rend)}</strong></div>
          {alt && <div className="stat bleu"><span>Alternative {pct(alt.w, 0)} {actif}</span><strong>{pct(alt.rejeu.rend)}</strong></div>}
        </div>
        <Graphique series={series} />
      </div>
      <div className="limites"><strong>{fiche.style === "avance" ? "Limites." : "À garder en tête."}</strong> {fiche.limites}</div>
      <div className="verif">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1E7B4C" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3z" /><path d="M8.5 12l2.5 2.5 4.5-5" /></svg>
        <span>Chiffres vérifiés : chacun provient d'une trace de calcul.</span>
        <Puce id={res.verif.id} onOpen={onOpen} />
      </div>
      <div className="rapides">
        {fiche.style === "avance"
          ? <button type="button" className="rapide" onClick={() => onStyle("inter")}>Explique-moi plus simplement</button>
          : <button type="button" className="rapide" onClick={() => onStyle("avance")}>Version plus technique</button>}
      </div>
    </div>
  );
}

/* ----- Fenêtre de détail d'une trace ----- */
function FenetreTrace({ trace, onClose }) {
  const ref = useRef(null);
  useEffect(() => { ref.current?.focus(); }, [trace]);
  return (
    <div className="voile" onClick={onClose}>
      <div className="fenetre" role="dialog" aria-modal="true" aria-label={`Trace ${trace.id}`} tabIndex={-1} ref={ref}
        onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
        <div className="fenetre-tete">
          <div><div className="mono blanc">{trace.id} · {trace.titre}</div><div className="pale petit">{trace.agent}</div></div>
          <button type="button" className="fermer" onClick={onClose} aria-label="Fermer">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M18 6 6 18" /><path d="M6 6l12 12" /></svg>
          </button>
        </div>
        <dl>
          <div><dt>Outil appelé</dt><dd className="mono blanc">{trace.outil}</dd></div>
          <div><dt>Entrées</dt><dd>{trace.entrees}</dd></div>
          <div><dt>Sortie</dt><dd className="blanc gras">{trace.sortie}</dd></div>
          <div><dt>Source</dt><dd>{trace.source}</dd></div>
          <div><dt>Période</dt><dd>{trace.periode}</dd></div>
        </dl>
        <p className="pale petit">Dans le vrai projet : enregistré dans Amazon DynamoDB. XIU et XBB sont des exemples de FNB.</p>
      </div>
    </div>
  );
}

/* ----- Écran 2 : chat + coulisses ----- */
function EcranAnalyse({ personaId, onRetour }) {
  const persona = PERSONAS[personaId];
  const g = GABARITS[persona.risque];
  const [saisie, setSaisie] = useState(persona.message);
  const [messages, setMessages] = useState([]);
  const [etapes, setEtapes] = useState([]);
  const [enCours, setEnCours] = useState(false);
  const [halluciner, setHalluciner] = useState(false);
  const [traceOuverte, setTraceOuverte] = useState(null);
  const finChat = useRef(null);
  const finAgents = useRef(null);

  useEffect(() => { finChat.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);
  useEffect(() => { finAgents.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [etapes]);

  const envoyer = async (texte) => {
    const msg = texte.trim();
    if (!msg || enCours) return;
    setSaisie("");
    setEnCours(true);
    setEtapes([]);
    setMessages((m) => [...m, { role: "user", texte: msg }, { role: "bot", attente: true }]);
    const collecte = [];
    const r = await orchestrer({
      personaId, message: msg, style: persona.style, halluciner,
      onEtape: (e) => { collecte.push(e); setEtapes((prev) => [...prev, e]); },
    });
    r.etapes = collecte;
    if (!r.arret) r.persona = persona;
    setMessages((m) => [...m.slice(0, -1), { role: "bot", res: r }]);
    setEnCours(false);
  };

  const changerStyle = (index, style) => {
    setMessages((m) => m.map((x, i) => {
      if (i !== index) return x;
      const r = x.res;
      const fiche = agentExplicabilite({ mandat: r.mandat, persona: r.persona, actif: r.actif, demande: r.demande, alt: r.alt, tMacro: r.tMacro, style, halluciner: false });
      return { ...x, res: { ...r, fiche } };
    }));
  };

  // Les traces de toutes les analyses de la conversation
  const ouvrir = (index) => (id) => {
    const r = messages[index]?.res;
    const t = r?.journal.traces.find((x) => x.id === id);
    if (t) setTraceOuverte(t);
  };
  const dernierIndexBot = messages.map((m, i) => (m.res ? i : -1)).filter((i) => i >= 0).pop();
  const ouvrirDepuisPanneau = (id) => {
    if (enCours) return;
    if (dernierIndexBot !== undefined) ouvrir(dernierIndexBot)(id);
  };

  const suggestions = [persona.message, "Et si je mets 10 % en Tesla ?", "Je veux investir dans Tesla.", "Achète-le pour moi."];

  return (
    <div className="split">
      {/* ----- Gauche : chat ----- */}
      <section className="col chat" aria-label="Conversation">
        <div className="col-tete">
          <div className="profil-actif">
            <span className="avatar petit" aria-hidden="true">{persona.nom[0]}</span>
            <div><strong>{persona.nom}, {persona.age} ans</strong><div className="gris petit">{g.label} · {persona.horizon} · {money(persona.capital)} fictifs</div></div>
          </div>
          <button type="button" className="lien" onClick={onRetour} disabled={enCours}>Changer de profil</button>
        </div>

        <div className="fil" aria-live="polite">
          {messages.length === 0 && (
            <div className="bulle bot">
              <p className="intro">Bonjour {persona.nom} ! Pose-moi ta question d'investissement. Je l'analyse en simulation, je vérifie qu'elle respecte ton profil, et je t'explique chaque chiffre.</p>
            </div>
          )}
          {messages.map((m, i) => {
            if (m.role === "user") return <div key={i} className="bulle user">{m.texte}</div>;
            if (m.attente) return <div key={i} className="bulle bot attente"><span className="spinner" aria-hidden="true" />Les agents analysent ta demande… suis leur travail à droite.</div>;
            return <Reponse key={i} res={m.res} onOpen={ouvrir(i)} onStyle={(s) => changerStyle(i, s)} />;
          })}
          <div ref={finChat} />
        </div>

        <form className="composeur" onSubmit={(e) => { e.preventDefault(); envoyer(saisie); }}>
          <div className="rapides">
            {suggestions.map((s) => <button key={s} type="button" className="rapide" disabled={enCours} onClick={() => setSaisie(s)}>{s.length > 46 ? s.slice(0, 44) + "…" : s}</button>)}
          </div>
          <div className="saisie">
            <label htmlFor="msg" className="sr">Ta question</label>
            <textarea id="msg" rows={2} value={saisie} disabled={enCours} placeholder="Écris ta question…"
              onChange={(e) => setSaisie(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(saisie); } }} />
            <button type="submit" className="bouton" disabled={enCours || !saisie.trim()}>Envoyer</button>
          </div>
        </form>
      </section>

      {/* ----- Droite : les agents ----- */}
      <section className="col coulisses" aria-label="Les agents au travail">
        <div className="col-tete sombre">
          <div><strong>Dans les coulisses</strong><div className="pale petit">Les agents apparaissent au fur et à mesure</div></div>
          <label className="bascule">
            <input type="checkbox" checked={halluciner} onChange={(e) => setHalluciner(e.target.checked)} disabled={enCours} />
            <span>Simuler une erreur du LLM</span>
          </label>
        </div>
        <div className="agents-zone">
          {etapes.length === 0 && (
            <div className="vide">
              <p>Envoie ta question : tu verras ici chaque agent travailler, ce qu'il calcule, ce qu'il vérifie et pourquoi.</p>
              <div className="mandat-vide">
                <div className="surtitre">Ton mandat · seuils fixés par l'équipe</div>
                <ul className="mini-calc">
                  <li><span>Poids max par titre</span><strong>{pct(g.poidsMax)}</strong></li>
                  <li><span>Volatilité max</span><strong>{pct(g.volMax)}</strong></li>
                  <li><span>Perte max tolérée</span><strong>{pct(g.perteMax)}</strong></li>
                  <li><span>Cryptoactifs max</span><strong>{pct(g.cryptoMax)}</strong></li>
                </ul>
              </div>
            </div>
          )}
          <ol className="agents">
            {etapes.map((e, i) => <CarteAgent key={i} e={e} onOpen={ouvrirDepuisPanneau} derniere={i === etapes.length - 1 && !enCours} />)}
            {enCours && (
              <li className="agent"><div className="agent-rail" aria-hidden="true"><span className="agent-pastille attente"><span className="spinner" /></span></div><div className="agent-corps"><p className="agent-texte gris">Agent suivant au travail…</p></div></li>
            )}
          </ol>
          <div ref={finAgents} />
        </div>
      </section>

      {traceOuverte && <FenetreTrace trace={traceOuverte} onClose={() => setTraceOuverte(null)} />}
    </div>
  );
}

export default function App() {
  const [personaId, setPersonaId] = useState(null);
  return (
    <div className="app">
      <style>{CSS}</style>
      <header className="topbar">
        <div className="wrap topbar-in">
          <div className="marque">
            <svg width="32" height="32" viewBox="0 0 34 34" fill="none" aria-hidden="true"><rect x="1" y="1" width="32" height="32" rx="8" stroke="#8FB0FF" strokeWidth="2" /><path d="M9 24 L15 12 L19 19 L25 9" stroke="#FFF" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <div><div className="marque-nom">AlphaForge AI</div><div className="marque-sous">Copilote d'investissement auto-explicatif</div></div>
          </div>
          <span className="badge-sim">Simulation · aucun conseil financier · données fictives</span>
        </div>
      </header>
      {personaId
        ? <EcranAnalyse key={personaId} personaId={personaId} onRetour={() => setPersonaId(null)} />
        : <EcranProfil onChoisir={setPersonaId} />}
    </div>
  );
}

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');
*{box-sizing:border-box}
body{margin:0}
.app{min-height:100vh;background:#F4F5F7;color:#15181D;font-family:Inter,system-ui,sans-serif;font-size:15px;line-height:1.5;display:flex;flex-direction:column}
.wrap{max-width:1360px;margin:0 auto;padding-left:24px;padding-right:24px;width:100%}
.topbar{background:#0F1B33;color:#fff;flex:none}
.topbar-in{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;padding-top:12px;padding-bottom:12px}
.marque{display:flex;align-items:center;gap:12px}
.marque-nom{font-family:'Space Grotesk',Inter,sans-serif;font-weight:700;font-size:19px}
.marque-sous{font-size:12.5px;color:#B9C6E4}
.badge-sim{font-size:12.5px;color:#FFE3A8;padding:5px 12px;border:1px solid #5B4A22;border-radius:999px;background:#2A2614}
.surtitre{font-size:12px;font-weight:600;color:#5A6372;letter-spacing:.4px;text-transform:uppercase}
.gris{color:#5A6372}.petit{font-size:12.5px}.pale{color:#9FB0D3}.blanc{color:#fff}.gras{font-weight:600}
.mono{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12.5px;font-weight:600}
.h-mini{margin:16px 0 6px;font-size:12px;font-weight:600;color:#3B4556;text-transform:uppercase;letter-spacing:.4px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
button:focus-visible,textarea:focus-visible{outline:2px solid #1F4FD1;outline-offset:2px}
.bouton{min-height:44px;padding:10px 20px;border:0;border-radius:10px;background:#1F4FD1;color:#fff;font:600 15px Inter,sans-serif;cursor:pointer}
.bouton:hover:not(:disabled){background:#163A9E}.bouton:disabled{background:#A9B1BE;cursor:not-allowed}
.bouton.large{width:100%;margin-top:auto}
.lien{min-height:40px;background:none;border:1px solid #CDD3DC;border-radius:8px;padding:6px 12px;font:500 13px Inter,sans-serif;color:#1F4FD1;cursor:pointer}
.lien:disabled{color:#8C95A3;cursor:not-allowed}

/* Écran profil */
.accueil{padding-top:40px;padding-bottom:56px}
.accueil-tete{max-width:720px;margin-bottom:28px}
.accueil h1{margin:6px 0 8px;font-family:'Space Grotesk',Inter,sans-serif;font-size:34px;line-height:1.15}
.cartes-profil{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}
.carte-profil{background:#fff;border:1px solid #E2E5EA;border-radius:16px;padding:24px;display:flex;flex-direction:column}
.carte-profil.inactif{opacity:.62}
.carte-profil h2{margin:12px 0 0;font-family:'Space Grotesk',Inter,sans-serif;font-size:22px}
.avatar{width:52px;height:52px;border-radius:50%;background:#DCE6FF;color:#1A3E9E;display:flex;align-items:center;justify-content:center;font:700 22px 'Space Grotesk',Inter,sans-serif;flex:none}
.avatar.petit{width:38px;height:38px;font-size:16px}
.jetons{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.jeton{font-size:12.5px;font-weight:600;padding:4px 10px;border-radius:999px;background:#F0F2F5;color:#3B4556}
.objectif{margin:0;font-size:14.5px}
.prefs{margin:0 0 20px;padding-left:18px;font-size:14px;color:#3B4556}
.prefs li{margin:2px 0}

/* Écran analyse : écran coupé en deux */
.split{flex:1;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);height:calc(100vh - 60px);min-height:560px}
.col{display:flex;flex-direction:column;min-height:0}
.col-tete{flex:none;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;padding:14px 22px;background:#fff;border-bottom:1px solid #E2E5EA}
.col-tete.sombre{background:#16233F;border-bottom-color:#26375C;color:#fff}
.profil-actif{display:flex;gap:10px;align-items:center}
.chat{background:#F4F5F7;border-right:1px solid #E2E5EA}
.fil{flex:1;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:16px}
.bulle{max-width:100%;border-radius:16px;padding:14px 16px;font-size:15px}
.bulle.user{align-self:flex-end;max-width:80%;background:#1F4FD1;color:#fff;border-bottom-right-radius:4px}
.bulle.bot{align-self:flex-start;background:#fff;border:1px solid #E2E5EA;border-bottom-left-radius:4px;width:100%}
.bulle.attente{display:flex;gap:10px;align-items:center;color:#5A6372;width:auto}
.intro{margin:0 0 12px;font-weight:600;font-size:15.5px}
.bulle.bot > .intro:last-child{margin:0}
.fiche{display:flex;flex-direction:column;gap:12px}
.fiche-ligne{display:flex;gap:10px;align-items:flex-start;font-size:14.5px}
.fiche-ligne .tag{width:110px;text-align:center;margin-top:2px}
.tag{flex:none;display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;padding:3px 7px;border-radius:6px}
.tag.fait{background:#E6EEFC;color:#1A3E9E}.tag.hyp{background:#FFF4D6;color:#6B4200}.tag.scen{background:#EEE8FB;color:#4B2C9E}
.encart{margin-top:16px;border:1px solid #E2E5EA;border-radius:12px;padding:14px}
.encart-titre{font-weight:600;font-size:14px;margin-bottom:10px}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px}
.stat{flex:1 1 120px;display:flex;flex-direction:column;border:1px solid #E2E5EA;border-radius:8px;padding:8px 10px;font-size:12.5px;color:#4A5568}
.stat strong{font:700 20px 'Space Grotesk',Inter,sans-serif;color:#3B4556}
.stat.rouge{border-color:#E8B4AE;background:#FFF7F6}.stat.rouge strong{color:#8A1C12}
.stat.bleu{border-color:#B9C9F3;background:#F3F6FF}.stat.bleu strong{color:#1A3E9E}
.graph{margin:0}.graph > svg{width:100%;height:auto;display:block}
.legende{margin-top:6px;display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:#3B4556}
.legende span{display:inline-flex;align-items:center;gap:6px}
.limites{margin-top:14px;padding:12px 14px;background:#F4F5F7;border-radius:10px;font-size:13.5px;color:#3B4556}
.verif{margin-top:12px;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 12px;border:1px solid #BFE0CB;background:#F0F9F3;border-radius:10px;font-size:13.5px;color:#14532D}
.verif span{flex:1;min-width:200px}
.rapides{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.rapide{min-height:36px;padding:6px 12px;border:1px solid #C9D3E6;border-radius:999px;background:#fff;font:500 13px Inter,sans-serif;color:#1A3E9E;cursor:pointer}
.rapide:hover:not(:disabled){background:#EEF3FF}.rapide:disabled{opacity:.5;cursor:not-allowed}
.composeur{flex:none;padding:10px 22px 16px;background:#fff;border-top:1px solid #E2E5EA}
.composeur .rapides{margin:0 0 10px}
.saisie{display:flex;gap:10px;align-items:flex-end}
.saisie textarea{flex:1;padding:12px 14px;border:1px solid #CDD3DC;border-radius:12px;font:inherit;font-size:15px;resize:none;background:#FAFBFC;color:#15181D}
.puce{font:600 11.5px/1 'JetBrains Mono',ui-monospace,monospace;padding:6px 8px;border:1px solid #C9D3E6;border-radius:6px;background:#fff;color:#1F4FD1;cursor:pointer;vertical-align:middle;margin:1px 2px}
.puce:hover{background:#EEF3FF;border-color:#1F4FD1}
.puces{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}

/* Coulisses */
.coulisses{background:#0F1B33}
.agents-zone{flex:1;overflow-y:auto;padding:20px 22px}
.bascule{display:flex;gap:8px;align-items:center;font-size:13px;color:#DCE4F5;cursor:pointer;min-height:40px}
.bascule input{width:18px;height:18px;flex:none}
.vide{color:#B9C6E4;font-size:14.5px}
.vide p{margin:0 0 16px}
.mandat-vide{background:#fff;border-radius:12px;padding:16px;color:#15181D}
.agents{list-style:none;margin:0;padding:0}
.agent{display:flex;gap:12px;animation:entree .4s ease}
.agent-rail{display:flex;flex-direction:column;align-items:center;flex:none;width:30px}
.agent-pastille{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font:700 13px 'Space Grotesk',Inter,sans-serif;flex:none}
.agent-pastille.attente{background:#26375C}
.agent-ligne{flex:1;width:2px;background:#33466F;margin:4px 0}
.agent-corps{flex:1;min-width:0;background:#fff;border-radius:12px;padding:12px 14px;margin-bottom:14px}
.agent-echec .agent-corps{box-shadow:inset 3px 0 0 #B42318}
.agent-tete{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.agent-role{font-size:12px;color:#5A6372}
.agent-texte{margin:6px 0 0;font-size:14px}
.agent-note{margin:8px 0 0;font-size:13px;color:#3B4556}
.consigne{margin:8px 0 0;font-size:13px;color:#8A1C12;font-style:italic}
.mini-kv{margin:8px 0 0;display:flex;flex-direction:column;gap:4px;font-size:13px}
.mini-kv div{display:flex;gap:8px;justify-content:space-between;border-top:1px solid #EEF0F3;padding-top:4px}
.mini-kv dt{color:#5A6372}.mini-kv dd{margin:0;font-weight:600;text-align:right}
.mini-calc{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-direction:column;gap:4px;font-size:13px}
.mini-calc li{display:flex;justify-content:space-between;align-items:center;gap:8px;border-top:1px solid #EEF0F3;padding-top:4px}
.calc-droite{display:inline-flex;align-items:center;gap:6px;flex:none}
.pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px}
.pill.ok{background:#E7F4EC;color:#14532D}.pill.ko{background:#FDECEA;color:#8A1C12}
.spinner{display:inline-block;width:16px;height:16px;flex:none;border:2.5px solid #C9D3E6;border-top-color:#1F4FD1;border-radius:50%;animation:tourne .8s linear infinite}
@keyframes tourne{to{transform:rotate(360deg)}}
@keyframes entree{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* Fenêtre de trace */
.voile{position:fixed;inset:0;background:rgba(10,16,30,.55);display:flex;align-items:center;justify-content:center;padding:20px;z-index:10}
.fenetre{width:min(560px,100%);max-height:90vh;overflow:auto;background:#0F1B33;color:#E6ECF8;border-radius:14px;padding:20px;outline:none}
.fenetre-tete{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.fermer{width:40px;height:40px;flex:none;border:1px solid #33466F;border-radius:8px;background:transparent;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center}
.fenetre dl{margin:16px 0 0;display:flex;flex-direction:column;gap:12px;font-size:14px}
.fenetre dt{font-size:11.5px;color:#9FB0D3;text-transform:uppercase;letter-spacing:.4px}
.fenetre dd{margin:2px 0 0}
.fenetre p{margin:16px 0 0}

@media (max-width:960px){
  .split{display:block;height:auto}
  .chat{border-right:0}
  .fil{overflow:visible}
  .agents-zone{overflow:visible}
}
@media (max-width:560px){.fiche-ligne{flex-direction:column;gap:4px}.fiche-ligne .tag{width:auto}.accueil h1{font-size:27px}}
@media (prefers-reduced-motion:reduce){.agent,.spinner{animation:none}}
`;
