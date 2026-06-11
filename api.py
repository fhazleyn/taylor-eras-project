# """
# api.py — eralyzer FastAPI backend

# Run:  uvicorn api:app --reload
# Then open: http://localhost:8000
# """

# import sys
# from pathlib import Path

# import pandas as pd
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from fastapi.staticfiles import StaticFiles
# from pydantic import BaseModel

# BASE = Path(__file__).parent
# sys.path.insert(0, str(BASE))

# # ── Era metadata ───────────────────────────────────────────────────────────────
# ERAS_META = {
#     "Taylor Swift": {"id": "debut",      "label": "Debut",      "year": 2006, "color": "#c8a97e"},
#     "Fearless":     {"id": "fearless",   "label": "Fearless",   "year": 2008, "color": "#d9a818"},
#     "Speak Now":    {"id": "speaknow",   "label": "Speak Now",  "year": 2010, "color": "#9a6cc1"},
#     "Red":          {"id": "red",        "label": "Red",        "year": 2012, "color": "#b53030"},
#     "1989":         {"id": "1989",       "label": "1989",       "year": 2014, "color": "#4a9fc7"},
#     "Reputation":   {"id": "rep",        "label": "Reputation", "year": 2017, "color": "#4a4a4a"},
#     "Lover":        {"id": "lover",      "label": "Lover",      "year": 2019, "color": "#db83b0"},
#     "Folklore":     {"id": "folklore",   "label": "Folklore",   "year": 2020, "color": "#6f8a5c"},
#     "Evermore":     {"id": "evermore",   "label": "Evermore",   "year": 2020, "color": "#b56830"},
#     "Midnights":    {"id": "midnights",  "label": "Midnights",  "year": 2022, "color": "#4a5aa8"},
# }

# # ── Album → Era mapping ────────────────────────────────────────────────────────
# ALBUM_ERA = {
#     "Taylor Swift":                      "Taylor Swift",
#     "Beautiful Eyes":                    "Taylor Swift",
#     "The Taylor Swift Holiday Collection":"Taylor Swift",
#     "Fearless":                          "Fearless",
#     "Fearless (Taylor's Version)":       "Fearless",
#     "Speak Now":                         "Speak Now",
#     "Red":                               "Red",
#     "Red (Taylor's Version)":            "Red",
#     "1989":                              "1989",
#     "reputation":                        "Reputation",
#     "Lover":                             "Lover",
#     "folklore":                          "Folklore",
#     "evermore":                          "Evermore",
#     "Midnights":                         "Midnights",
# }

# # ── Load resources at startup ──────────────────────────────────────────────────
# text_agent = None
# try:
#     from src.text_agent import TextAgent
#     agent_path = BASE / "models" / "text_agent.pkl"
#     if agent_path.exists():
#         text_agent = TextAgent.load(str(agent_path))
#         print(f"[api] TextAgent loaded — {len(text_agent.classes_)} eras")
#     else:
#         print(f"[api] TextAgent not found at {agent_path} — run: python train_text_agent.py")
# except Exception as e:
#     print(f"[api] TextAgent load failed: {e}")

# dataset: pd.DataFrame | None = None
# try:
#     # Primary: full merged dataset (Debut → Folklore, 183 songs, has audio features)
#     primary_path = BASE / "TaylorSwiftEras" / "Data" / "Final" / "taylor_merged_df.csv"
#     df_primary   = pd.read_csv(primary_path)
#     df_primary["era"]    = df_primary["album_name"].map(ALBUM_ERA).fillna("Unknown")
#     df_primary["lyrics"] = df_primary["lyric"]

#     # Fallback: processed dataset (Evermore + Midnights + some overlap, 93 songs)
#     fallback_path = BASE / "data" / "processed" / "taylor_swift_eras_processed.csv"
#     df_fallback   = pd.read_csv(fallback_path)

#     # Merge: primary first, then any fallback songs not already present
#     primary_titles  = set(df_primary["track_name"].str.lower().str.strip())
#     df_extra        = df_fallback[
#         ~df_fallback["track_name"].str.lower().str.strip().isin(primary_titles)
#     ].copy()

#     dataset = pd.concat([df_primary, df_extra], ignore_index=True)
#     print(f"[api] Dataset loaded: {len(dataset)} songs "
#           f"({len(df_primary)} primary + {len(df_extra)} fallback)")
# except Exception as e:
#     print(f"[api] Dataset load failed: {e}")

