pyinstaller --onefile --noconsole --name QuranReciterID `
  --add-data "pretrained_models;pretrained_models" `
  --add-data "app/static;app/static" --add-data "data;data" `
  --collect-all app --collect-all speechbrain --collect-all librosa `
  --collect-data sklearn `
  --collect-all webview --collect-all uvicorn --collect-all imageio_ffmpeg `
  launcher.py
