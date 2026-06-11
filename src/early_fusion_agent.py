import os
import pickle
import numpy as np
import pandas as pd

from scipy.sparse import hstack, csr_matrix

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC


class EarlyFusionAgent:
    """
    Real Early Fusion Agent.

    This agent combines:
    1. Lyric features from TF-IDF
    2. Spotify audio features

    Then it trains ONE classifier on the combined feature vector.
    """

    def __init__(self, max_text_features=3000):
        self.audio_features = [
            "danceability", "energy", "key", "loudness", "mode",
            "speechiness", "acousticness", "instrumentalness",
            "liveness", "valence", "tempo", "duration_ms"
        ]

        self.tfidf = TfidfVectorizer(
            max_features=max_text_features,
            ngram_range=(1, 2),
            stop_words="english",
            min_df=2
        )

        self.audio_scaler = StandardScaler()

        base_models = [
            (
                "logreg",
                LogisticRegression(
                    max_iter=3000,
                    class_weight="balanced",
                    random_state=42
                )
            ),
            (
                "svm",
                LinearSVC(
                    class_weight="balanced",
                    random_state=42
                )
            ),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=150,
                    max_depth=10,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1
                )
            )
        ]

        self.classifier = StackingClassifier(
            estimators=base_models,
            final_estimator=LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42
            ),
            stack_method="auto",
            n_jobs=-1
        )

        self.classes_ = None
        self.is_fitted = False

    def _get_lyrics_column(self, df: pd.DataFrame):
        if "lyrics" in df.columns:
            return df["lyrics"].fillna("").astype(str)
        if "lyric" in df.columns:
            return df["lyric"].fillna("").astype(str)
        raise ValueError("Dataset must contain either 'lyrics' or 'lyric' column.")

    def _build_features(self, lyrics, audio_df: pd.DataFrame, fit: bool):
        """
        Build the early-fusion feature matrix.

        Text features: TF-IDF sparse matrix
        Audio features: scaled numerical matrix
        Final input: [TF-IDF features + audio features]
        """

        if fit:
            text_matrix = self.tfidf.fit_transform(lyrics)
        else:
            text_matrix = self.tfidf.transform(lyrics)

        audio_values = (
            audio_df[self.audio_features]
            .fillna(0)
            .astype(float)
            .values
        )

        if fit:
            audio_scaled = self.audio_scaler.fit_transform(audio_values)
        else:
            audio_scaled = self.audio_scaler.transform(audio_values)

        audio_matrix = csr_matrix(audio_scaled)

        combined_matrix = hstack([text_matrix, audio_matrix], format="csr")
        return combined_matrix

    def fit(self, df: pd.DataFrame, era_labels):
        lyrics = self._get_lyrics_column(df)

        X_fused = self._build_features(
            lyrics=lyrics,
            audio_df=df,
            fit=True
        )

        self.classifier.fit(X_fused, era_labels)

        self.classes_ = self.classifier.classes_
        self.is_fitted = True

        return self

    def predict_with_evidence(self, lyrics: str, audio_data: dict) -> dict:
        if not self.is_fitted:
            raise RuntimeError("EarlyFusionAgent must be fitted before prediction.")

        lyrics_list = [str(lyrics)]

        audio_df = pd.DataFrame([audio_data])

        X_fused = self._build_features(
            lyrics=lyrics_list,
            audio_df=audio_df,
            fit=False
        )

        probabilities_array = self.classifier.predict_proba(X_fused)[0]

        probabilities = {
            era: float(prob)
            for era, prob in zip(self.classes_, probabilities_array)
        }

        predicted_era = max(probabilities, key=probabilities.get)
        confidence = probabilities[predicted_era]

        top3 = sorted(
            probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        top3_text = ", ".join(
            f"{era} ({prob:.0%})"
            for era, prob in top3
        )

        evidence = {
            "fusion_type": "early_fusion",
            "text_features": "TF-IDF unigrams and bigrams",
            "audio_features": {
                feat: audio_data.get(feat, 0)
                for feat in self.audio_features
            },
            "top3_candidates": top3
        }

        reasoning = (
            f"The early fusion model predicts {predicted_era} with {confidence:.0%} confidence. "
            f"This prediction is based on a single combined feature vector containing both TF-IDF lyric patterns "
            f"and scaled Spotify audio features. The top candidates were {top3_text}."
        )

        return {
            "predicted_era": predicted_era,
            "probabilities": probabilities,
            "evidence": evidence,
            "reasoning": reasoning
        }

    def save(self, path="models/early_fusion_agent.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path="models/early_fusion_agent.pkl"):
        with open(path, "rb") as f:
            return pickle.load(f)