# # ── App ────────────────────────────────────────────────────────────────────────
# app = FastAPI(title="eralyzer API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# class DebateRequest(BaseModel):
#     song_title: str
#     artist: str = "Taylor Swift"


# # ── Text helpers ──────────────────────────────────────────────────────────────
# def trim_to_words(text: str, max_words: int = 30) -> str:
#     """Return text capped at max_words, ending at the last clean sentence if possible."""
#     words = text.split()
#     if len(words) <= max_words:
#         return text.strip()
#     clipped = " ".join(words[:max_words])
#     # Try to end at the last sentence boundary within the clipped text
#     for punct in (".", "!", "?"):
#         idx = clipped.rfind(punct)
#         if idx > len(clipped) // 3:          # ignore boundary too near the start
#             return clipped[:idx + 1].strip()
#     # No clean boundary — end at last word, ensure it closes with a period
#     return clipped.rstrip(",:;—") + "."


# # ── Song lookup ────────────────────────────────────────────────────────────────
# def find_song(title: str) -> dict | None:
#     if dataset is None:
#         return None
#     title_lc = title.lower().strip()
#     names    = dataset["track_name"].str.lower().str.strip()
#     # Exact match first
#     mask = names == title_lc
#     if mask.any():
#         return dataset[mask].iloc[0].to_dict()
#     # Partial match
#     mask = names.str.contains(title_lc, na=False, regex=False)
#     if mask.any():
#         return dataset[mask].iloc[0].to_dict()
#     return None


# # ── Audio Agent (hardcoded until Member 3 integrates real model) ───────────────
# def audio_agent_open(predicted: str, lyric_conf: float) -> list:
#     if lyric_conf >= 0.65:
#         return [
#             {"who": "audio", "text": "> Fetching Spotify feature vector…"},
#             {"who": "audio", "text": "> danceability · energy · valence · acousticness loaded."},
#             {"who": "audio", "text": f"> Feature cluster aligns with <emp>{predicted}</emp> signature."},
#             {"who": "audio", "text": "> No strong objection. Deferring to Lyric Agent.", "cls": "is-resolve"},
#         ]
#     return [
#         {"who": "audio", "text": "> Fetching Spotify feature vector…"},
#         {"who": "audio", "text": "> Moderate ambiguity in audio cluster."},
#         {"who": "audio", "text": f"> Audio leans <emp>{predicted}</emp> but adjacent-era overlap detected."},
#         {"who": "audio", "text": "> Requesting Lyric Agent to reinforce with LDA evidence."},
#     ]


# def audio_agent_concede(predicted: str) -> list:
#     return [
#         {"who": "audio", "text": "> Re-examining feature cluster after lyric signal…"},
#         {"who": "audio", "text": f"> Lyric anchor convincing. Updating to <emp>{predicted}</emp>.", "cls": "is-concede"},
#         {"who": "audio", "text": "> Consensus reached.", "cls": "is-resolve"},
#     ]


# # ── Debate script builder ──────────────────────────────────────────────────────
# def build_debate_script(ta: dict, song_title: str) -> dict:
#     predicted  = ta["predicted_era"]
#     probs      = ta["probabilities"]
#     evidence   = ta["evidence"]
#     reasoning  = ta["reasoning"]

#     keywords   = evidence.get("top_keywords", [])[:5]
#     topic      = evidence.get("dominant_topic", "")
#     sentiment  = evidence.get("sentiment", {})
#     lyric_conf = float(probs.get(predicted, 0))

#     sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
#     runner_up    = sorted_probs[1] if len(sorted_probs) > 1 else None

#     kw_str     = '", "'.join(keywords) if keywords else "—"
#     sent_val   = sentiment.get("compound", 0)
#     sent_label = (
#         "strongly negative" if sent_val < -0.5 else
#         "mildly negative"   if sent_val < -0.1 else
#         "neutral"           if sent_val <  0.1 else
#         "mildly positive"   if sent_val <  0.5 else
#         "strongly positive"
#     )
#     short_reason = trim_to_words(reasoning, max_words=30)
#     era_meta     = ERAS_META.get(predicted, {"id": "midnights", "label": predicted, "color": "#4a5aa8"})
#     high_conf    = lyric_conf >= 0.65

