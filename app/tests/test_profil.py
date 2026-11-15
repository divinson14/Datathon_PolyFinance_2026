import pytest

from src import bedrock_client
from src.agents import profil
from src.config import PERSONAS
from src.donnees.chargeur import charger
from src.traces.journal import Journal

ROBERT = PERSONAS["robert"]          # capital 200 000 $
_, UNIVERS, _ = charger()


def ext(message, persona=ROBERT, journal=None):
    return profil.extraire(message, persona, UNIVERS, journal)


@pytest.mark.parametrize("message, symbole, part", [
    ("Je pense mettre 30 % dans Tesla.", "TSLA", 0.30),
    ("Tesla à 30%", "TSLA", 0.30),
    ("Et 3,5 % de TSLA ?", "TSLA", 0.035),
    ("10 pour cent en Nvidia", "NVDA", 0.10),
    ("5 % de Bitcoin", "BTC-USD", 0.05),
    ("Je veux 10 % dans l'or", "GLD", 0.10),
    ("Et si je mettais 20 % sur le Nasdaq ?", "QQQ", 0.20),
])
def test_extraction_actif_et_pourcentage(message, symbole, part):
    r = ext(message)
    if symbole not in set(UNIVERS["symbole"]):
        pytest.skip("actif absent des données de démo")
    assert r["symbole"] == symbole and r["part"] == pytest.approx(part) and r["informations_manquantes"] == []


def test_montant_converti_par_le_code():
    r = ext("Je voudrais placer 50 000 $ dans Tesla.")
    assert r["part"] == pytest.approx(0.25) and r["lecture"]["type"] == "montant"


def test_montant_egal_au_capital_n_est_pas_une_part():
    r = ext("J'ai 200 000 $ de côté, je pense à Tesla.")
    assert r["part"] is None and "part du portefeuille" in r["informations_manquantes"]


def test_pourcentage_prioritaire_sur_le_capital_cite():
    r = ext(ROBERT["message_exemple"])        # « J'ai 200 000 $ … mettre 30 % dedans »
    assert r["symbole"] == "TSLA" and r["part"] == pytest.approx(0.30)


def test_part_manquante_pose_une_question():
    r = ext("Je veux investir dans Tesla.")
    assert r["part"] is None and r["question"]


def test_plusieurs_actifs_ambigus():
    r = ext("Je veux mettre 10 % dans Tesla ou dans Nvidia.")
    assert r["symbole"] is None and "actif à analyser" in r["informations_manquantes"]


def test_part_superieure_a_100_refusee():
    r = ext("Je mets 150 % dans Tesla.")
    assert r["part"] is None and "part valide" in r["informations_manquantes"]


def test_mots_courants_pas_pris_pour_des_tickers():
    """« or » (conjonction), « td » ou « pg » en minuscules ne doivent pas déclencher un actif."""
    assert profil.actifs_mentionnes("or je pense que td et pg, c'est flou", UNIVERS) == []


def test_extraction_tracee():
    j = Journal()
    r = ext("Je voudrais placer 50 000 $ dans Tesla.", journal=j)
    t = j.trouver(r["trace"])
    assert t["titre"] == "Extraction de la demande" and "25 %" in t["sortie"] and "50 000 $" in t["sortie"]


def _faux_llm(monkeypatch, reponse):
    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", lambda *a, **k: reponse)


def test_llm_chiffre_invente_rejete(monkeypatch):
    """Le LLM « recopie » un extrait qui n'est pas dans le message : rejeté, la part vient du code."""
    _faux_llm(monkeypatch, {"symbole": "TSLA", "symboles_mentionnes": ["TSLA"], "extrait_part": "25 %"})
    r = ext("Je veux mettre un tiers de mon argent dans le constructeur d'Elon Musk.")
    assert r["symbole"] == "TSLA" and r["part"] is None and "ABSENT" in r["methode"]


def test_llm_periphrase_acceptee(monkeypatch):
    _faux_llm(monkeypatch, {"symbole": "TSLA", "symboles_mentionnes": ["TSLA"], "extrait_part": "15 %"})
    r = ext("Je veux 15 % dans le constructeur de voitures électriques d'Elon Musk.")
    assert r["symbole"] == "TSLA" and r["part"] == pytest.approx(0.15)


def test_llm_symbole_hors_univers_ignore(monkeypatch):
    _faux_llm(monkeypatch, {"symbole": "BBD-B.TO", "symboles_mentionnes": ["BBD-B.TO"], "extrait_part": "10 %"})
    r = ext("Je veux 10 % dans Bombardier.")
    assert r["symbole"] is None and "actif" in r["informations_manquantes"]


# ---------- Mandat ----------

