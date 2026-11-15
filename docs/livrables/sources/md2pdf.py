"""Convertisseur Markdown → PDF (sous-ensemble utilisé par les documents du projet) avec ReportLab.
Usage : python md2pdf.py entree.md sortie.pdf [--taille 10] [--marge 18] [--titre "..."]"""
import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

F = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Arial", F + "Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", F + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", F + "Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", F + "Arial Bold Italic.ttf"))
pdfmetrics.registerFont(TTFont("ArialUni", F + "Arial Unicode.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-BoldItalic")

BLEU = colors.HexColor("#1F4FB0")
GRIS = colors.HexColor("#555555")


def styles(t: float):
    base = ParagraphStyle("base", fontName="Arial", fontSize=t, leading=t * 1.32, alignment=TA_LEFT, spaceAfter=t * 0.45)
    return {
        "p": base,
        "h1": ParagraphStyle("h1", parent=base, fontName="Arial-Bold", fontSize=t * 1.9, leading=t * 2.2, spaceAfter=t * 0.3, textColor=BLEU),
        "h2": ParagraphStyle("h2", parent=base, keepWithNext=1, fontName="Arial-Bold", fontSize=t * 1.35, leading=t * 1.6, spaceBefore=t * 0.9, spaceAfter=t * 0.35, textColor=BLEU),
        "h3": ParagraphStyle("h3", parent=base, keepWithNext=1, fontName="Arial-Bold", fontSize=t * 1.1, leading=t * 1.35, spaceBefore=t * 0.6, spaceAfter=t * 0.25),
        "cite": ParagraphStyle("cite", parent=base, textColor=GRIS, leftIndent=t, fontName="Arial-Italic"),
        "petit": ParagraphStyle("petit", parent=base, fontSize=t * 0.8, leading=t * 1.05, textColor=GRIS),
        "cell": ParagraphStyle("cell", parent=base, fontSize=t * 0.88, leading=t * 1.12, spaceAfter=0),
        "cellh": ParagraphStyle("cellh", parent=base, fontSize=t * 0.88, leading=t * 1.12, spaceAfter=0, fontName="Arial-Bold"),
        "code": ParagraphStyle("code", parent=base, fontName="Courier", fontSize=t * 0.85, leading=t * 1.1,
                               backColor=colors.HexColor("#F3F4F6"), leftIndent=4, borderPadding=4),
        "li": ParagraphStyle("li", parent=base, spaceAfter=t * 0.15),
    }


def inline(texte: str) -> str:
    texte = re.sub(r"<!--.*?-->", "", texte)
    texte = re.sub(r"</?sub>", "", texte)
    codes = []
    texte = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes) - 1}\x00", texte)
    texte = html.escape(texte, quote=False)
    texte = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", texte)          # liens : texte seul (lisible imprimé)
    texte = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texte)
    texte = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", texte)
    texte = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<i>\1</i>", texte)
    texte = re.sub(r"\x00(\d+)\x00", lambda m: f'<font face="Courier">{html.escape(codes[int(m.group(1))], quote=False)}</font>', texte)
    texte = re.sub(r"[→≤≥≠Σλ′−]", lambda m: f'<font face="ArialUni">{m.group(0)}</font>', texte)
    return texte.strip()