#     # Round 1 — Lyric Agent opens
#     script: list[dict] = [
#         {"who": "lyric", "text": f'> Tokenising: "{song_title}"…'},
#         {"who": "lyric", "text": f'> Top TF-IDF signals: "{kw_str}"'},
#         {"who": "lyric", "text": f'> LDA dominant topic: <emp>{topic}</emp>'},
#         {"who": "lyric", "text": f'> Sentiment: {sent_label} (compound=<num>{sent_val:.2f}</num>)'},
#         {"who": "lyric", "text": f'> TF-IDF prediction: <emp>{predicted} — {lyric_conf:.0%}</emp>'},
#     ]
#     if runner_up and runner_up[1] > 0.15:
#         script.append({
#             "who": "lyric",
#             "text": f'> Runner-up: {runner_up[0]} (<num>{runner_up[1]:.0%}</num>)',
#         })

#     # Round 1 — Audio Agent responds
#     script.extend(audio_agent_open(predicted, lyric_conf))

#     # Round 2 — only if low confidence
#     if not high_conf:
#         script.append({"who": "sys", "text": "── DEBATE ROUND 2 ──"})
#         script.append({
#             "who": "lyric",
#             "text": "> Reinforcing with LDA topic distribution and LLM signal…",
#             "cls": "is-emphatic",
#         })
#         if runner_up:
#             script.append({
#                 "who": "lyric",
#                 "text": (
#                     f'> Gap: {predicted} ({lyric_conf:.0%}) vs '
#                     f'{runner_up[0]} ({runner_up[1]:.0%}) — lyric diction is decisive.'
#                 ),
#                 "cls": "is-emphatic",
#             })
#         script.extend(audio_agent_concede(predicted))

#     # LLM reasoning reveal (capped at 30 words — fits on one CLI line)
#     script.append({"who": "sys",   "text": "── LLM REASONING ──"})
#     script.append({"who": "lyric", "text": f'> {short_reason}', "cls": "is-emphatic"})
#     script.append({"who": "lyric", "text": f'> Final verdict: <emp>{predicted}</emp>', "cls": "is-resolve"})
#     script.append({"who": "audio", "text": "> Consensus. Stacking classifier locked.", "cls": "is-resolve"})

#     rounds  = 1 if high_conf else 2
#     runtime = round(1.4 + rounds * 0.5, 2)

#     return {
#         "id":         "live",
#         "title":      song_title,
#         "artist":     "Taylor Swift",
#         "era":        era_meta["id"],
#         "audioConf":  round(lyric_conf * 0.85, 2),
#         "lyricConf":  round(lyric_conf, 2),
#         "stacking":   round(min(lyric_conf * 1.05, 0.99), 2),
#         "badge":      "consensus",
#         "reason":     short_reason,
#         "rounds":     rounds,
#         "runtime":    runtime,
#         "audioFinal": f"{predicted} — {lyric_conf * 0.85:.0%}",
#         "lyricFinal": f"{predicted} — {lyric_conf:.0%}",
#         "script":     script,
#     }


# # ── API routes (must be defined BEFORE the static mount) ──────────────────────
# @app.get("/status")
# def status():
#     return {
#         "text_agent":    text_agent is not None,
#         "dataset_songs": len(dataset) if dataset is not None else 0,
#     }


# @app.post("/debate")
# def run_debate(req: DebateRequest):
#     if text_agent is None:
#         return JSONResponse(
#             {"error": "TextAgent not loaded. Run: python train_text_agent.py"},
#             status_code=503,
#         )

#     song = find_song(req.song_title)
#     if song is None:
#         return JSONResponse(
#             {"error": f'"{req.song_title}" not found in dataset. Try a Taylor Swift song title.'},
#             status_code=404,
#         )

#     lyrics = str(song.get("lyrics", "")).strip()
#     if not lyrics:
#         return JSONResponse({"error": "No lyrics found for this song."}, status_code=404)

#     try:
#         ta_result = text_agent.predict_with_evidence(lyrics)
#         demo      = build_debate_script(ta_result, req.song_title)
#         return JSONResponse(demo)
#     except Exception as e:
#         return JSONResponse({"error": str(e)}, status_code=500)


# # ── Serve static files (must come AFTER API routes) ───────────────────────────
# app.mount("/", StaticFiles(directory=str(BASE), html=True), name="static")


"""
api.py — eralyzer FastAPI backend

Run:  uvicorn api:app --reload
Then open: http://localhost:8000
"""

"""
api.py — eralyzer FastAPI backend (Late Fusion Debate Orchestrator)
"""