def test_mandat_persona_reprend_le_gabarit_de_config():
    from src.config import GABARITS
    m = profil.construire_mandat("robert")
    assert m["gabarit"]["volatilite_max"] == GABARITS["faible_a_modere"]["volatilite_max"]
    assert m["horizon_ans"] == {"min": 3.0, "max": 5.0} and not m["bloquant"] and m["tensions"] == []
    assert m["contraintes"]["exclusions_esg"] is False and profil.construire_mandat("mateo")["contraintes"]["exclusions_esg"]


def test_mandat_tolerance_jamais_deduite():
    m = profil.construire_mandat(saisie={"age": 26, "horizon_ans": 20, "objectif": "croissance"})
    assert m["bloquant"] and m["gabarit"] is None and "tolérance au risque" in m["informations_manquantes"]


def test_mandat_tension_horizon_court_signalee_pas_corrigee():
    m = profil.construire_mandat(saisie={"tolerance": "eleve", "horizon_ans": 3, "age": 30, "objectif": "x"})
    assert m["tensions"] and m["gabarit"]["id"] == "eleve"          # signalé, la tolérance reste celle saisie


def test_mandat_hypotheses_affichees_pour_profil_saisi():
    m = profil.construire_mandat(saisie={"tolerance": "modere", "horizon_ans": 10})
    assert m["profil"]["capital"] > 0 and any("capital fictif" in h for h in m["hypotheses"])
    assert {"âge", "objectif"} <= set(m["informations_manquantes"]) and not m["bloquant"]


def test_mandat_trace():
    j = Journal()
    m = profil.construire_mandat("amira", journal=j)
    assert j.trouver(m["trace"])["titre"] == "Construction du mandat"


def test_portefeuilles_types_conformes_a_leur_gabarit():
    from src.config import GABARITS, PROFIL
    from src.outils import calculs
    from src.regles.moteur import verifier_mandat
    _, univers, source = charger()
    if "FICTIVES" in source:
        pytest.skip("calibré sur les données réelles")
    for tol, pf in PROFIL["portefeuilles_types"].items():
        assert abs(sum(pf["poids"].values()) - 1) < 1e-9
        v = verifier_mandat(Journal(), pf["poids"], calculs.mesures(pf["poids"]), GABARITS[tol], univers, "type")
        assert v["violees"] == [], tol


def test_llm_indisponible_repli_local(monkeypatch):
    def panne(*a, **k):
        raise ConnectionError("Bedrock injoignable")
    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", panne)
    r = ext("Je pense mettre 30 % dans Tesla.")
    assert r["symbole"] == "TSLA" and r["part"] == pytest.approx(0.30) and "repli" in r["methode"]


def test_bedrock_client_ignore_les_blocs_non_texte(monkeypatch):
    """Les modèles récents peuvent renvoyer un bloc de raisonnement AVANT le texte."""
    class FauxClient:
        def converse(self, **params):
            return {"output": {"message": {"content": [{"reasoningContent": {"reasoningText": {"text": "…"}}},
                                                       {"text": '{"symbole": "TSLA"}'}]}}, "stopReason": "end_turn"}
    monkeypatch.setenv("BEDROCK_MODELE_RAPIDE", "faux")
    monkeypatch.setattr(bedrock_client, "_bedrock", lambda: FauxClient())
    assert bedrock_client.appeler("x", modele="rapide") == '{"symbole": "TSLA"}'


# ---------- Mémoire de conversation ----------

def _conversation(messages, persona="robert"):
    """Rejoue une conversation comme l'interface : la mémoire suit la dernière demande comprise."""
    from src.orchestrateur import executer
    memoire, resultats = None, []
    for m in messages:
        res = executer(persona, m, memoire=memoire)
        dem = res.get("demande_extraite")
        if dem is not None:
            avant = (memoire or {}).get("derniere_lecture")
            lecture = dem["lecture"] if dem["part"] is not None else None
            memoire = {"symbole": dem["symbole"], "lecture": lecture, "derniere_lecture": lecture or avant}
        resultats.append(res)
    return resultats


def test_conversation_de_yoel_rejouee():
    """Bombardier (hors univers) → NVIDIA sans part → « 10000$ » doit analyser NVIDIA à 5 %."""
    r = _conversation(["je pense plutôt investir dans bombardier", "je pense plutôt investir dans nvidia", "10000$"])
    assert r[0]["arret"] and r[1]["arret"]
    assert "part du portefeuille" in r[1]["demande_extraite"]["informations_manquantes"]
    assert not r[2]["arret"] and r[2]["symbole"] == "NVDA" and r[2]["demande"]["part"] == pytest.approx(0.05)
    assert "actif NVDA" in r[2]["demande_extraite"]["reprises"]


