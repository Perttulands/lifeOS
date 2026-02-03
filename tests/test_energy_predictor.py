"""
Tests for the energy prediction ML model.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Skip if scipy not available
pytest.importorskip("scipy")
pytest.importorskip("numpy")

from src.energy_predictor import (
    EnergyPredictor,
    PredictionComparator,
    EnergyPrediction,
    PredictionSource,
    TrainingData
)


def generate_training_data(days: int = 30) -> tuple:
    """Generate synthetic training data with known patterns."""
    data_points = []
    journal_entries = []
    base_date = datetime.now() - timedelta(days=days)

    for i in range(days):
        date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        day_of_week = (base_date + timedelta(days=i)).weekday()

        # Sleep: 6-9 hours with some variance
        is_weekend = day_of_week >= 5
        sleep_duration = 7.0 + (1.0 if is_weekend else 0) + (i % 3 - 1) * 0.3
        deep_sleep = 1.2 + (sleep_duration - 7) * 0.2

        # Readiness: based on sleep quality
        readiness = 60 + (sleep_duration - 7) * 8 + deep_sleep * 5

        # Energy: correlated with sleep and readiness
        # Scale: 1-5 for journal (will be converted to 1-10)
        energy = min(5, max(1, int(1 + (sleep_duration - 6) * 0.8 + (readiness - 60) / 20)))

        data_points.append({
            'date': date,
            'type': 'sleep',
            'value': sleep_duration,
            'metadata': {
                'deep_sleep_hours': deep_sleep,
                'score': int(readiness * 0.9)
            }
        })

        data_points.append({
            'date': date,
            'type': 'readiness',
            'value': readiness,
            'metadata': {}
        })

        # Only add energy for some days (simulating real usage)
        if i % 2 == 0:
            journal_entries.append({
                'date': date,
                'energy': energy
            })

    return data_points, journal_entries


class TestEnergyPredictor:
    """Test suite for EnergyPredictor."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance."""
        return EnergyPredictor()

    @pytest.fixture
    def training_data(self):
        """Generate training data."""
        return generate_training_data(30)

    def test_init(self, predictor):
        """Test predictor initialization."""
        assert predictor is not None
        assert not predictor.is_trained
        assert predictor.VERSION == "1.0"

    def test_prepare_training_data(self, predictor, training_data):
        """Test training data preparation."""
        data_points, journal_entries = training_data
        prepared = predictor.prepare_training_data(data_points, journal_entries)

        assert prepared is not None
        assert isinstance(prepared, TrainingData)
        assert prepared.sample_count >= 7
        assert len(prepared.feature_names) == 5
        assert prepared.features.shape[1] == 5  # 5 features

    def test_prepare_training_data_insufficient(self, predictor):
        """Test with insufficient data."""
        # Only 3 days of data
        data_points, journal_entries = generate_training_data(3)
        prepared = predictor.prepare_training_data(data_points, journal_entries)

        # Should return None due to insufficient samples
        assert prepared is None

    def test_train(self, predictor, training_data):
        """Test model training."""
        data_points, journal_entries = training_data
        prepared = predictor.prepare_training_data(data_points, journal_entries)

        assert prepared is not None

        metrics = predictor.train(prepared)

        assert predictor.is_trained
        assert 'sample_count' in metrics
        assert 'r_squared' in metrics
        assert 'feature_importance' in metrics
        assert metrics['sample_count'] > 0
        assert 0 <= metrics['r_squared'] <= 1

    def test_predict_before_training(self, predictor):
        """Test that predict fails before training."""
        with pytest.raises(ValueError, match="must be trained"):
            predictor.predict(7.5, 1.5, 75, 1, 5.0)

    def test_predict_after_training(self, predictor, training_data):
        """Test prediction after training."""
        data_points, journal_entries = training_data
        prepared = predictor.prepare_training_data(data_points, journal_entries)
        predictor.train(prepared)

        prediction = predictor.predict(
            sleep_duration=7.5,
            deep_sleep=1.5,
            readiness_score=75,
            day_of_week=1,  # Tuesday
            prev_day_energy=6.0
        )

        assert prediction is not None
        assert isinstance(prediction, EnergyPrediction)
        assert prediction.source == PredictionSource.ML
        assert 1.0 <= prediction.predicted_energy <= 10.0
        assert 0 <= prediction.confidence <= 1

    def test_predict_clamps_output(self, predictor, training_data):
        """Test that predictions are clamped to valid range."""
        data_points, journal_entries = training_data
        prepared = predictor.prepare_training_data(data_points, journal_entries)
        predictor.train(prepared)

        # Extreme inputs
        prediction = predictor.predict(
            sleep_duration=12.0,  # Very high
            deep_sleep=4.0,
            readiness_score=100,
            day_of_week=6,
            prev_day_energy=10.0
        )

        assert 1.0 <= prediction.predicted_energy <= 10.0

    def test_predict_from_data(self, predictor, training_data):
        """Test predict_from_data method."""
        data_points, journal_entries = training_data
        prepared = predictor.prepare_training_data(data_points, journal_entries)
        predictor.train(prepared)

        # Get a date that has data
        target_date = data_points[0]['date']

        prediction = predictor.predict_from_data(data_points, target_date)

        assert prediction is not None
        assert prediction.date == target_date

    def test_model_params_persistence(self, predictor, training_data):
        """Test saving and loading model parameters."""
        data_points, journal_entries = training_data
        prepared = predictor.prepare_training_data(data_points, journal_entries)
        predictor.train(prepared)

        params = predictor.get_model_params()
        assert params is not None
        assert 'coefficients' in params
        assert 'intercept' in params
        assert 'feature_means' in params

        # Create new predictor and load params
        new_predictor = EnergyPredictor()
        assert not new_predictor.is_trained

        success = new_predictor.load_model_params(params)
        assert success
        assert new_predictor.is_trained

        # Both should give same predictions
        pred1 = predictor.predict(7.5, 1.5, 75, 1, 5.0)
        pred2 = new_predictor.predict(7.5, 1.5, 75, 1, 5.0)

        assert pred1.predicted_energy == pred2.predicted_energy


