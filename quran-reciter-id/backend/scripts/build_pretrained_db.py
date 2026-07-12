"""
Build reciter_database.json + reciters_metadata.json from the
open-source HuggingFace model `iarhamanwaar/quran-reciter-id-ecapa`
which ships pretrained centroids for 364 famous Quran reciters.

Runs at CI build time (or manually) so the final EXE ships with a
ready-to-use fingerprint database — no model training needed.
"""
from __future__ import annotations
import json, re, sys, urllib.request
from pathlib import Path

HF_BASE = "https://huggingface.co/iarhamanwaar/quran-reciter-id-ecapa/resolve/main"

# --- Arabic name overrides for the most famous reciters ------------------
# The HF metadata stores transliterated English names. We map the well-known
# ones to their proper Arabic display name. Anything not in this map falls
# back to the transliteration (still recognizable, just in English letters).
ARABIC_NAMES = {
    "Abdulbasit_Abdulsamad_(MP3_Quran)": ("عبد الباسط عبد الصمد", "مصر"),
    "Abdulbasit_Abdulsamad_Mojawwad_(MP3_Quran)": ("عبد الباسط عبد الصمد - مجوّد", "مصر"),
    "Abdulbasit_Abdussamad_Warsh_an_Nafi_(MP3_Quran)": ("عبد الباسط - ورش عن نافع", "مصر"),
    "Abdulbari_Ath-Thubaity_(MP3_Quran)": ("عبد الباري الثبيتي", "السعودية"),
    "Abdurrahman_Alsudaes_(MP3_Quran)": ("عبد الرحمن السديس", "السعودية"),
    "Abdurrahman_As-Sudais_(MP3_Quran)": ("عبد الرحمن السديس", "السعودية"),
    "Saud_Alshuraim_(MP3_Quran)": ("سعود الشريم", "السعودية"),
    "Mishary_Rashid_Alafasy_(MP3_Quran)": ("مشاري راشد العفاسي", "الكويت"),
    "Mishari_Rashid_Alafasy_(MP3_Quran)": ("مشاري راشد العفاسي", "الكويت"),
    "Maher_Almuaiqly_(MP3_Quran)": ("ماهر المعيقلي", "السعودية"),
    "Ahmed_Alajmi_(MP3_Quran)": ("أحمد بن علي العجمي", "السعودية"),
    "Saad_Alghamdi_(MP3_Quran)": ("سعد الغامدي", "السعودية"),
    "Ali_Alhudaify_(MP3_Quran)": ("علي الحذيفي", "السعودية"),
    "Muhammad_Ayoub_(MP3_Quran)": ("محمد أيوب", "السعودية"),
    "Muhammad_Sideeq_Alminshawi_(MP3_Quran)": ("محمد صديق المنشاوي", "مصر"),
    "Mahmoud_Khalil_Alhussary_(MP3_Quran)": ("محمود خليل الحصري", "مصر"),
    "Yasser_Aldosari_(MP3_Quran)": ("ياسر الدوسري", "السعودية"),
    "Nasser_Alqatami_(MP3_Quran)": ("ناصر القطامي", "السعودية"),
    "Idrees_Abkar_(MP3_Quran)": ("إدريس أبكر", "السعودية"),
    "Fares_Abbad_(MP3_Quran)": ("فارس عباد", "اليمن"),
    "Hani_Arrifai_(MP3_Quran)": ("هاني الرفاعي", "السعودية"),
    "Khalid_Aljalil_(MP3_Quran)": ("خالد الجليل", "السعودية"),
    "Salah_Bukhatir_(MP3_Quran)": ("صلاح بوخاطر", "الإمارات"),
    "Abdullah_Basfer_(MP3_Quran)": ("عبد الله بصفر", "السعودية"),
    "Abdullah_Khayyat_(MP3_Quran)": ("عبد الله خياط", "السعودية"),
    "Abdullah_Awad_Aljuhany_(MP3_Quran)": ("عبد الله الجهني", "السعودية"),
    "Bandar_Balila_(MP3_Quran)": ("بندر بليلة", "السعودية"),
    "Aadel_Alkalbani_(MP3_Quran)": ("عادل الكلباني", "السعودية"),
}


def _friendly(en_key: str) -> tuple[str, str]:
    if en_key in ARABIC_NAMES:
        return ARABIC_NAMES[en_key]
    display = re.sub(r"_\(MP3_Quran\)$", "", en_key).replace("_", " ").strip()
    return display, "غير محدد"


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        return
    print(f"↓ {url}")
    urllib.request.urlretrieve(url, dst)


def main() -> int:
    out_dir = Path(__file__).resolve().parent.parent / "data"
    emb_dir = out_dir / "embeddings"
    tmp_dir = out_dir / "_pretrained_cache"

    metadata_pt = tmp_dir / "metadata.json"
    centroids_pt = tmp_dir / "centroids.pt"
    _download(f"{HF_BASE}/metadata.json", metadata_pt)
    _download(f"{HF_BASE}/centroids.pt", centroids_pt)

    import torch  # imported after download to keep the script light on failure
    meta = json.loads(metadata_pt.read_text(encoding="utf-8"))
    id_to_reciter: dict[str, str] = meta["id_to_reciter"]
    centroids = torch.load(centroids_pt, map_location="cpu", weights_only=False)
    # shape: [num_reciters, k_subcentroids, embedding_dim]
    if centroids.dim() == 3:
        vectors = centroids.mean(dim=1)  # average sub-centroids -> [N, dim]
    else:
        vectors = centroids
    vectors = torch.nn.functional.normalize(vectors, p=2, dim=1)

    reciters_emb, reciters_meta = [], []
    for idx_str, en_key in id_to_reciter.items():
        i = int(idx_str)
        display, country = _friendly(en_key)
        reciters_emb.append({
            "reciter_name": display,
            "embedding": vectors[i].tolist(),
        })
        reciters_meta.append({
            "name": display,
            "name_english": en_key.replace("_", " "),
            "country": country,
            "bio": "مصدر البصمة: النموذج المفتوح المصدر iarhamanwaar/quran-reciter-id-ecapa على HuggingFace.",
            "birth_year": "-",
            "death_year": None,
            "image_url": "",
            "recitation_style": "حفص عن عاصم",
        })

    emb_dir.mkdir(parents=True, exist_ok=True)
    (emb_dir / "reciter_database.json").write_text(json.dumps({
        "version": "hf-ecapa-v1",
        "source": "iarhamanwaar/quran-reciter-id-ecapa",
        "embedding_dim": int(vectors.shape[1]),
        "reciters": reciters_emb,
    }, ensure_ascii=False), encoding="utf-8")

    (out_dir / "reciters_metadata.json").write_text(json.dumps({
        "reciters": reciters_meta,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ built database with {len(reciters_emb)} reciters "
          f"(dim={vectors.shape[1]}) → {emb_dir / 'reciter_database.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
