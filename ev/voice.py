"""Voice: Kokoro speaks each beat on your machine; whisper.cpp listens back for misread words and word times."""
import difflib
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from ev import gates, research, storyboard
from ev.common import MODELS, SR, VIDEOS, WHISPER, ffmpeg, load, norm, progress, run

_kokoro = None


def voice_name(value):
    """A Kokoro English voice: a* is US English, b* is UK English, for example af_heart or bm_george."""
    voice = str(value or "af_heart").strip()
    if not re.fullmatch(r"[ab][fm]_[a-z]+", voice):
        raise SystemExit(f"voice: use a Kokoro English voice such as af_heart, am_michael, bf_emma, or bm_george, not {value!r}")
    return voice


def key_flags(say):
    """For each word of `say`: True if it sits between *asterisks*, which the captions show in the key color."""
    flags, inside = [], False
    for token in say.split():
        starts = token.startswith("*")
        flags.append(inside or starts)
        inside = (inside or starts) and not token.rstrip(".,!?;:'\")").endswith("*")
    return flags


def speak(text, wav, voice, speed):
    """Write one voice clip as a 24 kHz mono WAV."""
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    samples, rate = _kokoro.create(text, voice=voice, speed=speed, lang="en-gb" if voice[0] == "b" else "en-us")
    sf.write(wav, samples, rate)
    if rate != SR:
        tmp = Path(wav).with_suffix(".tmp.wav")
        ffmpeg("-i", wav, "-ar", SR, "-ac", 1, tmp)
        tmp.replace(wav)


def hear(wav):
    """whisper.cpp listens to one clip. Returns [{"w", "start", "end"}] in seconds."""
    if not shutil.which("whisper-cli"):
        return []
    with tempfile.TemporaryDirectory() as tmp:
        w16, out = Path(tmp) / "a.wav", Path(tmp) / "out"
        ffmpeg("-i", wav, "-ar", 16000, "-ac", 1, w16)
        run("whisper-cli", "-m", WHISPER, "-f", w16, "-l", "en", "-ml", 1, "-sow", "-oj", "-of", out, "-np",
            capture_output=True)
        segments = json.loads(out.with_suffix(".json").read_text())["transcription"]
    return [{"w": s["text"].strip(), "start": s["offsets"]["from"] / 1000, "end": s["offsets"]["to"] / 1000}
            for s in segments if s["text"].strip() and not s["text"].strip().startswith("[")]


NUMBER_WORDS = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                   "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety "
                   "hundred thousand million billion point percent".split())


def score(said, heard):
    """How much of the script whisper heard (0 to 1). "two percent" heard as "2%" is not a miss."""
    said = [w for w in said if w not in NUMBER_WORDS]
    heard = [w for w in heard if not any(ch.isdigit() for ch in w)]
    return round(difflib.SequenceMatcher(None, said, heard, autojunk=False).ratio(), 2)


def align(text, heard, duration):
    """Give every script word a start and end time. Matched words take whisper's times."""
    words = text.split()
    said, got = [norm(w) for w in words], [norm(h["w"]) for h in heard]
    times = [None] * len(words)
    for i, j, n in difflib.SequenceMatcher(None, said, got, autojunk=False).get_matching_blocks():
        for k in range(n):
            times[i + k] = (heard[j + k]["start"], heard[j + k]["end"])
    i = 0
    while i < len(words):  # words whisper missed: spread them between their known neighbours
        if times[i]:
            i += 1
            continue
        j = i
        while j < len(words) and not times[j]:
            j += 1
        lo = times[i - 1][1] if i else 0.0
        hi = times[j][0] if j < len(words) else duration
        step = max(hi - lo, 0) / (j - i)
        for k in range(i, j):
            times[k] = (lo + (k - i) * step, lo + (k - i + 1) * step)
        i = j
    out = [{"w": w, "start": round(s, 3), "end": round(e, 3)} for w, (s, e) in zip(words, times)]
    return out, (score(said, got) if heard else None)