class TestPredictionComparator:
    """Test suite for PredictionComparator."""

    @pytest.fixture
    def comparator(self):
        """Create comparator instance."""
        return PredictionComparator()

    def test_init(self, comparator):
        """Test comparator initialization."""
        assert comparator is not None

    def test_record_ml_prediction(self, comparator):
        """Test recording ML predictions."""
        prediction = EnergyPrediction(
            date="2024-01-15",
            source=PredictionSource.ML,
            predicted_energy=7.5,
            confidence=0.85,
            features_used={"sleep_duration": 7.5}
        )

        comparator.record_ml_prediction(prediction)

        all_preds = comparator.get_all_predictions()
        assert len(all_preds['ml']) == 1
        assert all_preds['ml'][0]['predicted_energy'] == 7.5

    def test_record_llm_prediction(self, comparator):
        """Test recording LLM predictions."""
        comparator.record_llm_prediction("2024-01-15", 8.0, 0.7)

        all_preds = comparator.get_all_predictions()
        assert len(all_preds['llm']) == 1
        assert all_preds['llm'][0]['predicted_energy'] == 8.0

    def test_record_actual(self, comparator):
        """Test recording actual energy."""
        comparator.record_actual("2024-01-15", 7.0)

        all_preds = comparator.get_all_predictions()
        assert len(all_preds['actuals']) == 1
        assert all_preds['actuals'][0]['energy'] == 7.0

    def test_calculate_accuracy_insufficient_data(self, comparator):
        """Test accuracy calculation with insufficient data."""
        # Only 2 predictions
        comparator.record_ml_prediction(EnergyPrediction(
            date="2024-01-15",
            source=PredictionSource.ML,
            predicted_energy=7.5,
            confidence=0.85,
            features_used={}
        ))
        comparator.record_ml_prediction(EnergyPrediction(
            date="2024-01-16",
            source=PredictionSource.ML,
            predicted_energy=6.5,
            confidence=0.85,
            features_used={}
        ))
        comparator.record_actual("2024-01-15", 7.0)
        comparator.record_actual("2024-01-16", 6.0)

        accuracy = comparator.calculate_accuracy(PredictionSource.ML)

        # Needs 3+ samples
        assert accuracy is None

    def test_calculate_accuracy_with_data(self, comparator):
        """Test accuracy calculation with sufficient data."""
        # Add 5 predictions
        for i in range(5):
            date = f"2024-01-{15+i}"
            comparator.record_ml_prediction(EnergyPrediction(
                date=date,
                source=PredictionSource.ML,
                predicted_energy=7.0 + i * 0.2,
                confidence=0.85,
                features_used={}
            ))
            comparator.record_actual(date, 7.0 + i * 0.1)  # Slightly different

        accuracy = comparator.calculate_accuracy(PredictionSource.ML)

        assert accuracy is not None
        assert accuracy.source == PredictionSource.ML
        assert accuracy.mae >= 0
        assert accuracy.rmse >= 0
        assert accuracy.sample_size == 5

    def test_compare_sources(self, comparator):
        """Test comparing ML vs LLM predictions."""
        # Add predictions for both sources
        for i in range(5):
            date = f"2024-01-{15+i}"

            # ML predictions
            comparator.record_ml_prediction(EnergyPrediction(
                date=date,
                source=PredictionSource.ML,
                predicted_energy=7.0 + i * 0.1,  # Closer to actual
                confidence=0.85,
                features_used={}
            ))

            # LLM predictions
            comparator.record_llm_prediction(date, 7.0 + i * 0.5, 0.7)  # Further from actual

            # Actual values
            comparator.record_actual(date, 7.0 + i * 0.1)

        result = comparator.compare_sources()

        assert result is not None
        assert result['ml'] is not None
        assert result['llm'] is not None
        # ML should win since predictions are closer
        assert result['winner'] == 'ml'


class TestEnergyPredictionDataclass:
    """Test EnergyPrediction dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        prediction = EnergyPrediction(
            date="2024-01-15",
            source=PredictionSource.ML,
            predicted_energy=7.5,
            confidence=0.85,
            features_used={"sleep_duration": 7.5}
        )

        d = prediction.to_dict()

        assert d['date'] == "2024-01-15"
        assert d['source'] == "ml"
        assert d['predicted_energy'] == 7.5
        assert d['confidence'] == 0.85
        assert d['model_version'] == "1.0"