import sys
import time
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from src.debate_orchestrator import DebateOrchestrator, load_eval_metrics
from src.model import load_model

# ── Era metadata ───────────────────────────────────────────────────────────────
ERAS_META = {
    "Taylor Swift": {"id": "debut",      "label": "Debut",      "year": 2006, "color": "#c8a97e"},
    "Fearless":     {"id": "fearless",   "label": "Fearless",   "year": 2008, "color": "#d9a818"},
    "Speak Now":    {"id": "speaknow",   "label": "Speak Now",  "year": 2010, "color": "#9a6cc1"},
    "Red":          {"id": "red",        "label": "Red",        "year": 2012, "color": "#b53030"},
    "1989":         {"id": "1989",       "label": "1989",       "year": 2014, "color": "#4a9fc7"},
    "Reputation":   {"id": "rep",        "label": "Reputation", "year": 2017, "color": "#4a4a4a"},
    "Lover":        {"id": "lover",      "label": "Lover",      "year": 2019, "color": "#db83b0"},
    "Folklore":     {"id": "folklore",   "label": "Folklore",   "year": 2020, "color": "#6f8a5c"},
    "Evermore":     {"id": "evermore",   "label": "Evermore",   "year": 2020, "color": "#b56830"},
    "Midnights":    {"id": "midnights",  "label": "Midnights",  "year": 2022, "color": "#4a5aa8"},
}

ALBUM_ERA = {
    "Taylor Swift": "Taylor Swift", "Beautiful Eyes": "Taylor Swift",
    "Fearless": "Fearless", "Speak Now": "Speak Now", "Red": "Red",
    "1989": "1989", "reputation": "Reputation", "Lover": "Lover",
    "folklore": "Folklore", "evermore": "Evermore", "Midnights": "Midnights",
}

# ── Load resources ────────────────────────────────────────────────────────────
# text_agent = None
# audio_agent = None
# early_fusion_agent = None

# try:
#     from src.text_agent import TextAgent
#     from src.audio_agent import AudioAgent
    
#     t_path = BASE / "models" / "text_agent.pkl"
#     a_path = BASE / "models" / "audio_agent.pkl"
#     if t_path.exists(): text_agent = TextAgent.load(str(t_path))
#     if a_path.exists(): audio_agent = AudioAgent.load(str(a_path))
#     print(f"[api] Agents Active: Text({text_agent is not None}) Audio({audio_agent is not None})")
# except Exception as e:
#     print(f"[api] Agent load failed: {e}")

# dataset: pd.DataFrame | None = None
# try:
#     primary_path = BASE / "TaylorSwiftEras" / "Data" / "Final" / "taylor_merged_df.csv"
#     dataset = pd.read_csv(primary_path)
#     dataset["era"] = dataset["album_name"].map(ALBUM_ERA).fillna("Unknown")
#     dataset["lyrics"] = dataset["lyric"]
# except Exception as e:
#     print(f"[api] Dataset load failed: {e}")

text_agent = None
audio_agent = None
debate_orchestrator: DebateOrchestrator | None = None

text_agent = None
audio_agent = None
early_fusion_agent = None

# ── Load agents ───────────────────────────────────────────────────────────────
try:
    from src.text_agent import TextAgent
    from src.audio_agent import AudioAgent

    try:
        from src.early_fusion_agent import EarlyFusionAgent
    except Exception as e:
        EarlyFusionAgent = None
        print(f"[api] EarlyFusionAgent import failed: {e}")

    t_path = BASE / "models" / "text_agent.pkl"
    a_path = BASE / "models" / "audio_agent.pkl"
    e_path = BASE / "models" / "early_fusion_agent.pkl"

    if t_path.exists():
        try:
            text_agent = TextAgent.load(str(t_path))
        except Exception as e:
            print(f"[api] TextAgent load failed: {e}")

    if a_path.exists():
        try:
            audio_agent = AudioAgent.load(str(a_path))
        except Exception as e:
            print(f"[api] AudioAgent load failed: {e}")

    if EarlyFusionAgent is not None and e_path.exists():
        try:
            early_fusion_agent = EarlyFusionAgent.load(str(e_path))
        except Exception as e:
            print(f"[api] EarlyFusionAgent load failed: {e}")

    print(
        f"[api] Agents Active: "
        f"Text({text_agent is not None}) "
        f"Audio({audio_agent is not None}) "
        f"EarlyFusion({early_fusion_agent is not None})"
    )

