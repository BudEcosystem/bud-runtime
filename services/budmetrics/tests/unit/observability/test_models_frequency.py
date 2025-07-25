"""Unit tests for FrequencyUnit and Frequency classes."""

import pytest

from budmetrics.observability.models import FrequencyUnit, Frequency


class TestFrequencyUnit:
    """Test cases for FrequencyUnit enum."""
    
    def test_frequency_unit_values(self):
        """Test that all frequency units have correct values."""
        assert FrequencyUnit.HOUR.value == "hour"
        assert FrequencyUnit.DAY.value == "day"
        assert FrequencyUnit.WEEK.value == "week"
        assert FrequencyUnit.MONTH.value == "month"
        assert FrequencyUnit.QUARTER.value == "quarter"
        assert FrequencyUnit.YEAR.value == "year"
    
    def test_frequency_unit_from_string(self):
        """Test creating FrequencyUnit from string values."""
        assert FrequencyUnit("hour") == FrequencyUnit.HOUR
        assert FrequencyUnit("day") == FrequencyUnit.DAY
        assert FrequencyUnit("week") == FrequencyUnit.WEEK
        assert FrequencyUnit("month") == FrequencyUnit.MONTH
        assert FrequencyUnit("quarter") == FrequencyUnit.QUARTER
        assert FrequencyUnit("year") == FrequencyUnit.YEAR
    
    def test_frequency_unit_invalid_value(self):
        """Test that invalid frequency unit raises ValueError."""
        with pytest.raises(ValueError):
            FrequencyUnit("invalid")
        with pytest.raises(ValueError):
            FrequencyUnit("second")  # Not in actual enum
        with pytest.raises(ValueError):
            FrequencyUnit("minute")  # Not in actual enum
    
    def test_frequency_unit_case_sensitivity(self):
        """Test that FrequencyUnit is case-sensitive."""
        with pytest.raises(ValueError):
            FrequencyUnit("HOUR")
        with pytest.raises(ValueError):
            FrequencyUnit("Hour")


class TestFrequency:
    """Test cases for Frequency class."""
    
    def test_standard_frequencies(self):
        """Test creating standard frequency instances."""
        # Test class methods for standard frequencies
        freq_hourly = Frequency.hourly()
        assert freq_hourly.value is None
        assert freq_hourly.unit == FrequencyUnit.HOUR
        
        freq_daily = Frequency.daily()
        assert freq_daily.value is None
        assert freq_daily.unit == FrequencyUnit.DAY
        
        freq_weekly = Frequency.weekly()
        assert freq_weekly.value is None
        assert freq_weekly.unit == FrequencyUnit.WEEK
        
        freq_monthly = Frequency.monthly()
        assert freq_monthly.value is None
        assert freq_monthly.unit == FrequencyUnit.MONTH
        
        freq_quarterly = Frequency.quarterly()
        assert freq_quarterly.value is None
        assert freq_quarterly.unit == FrequencyUnit.QUARTER
        
        freq_yearly = Frequency.yearly()
        assert freq_yearly.value is None
        assert freq_yearly.unit == FrequencyUnit.YEAR
    
    def test_custom_frequencies_simple(self):
        """Test creating simple custom frequency instances."""
        # Test custom frequency creation
        freq = Frequency.custom(7, FrequencyUnit.DAY)
        assert freq.value == 7
        assert freq.unit == FrequencyUnit.DAY
        
        # Test with string unit
        freq2 = Frequency.custom(3, "hour")
        assert freq2.value == 3
        assert freq2.unit == FrequencyUnit.HOUR
        
        # Test various custom frequencies
        test_cases = [
            (3, FrequencyUnit.HOUR),
            (7, FrequencyUnit.DAY),
            (2, FrequencyUnit.WEEK),
            (6, FrequencyUnit.MONTH),
            (2, FrequencyUnit.QUARTER),
            (5, FrequencyUnit.YEAR),
        ]
        
        for value, unit in test_cases:
            freq = Frequency.custom(value, unit)
            assert freq.value == value
            assert freq.unit == unit
    
    def test_frequency_name_property(self):
        """Test the name property of Frequency."""
        # Standard frequencies (value=None)
        freq = Frequency.hourly()
        assert freq.name == "hourly"
        
        freq = Frequency.daily()
        assert freq.name == "dayly"
        
        # Custom frequencies with value=1
        freq = Frequency.custom(1, FrequencyUnit.DAY)
        assert freq.name == "dayly"
        
        # Custom frequencies with value > 1
        freq = Frequency.custom(7, FrequencyUnit.DAY)
        assert freq.name == "every_7_days"
        
        freq = Frequency.custom(3, FrequencyUnit.HOUR)
        assert freq.name == "every_3_hours"
    
    def test_to_clickhouse_interval(self):
        """Test conversion to ClickHouse INTERVAL syntax."""
        # Standard frequency (value=None)
        freq = Frequency.daily()
        assert freq.to_clickhouse_interval() == "INTERVAL 1 DAY"
        assert freq.to_clickhouse_interval("desc") == "INTERVAL -1 DAY"
        
        # Custom frequency
        freq = Frequency.custom(7, FrequencyUnit.DAY)
        assert freq.to_clickhouse_interval() == "INTERVAL 7 DAY"
        assert freq.to_clickhouse_interval("desc") == "INTERVAL -7 DAY"
        
        freq = Frequency.custom(3, FrequencyUnit.MONTH)
        assert freq.to_clickhouse_interval() == "INTERVAL 3 MONTH"
        assert freq.to_clickhouse_interval("desc") == "INTERVAL -3 MONTH"
    
    def test_frequency_str_method(self):
        """Test string representation of frequency."""
        freq = Frequency.custom(7, FrequencyUnit.DAY)
        assert str(freq) == "every_7_days"
        
        freq_standard = Frequency.daily()
        assert str(freq_standard) == "dayly"
    
    def test_invalid_unit_string(self):
        """Test creating custom frequency with invalid unit string."""
        with pytest.raises(ValueError):
            Frequency.custom(3, "invalid_unit")
        
        with pytest.raises(ValueError):
            Frequency.custom(3, "seconds")  # Not in enum
    
    def test_frequency_initialization(self):
        """Test direct Frequency initialization."""
        # Test with None value (standard frequency)
        freq = Frequency(None, FrequencyUnit.DAY)
        assert freq.value is None
        assert freq.unit == FrequencyUnit.DAY
        
        # Test with numeric value (custom frequency)
        freq = Frequency(7, FrequencyUnit.DAY)
        assert freq.value == 7
        assert freq.unit == FrequencyUnit.DAY