from __future__ import annotations

import random
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Constantes de layout
# ---------------------------------------------------------------------------
SLIDE_W, SLIDE_H = 1080, 1350   # format 4:5 Instagram portrait
SLIDE_SIZE = (SLIDE_W, SLIDE_H)
SLIDE_MID  = SLIDE_H // 2       # 675 — limite entre zone texte et zone mascotte

MARGIN_LEFT  = 80
MARGIN_RIGHT = 140                     # marge droite élargie (évite icônes réseau)
MARGIN       = MARGIN_LEFT             # alias pour usage général (pagination, décors)
TEXT_W       = SLIDE_W - MARGIN_LEFT - MARGIN_RIGHT   # 860 px disponibles en largeur

DECO_SIZE   = 158                      # hauteur icônes coins (132 × 1.2)
DECO_MARGIN = 30
# Le texte ne commence jamais avant la fin des icônes décoratives
TEXT_Y_MIN  = DECO_MARGIN + DECO_SIZE + 25   # ≈ 165 px du haut

BOTTOM_RESERVE = 90   # espace bas pour pagination + flèche
CONTENT_BOTTOM = SLIDE_H - BOTTOM_RESERVE  # 990 → limite basse du contenu

ARROW_HEIGHT = 204                     # 170 × 1.2

FONTS_DIR    = Path(__file__).parent.parent / "assets" / "fonts"
FONT_ANTON   = FONTS_DIR / "Anton-Regular.ttf"
FONT_POPPINS = FONTS_DIR / "Poppins-Medium.ttf"

ICONS_DIR    = Path(__file__).parent.parent / "assets" / "ICONES"
ARROW_YELLOW = ICONS_DIR / "JAUNE" / "fleche.png"
ARROW_GREEN  = ICONS_DIR / "VERT"  / "fleche.png"

DECO_ICONS = {
    0: [ICONS_DIR / "JAUNE" / "etoiles.png"],
    1: [ICONS_DIR / "VERT"  / "ballon.png", ICONS_DIR / "VERT" / "confetti.png"],
}

PALETTE = [
    {"bg": "#0c6405", "text": "#FFFFFF", "accent": "#ffd275"},
    {"bg": "#ffd275", "text": "#1A1A1A", "accent": "#0c6405"},
]

MARKUP_RE = re.compile(r'==(.+?)==|\*(.+?)\*')

# ---------------------------------------------------------------------------
# Polices
# ---------------------------------------------------------------------------

