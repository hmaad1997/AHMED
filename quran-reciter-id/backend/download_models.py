from speechbrain.pretrained import EncoderClassifier
for name in ("ecapa", "xvect"):
    src = f"speechbrain/spkrec-{name}-voxceleb"
    EncoderClassifier.from_hparams(source=src, savedir=f"pretrained_models/spkrec-{name}-voxceleb")
    print("ok:", src, flush=True)