def test_relance_reprend_l_actif_et_change_la_part():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "et à 5 % ?"])
    assert r[1]["symbole"] == "TSLA" and r[1]["demande"]["part"] == pytest.approx(0.05)


def test_relance_reprend_la_part_pour_un_autre_actif():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "et NVIDIA ?"])
    assert r[1]["symbole"] == "NVDA" and r[1]["demande"]["part"] == pytest.approx(0.30)
    assert any("part" in x for x in r[1]["demande_extraite"]["reprises"])


def test_nouvelle_phrase_ne_reprend_rien_en_silence():
    """Une phrase complète vers un actif inconnu ne doit JAMAIS être comprise comme l'actif précédent."""
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "je pense plutôt investir 10 % dans bombardier"])
    assert r[1]["arret"] and r[1]["demande_extraite"]["symbole"] is None


def test_sans_memoire_une_part_seule_demande_l_actif():
    r = _conversation(["5 %"])
    assert r[0]["arret"] and "actif" in r[0]["demande_extraite"]["informations_manquantes"]


def test_reprise_tracee():
    from src.orchestrateur import executer
    from src.traces.journal import Journal
    memoire = {"symbole": "TSLA", "lecture": None}
    res = executer("robert", "5 %", memoire=memoire)
    t = res["journal"].trouver(res["demande_extraite"]["trace"])
    assert "repris de l'échange précédent : actif TSLA" in t["sortie"]


def test_message_actif_inconnu_lisible():
    r = ext("Je veux mettre 20 % dans Bombardier.")
    assert "actions canadiennes (RY" in r["question"] and "RY.TO" not in r["question"]


def test_comparaison_reprend_la_part_meme_avec_une_phrase():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "et qu'en est-il pour nvidia ?"])
    assert r[1]["symbole"] == "NVDA" and r[1]["demande"]["part"] == pytest.approx(0.30)


def test_comparaison_ne_reprend_jamais_un_actif():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "et pour Bombardier, qu'en est-il ?"])
    assert r[1]["arret"] and r[1]["demande_extraite"]["symbole"] is None


def test_nombre_nu_demande_l_unite():
    r = _conversation(["je veux investir dans nvidia", "100"])
    q = r[1]["demande_extraite"]["question"]
    assert r[1]["arret"] and "100 % ou 100 $" in q and "NVDA" in q


def test_demande_en_attente_conservee():
    """« je t'ai demandé au début » : on redemande la part pour NVDA au lieu de « actif non reconnu »."""
    r = _conversation(["je veux investir dans nvidia", "je t'ai demandé au début"])
    dem = r[1]["demande_extraite"]
    assert dem["symbole"] == "NVDA" and "part du portefeuille" in dem["informations_manquantes"]
    assert "NVDA" in dem["question"] and "ne reconnais pas" not in dem["question"]


def test_conversation_complete_de_yoel():
    r = _conversation(["je veux investir dans nvidia", "100", "100$", "Tout le monde parle de Tesla, je pense mettre 30 % dedans.",
                       "et qu'en est-il pour nvidia ?"])
    assert r[1]["arret"] and not r[2]["arret"] and r[2]["symbole"] == "NVDA"
    assert r[3]["symbole"] == "TSLA" and r[4]["symbole"] == "NVDA" and r[4]["demande"]["part"] == pytest.approx(0.30)


def test_comparaison_tolere_les_fautes():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "et qu'en est til pour nvidia?"])
    assert r[1]["symbole"] == "NVDA" and r[1]["demande"]["part"] == pytest.approx(0.30)


def test_reference_a_une_part_deja_donnee():
    """Tesla 30 % → « et pour NVIDIA ? » sans part → « ce que je t'ai demandé au début » : 30 % repris ET affiché."""
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "je veux investir dans nvidia",
                       "ce que je t'ai demandé au début"])
    assert r[1]["arret"]
    assert not r[2]["arret"] and r[2]["symbole"] == "NVDA" and r[2]["demande"]["part"] == pytest.approx(0.30)
    assert any("dernière part indiquée" in x for x in r[2]["demande_extraite"]["reprises"])


def test_reference_sans_part_connue_redemande():
    r = _conversation(["je veux investir dans nvidia", "ce que je t'ai demandé au début"])
    assert r[1]["arret"] and "NVDA" in r[1]["demande_extraite"]["question"]


# ---------- Règle 4 : ni actif ni part → jamais d'analyse ----------

def test_bonjour_ne_relance_jamais_une_analyse():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "qu'en est til de nvdia?" , "bonjour"])
    assert r[2]["arret"] and "Je suis un outil de simulation" in r[2]["demande_extraite"]["question"]


