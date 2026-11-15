"""One-pager InvestIA en format flyer (une page Letter), dessiné avec ReportLab. Chiffres : exécution réelle de l'application."""
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

F = "/System/Library/Fonts/Supplemental/"
for nom, fichier in [("A", "Arial.ttf"), ("AB", "Arial Bold.ttf"), ("AI", "Arial Italic.ttf"), ("AU", "Arial Unicode.ttf")]:
    pdfmetrics.registerFont(TTFont(nom, F + fichier))
pdfmetrics.registerFontFamily("A", normal="A", bold="AB", italic="AI", boldItalic="AB")

NUIT, BLEU, BLEU_C, ENCRE = colors.HexColor("#0B1F44"), colors.HexColor("#1F6FEB"), colors.HexColor("#EAF1FE"), colors.HexColor("#111827")
GRIS, GRIS_C, ROUGE, VERT = colors.HexColor("#6B7280"), colors.HexColor("#F3F4F6"), colors.HexColor("#D93025"), colors.HexColor("#12805C")
W, H = letter
M = 34                                                  # marge


def para(c, texte, x, y_haut, largeur, taille=8.6, couleur=ENCRE, police="A", interligne=1.3):
    st = ParagraphStyle("p", fontName=police, fontSize=taille, leading=taille * interligne, textColor=couleur)
    p = Paragraph(texte, st)
    _, h = p.wrap(largeur, 1000)
    p.drawOn(c, x, y_haut - h)
    return y_haut - h


def carte(c, x, y, w, h, fond=colors.white, bord=colors.HexColor("#E5E7EB")):
    c.setFillColor(fond); c.setStrokeColor(bord); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)


def titre_section(c, texte, x, y, couleur=BLEU):
    c.setFillColor(couleur); c.setFont("AB", 7.6)
    c.drawString(x, y, texte.upper())


def courbe(c, x, y, w, h, donnees):
    pts, bascule, limite = donnees["courbe"], donnees["bascule"], donnees["limite"]
    xmax = 0.42
    px = lambda v: x + 22 + (w - 30) * v / xmax
    py = lambda v: y + 16 + (h - 30) * v
    c.setStrokeColor(colors.HexColor("#E5E7EB")); c.setLineWidth(0.4)
    c.setFont("A", 5.6); c.setFillColor(GRIS)
    for v in (0, 0.5, 1):
        c.line(px(0), py(v), px(xmax), py(v)); c.drawRightString(px(0) - 3, py(v) - 2, f"{int(v * 100)} %")
    for v in (0, 0.1, 0.2, 0.3, 0.4):
        c.drawCentredString(px(v), y + 7, f"{int(v * 100)} %")
    c.setFillColor(colors.HexColor("#F3F4F6")); c.setStrokeColor(colors.white)
    c.rect(px(bascule + 0.005), py(0), px(xmax) - px(bascule + 0.005), py(1) - py(0), stroke=0, fill=1)   # zone hors profil
    c.setStrokeColor(ROUGE); c.setDash(3, 2); c.setLineWidth(0.8)
    c.line(px(0), py(limite), px(xmax), py(limite)); c.setDash()
    c.setFillColor(ROUGE); c.setFont("A", 5.8); c.drawRightString(px(xmax), py(limite) + 3, f"limite du profil : {int(limite * 100)} % du risque")
    c.setStrokeColor(BLEU); c.setLineWidth(1.6)
    chemin = c.beginPath(); chemin.moveTo(px(pts[0][0]), py(pts[0][1]))
    for a, b in pts[1:]:
        chemin.lineTo(px(a), py(b))
    c.drawPath(chemin, stroke=1, fill=0)
    y30 = next(b for a, b in pts if abs(a - 0.30) < 1e-9)
    yb = next(b for a, b in pts if abs(a - bascule) < 1e-9)
    for (a, b), lib, dx, coul in [((0.30, y30), "demande : 30 %", -4, ENCRE), ((bascule, yb), f"point de bascule : {int(bascule * 100)} %", 5, VERT)]:
        c.setFillColor(coul); c.setStrokeColor(colors.white); c.circle(px(a), py(b), 2.6, stroke=1, fill=1)
        c.setFont("AB", 6.2)
        (c.drawRightString if dx < 0 else c.drawString)(px(a) + dx, py(b) + (5 if dx < 0 else -9), lib)
    c.setFillColor(GRIS); c.setFont("A", 5.6)
    c.drawCentredString(x + w / 2, y - 1, "part de Tesla dans le portefeuille de Robert (axe vertical : part du risque)")