def _font(path: Path, size: int):
    if path.exists():
        return ImageFont.truetype(str(path), size)
    for fb in ["/System/Library/Fonts/Helvetica.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(fb, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _strip_emojis(text: str) -> str:
    pat = re.compile(
        "[" "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF" "\U0001F1E0-\U0001F1FF"
        "\U00002500-\U00002BEF" "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251" "\U0001F926-\U0001FA9F"
        "\U00010000-\U0010FFFF"
        "\u200d\u2640-\u2642\u2600-\u2B55\u23cf\u23e9\u231a\ufe0f\u3030"
        "]+", flags=re.UNICODE,
    )
    return pat.sub("", text).strip()


# ---------------------------------------------------------------------------
# Taille automatique (seuils révisés, minimums plus grands)
# ---------------------------------------------------------------------------

def _auto_size(n: int, large: int, medium: int, small: int) -> int:
    if n <= 35:   return large
    if n <= 75:   return medium
    return small


# ---------------------------------------------------------------------------
# Parser markup & builder de lignes
# ---------------------------------------------------------------------------

def _parse_tokens(text: str) -> list:
    tokens, last = [], 0
    for m in MARKUP_RE.finditer(text):
        if m.start() > last:
            for w in text[last:m.start()].split():
                tokens.append((w, "normal"))
        style = "highlight" if m.group(1) else "accent"
        tokens.append(((m.group(1) or m.group(2)).strip(), style))
        last = m.end()
    for w in text[last:].split():
        tokens.append((w, "normal"))
    return tokens


def _measure(draw, text: str, font) -> float:
    """Mesure la largeur réelle du texte via textbbox (plus précis qu'textlength pour Anton)."""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return float(bb[2] - bb[0])
    except Exception:
        try:
            return draw.textlength(text, font=font)
        except Exception:
            return len(text) * getattr(font, "size", 20) * 0.55


def _build_lines(tokens: list, font_n, font_s, max_w: int, draw) -> tuple:
    space_w = _measure(draw, " ", font_n)
    lines, cur, cur_w = [], [], 0.0
    for text, style in tokens:
        if style == "newline":
            lines.append(cur if cur else []); cur = []; cur_w = 0.0
            continue
        f = font_s if style != "normal" else font_n
        tw = _measure(draw, text, f)
        if cur and cur_w + space_w + tw > max_w:
            lines.append(cur); cur = [(text, style, tw)]; cur_w = tw
        else:
            if cur: cur_w += space_w
            cur.append((text, style, tw)); cur_w += tw
    if cur: lines.append(cur)
    return lines, space_w


def _parse_tokens_multiline(text: str) -> list:
    """Comme _parse_tokens mais préserve les sauts de ligne (\n) comme tokens spéciaux."""
    tokens = []
    for i, segment in enumerate(text.split('\n')):
        if i > 0:
            tokens.append(('\n', 'newline'))
        tokens.extend(_parse_tokens(segment))
    return tokens


# ---------------------------------------------------------------------------
# Rendu rich text
# ---------------------------------------------------------------------------

def _render_lines(draw, lines: list, x0: int, y0: int, area_w: int,
                  fn, fs, tc: str, ac: str,
                  lh: int, sw: float) -> int:
    y = y0
    for line in lines:
        if line:   # ligne vide (saut de ligne forcé) → on avance juste de lh
            lw = sum(tw for _, _, tw in line) + sw * max(0, len(line) - 1)
            x  = max(float(x0), x0 + (area_w - lw) / 2)
            for text, style, tw in line:
                f    = fs if style != "normal" else fn
                fill = ac if style in ("highlight", "accent") else tc
                draw.text((int(x), int(y)), text, font=f, fill=fill)
                x += tw + sw
        y += lh
    return int(y)


def _block_h(lines: list, lh: int) -> int:
    return len(lines) * lh


# ---------------------------------------------------------------------------
# Mascotte proportionnelle
# ---------------------------------------------------------------------------

def _paste_mascot(img: Image.Image, path, text_bottom: int) -> None:
    if not path: return
    p = Path(path)
    if not p.exists(): return
    try:
        raw = Image.open(p).convert("RGBA")
        # Espace disponible entre fin de texte et bas de la zone contenu
        gap   = 20
        avail_h = CONTENT_BOTTOM - text_bottom - gap
        avail_w = SLIDE_W - 2 * MARGIN
        # Mascotte : entre 150 et 400 px de haut
        th = max(150, min(400, int(avail_h * 0.92)))
        tw = int(raw.width * th / raw.height)
        if tw > avail_w:
            tw = avail_w; th = int(raw.height * tw / raw.width)
        mascot = raw.resize((tw, th), Image.LANCZOS)
        mx = (SLIDE_W - tw) // 2
        my = text_bottom + gap + max(0, (avail_h - th) // 2)
        img.paste(mascot, (mx, my), mascot)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Décors
# ---------------------------------------------------------------------------

def _paste_arrow(img: Image.Image, pi: int, offset: int = 0) -> None:
    path = ARROW_YELLOW if (pi + offset) % 2 == 0 else ARROW_GREEN
    if not path.exists(): return
    try:
        a = Image.open(path).convert("RGBA")
        nh = ARROW_HEIGHT; nw = int(a.width * nh / a.height)
        a  = a.resize((nw, nh), Image.LANCZOS)
        img.paste(a, (SLIDE_W - nw - 40, SLIDE_H - nh - 40), a)
    except Exception:
        pass


def _paste_corner_deco(img: Image.Image, pi: int, force_both: bool = False, offset: int = 0) -> None:
    avail = [p for p in DECO_ICONS.get((pi + offset) % 2, []) if p.exists()]
    if not avail: return
    placement = "both" if force_both else random.choice(["left", "right", "both"])
    corners   = ["left", "right"] if placement == "both" else [placement]

    def _load(p: Path):
        ic = Image.open(p).convert("RGBA")
        nh = DECO_SIZE; nw = int(ic.width * nh / ic.height)
        return ic.resize((nw, nh), Image.LANCZOS)

    for corner in corners:
        ic = _load(random.choice(avail))
        iw, _ = ic.size
        x = DECO_MARGIN if corner == "left" else SLIDE_W - iw - DECO_MARGIN
        img.paste(ic, (x, DECO_MARGIN), ic)


def _draw_number(draw, num: str, total: int, tc: str) -> None:
    f = _font(FONT_POPPINS, 30)
    draw.text((MARGIN, SLIDE_H - 40 - 30), f"{num} / {total}", font=f, fill=tc)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _base(pi: int, offset: int = 0):
    c   = PALETTE[(pi + offset) % 2]
    img = Image.new("RGB", SLIDE_SIZE, color=c["bg"])
    draw = ImageDraw.Draw(img)
    return img, draw, c


def _build_hook(text: str, img_path, idx: int, out: Path, total: int = 5,
                palette_offset: int = 0) -> str:
    img, draw, c = _base(idx, palette_offset)
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    clean = _strip_emojis(text)
    n     = len(re.sub(r'[=*]', '', clean))
    fs    = _auto_size(n, large=110, medium=94, small=80)
    lh    = int(fs * 1.22 * 1.1)   # interligne élargi pour le hook
    font  = _font(FONT_ANTON, fs)

    tokens        = _parse_tokens_multiline(clean)
    lines, sw     = _build_lines(tokens, font, font, TEXT_W, dummy)
    bh            = _block_h(lines, lh)

    text_zone_h   = SLIDE_MID - TEXT_Y_MIN
    y0            = TEXT_Y_MIN + max(0, (text_zone_h - bh) // 2)

    text_bottom   = _render_lines(draw, lines, MARGIN, y0, TEXT_W,
                                  font, font, c["text"], c["accent"], lh, sw)

    _paste_mascot(img, img_path, text_bottom)
    _paste_corner_deco(img, idx, force_both=True, offset=palette_offset)
    _paste_arrow(img, idx, offset=palette_offset)
    _draw_number(draw, "1", total, c["text"])

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), "PNG")
    return str(out)


def _build_content(title: str, content: str, img_path, idx: int,
                   out: Path, slide_num: str, total: int = 5,
                   palette_offset: int = 0) -> str:
    img, draw, c = _base(idx, palette_offset)
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    clean_t = _strip_emojis(title)
    clean_b = _strip_emojis(content)
    n_t     = len(re.sub(r'[=*]', '', clean_t))
    fs_t    = _auto_size(n_t, large=92, medium=78, small=66)
    lh_t    = int(fs_t * 1.18)
    ft      = _font(FONT_ANTON, fs_t)

    n_b     = len(re.sub(r'[=*]', '', clean_b))
    fs_b    = _auto_size(n_b, large=60, medium=54, small=48)
    lh_b    = int(fs_b * 1.48)
    fb      = _font(FONT_POPPINS, fs_b)

    tok_t, tok_b  = _parse_tokens_multiline(clean_t), _parse_tokens_multiline(clean_b)
    lines_t, sw_t = _build_lines(tok_t, ft, ft, TEXT_W, dummy)
    lines_b, sw_b = _build_lines(tok_b, fb, fb, TEXT_W, dummy)

    GAP = 33   # interligne titre → contenu (22 × 1.5)
    bh_total = _block_h(lines_t, lh_t) + GAP + _block_h(lines_b, lh_b)

    text_zone_h = SLIDE_MID - TEXT_Y_MIN
    y0 = TEXT_Y_MIN + max(0, (text_zone_h - bh_total) // 2)

    y1 = _render_lines(draw, lines_t, MARGIN, y0, TEXT_W,
                       ft, ft, c["text"], c["accent"], lh_t, sw_t)
    text_bottom = _render_lines(draw, lines_b, MARGIN, y1 + GAP, TEXT_W,
                                fb, fb, c["text"], c["accent"], lh_b, sw_b)

    _paste_mascot(img, img_path, text_bottom)
    _paste_corner_deco(img, idx, offset=palette_offset)
    _paste_arrow(img, idx, offset=palette_offset)
    _draw_number(draw, slide_num, total, c["text"])

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), "PNG")
    return str(out)


