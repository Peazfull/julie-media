import io
import json
import os
import uuid
import zipfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / "secrets" / ".env")

# ---------------------------------------------------------------------------
# Config page — doit être le PREMIER appel Streamlit
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Carrousel TDAH",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Streamlit Cloud : injecte st.secrets dans os.environ pour que les modules API
# puissent continuer à utiliser os.getenv("OPENAI_API_KEY")
try:
    for _secret_key, _secret_val in st.secrets.items():
        if _secret_key not in os.environ:
            os.environ[_secret_key] = str(_secret_val)
except Exception:
    pass

from api.generate_carousel import generate_carousel, generate_caption
from api.generate_topics import generate_topics
from utils.drive_uploader import is_drive_configured, upload_carousel
from utils.image_picker import pick_images_for_carousel, reshuffle
from utils.slide_builder import build_carousel, build_single_slide

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

BRAND_GREEN  = "#0c6405"
BRAND_YELLOW = "#ffd275"
CARD_GREEN   = "#e9f5e8"   # fond carte slide paire
CARD_YELLOW  = "#fffbea"   # fond carte slide impaire

# ---------------------------------------------------------------------------
# Accès protégé par mot de passe (optionnel — actif si APP_PASSWORD est défini)
# ---------------------------------------------------------------------------
_app_password = os.environ.get("APP_PASSWORD", "")
if _app_password:
    if not st.session_state.get("_authenticated"):
        st.markdown("""
        <style>
        .login-box { max-width:360px; margin:10vh auto; padding:2.5rem;
            background:#fff; border-radius:16px;
            box-shadow:0 4px 24px rgba(0,0,0,0.10); }
        .login-box h2 { color:#0c6405; margin-bottom:0.2rem; font-size:1.4rem; }
        .login-box p  { color:#888; font-size:0.85rem; margin-bottom:1.5rem; }
        </style>
        <div class="login-box">
          <h2>🧠 Sparky</h2>
          <p>Accès réservé — entre le mot de passe</p>
        </div>
        """, unsafe_allow_html=True)
        pwd = st.text_input("Mot de passe", type="password", label_visibility="collapsed",
                            placeholder="Mot de passe…")
        if st.button("Accéder", type="primary"):
            if pwd == _app_password:
                st.session_state["_authenticated"] = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
        st.stop()

