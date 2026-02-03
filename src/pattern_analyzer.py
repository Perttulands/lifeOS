"""
LifeOS Statistical Pattern Analyzer

Real statistical analysis for pattern detection:
- Pearson/Spearman correlations with p-values
- Sliding window trend detection
- Day-of-week pattern analysis
- Statistical significance testing
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import math

try:
    import numpy as np
    from scipy import stats
    from scipy.stats import pearsonr, spearmanr, ttest_ind, linregress
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    # Fallback implementations for basic stats
    np = None


@dataclass
class CorrelationResult:
    """Result of a correlation analysis."""
    var1: str
    var2: str
    coefficient: float  # -1 to 1
    p_value: float
    sample_size: int
    is_significant: bool  # p < 0.05


@dataclass
class TrendResult:
    """Result of a trend analysis."""
    variable: str
    direction: str  # 'increasing', 'decreasing', 'stable'
    slope: float
    r_squared: float
    change_percent: float
    sample_size: int
    is_significant: bool


@dataclass
class DayOfWeekPattern:
    """Day-of-week pattern for a variable."""
    variable: str
    best_day: str
    worst_day: str
    best_avg: float
    worst_avg: float
    difference_percent: float
    is_significant: bool
    day_averages: Dict[str, float]


@dataclass
class DetectedPattern:
    """A statistically detected pattern."""
    name: str
    description: str
    pattern_type: str  # 'correlation', 'trend', 'day_of_week', 'anomaly'
    variables: List[str]
    strength: float  # -1 to 1
    confidence: float  # Based on p-value
    sample_size: int
    actionable: bool
    details: Dict[str, Any]


class PatternAnalyzer:
    """
    Statistical pattern analyzer for LifeOS data.

    Performs real statistical analysis to find patterns in sleep,
    activity, readiness, and other metrics.
    """

    # Minimum samples for reliable analysis
    MIN_SAMPLES_CORRELATION = 7
    MIN_SAMPLES_TREND = 7
    MIN_SAMPLES_PER_DAY = 2

    # Significance threshold
    SIGNIFICANCE_LEVEL = 0.05

    # Correlation strength thresholds
    WEAK_CORRELATION = 0.3
    MODERATE_CORRELATION = 0.5
    STRONG_CORRELATION = 0.7

    def __init__(self):
        if not HAS_SCIPY:
            raise ImportError(
                "scipy and numpy required for pattern analysis. "
                "Install with: pip install scipy numpy"
            )

    def analyze_all(
        self,
        data_points: List[Dict[str, Any]],
        min_days: int = 7
    ) -> List[DetectedPattern]:
        """
        Run all pattern detection analyses.

        Args:
            data_points: List of data points with date, type, value, metadata
            min_days: Minimum days of data required

        Returns:
            List of detected patterns, sorted by confidence
        """
        patterns = []

        # Organize data by date and type
        organized = self._organize_data(data_points)

        if len(organized['dates']) < min_days:
            return []

        # Run correlation analysis
        patterns.extend(self._find_correlations(organized))

        # Run trend analysis
        patterns.extend(self._find_trends(organized))

        # Run day-of-week analysis
        patterns.extend(self._find_day_patterns(organized))

        # Sort by confidence (highest first)
        patterns.sort(key=lambda p: (p.confidence, abs(p.strength)), reverse=True)

        return patterns

    def _organize_data(
        self,
        data_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Organize data points by date and type for analysis."""
        by_date = defaultdict(dict)

        for dp in data_points:
            date = dp.get('date')
            dp_type = dp.get('type')
            value = dp.get('value')
            metadata = dp.get('metadata', {})

            if date and dp_type and value is not None:
                by_date[date][dp_type] = {
                    'value': float(value),
                    'metadata': metadata
                }

        # Extract time series for each variable
        dates = sorted(by_date.keys())

        # Build time series dict
        variables = defaultdict(list)
        date_indices = []

        for i, date in enumerate(dates):
            date_indices.append(date)
            day_data = by_date[date]

            # Extract all metrics
            if 'sleep' in day_data:
                variables['sleep_duration'].append(day_data['sleep']['value'])
                meta = day_data['sleep'].get('metadata', {})
                if 'deep_sleep_hours' in meta:
                    variables['deep_sleep'].append(meta['deep_sleep_hours'])
                if 'rem_sleep_hours' in meta:
                    variables['rem_sleep'].append(meta['rem_sleep_hours'])
                if 'efficiency' in meta:
                    variables['sleep_efficiency'].append(meta['efficiency'])
                if 'score' in meta:
                    variables['sleep_score'].append(meta['score'])
            else:
                variables['sleep_duration'].append(np.nan)
                variables['deep_sleep'].append(np.nan)
                variables['rem_sleep'].append(np.nan)
                variables['sleep_efficiency'].append(np.nan)
                variables['sleep_score'].append(np.nan)

            if 'readiness' in day_data:
                variables['readiness'].append(day_data['readiness']['value'])
            else:
                variables['readiness'].append(np.nan)

            if 'activity' in day_data:
                variables['activity'].append(day_data['activity']['value'])
            else:
                variables['activity'].append(np.nan)

            if 'energy' in day_data:
                variables['energy'].append(day_data['energy']['value'])
            else:
                variables['energy'].append(np.nan)

        # Convert to numpy arrays
        for key in variables:
            variables[key] = np.array(variables[key])

        return {
            'dates': dates,
            'date_indices': date_indices,
            'variables': dict(variables),
            'by_date': dict(by_date)
        }

    def _find_correlations(
        self,
        organized: Dict[str, Any]
    ) -> List[DetectedPattern]:
        """Find significant correlations between variables."""
        patterns = []
        variables = organized['variables']

        # Define meaningful correlation pairs
        correlation_pairs = [
            ('sleep_duration', 'readiness', 'Sleep duration affects next-day readiness'),
            ('sleep_duration', 'activity', 'Sleep duration affects activity levels'),
            ('deep_sleep', 'readiness', 'Deep sleep quality drives readiness'),
            ('deep_sleep', 'energy', 'Deep sleep affects perceived energy'),
            ('sleep_efficiency', 'readiness', 'Sleep efficiency impacts readiness'),
            ('sleep_score', 'activity', 'Sleep score correlates with activity'),
            ('activity', 'sleep_score', 'Activity level affects sleep quality'),
            ('readiness', 'activity', 'Readiness predicts activity capacity'),
        ]

        for var1, var2, hypothesis in correlation_pairs:
            if var1 not in variables or var2 not in variables:
                continue

            result = self._calculate_correlation(
                variables[var1],
                variables[var2]
            )

            if result and result.is_significant and abs(result.coefficient) >= self.WEAK_CORRELATION:
                pattern = self._correlation_to_pattern(result, var1, var2, hypothesis)
                patterns.append(pattern)

        return patterns

    def _calculate_correlation(
        self,
        x: np.ndarray,
        y: np.ndarray
    ) -> Optional[CorrelationResult]:
        """Calculate Pearson correlation with p-value."""
        # Remove NaN pairs
        mask = ~(np.isnan(x) | np.isnan(y))
        x_clean = x[mask]
        y_clean = y[mask]

        if len(x_clean) < self.MIN_SAMPLES_CORRELATION:
            return None

        try:
            coef, p_value = pearsonr(x_clean, y_clean)

            return CorrelationResult(
                var1="",  # Will be set by caller
                var2="",
                coefficient=coef,
                p_value=p_value,
                sample_size=len(x_clean),
                is_significant=p_value < self.SIGNIFICANCE_LEVEL
            )
        except Exception:
            return None

    def _correlation_to_pattern(
        self,
        result: CorrelationResult,
        var1: str,
        var2: str,
        hypothesis: str
    ) -> DetectedPattern:
        """Convert correlation result to a pattern."""
        # Determine strength description
        abs_coef = abs(result.coefficient)
        if abs_coef >= self.STRONG_CORRELATION:
            strength_desc = "strong"
        elif abs_coef >= self.MODERATE_CORRELATION:
            strength_desc = "moderate"
        else:
            strength_desc = "weak"

        # Direction
        direction = "positive" if result.coefficient > 0 else "negative"

        # Human-readable variable names
        var_names = {
            'sleep_duration': 'sleep duration',
            'deep_sleep': 'deep sleep',
            'rem_sleep': 'REM sleep',
            'sleep_efficiency': 'sleep efficiency',
            'sleep_score': 'sleep score',
            'readiness': 'readiness score',
            'activity': 'activity score',
            'energy': 'energy level'
        }

        v1_name = var_names.get(var1, var1)
        v2_name = var_names.get(var2, var2)

        # Build description
        if result.coefficient > 0:
            desc = f"Higher {v1_name} correlates with higher {v2_name}"
        else:
            desc = f"Higher {v1_name} correlates with lower {v2_name}"

        desc += f" (r={result.coefficient:.2f}, p={result.p_value:.3f}, n={result.sample_size})"

        # Name
        name = f"{strength_desc.title()} {direction} correlation: {v1_name} → {v2_name}"

        # Confidence based on p-value (lower p = higher confidence)
        confidence = 1.0 - result.p_value

        return DetectedPattern(
            name=name,
            description=desc,
            pattern_type='correlation',
            variables=[var1, var2],
            strength=result.coefficient,
            confidence=confidence,
            sample_size=result.sample_size,
            actionable=True,  # Most correlations are actionable
            details={
                'coefficient': result.coefficient,
                'p_value': result.p_value,
                'hypothesis': hypothesis
            }
        )

    def _find_trends(
        self,
        organized: Dict[str, Any]
    ) -> List[DetectedPattern]:
        """Find significant trends over time."""
        patterns = []
        variables = organized['variables']
        dates = organized['dates']

        for var_name, values in variables.items():
            result = self._calculate_trend(values, dates)

            if result and result.is_significant and abs(result.change_percent) >= 5:
                pattern = self._trend_to_pattern(result, var_name)
                patterns.append(pattern)

        return patterns

    def _calculate_trend(
        self,
        values: np.ndarray,
        dates: List[str]
    ) -> Optional[TrendResult]:
        """Calculate linear trend with significance testing."""
        # Remove NaN
        mask = ~np.isnan(values)
        clean_values = values[mask]

        if len(clean_values) < self.MIN_SAMPLES_TREND:
            return None

        # Use indices as x values (days)
        x = np.arange(len(clean_values))

        try:
            slope, intercept, r_value, p_value, std_err = linregress(x, clean_values)

            # Calculate change over the period
            start_val = intercept
            end_val = intercept + slope * (len(clean_values) - 1)

            if start_val > 0:
                change_percent = ((end_val - start_val) / start_val) * 100
            else:
                change_percent = 0

            # Determine direction
            if p_value < self.SIGNIFICANCE_LEVEL:
                if slope > 0:
                    direction = 'increasing'
                elif slope < 0:
                    direction = 'decreasing'
                else:
                    direction = 'stable'
            else:
                direction = 'stable'

            return TrendResult(
                variable="",  # Set by caller
                direction=direction,
                slope=slope,
                r_squared=r_value ** 2,
                change_percent=change_percent,
                sample_size=len(clean_values),
                is_significant=p_value < self.SIGNIFICANCE_LEVEL
            )
        except Exception:
            return None

    def _trend_to_pattern(
        self,
        result: TrendResult,
        var_name: str
    ) -> DetectedPattern:
        """Convert trend result to a pattern."""
        var_names = {
            'sleep_duration': 'sleep duration',
            'deep_sleep': 'deep sleep',
            'rem_sleep': 'REM sleep',
            'sleep_efficiency': 'sleep efficiency',
            'sleep_score': 'sleep score',
            'readiness': 'readiness',
            'activity': 'activity',
            'energy': 'energy'
        }

        v_name = var_names.get(var_name, var_name)

        if result.direction == 'increasing':
            name = f"Improving {v_name}"
            desc = f"Your {v_name} has been increasing by {result.change_percent:.1f}% over {result.sample_size} days"
            actionable = True
        elif result.direction == 'decreasing':
            name = f"Declining {v_name}"
            desc = f"Your {v_name} has been decreasing by {abs(result.change_percent):.1f}% over {result.sample_size} days"
            actionable = True
        else:
            name = f"Stable {v_name}"
            desc = f"Your {v_name} has been stable over {result.sample_size} days"
            actionable = False

        desc += f" (R²={result.r_squared:.2f})"

        return DetectedPattern(
            name=name,
            description=desc,
            pattern_type='trend',
            variables=[var_name],
            strength=result.slope,  # Normalized slope would be better
            confidence=result.r_squared,
            sample_size=result.sample_size,
            actionable=actionable,
            details={
                'direction': result.direction,
                'slope': result.slope,
                'r_squared': result.r_squared,
                'change_percent': result.change_percent
            }
        )

    def _find_day_patterns(
        self,
        organized: Dict[str, Any]
    ) -> List[DetectedPattern]:
        """Find day-of-week patterns."""
        patterns = []
        by_date = organized['by_date']

        # Group by day of week
        day_values = defaultdict(lambda: defaultdict(list))

        for date, data in by_date.items():
            day_of_week = datetime.strptime(date, "%Y-%m-%d").strftime("%A")

            if 'sleep' in data:
                day_values['sleep_duration'][day_of_week].append(data['sleep']['value'])
                meta = data['sleep'].get('metadata', {})
                if 'deep_sleep_hours' in meta:
                    day_values['deep_sleep'][day_of_week].append(meta['deep_sleep_hours'])
                if 'score' in meta:
                    day_values['sleep_score'][day_of_week].append(meta['score'])

            if 'readiness' in data:
                day_values['readiness'][day_of_week].append(data['readiness']['value'])

            if 'activity' in data:
                day_values['activity'][day_of_week].append(data['activity']['value'])

        # Analyze each variable
        for var_name, day_data in day_values.items():
            result = self._analyze_day_pattern(var_name, day_data)

            if result and result.is_significant and result.difference_percent >= 10:
                pattern = self._day_pattern_to_pattern(result)
                patterns.append(pattern)

        return patterns

    def _analyze_day_pattern(
        self,
        var_name: str,
        day_data: Dict[str, List[float]]
    ) -> Optional[DayOfWeekPattern]:
        """Analyze day-of-week pattern for a variable."""
        # Calculate averages per day
        day_averages = {}
        for day, values in day_data.items():
            if len(values) >= self.MIN_SAMPLES_PER_DAY:
                day_averages[day] = np.mean(values)

        if len(day_averages) < 3:  # Need at least 3 days with data
            return None

        # Find best and worst days
        best_day = max(day_averages, key=day_averages.get)
        worst_day = min(day_averages, key=day_averages.get)

        best_avg = day_averages[best_day]
        worst_avg = day_averages[worst_day]

        if worst_avg > 0:
            diff_percent = ((best_avg - worst_avg) / worst_avg) * 100
        else:
            diff_percent = 0

        # Statistical test: ANOVA would be ideal, but t-test between best/worst
        best_values = day_data[best_day]
        worst_values = day_data[worst_day]

        is_significant = False
        if len(best_values) >= 2 and len(worst_values) >= 2:
            try:
                _, p_value = ttest_ind(best_values, worst_values)
                is_significant = p_value < self.SIGNIFICANCE_LEVEL
            except Exception:
                pass

        return DayOfWeekPattern(
            variable=var_name,
            best_day=best_day,
            worst_day=worst_day,
            best_avg=best_avg,
            worst_avg=worst_avg,
            difference_percent=diff_percent,
            is_significant=is_significant,
            day_averages=day_averages
        )

    def _day_pattern_to_pattern(
        self,
        result: DayOfWeekPattern
    ) -> DetectedPattern:
        """Convert day-of-week pattern to DetectedPattern."""
        var_names = {
            'sleep_duration': 'sleep duration',
            'deep_sleep': 'deep sleep',
            'sleep_score': 'sleep score',
            'readiness': 'readiness',
            'activity': 'activity'
        }

        v_name = var_names.get(result.variable, result.variable)

        name = f"{result.best_day} vs {result.worst_day}: {v_name}"

        desc = (
            f"Your {v_name} is {result.difference_percent:.0f}% higher on {result.best_day}s "
            f"({result.best_avg:.1f}) compared to {result.worst_day}s ({result.worst_avg:.1f})"
        )

        return DetectedPattern(
            name=name,
            description=desc,
            pattern_type='day_of_week',
            variables=[result.variable],
            strength=result.difference_percent / 100,  # Normalize to 0-1 range
            confidence=0.8 if result.is_significant else 0.5,
            sample_size=sum(len(v) for v in []),  # Would need to track this
            actionable=True,
            details={
                'best_day': result.best_day,
                'worst_day': result.worst_day,
                'best_avg': result.best_avg,
                'worst_avg': result.worst_avg,
                'day_averages': result.day_averages
            }
        )

    def analyze_sliding_window(
        self,
        organized: Dict[str, Any],
        window_size: int = 7
    ) -> List[DetectedPattern]:
        """
        Analyze patterns using sliding windows.

        Detects changes in metrics between recent and previous windows.
        """
        patterns = []
        variables = organized['variables']
        dates = organized['dates']

        if len(dates) < window_size * 2:
            return []  # Need at least 2 windows

        for var_name, values in variables.items():
            # Remove NaN
            mask = ~np.isnan(values)
            clean_values = values[mask]

            if len(clean_values) < window_size * 2:
                continue

            # Compare recent window to previous window
            recent = clean_values[-window_size:]
            previous = clean_values[-window_size*2:-window_size]

            recent_mean = np.mean(recent)
            previous_mean = np.mean(previous)

            if previous_mean > 0:
                change_percent = ((recent_mean - previous_mean) / previous_mean) * 100
            else:
                continue

            # Statistical test
            try:
                _, p_value = ttest_ind(recent, previous)
                is_significant = p_value < self.SIGNIFICANCE_LEVEL
            except Exception:
                continue

            # Only report significant changes
            if is_significant and abs(change_percent) >= 10:
                var_names = {
                    'sleep_duration': 'sleep duration',
                    'deep_sleep': 'deep sleep',
                    'sleep_score': 'sleep score',
                    'readiness': 'readiness',
                    'activity': 'activity'
                }
                v_name = var_names.get(var_name, var_name)

                if change_percent > 0:
                    name = f"Recent improvement in {v_name}"
                    desc = f"Your {v_name} increased {change_percent:.0f}% in the last {window_size} days"
                else:
                    name = f"Recent decline in {v_name}"
                    desc = f"Your {v_name} decreased {abs(change_percent):.0f}% in the last {window_size} days"

                desc += f" compared to the previous {window_size} days (p={p_value:.3f})"

                patterns.append(DetectedPattern(
                    name=name,
                    description=desc,
                    pattern_type='window_change',
                    variables=[var_name],
                    strength=change_percent / 100,
                    confidence=1.0 - p_value,
                    sample_size=window_size * 2,
                    actionable=True,
                    details={
                        'recent_mean': recent_mean,
                        'previous_mean': previous_mean,
                        'change_percent': change_percent,
                        'p_value': p_value,
                        'window_size': window_size
                    }
                ))

        return patterns


# Singleton instance
_analyzer: Optional[PatternAnalyzer] = None


def get_analyzer() -> PatternAnalyzer:
    """Get or create the pattern analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = PatternAnalyzer()
    return _analyzer