def narrate(video):
    """Speak every beat (cached), check it with whisper.cpp, print each beat, and write build/narration.json,
    build/narration.wav, and storyboard.md. Part of step 1, so no approval needed."""
    spec = load(video)
    voice = voice_name(spec.get("voice"))
    speed, gap = float(spec.get("speed", 1.0)), float(spec.get("gap", 0.35))
    audio = video / "build" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    scenes, flagged = {}, []
    total, done = sum(len(s["beats"]) for p in spec["parts"] for s in p["scenes"]), 0
    for n, part in enumerate(spec["parts"], 1):
        length = 0.0
        print(f"PART {n}: {part.get('title', '')}")
        for scene in part["scenes"]:
            scenes[scene["id"]] = []
            for i, beat in enumerate(scene["beats"]):
                say = " ".join(str(beat["say"]).split())
                bid, text = str(beat.get("id", i)), say.replace("*", "")
                key = hashlib.sha1(f"kokoro|{voice}|{speed}|{text}".encode()).hexdigest()[:10]
                wav = audio / f"{scene['id']}-{bid}-{key}.wav"
                meta = wav.with_suffix(".json")
                done += 1
                if not meta.exists():
                    progress(video, "Making the voice", f"beat {done} of {total}")
                    speak(text, wav, voice, speed)
                    heard, duration = hear(wav), sf.info(wav).duration
                    words, match = align(text, heard, duration)
                    meta.write_text(json.dumps({"duration": duration, "words": words, "match": match,
                                                "heard": " ".join(h["w"] for h in heard)}))
                m = json.loads(meta.read_text())
                m["words"] = [{**w, "key": k} for w, k in zip(m["words"], key_flags(say))]
                scenes[scene["id"]].append({"id": bid, "text": text, "wav": str(wav.resolve()), **m})
                length += m["duration"] + gap + float(beat.get("hold", 0))
                print(f"  {scene['id']}/{bid}  {m['duration']:.1f}s  match {m['match']}\n"
                      f"      say:  {say}\n      show: {beat.get('show', '(missing)')}")
                if m["match"] is not None and m["match"] < 0.85:
                    flagged.append(f"  {scene['id']}/{bid}\n    script: {text}\n    heard:  {m['heard']}")
        print(f"  part {n} length: {length:.0f}s")
    narration = {"source": gates.fingerprint(video, "plan"), "gap": gap, "scenes": scenes}
    (video / "build" / "narration.json").write_text(json.dumps(narration, indent=1))
    silence = np.zeros(int(gap * SR), np.float32)
    clips = [x for beats in scenes.values() for b in beats for x in (sf.read(b["wav"], dtype="float32")[0], silence)]
    sf.write(video / "build" / "narration.wav", np.concatenate(clips), SR)
    print(f"Listen: {video}/build/narration.wav")
    if flagged:
        print("CHECK: the voice may say these wrong. Respell the words, then run again.\n" + "\n".join(flagged))
    sourcing = research.checks(spec, video / "research.md")
    if sourcing:
        print("CHECK: facts without a source in research.md.\n" + "\n".join(f"  {x}" for x in sourcing))
    progress(video, "done", "")
    board = storyboard.refresh(video, spec, narration)
    print(f"Storyboard: {video}/storyboard.md")
    if board["checks"]:
        print("CHECK: the storyboard.\n" + "\n".join(f"  {x}" for x in board["checks"]))
    return spec, narration


def transcribe(path, model="base.en"):
    """Speech to text with whisper.cpp: writes <file>.txt and <file>.srt next to the file."""
    m = WHISPER if model == "base.en" else VIDEOS / ".models" / f"ggml-{model}.bin"  # the only writable folder
    if not m.exists():
        m.parent.mkdir(exist_ok=True)
        run("curl", "-fL", "-o", m, f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model}.bin")
    with tempfile.TemporaryDirectory() as tmp:
        w16 = Path(tmp) / "a.wav"
        ffmpeg("-i", path, "-ar", 16000, "-ac", 1, w16)
        run("whisper-cli", "-m", m, "-f", w16, "-l", "auto", "-otxt", "-osrt", "-of", path.with_suffix(""), "-np")
    print(f"DONE {path.with_suffix('.txt')} and {path.with_suffix('.srt')}")
