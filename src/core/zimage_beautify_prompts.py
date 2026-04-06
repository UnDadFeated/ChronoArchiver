"""
Beautify mode prompts for Z-Image img2img (AI Image Upscaler).

**Plain upscale** (Beautify off) uses a **minimal-change** refinement prompt and **lower** denoise
than Beautify — prioritize fidelity to the file.

**Beautify** (face detected) targets a **different aesthetic**: **Hollywood publicity still** and
**luxury magazine editorial** — luminous skin, dimensional lighting, camera-ready polish — while
**locking identity** (same person, same bone structure, same defining traits: eye shape, nose, smile,
moles, freckles pattern). This is intentionally stronger img2img than plain upscale (see
``zimage_auto_params``).

**Models:** Z-Image-Turbo img2img; **OpenCV** face box; optional **BLIP** for scene + facial hints.

**Reference mood:** High-end editorial beauty (Vogue / red-carpet / movie poster) — not a beauty-filter
cartoon. Pikaso “high-end skin retouch” remains a secondary editorial reference:
https://www.freepik.com/pikaso/spaces/a160e7da-e42e-41a9-bcfb-c0ae347984e0
"""

from __future__ import annotations

# Canonical Pikaso space (utm params optional for sharing).
PIKASO_HIGH_END_SKIN_SPACE_URL = "https://www.freepik.com/pikaso/spaces/a160e7da-e42e-41a9-bcfb-c0ae347984e0"

# Negatives: quality/anatomy/uncanny + identity drift + color blotches. “Heavy makeup” = garish/clowny;
# editorial makeup is steered in the positive.
BEAUTIFY_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, jpeg artifacts, noise, "
    "bad anatomy, bad proportions, deformed, mutation, "
    "distorted face, asymmetrical face, asymmetrical eyes, lazy eye, cross-eyed, "
    "wrong face, different person, face swap, lookalike, identity change, "
    "uncanny valley, doll face, wax figure, plastic skin, waxy skin, over-smoothed skin, "
    "poorly drawn face, duplicate face, multiple faces, extra limbs, "
    "blush, rouge, blusher, pink cheeks, red cheeks, rosy cheeks, flushed cheeks, blotchy redness, "
    "inflamed skin, sunburned face, bruise, bruised skin, purple shadows on skin, mottled complexion, "
    "grey skin, gray skin, ashy skin, muddy skin, sallow skin, desaturated skin patches, "
    "uneven skin tone, chin discoloration, jaw discoloration, sickly pallor, "
    "garish makeup, clown makeup, cheap beauty filter, heavy Instagram filter, anime face, fake tan streak, "
    "harsh mugshot lighting, flat ugly lighting, amateur snapshot, webcam quality"
)


def build_beautify_positive(
    *,
    freckle_heavy: bool,
    analysis_notes: str | None = None,
) -> str:
    """
    :param freckle_heavy: optional heuristic for denser freckling.
    :param analysis_notes: optional BLIP text (scene + skin + regional hints, sanitized) merged into the prompt.
    """
    # Identity first — then “movie star / cover” polish (research: editorial glam = dimensional light,
    # luminous skin with real texture, refined grade, confident camera-ready presence).
    core = (
        "Hollywood publicity portrait and luxury fashion magazine editorial — photorealistic, 8k uhd, DSLR sharp. "
        "CRITICAL: same real person as the photograph — preserve identity, ethnicity, age, bone structure, "
        "eye shape, nose, smile, jaw, ears, and any distinctive moles or scars; do not morph into another face. "
        "Goal: the most flattering, star-quality version of THIS individual — like a top retoucher prepared "
        "them for a film poster or Vogue beauty spread: dimensional soft key light, subtle Rembrandt or butterfly "
        "feel where it fits the existing photo, gentle separation from background, soft cinematic contrast. "
        "Luminous healthy skin with believable micro-texture and pores — glossy magazine print appeal without plastic. "
        "Refined color grade, controlled highlights, clean shadows, confident rested gaze, defined jawline, camera-ready. "
        "85mm–100mm portrait compression look, shallow depth, premium headshot / cover energy. "
        "Women: sophisticated editorial makeup — defined eyes and lips, even base, red-carpet polish, not garish. "
        "Men: leading-man grooming — matte-satin skin, neat brows and beard if present, subtle under-eye freshness, no lipstick. "
        "Infer presentation from the image. "
        "No muddy grey patches, no bruise-like purple or blotchy red on cheeks, chin, or around the nose."
    )
    if freckle_heavy:
        core += (
            " Dense freckles: keep the pattern recognizable; warm natural freckles with gentle evening of surrounding tone; "
            "no grey halos between freckles, no mottled red jaw."
        )

    base = f"Beautify — magazine / movie-star polish (identity-locked): {core}"
    notes = (analysis_notes or "").strip()
    if notes:
        return f"{base} Local scene and face analysis (hints only — do not override identity): {notes}"
    return base
