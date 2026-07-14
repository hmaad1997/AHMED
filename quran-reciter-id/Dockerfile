FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 git && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir torch==2.1.0+cpu torchaudio==2.1.0+cpu \
    -f https://download.pytorch.org/whl/torch_stable.html
RUN pip install --no-cache-dir -r requirements.txt
COPY requirements-fingerprint.txt /tmp/req-fp.txt
RUN pip install --no-cache-dir -r /tmp/req-fp.txt || true
RUN pip install --no-cache-dir yt-dlp

COPY backend/ .
COPY auto_fingerprint_worker.py worker_startup.py app/

RUN python -c "from speechbrain.pretrained import EncoderClassifier; \
    EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', \
    savedir='/home/user/app/models')"

RUN python -u scripts/build_pretrained_db.py || true
RUN python -u scripts/enrich_from_mp3quran.py || true

RUN chown -R 1000:1000 /home/user/app
USER user

EXPOSE 7860
ENV PYTHONUTF8=1
ENV HF_HOME=/home/user/app/models

CMD ["python", "-c", "import app.main_dual_patch; import app.worker_startup; import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=7860)"]
