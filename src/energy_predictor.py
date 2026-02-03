"""
LifeOS Energy Prediction ML

Simple regression model for energy level prediction.
Compares ML predictions against LLM predictions and tracks accuracy.
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict
from enum import Enum

if TYPE_CHECKING:
    import numpy as np

try:
    import numpy as np
    from scipy import stats
    from scipy.stats import linregress
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    np = None  # type: ignore


class PredictionSource(Enum):
    """Source of energy prediction."""
    ML = "ml"
    LLM = "llm"


@dataclass
class EnergyPrediction:
    """Result of an energy prediction."""
    date: str
    source: PredictionSource
    predicted_energy: float  # 1-10 scale
    confidence: float  # 0-1
    features_used: Dict[str, float]
    model_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "source": self.source.value,
            "predicted_energy": self.predicted_energy,
            "confidence": self.confidence,
            "features_used": self.features_used,
            "model_version": self.model_version
        }


@dataclass
class PredictionAccuracy:
    """Accuracy metrics for predictions."""
    source: PredictionSource
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Squared Error
    correlation: float  # Correlation with actual
    sample_size: int
    period_start: str
    period_end: str


@dataclass
class TrainingData:
    """Prepared training data."""
    features: "np.ndarray"  # (n_samples, n_features)
    targets: "np.ndarray"  # (n_samples,)
    feature_names: List[str]
    dates: List[str]
    sample_count: int


class EnergyPredictor:
    """
    ML-based energy level predictor.

    Uses linear regression with features:
    - sleep_duration: Total sleep hours
    - deep_sleep: Deep sleep hours
    - readiness_score: Oura readiness score (0-100)
    - day_of_week: 0-6 (Monday-Sunday)
    - prev_day_energy: Previous day's energy (if available)

    Target: energy level on 1-10 scale
    """

    VERSION = "1.1"  # Updated for meeting density feature
    MIN_TRAINING_SAMPLES = 7

    # Feature names in order
    FEATURE_NAMES = [
        "sleep_duration",
        "deep_sleep",
        "readiness_score",
        "day_of_week",
        "prev_day_energy",
        "meeting_hours"  # Calendar integration feature
    ]

    def __init__(self):
        if not HAS_SCIPY:
            raise ImportError(
                "scipy and numpy required for energy prediction. "
                "Install with: pip install scipy numpy"
            )

        # Model parameters (coefficients for linear regression)
        self._coefficients: Optional[np.ndarray] = None
        self._intercept: float = 0.0
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None
        self._is_trained: bool = False
        self._training_r_squared: float = 0.0
        self._training_sample_count: int = 0

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._is_trained

    def prepare_training_data(
        self,
        data_points: List[Dict[str, Any]],
        journal_entries: List[Dict[str, Any]]
    ) -> Optional[TrainingData]:
        """
        Prepare training data from data points and journal entries.

        Args:
            data_points: List of DataPoint records (sleep, readiness, etc.)
            journal_entries: List of JournalEntry records (manual energy logs)

        Returns:
            TrainingData if sufficient samples, None otherwise
        """
        # Organize data by date
        by_date: Dict[str, Dict[str, Any]] = {}

        for dp in data_points:
            dp_date = dp.get("date")
            if not dp_date:
                continue
            if isinstance(dp_date, date):
                dp_date = dp_date.isoformat()

            if dp_date not in by_date:
                by_date[dp_date] = {}

            dp_type = dp.get("type")
            value = dp.get("value")
            metadata = dp.get("metadata", {})

            if dp_type == "sleep":
                by_date[dp_date]["sleep_duration"] = float(value)
                if isinstance(metadata, dict):
                    by_date[dp_date]["deep_sleep"] = metadata.get("deep_sleep_hours", 0.0)
            elif dp_type == "readiness":
                by_date[dp_date]["readiness_score"] = float(value)
            elif dp_type == "meeting_density":
                by_date[dp_date]["meeting_hours"] = float(value) if value else 0.0

        # Add energy from journal entries
        for entry in journal_entries:
            entry_date = entry.get("date")
            energy = entry.get("energy")
            if not entry_date or energy is None:
                continue
            if isinstance(entry_date, date):
                entry_date = entry_date.isoformat()

            if entry_date not in by_date:
                by_date[entry_date] = {}

            # Convert 1-5 scale to 1-10 scale
            by_date[entry_date]["energy"] = float(energy) * 2

        # Build feature matrix
        dates = sorted(by_date.keys())
        features_list = []
        targets_list = []
        valid_dates = []

        for i, d in enumerate(dates):
            day_data = by_date[d]

            # Skip if no energy target
            if "energy" not in day_data:
                continue

            # Extract features
            sleep_duration = day_data.get("sleep_duration")
            deep_sleep = day_data.get("deep_sleep")
            readiness = day_data.get("readiness_score")

            # Skip if missing required features
            if sleep_duration is None or readiness is None:
                continue

            # Day of week (0=Monday, 6=Sunday)
            dt = datetime.strptime(d, "%Y-%m-%d")
            day_of_week = dt.weekday()

            # Previous day energy
            prev_energy = 5.0  # Default to middle
            if i > 0:
                prev_date = dates[i - 1]
                if "energy" in by_date[prev_date]:
                    prev_energy = by_date[prev_date]["energy"]

            # Meeting hours (from calendar integration)
            meeting_hours = day_data.get("meeting_hours", 0.0)

            # Build feature vector
            features = [
                sleep_duration,
                deep_sleep if deep_sleep is not None else 0.0,
                readiness,
                float(day_of_week),
                prev_energy,
                meeting_hours
            ]

            features_list.append(features)
            targets_list.append(day_data["energy"])
            valid_dates.append(d)

        if len(features_list) < self.MIN_TRAINING_SAMPLES:
            return None

        return TrainingData(
            features=np.array(features_list),
            targets=np.array(targets_list),
            feature_names=self.FEATURE_NAMES.copy(),
            dates=valid_dates,
            sample_count=len(features_list)
        )

    def train(self, training_data: TrainingData) -> Dict[str, Any]:
        """
        Train the linear regression model.

        Args:
            training_data: Prepared training data

        Returns:
            Training metrics
        """
        X = training_data.features
        y = training_data.targets

        # Standardize features
        self._feature_means = np.mean(X, axis=0)
        self._feature_stds = np.std(X, axis=0)
        # Avoid division by zero
        self._feature_stds[self._feature_stds == 0] = 1.0

        X_scaled = (X - self._feature_means) / self._feature_stds

        # Add bias column
        X_bias = np.column_stack([np.ones(len(X_scaled)), X_scaled])

        # Solve normal equation: theta = (X^T X)^-1 X^T y
        try:
            theta = np.linalg.lstsq(X_bias, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse
            theta = np.linalg.pinv(X_bias) @ y

        self._intercept = theta[0]
        self._coefficients = theta[1:]
        self._is_trained = True
        self._training_sample_count = len(y)

        # Calculate R-squared
        y_pred = X_bias @ theta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self._training_r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Calculate feature importance (absolute coefficient values)
        feature_importance = dict(zip(
            self.FEATURE_NAMES,
            np.abs(self._coefficients).tolist()
        ))

        return {
            "sample_count": len(y),
            "r_squared": self._training_r_squared,
            "feature_importance": feature_importance,
            "intercept": self._intercept,
            "coefficients": dict(zip(self.FEATURE_NAMES, self._coefficients.tolist()))
        }

    def predict(
        self,
        sleep_duration: float,
        deep_sleep: float,
        readiness_score: float,
        day_of_week: int,
        prev_day_energy: float = 5.0,
        meeting_hours: float = 0.0
    ) -> EnergyPrediction:
        """
        Predict energy level for given features.

        Args:
            sleep_duration: Total sleep hours
            deep_sleep: Deep sleep hours
            readiness_score: Oura readiness score (0-100)
            day_of_week: 0-6 (Monday-Sunday)
            prev_day_energy: Previous day's energy (1-10)
            meeting_hours: Total meeting hours for the day (from calendar)

        Returns:
            EnergyPrediction with predicted value and confidence
        """
        if not self._is_trained:
            raise ValueError("Model must be trained before predicting")

        # Build feature vector
        features = np.array([
            sleep_duration,
            deep_sleep,
            readiness_score,
            float(day_of_week),
            prev_day_energy,
            meeting_hours
        ])

        # Standardize
        features_scaled = (features - self._feature_means) / self._feature_stds

        # Predict
        raw_pred = self._intercept + np.dot(self._coefficients, features_scaled)

        # Clamp to valid range
        predicted_energy = float(np.clip(raw_pred, 1.0, 10.0))

        # Confidence based on R-squared and feature completeness
        confidence = self._training_r_squared * 0.8 + 0.2  # Scale 0.2-1.0

        return EnergyPrediction(
            date=datetime.now().strftime("%Y-%m-%d"),
            source=PredictionSource.ML,
            predicted_energy=round(predicted_energy, 1),
            confidence=round(confidence, 2),
            features_used={
                "sleep_duration": sleep_duration,
                "deep_sleep": deep_sleep,
                "readiness_score": readiness_score,
                "day_of_week": day_of_week,
                "prev_day_energy": prev_day_energy,
                "meeting_hours": meeting_hours
            },
            model_version=self.VERSION
        )

    def predict_from_data(
        self,
        data_points: List[Dict[str, Any]],
        target_date: str,
        prev_energy: Optional[float] = None
    ) -> Optional[EnergyPrediction]:
        """
        Predict energy from data points for a specific date.

        Args:
            data_points: Data points containing sleep/readiness for target_date
            target_date: Date to predict for (YYYY-MM-DD)
            prev_energy: Previous day's energy (optional)

        Returns:
            EnergyPrediction or None if insufficient data
        """
        if not self._is_trained:
            return None

        # Find data for target date
        sleep_duration = None
        deep_sleep = 0.0
        readiness_score = None
        meeting_hours = 0.0

        for dp in data_points:
            dp_date = dp.get("date")
            if isinstance(dp_date, date):
                dp_date = dp_date.isoformat()

            if dp_date != target_date:
                continue

            dp_type = dp.get("type")
            value = dp.get("value")
            metadata = dp.get("metadata", {})

            if dp_type == "sleep":
                sleep_duration = float(value)
                if isinstance(metadata, dict):
                    deep_sleep = metadata.get("deep_sleep_hours", 0.0)
            elif dp_type == "readiness":
                readiness_score = float(value)
            elif dp_type == "meeting_density":
                meeting_hours = float(value) if value else 0.0

        # Need at minimum sleep and readiness
        if sleep_duration is None or readiness_score is None:
            return None

        # Day of week
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        day_of_week = dt.weekday()

        prediction = self.predict(
            sleep_duration=sleep_duration,
            deep_sleep=deep_sleep,
            readiness_score=readiness_score,
            day_of_week=day_of_week,
            prev_day_energy=prev_energy if prev_energy else 5.0,
            meeting_hours=meeting_hours
        )
        prediction.date = target_date

        return prediction

    def get_model_params(self) -> Optional[Dict[str, Any]]:
        """Get model parameters for persistence."""
        if not self._is_trained:
            return None

        return {
            "version": self.VERSION,
            "coefficients": self._coefficients.tolist(),
            "intercept": float(self._intercept),
            "feature_means": self._feature_means.tolist(),
            "feature_stds": self._feature_stds.tolist(),
            "feature_names": self.FEATURE_NAMES,
            "r_squared": self._training_r_squared,
            "sample_count": self._training_sample_count
        }

    def load_model_params(self, params: Dict[str, Any]) -> bool:
        """
        Load model parameters from persistence.

        Args:
            params: Model parameters dictionary

        Returns:
            True if loaded successfully
        """
        try:
            self._coefficients = np.array(params["coefficients"])
            self._intercept = float(params["intercept"])
            self._feature_means = np.array(params["feature_means"])
            self._feature_stds = np.array(params["feature_stds"])
            self._training_r_squared = params.get("r_squared", 0.5)
            self._training_sample_count = params.get("sample_count", 0)
            self._is_trained = True
            return True
        except (KeyError, ValueError, TypeError):
            return False


class PredictionComparator:
    """
    Compares ML and LLM predictions and tracks accuracy.
    """

    def __init__(self):
        self._ml_predictions: List[Dict[str, Any]] = []
        self._llm_predictions: List[Dict[str, Any]] = []
        self._actuals: Dict[str, float] = {}  # date -> actual energy

    def record_ml_prediction(self, prediction: EnergyPrediction):
        """Record an ML prediction."""
        self._ml_predictions.append(prediction.to_dict())

    def record_llm_prediction(
        self,
        date: str,
        predicted_energy: float,
        confidence: float = 0.5
    ):
        """Record an LLM prediction."""
        self._llm_predictions.append({
            "date": date,
            "source": PredictionSource.LLM.value,
            "predicted_energy": predicted_energy,
            "confidence": confidence
        })

    def record_actual(self, date: str, actual_energy: float):
        """Record actual energy level (1-10 scale)."""
        self._actuals[date] = actual_energy

    def calculate_accuracy(
        self,
        source: PredictionSource
    ) -> Optional[PredictionAccuracy]:
        """
        Calculate accuracy metrics for a prediction source.

        Returns PredictionAccuracy or None if insufficient data.
        """
        predictions = (
            self._ml_predictions if source == PredictionSource.ML
            else self._llm_predictions
        )

        # Match predictions with actuals
        pairs = []
        for pred in predictions:
            pred_date = pred["date"]
            if pred_date in self._actuals:
                pairs.append((
                    pred["predicted_energy"],
                    self._actuals[pred_date]
                ))

        if len(pairs) < 3:
            return None

        predicted = np.array([p[0] for p in pairs])
        actual = np.array([p[1] for p in pairs])

        # MAE
        mae = float(np.mean(np.abs(predicted - actual)))

        # RMSE
        rmse = float(np.sqrt(np.mean((predicted - actual) ** 2)))

        # Correlation
        if len(pairs) >= 3:
            corr, _ = stats.pearsonr(predicted, actual)
            correlation = float(corr) if not np.isnan(corr) else 0.0
        else:
            correlation = 0.0

        # Find date range
        dates = [pred["date"] for pred in predictions if pred["date"] in self._actuals]

        return PredictionAccuracy(
            source=source,
            mae=round(mae, 2),
            rmse=round(rmse, 2),
            correlation=round(correlation, 2),
            sample_size=len(pairs),
            period_start=min(dates),
            period_end=max(dates)
        )

    def compare_sources(self) -> Dict[str, Any]:
        """
        Compare ML vs LLM prediction accuracy.

        Returns comparison metrics.
        """
        ml_acc = self.calculate_accuracy(PredictionSource.ML)
        llm_acc = self.calculate_accuracy(PredictionSource.LLM)

        result = {
            "ml": asdict(ml_acc) if ml_acc else None,
            "llm": asdict(llm_acc) if llm_acc else None,
            "winner": None,
            "comparison": None
        }

        if ml_acc and llm_acc:
            # Lower MAE is better
            if ml_acc.mae < llm_acc.mae:
                result["winner"] = "ml"
                result["comparison"] = f"ML beats LLM by {llm_acc.mae - ml_acc.mae:.2f} MAE"
            elif llm_acc.mae < ml_acc.mae:
                result["winner"] = "llm"
                result["comparison"] = f"LLM beats ML by {ml_acc.mae - llm_acc.mae:.2f} MAE"
            else:
                result["winner"] = "tie"
                result["comparison"] = "Both models have equal MAE"

        return result

    def get_all_predictions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all recorded predictions."""
        return {
            "ml": self._ml_predictions,
            "llm": self._llm_predictions,
            "actuals": [
                {"date": d, "energy": e}
                for d, e in sorted(self._actuals.items())
            ]
        }


# Singleton instances
_predictor: Optional[EnergyPredictor] = None
_comparator: Optional[PredictionComparator] = None


def get_energy_predictor() -> EnergyPredictor:
    """Get or create the energy predictor singleton."""
    global _predictor
    if _predictor is None:
        _predictor = EnergyPredictor()
    return _predictor


def get_prediction_comparator() -> PredictionComparator:
    """Get or create the prediction comparator singleton."""
    global _comparator
    if _comparator is None:
        _comparator = PredictionComparator()
    return _comparator