def tableau(lignes, st, largeur):
    rangs = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lignes]
    rangs = [r for r in rangs if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    n = max(len(r) for r in rangs)
    donnees = [[Paragraph(inline(c), st["cellh" if i == 0 else "cell"]) for c in r + [""] * (n - len(r))]
               for i, r in enumerate(rangs)]
    taille = st["cell"].fontSize
    propre = lambda c: re.sub(r"[*`]", "", c)
    # largeur minimale = mot le plus long de la colonne (en gras), pour ne jamais couper un mot
    mins = [max(pdfmetrics.stringWidth(m, "Arial-Bold", taille) for r in rangs for m in (propre(r[j]) if j < len(r) else "").split() or [""]) + 12
            for j in range(n)]
    longueurs = [max(len(propre(r[j] if j < len(r) else "")) for r in rangs) + 4 for j in range(n)]
    reste = max(0, largeur - sum(mins))
    total = sum(longueurs)
    t = Table(donnees, colWidths=[mn + reste * l / total for mn, l in zip(mins, longueurs)], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1FE")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D3E6")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def image(chemin: Path, largeur):
    if chemin.suffix.lower() in (".png", ".jpg", ".jpeg"):           # image matricielle : pleine largeur
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image
        w, h = ImageReader(str(chemin)).getSize()
        return Image(str(chemin), width=largeur, height=largeur * h / w)
    try:
        from svglib.svglib import svg2rlg
        d = svg2rlg(str(chemin))
        echelle = min(1.0, largeur / d.width)
        d.width, d.height = d.width * echelle, d.height * echelle
        d.scale(echelle, echelle)
        return d
    except Exception as e:                                              # noqa: BLE001
        print("image ignorée :", chemin, e)
        return None


def convertir(src: Path, dst: Path, taille: float, marge: float, titre: str):
    st = styles(taille)
    doc = SimpleDocTemplate(str(dst), pagesize=letter, leftMargin=marge * mm, rightMargin=marge * mm,
                            topMargin=marge * mm, bottomMargin=marge * mm, title=titre, author="Équipe InvestIA")
    largeur = letter[0] - 2 * marge * mm
    histoire, lignes, i = [], src.read_text(encoding="utf-8").splitlines(), 0

    def para_buffer(buf, style="p"):
        if buf:
            histoire.append(Paragraph(inline(" ".join(x.strip() for x in buf)), st[style]))

    buf = []
    while i < len(lignes):
        l = lignes[i]
        if l.strip().startswith("```"):
            para_buffer(buf); buf = []
            j = i + 1
            while j < len(lignes) and not lignes[j].strip().startswith("```"):
                j += 1
            histoire.append(Preformatted("\n".join(lignes[i + 1:j]), st["code"]))
            histoire.append(Spacer(1, taille * 0.4)); i = j + 1; continue
        if m := re.match(r"^(#{1,3})\s+(.*)", l):
            para_buffer(buf); buf = []
            histoire.append(Paragraph(inline(m.group(2)), st["h" + str(len(m.group(1)))])); i += 1; continue
        if m := re.match(r"^!\[.*?\]\((.*?)\)", l.strip()):
            para_buffer(buf); buf = []
            img = image((src.parent / m.group(1)).resolve(), largeur)
            if img is not None:
                histoire += [img, Spacer(1, taille * 0.5)]
            i += 1; continue
        if l.strip().startswith("|"):
            para_buffer(buf); buf = []
            j = i
            while j < len(lignes) and lignes[j].strip().startswith("|"):
                j += 1
            histoire += [tableau(lignes[i:j], st, largeur - (8 if l.startswith("  ") else 0)), Spacer(1, taille * 0.6)]
            i = j; continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", l):
            para_buffer(buf); buf = []
            items, ordonne = [], bool(re.match(r"^\s*\d+\.", l))
            while i < len(lignes) and (re.match(r"^\s*([-*]|\d+\.)\s+", lignes[i]) or
                                       (lignes[i].startswith("  ") and lignes[i].strip() and not lignes[i].strip().startswith("|"))):
                cur = lignes[i]
                if re.match(r"^\s*([-*]|\d+\.)\s+", cur):
                    niveau = (len(cur) - len(cur.lstrip())) // 2
                    items.append([niveau, re.sub(r"^\s*([-*]|\d+\.)\s+", "", cur)])
                else:
                    items[-1][1] += " " + cur.strip()
                i += 1
            numero = 0
            for n, t in items:                       # niveau 0 : numéro ou puce ; sous-niveaux : tiret en retrait
                if n == 0:
                    numero += 1
                    puce = f"{numero}." if ordonne else "•"
                else:
                    puce = "–"
                style = ParagraphStyle(f"li{n}", parent=st["li"], leftIndent=14 + 14 * n, bulletIndent=2 + 14 * n,
                                       bulletFontName="Arial-Bold" if n == 0 else "Arial")
                histoire.append(Paragraph(inline(t), style, bulletText=puce))
            histoire.append(Spacer(1, taille * 0.3)); continue
        if l.strip().startswith(">"):
            para_buffer(buf); buf = []
            bloc = []
            while i < len(lignes) and lignes[i].strip().startswith(">"):
                bloc.append(lignes[i].strip().lstrip(">")); i += 1
            histoire.append(Paragraph(inline(" ".join(bloc)), st["cite"])); continue
        if l.strip() in ("---", "***"):
            para_buffer(buf); buf = []; histoire.append(Spacer(1, taille * 0.5)); i += 1; continue
        if not l.strip():
            para_buffer(buf, "petit" if buf and buf[0].lstrip().startswith("<sub>") else "p"); buf = []; i += 1; continue
        buf.append(l); i += 1
    para_buffer(buf, "petit" if buf and buf[0].lstrip().startswith("<sub>") else "p")
    doc.build(histoire)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("src"); a.add_argument("dst")
    a.add_argument("--taille", type=float, default=10); a.add_argument("--marge", type=float, default=18)
    a.add_argument("--titre", default="InvestIA")
    x = a.parse_args()
    convertir(Path(x.src), Path(x.dst), x.taille, x.marge, x.titre)