except Exception as e:
    print(f"[api] Agent load failed: {e}")


# ── Load fusion model + evaluation metrics ───────────────────────────────────
late_fusion_model = load_model(str(BASE / "model.pkl"))
early_fusion_model = early_fusion_agent
eval_metrics = load_eval_metrics(BASE)


# ── Load local dataset ────────────────────────────────────────────────────────
dataset: pd.DataFrame | None = None

try:
    primary_path = BASE / "TaylorSwiftEras" / "Data" / "Final" / "taylor_merged_df.csv"
    dataset = pd.read_csv(primary_path)
    dataset["era"] = dataset["album_name"].map(ALBUM_ERA).fillna("Unknown")
    dataset["lyrics"] = dataset["lyric"]
except Exception as e:
    print(f"[api] Dataset load failed: {e}")


# ── Initialize debate orchestrator ────────────────────────────────────────────
if text_agent is not None and audio_agent is not None:
    debate_orchestrator = DebateOrchestrator(
        text_agent=text_agent,
        audio_agent=audio_agent,
        late_fusion_model=late_fusion_model
        if getattr(late_fusion_model, "fusion_type", None) == "late"
        else None,
        early_fusion_model=early_fusion_model,
        eval_metrics=eval_metrics,
        eras_meta=ERAS_META,
    )
    print("[api] DebateOrchestrator (LangGraph) initialized")


# ── Live API collectors fallback ──────────────────────────────────────────────
spotify_collector = None
genius_collector = None

try:
    from src.spotify_collector import SpotifyCollector

    sp_id = os.getenv("SPOTIFY_API_ID")
    sp_secret = os.getenv("SPOTIFY_API_TOKEN")

    if sp_id and sp_secret:
        spotify_collector = SpotifyCollector(sp_id, sp_secret)
        print("[api] SpotifyCollector ready")
    else:
        print("[api] Spotify keys missing — live audio lookup disabled")

except Exception as e:
    print(f"[api] SpotifyCollector init failed: {e}")


try:
    from src.genius_collector import GeniusCollector

    genius_token = os.getenv("GENIUS_API_TOKEN")

    if genius_token:
        genius_collector = GeniusCollector(genius_token)
        print("[api] GeniusCollector ready")
    else:
        print("[api] Genius key missing — live lyrics lookup disabled")

except Exception as e:
    print(f"[api] GeniusCollector init failed: {e}")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="eralyzer API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class DebateRequest(BaseModel):
    song_title: str
    artist: str = "Taylor Swift"
    fusion: str = "late"

def find_song(title: str) -> dict | None:
    if dataset is None:
        return None

    title_lc = title.lower().strip()
    names = dataset["track_name"].str.lower().str.strip()

    mask = names == title_lc
    if mask.any():
        return dataset[mask].iloc[0].to_dict()

    mask = names.str.contains(title_lc, na=False, regex=False)
    if mask.any():
        return dataset[mask].iloc[0].to_dict()

    return None

@app.get("/status")
def status():
    return {
        "text_agent": text_agent is not None,
        "audio_agent": audio_agent is not None,
        "debate_orchestrator": debate_orchestrator is not None,
        "late_fusion_model": late_fusion_model is not None,
        "dataset_songs": len(dataset) if dataset is not None else 0,
    }


@app.get("/fusion-metrics")
def fusion_metrics():
    if debate_orchestrator is None:
        return JSONResponse({"error": "Debate orchestrator not initialized"}, status_code=503)
    return JSONResponse(debate_orchestrator.get_fusion_comparison())


