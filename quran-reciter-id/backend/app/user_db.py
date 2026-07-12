"""
User Reciter Database — persistent storage for user-uploaded reciters.
Stored in %APPDATA%/QuranReciterID (Windows) or ~/.quran_reciter_id (other).
Survives across EXE restarts and updates.
"""
import os, json, shutil, time
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


def user_data_dir() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"]) / "QuranReciterID"
    else:
        base = Path.home() / ".quran_reciter_id"
    (base / "audio").mkdir(parents=True, exist_ok=True)
    (base / "history").mkdir(parents=True, exist_ok=True)
    return base


class UserReciterDB:
    """Stores user-added reciters (name + audio samples + averaged embedding)."""

    def __init__(self):
        self.root = user_data_dir()
        self.db_file = self.root / "user_reciters.json"
        self.history_file = self.root / "history.json"
        self.data: Dict[str, Dict] = {}      # name -> {name, country, bio, samples:[paths], embedding:[...], created}
        self.history: List[Dict] = []
        self._load()

    def _load(self):
        if self.db_file.exists():
            try:
                self.data = json.loads(self.db_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"user DB load failed: {e}")
                self.data = {}
        if self.history_file.exists():
            try:
                self.history = json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                self.history = []

    def _save(self):
        self.db_file.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_history(self):
        self.history_file.write_text(json.dumps(self.history[-500:], ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Reciters ---
    def list_reciters(self) -> List[Dict]:
        out = []
        for name, r in self.data.items():
            out.append({
                "name": name,
                "name_english": r.get("name_english", name),
                "country": r.get("country", "مخصّص"),
                "bio": r.get("bio", "قارئ مضاف من قِبل المستخدم"),
                "birth_year": r.get("birth_year", "-"),
                "death_year": r.get("death_year"),
                "image_url": r.get("image_url", ""),
                "recitation_style": r.get("recitation_style", "مخصّص"),
                "samples": len(r.get("samples", [])),
                "user_added": True,
            })
        return out

    def vectors(self) -> Dict[str, np.ndarray]:
        return {n: np.array(r["embedding"]) for n, r in self.data.items() if "embedding" in r}

    def add_reciter(self, name: str, audio_files: List[bytes], filenames: List[str],
                    ai_engine, country: str = "", bio: str = "") -> Dict:
        name = name.strip()
        if not name:
            raise ValueError("اسم القارئ مطلوب")
        if not audio_files:
            raise ValueError("مطلوب ملف صوتي واحد على الأقل")

        safe = "".join(c for c in name if c.isalnum() or c in " _-").strip() or f"reciter_{int(time.time())}"
        audio_dir = self.root / "audio" / safe
        audio_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []
        embeddings = []
        for idx, (blob, fname) in enumerate(zip(audio_files, filenames)):
            ext = Path(fname).suffix or ".wav"
            dst = audio_dir / f"sample_{int(time.time())}_{idx}{ext}"
            dst.write_bytes(blob)
            try:
                emb = ai_engine.process_audio_file(dst)
                embeddings.append(np.asarray(emb).flatten())
                saved_paths.append(str(dst))
            except Exception as e:
                logger.error(f"embedding failed for {dst}: {e}")

        if not embeddings:
            raise ValueError("فشل توليد بصمة صوتية من الملفات المرفوعة")

        # merge with existing samples if reciter already exists
        existing = self.data.get(name, {})
        old_samples = existing.get("samples", [])
        old_emb = existing.get("embedding")
        if old_emb:
            embeddings.append(np.array(old_emb))

        avg = np.mean(np.stack(embeddings), axis=0)
        avg = avg / (np.linalg.norm(avg) + 1e-9)

        self.data[name] = {
            "name": name,
            "name_english": existing.get("name_english", name),
            "country": country or existing.get("country", "مخصّص"),
            "bio": bio or existing.get("bio", "قارئ مضاف من قِبل المستخدم"),
            "birth_year": existing.get("birth_year", "-"),
            "death_year": existing.get("death_year"),
            "image_url": existing.get("image_url", ""),
            "recitation_style": existing.get("recitation_style", "مخصّص"),
            "samples": old_samples + saved_paths,
            "embedding": avg.tolist(),
            "created": existing.get("created", time.time()),
            "updated": time.time(),
        }
        self._save()
        return {"name": name, "samples": len(self.data[name]["samples"])}

    def delete_reciter(self, name: str) -> bool:
        if name not in self.data:
            return False
        safe = "".join(c for c in name if c.isalnum() or c in " _-").strip()
        audio_dir = self.root / "audio" / safe
        if audio_dir.exists():
            shutil.rmtree(audio_dir, ignore_errors=True)
        del self.data[name]
        self._save()
        return True

    # --- History ---
    def log_identification(self, entry: Dict):
        entry["ts"] = time.time()
        self.history.append(entry)
        self._save_history()

    def list_history(self, limit: int = 100) -> List[Dict]:
        return list(reversed(self.history[-limit:]))

    def get_data_path(self) -> str:
        return str(self.root)