def test_bonjour_sans_historique():
    r = _conversation(["bonjour"])
    assert r[0]["arret"] and "Par exemple" in r[0]["demande_extraite"]["question"]


def test_part_seule_reprend_le_dernier_actif():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "5 %"])
    assert r[1]["symbole"] == "TSLA" and r[1]["demande"]["part"] == pytest.approx(0.05)


def test_actif_seul_sans_comparaison_demande_la_part():
    r = _conversation(["Je pense mettre 30 % dans Tesla.", "je pense à nvidia"])
    assert r[1]["arret"] and "part du portefeuille" in r[1]["demande_extraite"]["informations_manquantes"]


# ---------- Demande en attente (multi-tours) : même logique que l'interface (st.session_state) ----------

def _session(messages, persona="robert"):
    """Rejoue une conversation comme ui/streamlit_app.py : mémoire + demande en attente mises à jour à chaque tour."""
    from src.agents.profil import maj_demande_en_attente
    from src.orchestrateur import executer
    memoire, en_attente, tours = None, None, []
    for m in messages:
        res = executer(persona, m, memoire=memoire, en_attente=en_attente)
        en_attente = maj_demande_en_attente(en_attente, res, m)
        dem = res.get("demande_extraite")
        if dem is not None:
            avant = (memoire or {}).get("derniere_lecture")
            lecture = dem["lecture"] if dem["part"] is not None else None
            memoire = {"symbole": dem["symbole"], "lecture": lecture, "derniere_lecture": lecture or avant}
        tours.append((res, en_attente))
    return tours


def test_part_puis_actif_analyse_tsla_10():
    from src.agents.profil import RELANCE_ACTIF
    (r1, att1), (r2, att2) = _session(["je veux mettre 10%", "tesla"])
    assert r1["arret"] and r1["etapes"][-1]["texte"] == RELANCE_ACTIF        # relance courte, pas les 31 symboles
    assert att1["lecture"]["part"] == pytest.approx(0.10) and att1["message_part"] == "je veux mettre 10%"
    assert not r2["arret"] and r2["symbole"] == "TSLA" and r2["mandat"]["demande"]["part"] == pytest.approx(0.10)
    profil_etape = next(e for e in r2["etapes"] if e["agent"] == "Agent Profil")
    assert "Complété à partir du message précédent : part = 10 %" in profil_etape["note"]
    trace = r2["journal"].trouver(r2["mandat"]["demande"]["trace"])
    assert "complété à partir du message précédent : part = 10 %" in trace["sortie"]
    assert att2 is None                                                       # analyse lancée → vidée


def test_actif_puis_part_analyse_tsla_10():
    (r1, att1), (r2, att2) = _session(["tesla", "10%"])
    assert r1["arret"] and att1["symbole"] == "TSLA"
    assert not r2["arret"] and r2["symbole"] == "TSLA" and r2["mandat"]["demande"]["part"] == pytest.approx(0.10)
    assert att2 is None


def test_part_puis_actif_hors_univers_liste_affichee():
    (_, _), (r2, att2) = _session(["je veux mettre 10%", "Ford"])
    assert r2["arret"] and "Il couvre 31 actifs" in r2["etapes"][-1]["texte"]
    assert att2["lecture"]["part"] == pytest.approx(0.10)                     # la part attend toujours son actif


@pytest.mark.parametrize("premier", ["tesla", "je veux mettre 10%"])
def test_demande_complete_remplace_la_demande_en_attente(premier):
    (_, att1), (r2, att2) = _session([premier, "Je pense mettre 5 % dans Nvidia."])
    assert att1 is not None
    assert not r2["arret"] and r2["symbole"] == "NVDA" and r2["mandat"]["demande"]["part"] == pytest.approx(0.05)
    assert not (r2["mandat"]["demande"].get("completes") or [])
    assert att2 is None


def test_part_reprise_seulement_si_ancree_dans_son_message():
    """Contrôle d'ancrage sur le message où la part a été trouvée : une part qui n'y figure pas n'est pas reprise."""
    from src.orchestrateur import executer
    faux = {"lecture": {"part": 0.4, "extrait": "40 %", "type": "pourcentage"}, "message_part": "je veux mettre 10%"}
    res = executer("robert", "tesla", en_attente=faux)
    assert res["arret"] and "part du portefeuille" in res["demande_extraite"]["informations_manquantes"]


def test_garde_fou_ne_vide_pas_la_demande_en_attente():
    from src.agents.profil import maj_demande_en_attente
    from src.orchestrateur import executer
    att = {"symbole": "TSLA", "message_symbole": "tesla"}
    res = executer("robert", "Achète-le pour moi.", en_attente=att)
    assert res["arret"] and maj_demande_en_attente(att, res, "Achète-le pour moi.") == att