@app.post("/debate")
def run_debate(req: DebateRequest):
    # ── 1. Find song locally first ────────────────────────────────────────────
    song = find_song(req.song_title)

    # ── 2. Live fallback: fetch from Genius + Spotify if not in dataset ──────
    if song is None:
        if genius_collector is None or spotify_collector is None:
            return JSONResponse(
                {
                    "error": (
                        f'"{req.song_title}" not found in local dataset '
                        "and live API lookup is not configured."
                    )
                },
                status_code=404,
            )

        lyrics = genius_collector.fetch_lyrics(req.song_title, req.artist)
        if not lyrics:
            return JSONResponse(
                {
                    "error": (
                        f'Lyrics for "{req.song_title}" by {req.artist} '
                        "could not be fetched from Genius."
                    )
                },
                status_code=404,
            )

        audio_features = spotify_collector.get_track_features(req.song_title, req.artist)
        if not audio_features:
            return JSONResponse(
                {
                    "error": (
                        f'Audio features for "{req.song_title}" by {req.artist} '
                        "could not be fetched from Spotify."
                    )
                },
                status_code=404,
            )

        song = {
            **audio_features,
            "track_name": req.song_title,
            "artist": req.artist,
            "lyrics": lyrics,
        }

        print(f"[api] Live fetch: '{req.song_title}' by {req.artist}")

    # ── 3. Make sure lyrics exist ─────────────────────────────────────────────
    if "lyrics" not in song or pd.isna(song.get("lyrics")):
        song["lyrics"] = song.get("lyric", "")

    lyrics = str(song.get("lyrics", "")).strip()
    if not lyrics:
        return JSONResponse(
            {"error": f'No lyrics found for "{req.song_title}".'},
            status_code=404,
        )

    try:
        # ── 4. Real early fusion: one trained joint model ─────────────────────
        if req.fusion == "early":
            if early_fusion_agent is None:
                return JSONResponse(
                    {
                        "error": (
                            "EarlyFusionAgent not loaded. "
                            "Run: python train_early_fusion_agent.py"
                        )
                    },
                    status_code=503,
                )

            start_time = time.perf_counter()

            ef_features = {
                f: song.get(f, 0)
                for f in early_fusion_agent.audio_features
            }

            ef_res = early_fusion_agent.predict_with_evidence(
                lyrics=lyrics,
                audio_data=ef_features,
            )

            elapsed = time.perf_counter() - start_time

            predicted = ef_res["predicted_era"]
            confidence = float(ef_res["probabilities"].get(predicted, 0))
            top3 = ef_res["evidence"].get("top3_candidates", [])

            top3_text = ", ".join(
                f"{era} ({prob:.0%})"
                for era, prob in top3
            ) or "—"

            meta = ERAS_META.get(
                predicted,
                {
                    "id": "midnights",
                    "label": predicted,
                    "color": "#4a5aa8",
                },
            )

            response_data = {
                "id": "live",
                "title": song.get("track_name", req.song_title),
                "artist": song.get("artist", req.artist),
                "era": meta["id"],
                "audioConf": round(confidence, 2),
                "lyricConf": round(confidence, 2),
                "stacking": round(confidence, 2),
                "badge": "joint-inference",
                "reason": ef_res["reasoning"],
                "rounds": 1,
                "runtime": elapsed,
                "audioFinal": "Included in joint vector",
                "lyricFinal": f"{predicted} — {confidence:.0%}",
                "script": [
                    {"who": "sys", "text": "── EARLY FUSION MODE: REAL JOINT MODEL ──"},
                    {"who": "lyric", "text": "> Extracting TF-IDF lyric features..."},
                    {"who": "lyric", "text": "> Scaling Spotify audio features..."},
                    {"who": "sys", "text": "> CONCATENATING TEXT + AUDIO FEATURES INTO ONE VECTOR..."},
                    {
                        "who": "lyric",
                        "text": "> Running trained early-fusion classifier...",
                        "cls": "is-emphatic",
                    },
                    {"who": "lyric", "text": f"> Top candidates: {top3_text}"},
                    {
                        "who": "lyric",
                        "text": f"> Early fusion prediction: <emp>{predicted} — {confidence:.0%}</emp>",
                        "cls": "is-resolve",
                    },
                    {"who": "sys", "text": "── INFERENCE REASONING ──"},
                    {
                        "who": "lyric",
                        "text": f"> {ef_res['reasoning']}",
                        "cls": "is-emphatic",
                    },
                    {
                        "who": "lyric",
                        "text": "> Single joint-model inference complete.",
                        "cls": "is-resolve",
                    },
                ],
            }

            return JSONResponse(response_data)

        # ── 5. Late fusion: use friend's DebateOrchestrator ──────────────────
        if debate_orchestrator is None:
            return JSONResponse(
                {
                    "error": (
                        "Agents not loaded. "
                        "Run: python train_text_agent.py && python train_audio_agent.py"
                    )
                },
                status_code=503,
            )

        response_data = debate_orchestrator.run_late_fusion_debate(song)
        return JSONResponse(response_data)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Serve static files (must come AFTER all API routes) ──────────────────────
app.mount("/", StaticFiles(directory=str(BASE), html=True), name="static")