import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.early_fusion_agent import EarlyFusionAgent

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent
MERGED_CSV = BASE / "TaylorSwiftEras" / "Data" / "Final" / "taylor_merged_df.csv"

ALBUM_ERA = {
    "Taylor Swift": "Taylor Swift",
    "Beautiful Eyes": "Taylor Swift",
    "The Taylor Swift Holiday Collection": "Taylor Swift",
    "Fearless": "Fearless",
    "Fearless (Taylor's Version)": "Fearless",
    "Speak Now": "Speak Now",
    "Red": "Red",
    "Red (Taylor's Version)": "Red",
    "1989": "1989",
    "reputation": "Reputation",
    "Lover": "Lover",
    "folklore": "Folklore",
}

TAYLORS_VERSION_ALBUMS = {
    "Fearless (Taylor's Version)",
    "Red (Taylor's Version)"
}

ERA_ORDER_8 = [
    "Taylor Swift", "Fearless", "Speak Now", "Red",
    "1989", "Reputation", "Lover", "Folklore"
]

AUDIO_COLS = [
    "danceability", "energy", "key", "loudness", "mode",
    "speechiness", "acousticness", "instrumentalness",
    "liveness", "valence", "tempo", "duration_ms"
]


def load_dataset() -> pd.DataFrame:
    df = pd.read_csv(MERGED_CSV)

    original_titles = set(
        df.loc[
            ~df["album_name"].isin(TAYLORS_VERSION_ALBUMS),
            "track_name"
        ]
        .str.lower()
        .str.strip()
    )

    df = df[
        ~df["album_name"].isin(TAYLORS_VERSION_ALBUMS)
        |
        ~df["track_name"].str.lower().str.strip().isin(original_titles)
    ].copy()

    df["era"] = df["album_name"].map(ALBUM_ERA)

    if "lyric" in df.columns and "lyrics" not in df.columns:
        df["lyrics"] = df["lyric"]

    df = df.dropna(subset=["era", "lyrics"])

    for col in AUDIO_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=AUDIO_COLS)

    return df.reset_index(drop=True)


def main():
    df = load_dataset()

    print(f"Dataset: {len(df)} songs across {df['era'].nunique()} eras")
    print(df["era"].value_counts().to_string())
    print()

    print("=== 5-Fold Stratified Cross-Validation (Early Fusion) ===")

    kf = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=42
    )

    cv_scores = []

    for fold, (train_idx, val_idx) in enumerate(kf.split(df, df["era"])):
        fold_agent = EarlyFusionAgent()

        fold_train = df.iloc[train_idx]
        fold_val = df.iloc[val_idx]

        fold_agent.fit(
            fold_train,
            fold_train["era"].tolist()
        )

        fold_preds = []

        for _, row in fold_val.iterrows():
            audio_data = {
                feat: row.get(feat, 0)
                for feat in fold_agent.audio_features
            }

            result = fold_agent.predict_with_evidence(
                lyrics=row["lyrics"],
                audio_data=audio_data
            )

            fold_preds.append(result["predicted_era"])

        score = accuracy_score(
            fold_val["era"].tolist(),
            fold_preds
        )

        cv_scores.append(score)
        print(f"  Fold {fold + 1}: {score:.3f}")

    print(f"\nCV Mean: {np.mean(cv_scores):.3f} ± {np.std(cv_scores):.3f}")
    print()

    df_train, df_test = train_test_split(
        df,
        test_size=0.2,
        random_state=42,
        stratify=df["era"]
    )

    print(f"Train: {len(df_train)} | Test: {len(df_test)}")
    print()

    agent = EarlyFusionAgent()

    agent.fit(
        df_train,
        df_train["era"].tolist()
    )

    y_true = []
    y_pred = []

    for _, row in df_test.iterrows():
        audio_data = {
            feat: row.get(feat, 0)
            for feat in agent.audio_features
        }

        result = agent.predict_with_evidence(
            lyrics=row["lyrics"],
            audio_data=audio_data
        )

        y_true.append(row["era"])
        y_pred.append(result["predicted_era"])

    print("=== Early Fusion Test Set Performance ===")
    print(classification_report(y_true, y_pred, zero_division=0))

    cm = confusion_matrix(
        y_true,
        y_pred,
        labels=ERA_ORDER_8
    )

    disp = ConfusionMatrixDisplay(
        cm,
        display_labels=ERA_ORDER_8
    )

    fig, ax = plt.subplots(figsize=(10, 8))
    disp.plot(
        ax=ax,
        xticks_rotation=45,
        colorbar=False
    )

    plt.title("Early Fusion Agent — Confusion Matrix")
    plt.tight_layout()

    os.makedirs("models", exist_ok=True)

    plt.savefig(
        "models/early_fusion_confusion_matrix.png",
        dpi=150
    )

    print("Confusion matrix saved → models/early_fusion_confusion_matrix.png")

    agent.save("models/early_fusion_agent.pkl")

    print("Saved → models/early_fusion_agent.pkl")


if __name__ == "__main__":
    main()