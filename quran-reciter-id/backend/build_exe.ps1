pyinstaller --onefile --noconsole --name QuranReciterID `
  --add-data "pretrained_models;pretrained_models" `
  --add-data "app/static;app/static" --add-data "data;data" `
  --collect-all app --collect-all speechbrain --collect-all librosa `
  --collect-data sklearn `
  --collect-all webview --collect-all uvicorn --collect-all imageio_ffmpeg `
  --collect-all silero_vad --collect-all onnxruntime `
  --hidden-import multiprocessing `
  --hidden-import webview.platforms.edgechromium `
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.http.h11_impl `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.protocols.websockets.wsproto_impl `
  --hidden-import uvicorn.lifespan.on --hidden-import uvicorn.lifespan.off `
  launcher.py