def _build_outro(text: str, img_path, idx: int, out: Path, total: int = 5,
                 palette_offset: int = 0) -> str:
    img, draw, c = _base(idx, palette_offset)
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    clean = _strip_emojis(text)
    n    = len(re.sub(r'[=*]', '', clean))
    fs   = _auto_size(n, large=64, medium=56, small=50)
    lh   = int(fs * 1.5)
    font = _font(FONT_POPPINS, fs)

    tokens       = _parse_tokens_multiline(clean)
    lines, sw    = _build_lines(tokens, font, font, TEXT_W, dummy)
    bh           = _block_h(lines, lh)

    text_zone_h  = SLIDE_MID - TEXT_Y_MIN
    y0           = TEXT_Y_MIN + max(0, (text_zone_h - bh) // 2)

    text_bottom  = _render_lines(draw, lines, MARGIN, y0, TEXT_W,
                                 font, font, c["text"], c["accent"], lh, sw)

    _paste_mascot(img, img_path, text_bottom)
    _paste_corner_deco(img, idx, offset=palette_offset)
    _draw_number(draw, str(total), total, c["text"])

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), "PNG")
    return str(out)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def build_single_slide(carousel_dict: dict, images: dict,
                       output_dir, carousel_id: str, slide_pos: int,
                       palette_offset: int = 0) -> str:
    """
    Rebuilde uniquement la slide à la position `slide_pos` (0-based dans la liste finale :
      0 = hook, 1..N = content slides, N+1 = outro).
    Retourne le path PNG mis à jour.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slides = carousel_dict.get("slides", [])
    total  = len(slides) + 2

    if slide_pos == 0:
        return _build_hook(
            text=carousel_dict.get("hook", ""),
            img_path=images.get("hook"),
            idx=0,
            out=output_dir / f"{carousel_id}_01_hook.png",
            total=total,
            palette_offset=palette_offset,
        )
    elif slide_pos == total - 1:
        return _build_outro(
            text=carousel_dict.get("outro", ""),
            img_path=images.get("outro"),
            idx=len(slides) + 1,
            out=output_dir / f"{carousel_id}_{total:02d}_outro.png",
            total=total,
            palette_offset=palette_offset,
        )
    else:
        i = slide_pos - 1
        slide = slides[i]
        return _build_content(
            title=slide.get("title", ""),
            content=slide.get("content", ""),
            img_path=images.get(f"slide_{i}"),
            idx=i + 1,
            out=output_dir / f"{carousel_id}_{i + 2:02d}_slide{i + 1}.png",
            slide_num=str(i + 2),
            total=total,
            palette_offset=palette_offset,
        )


def build_carousel(carousel_dict: dict, images: dict,
                   output_dir, carousel_id: str = "carousel",
                   palette_offset: int = 0) -> list:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    slides = carousel_dict.get("slides", [])
    total  = len(slides) + 2
    paths  = []

    paths.append(_build_hook(
        text=carousel_dict.get("hook", ""),
        img_path=images.get("hook"),
        idx=0,
        out=output_dir / f"{carousel_id}_01_hook.png",
        total=total,
        palette_offset=palette_offset,
    ))
    for i, slide in enumerate(slides):
        paths.append(_build_content(
            title=slide.get("title", ""),
            content=slide.get("content", ""),
            img_path=images.get(f"slide_{i}"),
            idx=i + 1,
            out=output_dir / f"{carousel_id}_{i + 2:02d}_slide{i + 1}.png",
            slide_num=str(i + 2),
            total=total,
            palette_offset=palette_offset,
        ))
    paths.append(_build_outro(
        text=carousel_dict.get("outro", ""),
        img_path=images.get("outro"),
        idx=len(slides) + 1,
        out=output_dir / f"{carousel_id}_{total:02d}_outro.png",
        total=total,
        palette_offset=palette_offset,
    ))
    return paths
