"""Carte de l'architecture AWS d'InvestIA (une page paysage). Usage : python carte_aws.py sortie.pdf [hebergement]"""
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

F = "/System/Library/Fonts/Supplemental/"
for nom, fichier in [("A", "Arial.ttf"), ("AB", "Arial Bold.ttf"), ("AI", "Arial Italic.ttf"), ("AU", "Arial Unicode.ttf")]:
    pdfmetrics.registerFont(TTFont(nom, F + fichier))
pdfmetrics.registerFontFamily("A", normal="A", bold="AB", italic="AI", boldItalic="AB")

W, H = landscape(letter)
NUIT, BLEU, ENCRE, GRIS = colors.HexColor("#0B1F44"), colors.HexColor("#1F6FEB"), colors.HexColor("#111827"), colors.HexColor("#6B7280")
ORANGE, ORANGE_C, ORANGE_T = colors.HexColor("#E8891C"), colors.HexColor("#FFF4E5"), colors.HexColor("#8A4B00")
BLEU_C, VERT = colors.HexColor("#EAF1FE"), colors.HexColor("#12805C")


def boite(c, x, y, w, h, titre, lignes, fond, bord, couleur_titre, taille=7.2, epais=1.0):
    c.setFillColor(fond); c.setStrokeColor(bord); c.setLineWidth(epais)
    c.roundRect(x, y, w, h, 6, 1, 1)
    c.setFillColor(couleur_titre); c.setFont("AB", 8.6); c.drawString(x + 8, y + h - 14, titre)
    c.setFillColor(ENCRE); c.setFont("A", taille)
    for i, l in enumerate(lignes):
        c.drawString(x + 8, y + h - 27 - i * (taille + 2.6), l)


def fleche(c, x1, y1, x2, y2, num=None, couleur=BLEU, tirets=False):
    c.setStrokeColor(couleur); c.setFillColor(couleur); c.setLineWidth(1.1)
    if tirets:
        c.setDash(3, 2)
    c.line(x1, y1, x2, y2); c.setDash()
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    p = c.beginPath(); p.moveTo(x2, y2)
    p.lineTo(x2 - 6 * math.cos(a - 0.4), y2 - 6 * math.sin(a - 0.4)); p.lineTo(x2 - 6 * math.cos(a + 0.4), y2 - 6 * math.sin(a + 0.4)); p.close()
    c.drawPath(p, stroke=0, fill=1)
    if num:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        c.setFillColor(couleur); c.circle(mx, my, 6.5, 0, 1)
        c.setFillColor(colors.white); c.setFont("AB", 7); c.drawCentredString(mx, my - 2.5, str(num))