MOOD_EMOJI = {
    "colere": "😠", "content": "😄", "ecole": "🎒",
    "excite": "🤩", "fatigue": "😴", "icones": "⭐",
    "nourriture": "🍎", "parents_adultes": "👨‍👩‍👧",
    "pensif": "🤔", "peur": "😨", "triste": "😢", "zen": "🧘",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_defaults = {"topics": [], "prev_topics": [], "carousels": [], "generating": False}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# CSS global
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* ── Base globale ── */
  html, body, [data-testid="stApp"] {{
    background: #F5F4F0 !important;
    font-family: 'Inter', sans-serif !important;
  }}
  .block-container {{
    padding: 4rem 2.5rem 5rem 2.5rem !important;
    max-width: 1080px !important;
  }}
  section[data-testid="stSidebar"] {{ display: none !important; }}

  /* ── Header simple ── */
  .app-header {{
    display: flex; align-items: center; gap: 14px;
    padding: 0.8rem 0 1rem 0;
    border-bottom: 2px solid {BRAND_GREEN};
    margin-bottom: 1.5rem;
  }}
  .app-header h1 {{
    color: {BRAND_GREEN}; font-size: 1.5rem; font-weight: 900;
    margin: 0; letter-spacing: -0.3px;
  }}

  /* ── Section titles ── */
  .section-title {{
    font-size: 0.72rem; font-weight: 700; color: #999;
    text-transform: uppercase; letter-spacing: 1.2px;
    margin: 2rem 0 0.8rem;
  }}

  /* ── Boutons ── */
  div[data-testid="stButton"] > button,
  div[data-testid="stDownloadButton"] > button {{
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
  }}
  div[data-testid="stButton"] > button:not([kind="primary"]):not(:disabled) {{
    background: #fff !important;
    border: 1.5px solid #DDD9D0 !important;
    color: #1C1C1A !important;
  }}
  div[data-testid="stButton"] > button:not([kind="primary"]):hover {{
    border-color: {BRAND_GREEN} !important;
    color: {BRAND_GREEN} !important;
    box-shadow: 0 2px 10px rgba(12,100,5,0.10) !important;
  }}
  div[data-testid="stButton"] > button[kind="primary"] {{
    background: {BRAND_GREEN} !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(12,100,5,0.25) !important;
  }}
  div[data-testid="stButton"] > button[kind="primary"]:hover {{
    background: #0e7a06 !important;
    box-shadow: 0 4px 16px rgba(12,100,5,0.30) !important;
    transform: translateY(-1px) !important;
  }}

  /* ── Cards carrousel ── */
  .carousel-card {{
    background: #FFFFFF;
    border: 1px solid #E8E5DE;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 2.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.05);
  }}
  .carousel-head {{
    background: linear-gradient(135deg, {BRAND_GREEN} 0%, #1a7a12 100%);
    padding: 1rem 1.4rem;
    display: flex; align-items: center; justify-content: space-between;
  }}
  .carousel-head-title {{
    color: #fff; font-size: 1rem; font-weight: 700;
    font-family: 'Inter', sans-serif;
  }}
  .mood-badge {{
    background: {BRAND_YELLOW}; color: #5a4000;
    padding: 4px 14px; border-radius: 20px;
    font-size: 0.78rem; font-weight: 700;
  }}

  /* ── Slide label badge ── */
  .slide-label {{
    background: #F5F4F0;
    border-bottom: 1px solid #EDEAE4;
    padding: 7px 1.4rem;
    display: flex; align-items: center; gap: 10px;
  }}

  /* ── Action bar ── */
  .action-bar {{
    background: #FAFAF8;
    border-top: 1px solid #EDEAE4;
    padding: 1rem 1.4rem;
    border-radius: 0 0 16px 16px;
  }}

  /* ── Inputs & textareas ── */
  div[data-testid="stTextInput"] input,
  div[data-testid="stTextArea"] textarea {{
    background: #FAFAF8 !important;
    color: #1C1C1A !important;
    border: 1.5px solid #DDD9D0 !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s !important;
  }}
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stTextArea"] textarea:focus {{
    border-color: {BRAND_GREEN} !important;
    box-shadow: 0 0 0 3px rgba(12,100,5,0.08) !important;
    background: #fff !important;
  }}
  label, .stTextArea label, .stTextInput label {{
    font-family: 'Inter', sans-serif !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #888 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
  }}

  /* ── Selectbox couleur ── */
  div[data-testid="stSelectbox"] select,
  div[data-testid="stSelectbox"] > div > div {{
    background: #FFFFFF !important;
    color: #1C1C1A !important;
    border: 1.5px solid #DDD9D0 !important;
    border-radius: 10px !important;
    font-size: 0.9rem !important;
  }}

  /* ── Expander ── */
  div[data-testid="stExpander"] {{
    background: #FFFFFF !important;
    border: 1.5px solid #E8E5DE !important;
    border-radius: 12px !important;
    overflow: hidden !important;
  }}
  div[data-testid="stExpander"] summary {{
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    color: #555 !important;
    padding: 0.6rem 0.8rem !important;
  }}

  /* ── Divider ── */
  hr {{ border: none !important; border-top: 1px solid #EDEAE4 !important; margin: 0 !important; }}

  /* ── Download button ── */
  div[data-testid="stDownloadButton"] > button {{
    background: #fff !important;
    border: 1.5px solid #DDD9D0 !important;
    color: #1C1C1A !important;
  }}
  div[data-testid="stDownloadButton"] > button:hover {{
    border-color: {BRAND_GREEN} !important;
    color: {BRAND_GREEN} !important;
  }}

  /* ── Spinner & messages ── */
  div[data-testid="stAlert"] {{
    border-radius: 10px !important;
    border: none !important;
  }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
SPARKY_IMG = Path(__file__).parent / "assets" / "images" / "content" / "content1.png"

col_logo, col_title = st.columns([1, 12])
with col_logo:
    if SPARKY_IMG.exists():
        st.image(str(SPARKY_IMG), width=56)
with col_title:
    st.markdown('<div class="app-header"><h1>Sparky</h1></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_and_store_carousel(sujet: str, palette_offset: int = 0) -> None:
    with st.spinner(f"✨ Génération du carrousel pour « {sujet} »…"):
        try:
            carousel_data = generate_carousel(sujet)

            humeur = carousel_data.get("humeur", "content")
            n_slides = len(carousel_data.get("slides", []))
            images_paths = pick_images_for_carousel(humeur, n_content_slides=n_slides)
            images_str = {k: str(v) if v else None for k, v in images_paths.items()}

            carousel_id = str(uuid.uuid4())[:8]
            png_paths = build_carousel(
                carousel_dict=carousel_data,
                images=images_str,
                output_dir=OUTPUT_DIR / carousel_id,
                carousel_id=carousel_id,
                palette_offset=palette_offset,
            )
            caption = generate_caption(
                sujet=sujet,
                hook=carousel_data.get("hook", ""),
                slides=carousel_data.get("slides", []),
            )
        except Exception as exc:
            import traceback
            st.error(f"Erreur génération : {exc}")
            st.code(traceback.format_exc())
            return

        st.session_state.carousels.insert(0, {
            "id": carousel_id, "sujet": sujet,
            "data": carousel_data, "humeur": humeur,
            "images": images_str, "png_paths": png_paths,
            "palette_offset": palette_offset,
            "caption": caption,
        })


def _rebuild_single(carousel_idx: int, slide_pos: int) -> None:
    """Rebuilde uniquement une slide et met à jour png_paths."""
    c   = st.session_state.carousels[carousel_idx]
    cid = c["id"]
    n   = len(c["data"].get("slides", []))
    # Reconstruit edited_data à partir des session_state courants
    edited_slides = [
        {
            "title":   st.session_state.get(f"{cid}_slide_{i}_title",   c["data"]["slides"][i].get("title", "")),
            "content": st.session_state.get(f"{cid}_slide_{i}_content", c["data"]["slides"][i].get("content", "")),
        }
        for i in range(n)
    ]
    edited_data = {
        "hook":   st.session_state.get(f"{cid}_hook",  c["data"].get("hook", "")),
        "slides": edited_slides,
        "outro":  st.session_state.get(f"{cid}_outro", c["data"].get("outro", "")),
        "humeur": c["data"].get("humeur", "content"),
    }
    new_path = build_single_slide(
        carousel_dict=edited_data, images=c["images"],
        output_dir=OUTPUT_DIR / cid, carousel_id=cid,
        slide_pos=slide_pos,
        palette_offset=c.get("palette_offset", 0),
    )
    st.session_state.carousels[carousel_idx]["data"] = edited_data
    png_paths = list(c["png_paths"])
    if slide_pos < len(png_paths):
        png_paths[slide_pos] = new_path
    else:
        png_paths.append(new_path)
    st.session_state.carousels[carousel_idx]["png_paths"] = png_paths


def _rebuild_carousel(idx: int) -> None:
    c = st.session_state.carousels[idx]
    cid = c["id"]
    n_slides = len(c["data"].get("slides", []))
    edited_slides = [
        {
            "title":   st.session_state.get(f"{cid}_slide_{i}_title",   c["data"]["slides"][i].get("title", "")),
            "content": st.session_state.get(f"{cid}_slide_{i}_content", c["data"]["slides"][i].get("content", "")),
        }
        for i in range(n_slides)
    ]
    edited_data = {
        "hook":   st.session_state.get(f"{cid}_hook",  c["data"].get("hook", "")),
        "slides": edited_slides,
        "outro":  st.session_state.get(f"{cid}_outro", c["data"].get("outro", "")),
        "humeur": c["data"].get("humeur", "content"),
    }
    png_paths = build_carousel(
        carousel_dict=edited_data, images=c["images"],
        output_dir=OUTPUT_DIR / cid, carousel_id=cid,
        palette_offset=c.get("palette_offset", 0),
    )
    st.session_state.carousels[idx]["data"] = edited_data
    st.session_state.carousels[idx]["png_paths"] = png_paths


def _make_zip(carousel: dict, caption_override: str = "") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in carousel["png_paths"]:
            p = Path(path)
            if p.exists():
                zf.write(p, p.name)
        zf.writestr("carousel.json", json.dumps(
            {"sujet": carousel["sujet"], "slides": carousel["data"]},
            ensure_ascii=False, indent=2,
        ))
        caption_text = caption_override or carousel.get("caption", "")
        if caption_text:
            zf.writestr("caption.txt", caption_text)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Section — Génération de sujets
# ---------------------------------------------------------------------------
st.markdown('<p class="section-title">💡 Choisis un sujet</p>', unsafe_allow_html=True)

btn_gen, btn_new = st.columns([2, 1])
with btn_gen:
    if st.button("✨ Générer des sujets", use_container_width=True, type="primary"):
        with st.spinner("Recherche de sujets…"):
            try:
                topics = generate_topics(st.session_state.prev_topics)
                st.session_state.topics = topics
                st.session_state.prev_topics = list(set(st.session_state.prev_topics + topics))[-30:]
            except Exception as exc:
                st.error(f"Erreur API : {exc}")
with btn_new:
    if st.session_state.topics:
        if st.button("🔀 Nouveaux sujets", use_container_width=True):
            with st.spinner("Nouveaux sujets…"):
                try:
                    topics = generate_topics(st.session_state.prev_topics)
                    st.session_state.topics = topics
                    st.session_state.prev_topics = list(set(st.session_state.prev_topics + topics))[-30:]
                except Exception as exc:
                    st.error(f"Erreur API : {exc}")

start_color = st.selectbox(
    "Couleur slide 1 :",
    ["🟢 Commencer en vert", "🟡 Commencer en jaune"],
    index=0,
    key="start_color_select",
    label_visibility="visible",
)

def _get_palette_offset() -> int:
    return 1 if "jaune" in st.session_state.get("start_color_select", "vert").lower() else 0

# Grille 2 colonnes pour les topics
if st.session_state.topics:
    st.markdown("<p style='font-size:0.85rem;color:#888;margin:0.5rem 0 0.25rem'>Clique sur un sujet pour générer son carrousel</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    for i, topic in enumerate(st.session_state.topics):
        col = c1 if i % 2 == 0 else c2
        with col:
            if st.button(f"📌  {topic}", use_container_width=True, key=f"topic_{topic}"):
                _build_and_store_carousel(topic, palette_offset=_get_palette_offset())
                st.rerun()

# Sujet personnalisé dans un expander
with st.expander("✏️  Sujet personnalisé"):
    custom_cols = st.columns([5, 1])
    with custom_cols[0]:
        custom_sujet = st.text_input(
            "Sujet", placeholder="Ex : 5 routines matinales pour enfants TDAH",
            label_visibility="collapsed",
        )
    with custom_cols[1]:
        if st.button("➕ Créer", use_container_width=True, type="primary"):
            if custom_sujet.strip():
                _build_and_store_carousel(custom_sujet.strip(), palette_offset=_get_palette_offset())
                st.rerun()
            else:
                st.warning("Entre un sujet d'abord.")

# ---------------------------------------------------------------------------
# Section — Carrousels générés
# ---------------------------------------------------------------------------
if st.session_state.carousels:
    st.markdown('<p class="section-title">🖼️ Carrousels générés</p>', unsafe_allow_html=True)

for idx, carousel in enumerate(st.session_state.carousels):
    cid      = carousel["id"]
    humeur   = carousel["humeur"]
    emoji    = MOOD_EMOJI.get(humeur, "✨")
    slides_data  = carousel["data"].get("slides", [])
    n_content    = len(slides_data)
    total_slides = n_content + 2

    # ── Wrapper card ──────────────────────────────────────────────────────
    st.markdown('<div class="carousel-card">', unsafe_allow_html=True)

    # Header
    head_l, head_r = st.columns([8, 1])
    with head_l:
        st.markdown(
            f'<div class="carousel-head">'
            f'<span class="carousel-head-title">📌 {carousel["sujet"]}</span>'
            f'<span class="mood-badge">{emoji} {humeur}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with head_r:
        if st.button("🗑️", key=f"del_{cid}", help="Supprimer"):
            st.session_state.carousels.pop(idx)
            st.rerun()

    # ── Slides : layout vertical ──────────────────────────────────────────
    def _slide_row(label, slide_index, png_path, img_key, fields, badge_color, bg, slide_pos):
        """Une slide = étiquette colorée + [image | champs] alignés nativement."""

        # Étiquette slide (bande colorée fine)
        st.markdown(
            f'<div style="background:{bg};border-radius:8px;padding:6px 12px;'
            f'margin-bottom:6px;display:flex;align-items:center;gap:8px;">'
            f'<span style="background:{badge_color};color:#fff;font-size:0.72rem;'
            f'font-weight:800;padding:2px 10px;border-radius:20px;">'
            f'{slide_index + 1} / {total_slides}</span>'
            f'<span style="font-size:0.82rem;color:#444;font-weight:600;">{label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        col_img, col_fields = st.columns([1, 2], gap="large")

        with col_img:
            if png_path and Path(png_path).exists():
                st.image(png_path, use_container_width=True)
            else:
                st.markdown(
                    "<div style='aspect-ratio:1;background:#eee;border-radius:8px;"
                    "display:flex;align-items:center;justify-content:center;"
                    "color:#bbb;font-size:0.8rem;'>Pas d'image</div>",
                    unsafe_allow_html=True,
                )
            img_path = carousel["images"].get(img_key)
            if st.button("🔀 Changer l'image", key=f"reshuffle_{cid}_{img_key}",
                         use_container_width=True):
                new_img = reshuffle(humeur, exclude_path=Path(img_path) if img_path else None)
                st.session_state.carousels[idx]["images"][img_key] = str(new_img) if new_img else None
                _rebuild_carousel(idx)
                st.rerun()

        with col_fields:
            for (state_key, field_label, default_val, height) in fields:
                if state_key not in st.session_state:
                    st.session_state[state_key] = default_val
                st.text_area(field_label, key=state_key, height=height)

            if st.button("↻ Actualiser cette slide",
                         key=f"refresh_{cid}_{img_key}",
                         use_container_width=True):
                _rebuild_single(idx, slide_pos)
                st.rerun()

        st.divider()

    # Hook
    _slide_row(
        label="🎣 Hook", slide_index=0,
        png_path=carousel["png_paths"][0] if carousel["png_paths"] else None,
        img_key="hook",
        fields=[(f"{cid}_hook", "Texte du hook", carousel["data"].get("hook", ""), 100)],
        badge_color=BRAND_GREEN, bg=CARD_GREEN,
        slide_pos=0,
    )

    # Slides contenu
    for i, slide in enumerate(slides_data):
        bg = CARD_GREEN if (i + 1) % 2 == 0 else CARD_YELLOW
        badge_color = BRAND_GREEN if (i + 1) % 2 == 0 else "#b8860b"
        png_path = carousel["png_paths"][i + 1] if (i + 1) < len(carousel["png_paths"]) else None
        _slide_row(
            label=f"💡 Point {i + 1}", slide_index=i + 1,
            png_path=png_path, img_key=f"slide_{i}",
            fields=[
                (f"{cid}_slide_{i}_title",   "Titre (Anton)",   slide.get("title", ""),   70),
                (f"{cid}_slide_{i}_content", "Contenu (Poppins)", slide.get("content", ""), 110),
            ],
            badge_color=badge_color, bg=bg,
            slide_pos=i + 1,
        )

    # Outro
    outro_idx = total_slides - 1
    outro_bg = CARD_GREEN if outro_idx % 2 == 0 else CARD_YELLOW
    outro_badge = BRAND_GREEN if outro_idx % 2 == 0 else "#b8860b"
    _slide_row(
        label="🙌 Outro", slide_index=outro_idx,
        png_path=carousel["png_paths"][outro_idx] if outro_idx < len(carousel["png_paths"]) else None,
        img_key="outro",
        fields=[(f"{cid}_outro", "Texte outro", carousel["data"].get("outro", ""), 110)],
        badge_color=outro_badge, bg=outro_bg,
        slide_pos=outro_idx,
    )

    # ── Caption TikTok / Instagram ─────────────────────────────────────────
    st.markdown(
        '<p style="font-size:0.72rem;font-weight:700;color:#999;text-transform:uppercase;'
        'letter-spacing:1.2px;margin:1.5rem 0 0.4rem;">📱 Caption TikTok / Instagram</p>',
        unsafe_allow_html=True,
    )
    caption_key = f"{cid}_caption"
    if caption_key not in st.session_state:
        st.session_state[caption_key] = carousel.get("caption", "")
    st.text_area(
        "Caption", key=caption_key, height=180, label_visibility="collapsed",
    )
    cap_col1, cap_col2 = st.columns([1, 4])
    with cap_col1:
        if st.button("↻ Regénérer la caption", key=f"regen_caption_{cid}", use_container_width=True):
            with st.spinner("Génération de la caption…"):
                try:
                    new_cap = generate_caption(
                        sujet=carousel["sujet"],
                        hook=carousel["data"].get("hook", ""),
                        slides=carousel["data"].get("slides", []),
                    )
                    st.session_state[caption_key] = new_cap
                    st.session_state.carousels[idx]["caption"] = new_cap
                except Exception as e:
                    st.error(f"Erreur caption : {e}")
            st.rerun()

    # ── Action bar ────────────────────────────────────────────────────────
    st.markdown('<div class="action-bar">', unsafe_allow_html=True)
    act1, act2, act3, act4 = st.columns(4)

    with act1:
        if st.button("🔄  Regénérer les slides", key=f"regen_{cid}", use_container_width=True, type="primary"):
            _rebuild_carousel(idx)
            st.rerun()

    with act2:
        current_offset = carousel.get("palette_offset", 0)
        inv_label = "🟡 Passer en jaune" if current_offset == 0 else "🟢 Passer en vert"
        if st.button(inv_label, key=f"invert_{cid}", use_container_width=True):
            new_offset = 1 - current_offset
            st.session_state.carousels[idx]["palette_offset"] = new_offset
            _rebuild_carousel(idx)
            st.rerun()

    with act3:
        st.download_button(
            label="⬇️  Télécharger ZIP",
            data=_make_zip(carousel, caption_override=st.session_state.get(f"{cid}_caption", "")),
            file_name=f"carousel_{cid}.zip",
            mime="application/zip",
            use_container_width=True,
            key=f"zip_{cid}",
        )

    with act4:
        if not is_drive_configured():
            st.button("🚧  Drive (GCP non configuré)", disabled=True,
                      use_container_width=True, key=f"drive_dis_{cid}")
        else:
            if st.button("📤  Envoyer vers Drive", use_container_width=True, key=f"drive_{cid}"):
                with st.spinner("Upload…"):
                    result = upload_carousel(carousel["png_paths"], cid)
                    if result["status"] == "ok":
                        st.success(f"✅ Uploadé — dossier : {result['folder_id']}")
                    elif result["status"] == "not_configured":
                        st.warning("GCP non configuré.")
                    else:
                        st.error(f"Erreur : {result.get('message')}")

    st.markdown("</div>", unsafe_allow_html=True)  # action-bar
    st.markdown("</div>", unsafe_allow_html=True)  # carousel-card