def main(sortie: str, donnees: dict):
    c = canvas.Canvas(sortie, pagesize=letter)
    c.setTitle("InvestIA — One-pager"); c.setAuthor("Équipe InvestIA")

    # --- Bandeau
    c.setFillColor(NUIT); c.rect(0, H - 118, W, 118, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("AB", 30); c.drawString(M, H - 58, "Invest")
    c.setFillColor(colors.HexColor("#6EA8FF")); c.drawString(M + c.stringWidth("Invest", "AB", 30), H - 58, "IA")
    c.setFillColor(colors.HexColor("#C7D2FE")); c.setFont("A", 8)
    c.drawRightString(W - M, H - 40, "Datathon PolyFinances 2026 · Banque Nationale × AWS")
    c.setFillColor(colors.white); c.setFont("AB", 13.5)
    c.drawString(M, H - 84, "On ne vous dit pas quoi acheter.")
    c.setFillColor(colors.HexColor("#93C5FD"))
    c.drawString(M, H - 102, "On vous montre jusqu'où votre décision reste cohérente avec vous.")

    # --- Chiffre-choc + problème (gauche) / courbe (droite)
    y0 = H - 136
    gw = 262
    carte(c, M, y0 - 168, gw, 168)
    titre_section(c, "Le problème", M + 12, y0 - 18)
    c.setFillColor(ENCRE); c.setFont("AB", 34); c.drawString(M + 12, y0 - 56, "30 %")
    c.setFont("A", 8); c.setFillColor(GRIS); c.drawString(M + 12, y0 - 68, "de ses dollars en Tesla…")
    c.setFillColor(ROUGE); c.setFont("AB", 34); c.drawString(M + 132, y0 - 56, "89,5 %")
    c.setFont("A", 8); c.setFillColor(GRIS); c.drawString(M + 132, y0 - 68, "…de son risque")
    para(c, "On pense en <b>dollars</b>, mais un portefeuille réagit au <b>risque</b>. Pour un investisseur prudent "
            "comme Robert, un seul titre volatil peut porter presque tous les hauts et les bas du portefeuille. "
            "Prudent, équilibré ou audacieux : personne ne voit cet écart, ni le moment où la décision ne lui "
            "correspond plus.", M + 12, y0 - 80, gw - 24, taille=8.2)

    cx = M + gw + 12
    cw = W - M - cx
    carte(c, cx, y0 - 168, cw, 168)
    titre_section(c, "La courbe de bascule (données réelles)", cx + 12, y0 - 18)
    courbe(c, cx + 8, y0 - 158, cw - 18, 128, donnees)

    # --- Solution : trois profils
    y1 = y0 - 182
    carte(c, M, y1 - 74, W - 2 * M, 74, fond=BLEU_C, bord=colors.HexColor("#C9D7F5"))
    titre_section(c, "Notre solution : le point de bascule", M + 12, y1 - 16)
    para(c, "On écrit sa question comme à une personne : « Je pense mettre 30 % dans Tesla ». InvestIA répond : "
            "<b>est-ce cohérent avec mon profil ? Sinon, jusqu'où ça le serait, et quelle limite casse en premier ?</b>",
         M + 12, y1 - 22, 300, taille=8.2)
    for i, (profil, val, qui) in enumerate([("Prudent", "3 %", "Robert"), ("Équilibré + ESG", "6 %", "Mateo"), ("Audacieux", "13 %", "Amira")]):
        bx = M + 330 + i * 72
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor("#C9D7F5")); c.roundRect(bx, y1 - 66, 66, 52, 6, 1, 1)
        c.setFillColor(BLEU); c.setFont("AB", 18); c.drawCentredString(bx + 33, y1 - 38, val)
        c.setFillColor(ENCRE); c.setFont("AB", 6.4); c.drawCentredString(bx + 33, y1 - 50, profil)
        c.setFillColor(GRIS); c.setFont("A", 6); c.drawCentredString(bx + 33, y1 - 59, qui)
    c.setFillColor(GRIS); c.setFont("AI", 6.4)
    c.drawString(M + 12, y1 - 68, "Même question, même moteur, trois limites : jamais « tout est permis », même pour un profil audacieux.")

    # --- Comment ça marche : 5 étapes
    y2 = y1 - 88
    titre_section(c, "Comment ça marche : 4 agents IA et un vérificateur", M, y2 - 4)
    etapes = [("Profil", "comprend la question,\ndemande ce qui manque"), ("Analyste", "fait les calculs\n(jamais l'IA)"),
              ("Gouvernance", "compare aux limites,\nose dire non"), ("Explicabilité", "explique en clair :\nfaits · hypothèses"),
              ("Vérificateur", "chaque chiffre prouvé,\naucun conseil")]
    bw, gap = (W - 2 * M - 4 * 14) / 5, 14
    for i, (nom, desc) in enumerate(etapes):
        bx = M + i * (bw + gap)
        fond = NUIT if nom == "Vérificateur" else colors.white
        carte(c, bx, y2 - 62, bw, 50, fond=fond, bord=BLEU if nom != "Vérificateur" else NUIT)
        c.setFillColor(colors.white if nom == "Vérificateur" else BLEU); c.setFont("AB", 8.6)
        c.drawCentredString(bx + bw / 2, y2 - 28, nom)
        c.setFillColor(colors.HexColor("#C7D2FE") if nom == "Vérificateur" else GRIS); c.setFont("A", 6.4)
        for k, ligne in enumerate(desc.split("\n")):
            c.drawCentredString(bx + bw / 2, y2 - 40 - k * 8, ligne)
        if i < 4:
            ax = bx + bw + 2
            c.setStrokeColor(BLEU); c.setLineWidth(1.1); c.line(ax, y2 - 37, ax + gap - 5, y2 - 37)
            c.setFillColor(BLEU); p = c.beginPath(); p.moveTo(ax + gap - 4, y2 - 37); p.lineTo(ax + gap - 8, y2 - 34.5); p.lineTo(ax + gap - 8, y2 - 39.5); p.close(); c.drawPath(p, stroke=0, fill=1)
    c.setFillColor(ENCRE); c.setFont("AB", 7.6)
    c.drawCentredString(W / 2, y2 - 76, "Le code calcule et juge · l'IA comprend et rédige · le code vérifie ce que l'IA a écrit")

    # --- Ce qui nous distingue (3 cartes)
    y3 = y2 - 90
    titre_section(c, "Ce qui nous distingue", M, y3 - 4)
    distinct = [("La part du risque, pas des dollars", "Une seule image montre où la demande sort du profil : la courbe de bascule."),
                ("Zéro chiffre inventé, zéro conseil", "Vérifié par le code à chaque réponse, pas seulement promis à l'IA."),
                ("Un assistant qui sait dire non", "Il nuance, refuse, relève les tensions avec le profil, et explique pourquoi.")]
    dw = (W - 2 * M - 2 * 10) / 3
    for i, (t, d) in enumerate(distinct):
        bx = M + i * (dw + 10)
        carte(c, bx, y3 - 66, dw, 54)
        c.setFillColor(BLEU); c.circle(bx + 14, y3 - 27, 6.5, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("AB", 7.5); c.drawCentredString(bx + 14, y3 - 29.5, str(i + 1))
        para(c, f"<b>{t}</b>", bx + 26, y3 - 20, dw - 34, taille=7.8)
        para(c, d, bx + 12, y3 - 38, dw - 22, taille=7, couleur=GRIS)

    # --- Valeur (2 cartes) + données / AWS
    y4 = y3 - 80
    vw = (W - 2 * M - 10) / 2
    for i, (t, d) in enumerate([("Pour l'investisseur", "Comprendre en dix secondes <b>pourquoi</b> une idée ne lui convient pas, et "
                                  "<b>jusqu'où</b> elle lui conviendrait. Chaque chiffre a sa preuve, en un clic."),
                                 ("Pour la banque", "Une vérification de <b>convenance</b> expliquée, traçable et auditable, "
                                  "qu'un conseiller peut partager telle quelle avec son client.")]):
        bx = M + i * (vw + 10)
        carte(c, bx, y4 - 58, vw, 58, fond=colors.HexColor("#E6F4EE"), bord=colors.HexColor("#BFE3D2"))
        titre_section(c, t, bx + 12, y4 - 15, couleur=VERT)
        para(c, d, bx + 12, y4 - 21, vw - 24, taille=7.8)

    y5 = y4 - 70
    titre_section(c, "Données et AWS", M, y5 - 4)
    y_txt = para(c, "31 placements · 5 ans de prix réels (Yahoo Finance) · tout en dollars canadiens (Banque du Canada) · aucune "
            "information « du futur ». <b>ESG : version partielle</b>, assumée (règle sectorielle + fonds ESG). "
            "<b>Modèles :</b> Claude Haiku 5.5 pour comprendre chaque message (rapide, ≈ 20× moins cher) ; Claude Sonnet 5.5 pour "
            "rédiger sans déformer un seul chiffre.",
         M, y5 - 9, W - 2 * M, taille=7.4, couleur=GRIS)
    bx = M
    for svc in ["Amazon Bedrock · Claude", "Bedrock Guardrails", "AWS Lambda", "Amazon S3", "Amazon DynamoDB", "Strands Agents"]:
        tw = c.stringWidth(svc, "AB", 7) + 16
        c.setFillColor(colors.HexColor("#FFF4E5")); c.setStrokeColor(colors.HexColor("#F5C27A"))
        c.roundRect(bx, y_txt - 18, tw, 14, 7, 1, 1)            # badges placés sous le texte, quelle que soit sa longueur
        c.setFillColor(colors.HexColor("#8A4B00")); c.setFont("AB", 7); c.drawString(bx + 8, y_txt - 14, svc)
        bx += tw + 6

    # --- Explicabilité
    y6 = y_txt - 24
    assert y6 - 28 > 46, "le flyer déborde sur le pied de page"
    carte(c, M, y6 - 28, W - 2 * M, 28, fond=GRIS_C, bord=colors.HexColor("#E5E7EB"))
    para(c, "<b>Chaque réponse se justifie.</b> Un clic montre, pour chaque chiffre, le calcul, les données utilisées et "
            "leur source ; ces preuves sont enregistrées sur AWS (Amazon DynamoDB) et consultables après coup.",
         M + 12, y6 - 6, W - 2 * M - 24, taille=7.6)

    # --- Pied de page
    c.setFillColor(NUIT); c.rect(0, 0, W, 40, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("AB", 7.6)
    c.drawString(M, 25, "Et ensuite ?")
    c.setFont("A", 7.2); c.setFillColor(colors.HexColor("#C7D2FE"))
    c.drawString(M + 50, 25, "Agent Auditeur (à venir) · plusieurs placements par question · horizon qui ajuste les limites · mode conseiller."
                 "  La suite, construisons-la ensemble.")
    c.setFont("A", 5.8); c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawString(M, 11, "Simulation éducative sur des profils fictifs : aucune transaction réelle, aucun conseil financier personnalisé. "
                 "Les performances passées ne prédisent pas les résultats futurs.")
    c.showPage(); c.save()


if __name__ == "__main__":
    main(sys.argv[2], json.load(open(sys.argv[1])))