def main(sortie, hebergement):
    c = canvas.Canvas(sortie, pagesize=landscape(letter))
    c.setTitle("InvestIA — Architecture AWS"); c.setAuthor("Équipe InvestIA")
    # En-tête
    c.setFillColor(NUIT); c.rect(0, H - 52, W, 52, 0, 1)
    c.setFillColor(colors.white); c.setFont("AB", 17); c.drawString(28, H - 32, "InvestIA — Architecture AWS")
    c.setFillColor(colors.HexColor("#C7D2FE")); c.setFont("A", 8.4)
    c.drawString(28, H - 45, "AWS exécute, stocke et contrôle ; le code d'InvestIA garde la décision. Région us-east-1.")
    c.drawRightString(W - 28, H - 32, "Datathon PolyFinances 2026 · Banque Nationale × AWS")

    # Colonne gauche : utilisateur + application
    boite(c, 24, 482, 140, 58, "Utilisateur", ["navigateur web", "profil fictif + question libre"], colors.white, colors.HexColor("#D1D5DB"), ENCRE, taille=7.6)
    boite(c, 24, 262, 150, 192, "Application InvestIA", ["Streamlit · Python", f"hébergée : {hebergement}", "", "Code (sans LLM) :",
                                                       "· orchestrateur des agents", "· moteur de règles (juge)", "· vérificateur de fidélité",
                                                       "  (chiffres + aucun conseil)", "· calcul du point de bascule", "",
                                                       "Les agents IA tournent", "sur Amazon Bedrock."],
          BLEU_C, BLEU, BLEU, taille=7.4)
    fleche(c, 88, 482, 88, 456, couleur=GRIS)
    c.setFillColor(GRIS); c.setFont("AI", 6.6); c.drawString(94, 466, "HTTPS")

    # Nuage AWS
    ax, ay, aw, ah = 196, 104, W - 196 - 22, 442
    c.setStrokeColor(ORANGE); c.setLineWidth(1.3); c.setDash(5, 3); c.roundRect(ax, ay, aw, ah, 10, 1, 0); c.setDash()
    c.setFillColor(ORANGE); c.roundRect(ax + 12, ay + ah - 9, 96, 16, 4, 0, 1)
    c.setFillColor(colors.white); c.setFont("AB", 8); c.drawString(ax + 20, ay + ah - 4, "AWS · us-east-1")

    # Bedrock (groupe)
    bx, by, bw, bh = ax + 16, 250, 334, 272
    c.setFillColor(colors.HexColor("#FFFBF5")); c.setStrokeColor(ORANGE); c.setLineWidth(0.8); c.roundRect(bx, by, bw, bh, 8, 1, 1)
    c.setFillColor(ORANGE_T); c.setFont("AB", 11); c.drawString(bx + 10, by + bh - 18, "Amazon Bedrock")
    boite(c, bx + 10, by + 150, 152, 92, "Claude Haiku 5.5", ["Agent Profil", "comprend la demande, même", "mal orthographiée", "rapide · ≈ 20× moins cher", "que Sonnet (appel à", "chaque message)"], ORANGE_C, ORANGE, ORANGE_T, taille=7.4)
    boite(c, bx + 172, by + 150, 152, 92, "Claude Sonnet 5.5", ["Agent Analyste (Strands :", "choisit ses outils)", "Agent Gouvernance (verdict)", "Agent Explicabilité :", "rédaction fidèle aux", "chiffres des traces"], ORANGE_C, ORANGE, ORANGE_T, taille=7.4)
    boite(c, bx + 10, by + 14, 314, 122, "Bedrock Guardrails  (guardrail 7xq7ledpn2cm)",
          ["Entrée : détection des sujets « transaction réelle »", "et « promesse de rendement »",
           "Sortie : blocage sur la réponse affichée,", "remplacée par un message sûr",
           "Chaque intervention écrit une trace de contrôle", "+ règle en code qui bloque tout ordre réel"], ORANGE_C, ORANGE, ORANGE_T, taille=7.4)

    # Lambda, S3, DynamoDB
    lx = bx + bw + 22
    lw = ax + aw - 16 - lx
    boite(c, lx, 410, lw, 112, "AWS Lambda  (Function URL)", ["Outils de calcul de l'Analyste :", "part du risque, rejeu 2022,", "volatilité, stress-test 12 mois",
                                                               "", "Authentification AWS_IAM :", "requêtes signées (SigV4)"], ORANGE_C, ORANGE, ORANGE_T, taille=7.4)
    boite(c, lx, 250, lw, 132, "Amazon S3", ["alphaforge-donnees-at2026", "bucket privé, accès public bloqué", "chiffrement SSE-S3",
                                             "prix en CAD, macro, ESG", "lecture seule par l'application", "manifeste SHA-256 vérifié", "à chaque lecture"], ORANGE_C, ORANGE, ORANGE_T, taille=7.4)
    boite(c, ax + 16, 120, aw - 32, 92, "Amazon DynamoDB  —  journal d'audit  (table alphaforge-traces · clé session + id)",
          ["Une ligne par étape : mandat, extraction, chaque calcul, verdicts, vérification de fidélité, contrôles Guardrails.",
           "Chaque trace : identifiant T-xx, horodatage, agent, outil, entrées, sortie, source, période, version des données.",
           "C'est la base de l'auto-explicabilité : chaque chiffre affiché renvoie à sa trace, consultable après coup.",
           "Si DynamoDB est indisponible, la trace est écrite localement : aucune preuve n'est perdue."], ORANGE_C, ORANGE, ORANGE_T, taille=7.6)

    # Flux numérotés
    fleche(c, 174, 400, bx + 10, by + 100, 1)                      # → Guardrails (entrée)
    fleche(c, 174, 430, bx + 10, by + 205, 2)                      # → Haiku
    fleche(c, 174, 372, bx + 10, by + 55, 6, tirets=True)          # Guardrails (sortie)
    fleche(c, bx + 324, by + 200, lx, 470, 3)                      # Sonnet/Strands → Lambda
    fleche(c, lx + lw / 2, 410, lx + lw / 2, 382, 4)               # Lambda → S3
    fleche(c, 174, 290, lx, 300, couleur=GRIS, tirets=True)        # app → S3 (chargement des données)
    c.setFillColor(GRIS); c.setFont("AI", 6.4); c.drawString(lx - 150, 289, "chargement des données (lecture S3)")
    for xx in (bx + 86, bx + 248, lx + lw / 2):
        fleche(c, xx, 250, xx, 212, couleur=VERT)                  # → DynamoDB
    c.setFillColor(VERT); c.setFont("AB", 7); c.drawString(lx + lw / 2 + 6, 226, "5 · traces de chaque étape")

    # Légende du parcours
    lgx, lgy = 24, 238
    c.setFillColor(ENCRE); c.setFont("AB", 8); c.drawString(lgx, lgy, "Parcours d'une demande")
    etapes = ["1  Guardrails filtre la demande", "2  Haiku construit le mandat", "3  Sonnet (Strands) appelle Lambda",
              "4  Lambda lit les données dans S3", "5  chaque étape écrit sa trace", "6  Guardrails filtre la réponse"]
    c.setFont("A", 7)
    for i, e in enumerate(etapes):
        c.setFillColor(ENCRE); c.drawString(lgx, lgy - 13 - i * 10.5, e)
    c.setFillColor(GRIS); c.setFont("AI", 6.4)
    c.drawString(lgx, lgy - 81, "Gouvernance, Explicabilité : Sonnet ;")
    c.drawString(lgx, lgy - 90, "le vérificateur contrôle avant 6.")

    # Bandeau bas : sécurité et résilience
    c.setFillColor(colors.HexColor("#F3F4F6")); c.setStrokeColor(colors.HexColor("#E5E7EB")); c.roundRect(24, 16, W - 48, 78, 6, 1, 1)
    st = ParagraphStyle("p", fontName="A", fontSize=7.6, leading=10, textColor=ENCRE)
    textes = [("Sécurité", "Aucune clé AWS dans le code ni dans git : identifiants temporaires ou rôle IAM. Données privées et chiffrées, "
                           "lecture seule. Lambda authentifiée par IAM. Aucune connexion à un système de courtage : aucune transaction réelle possible."),
              ("Résilience", "Identifiants expirés, modèle refusé, réponse tronquée, Lambda ou DynamoDB indisponible : repli déterministe "
                             "(gabarit, plan fixe, fichier local de traces) et motif affiché à l'utilisateur. S3 illisible : arrêt avec un message clair, "
                             "jamais d'autres données en silence."),
              ("Pourquoi ces choix", "Services managés, sans serveur à administrer pendant un datathon ; un modèle par besoin "
                                     "(Haiku pour le volume, Sonnet pour la fidélité) ; un journal hors de l'application pour que les preuves survivent à la session.")]
    cw = (W - 48 - 32) / 3
    for i, (t, d) in enumerate(textes):
        p = Paragraph(f"<b>{t}.</b> {d}", st); _, h = p.wrap(cw, 100); p.drawOn(c, 36 + i * (cw + 8), 86 - h)
    c.showPage(); c.save()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Streamlit Community Cloud")
