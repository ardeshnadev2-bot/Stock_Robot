import pytest
import pandas as pd
import numpy as np
from src.data.data_validator import DataValidator
from src.utils.error_handler import ValidationError

def test_validator_empty_dataframe():
    """Test validator behavior with empty dataframes."""
    validator = DataValidator()
    with pytest.raises(ValidationError) as excinfo:
        validator.validate_and_clean(pd.DataFrame())
    assert "DataFrame is empty" in str(excinfo.value)

def test_validator_missing_columns():
    """Test validation fails when required columns are missing."""
    validator = DataValidator()
    # Missing Volume
    df = pd.DataFrame({
        "Date": ["2026-08-01"],
        "Open": [100.0],
        "High": [105.0],
        "Low": [95.0],
        "Close": [101.0]
    })
    with pytest.raises(ValidationError) as excinfo:
        validator.validate_and_clean(df)
    assert "Missing required market data columns" in str(excinfo.value)

def test_validator_duplicates_deduplication():
    """Test validator drops duplicate date records."""
    validator = DataValidator()
    df = pd.DataFrame({
        "Date": ["2026-08-01", "2026-08-01", "2026-08-02"],
        "Open": [100.0, 100.0, 102.0],
        "High": [105.0, 105.0, 107.0],
        "Low": [95.0, 95.0, 97.0],
        "Close": [101.0, 101.0, 103.0],
        "Volume": [1000, 1000, 1200]
    })
    
    cleaned = validator.validate_and_clean(df)
    assert len(cleaned) == 2
    # Ensure date has no timezone and is standardized
    assert list(cleaned['open']) == [100.0, 102.0]

def test_validator_invalid_ohlc_relationships():
    """Test validator fixes invalid OHLC range values."""
    validator = DataValidator()
    # High (90) is lower than Open (100) and Close (105)
    # Low (110) is higher than everything else
    df = pd.DataFrame({
        "Date": ["2026-08-01"],
        "Open": [100.0],
        "High": [90.0],
        "Low": [110.0],
        "Close": [105.0],
        "Volume": [1000]
    })
    
    cleaned = validator.validate_and_clean(df)
    
    # Check that high has been adjusted to max (110) and low to min (90)
    assert cleaned.loc[0, 'high'] == 110.0
    assert cleaned.loc[0, 'low'] == 90.0
    assert cleaned.loc[0, 'high'] >= cleaned.loc[0, 'open']
    assert cleaned.loc[0, 'low'] <= cleaned.loc[0, 'close']

def test_validator_missing_nan_handling():
    """Test validator recovers and cleans NaN values."""
    validator = DataValidator()
    df = pd.DataFrame({
        "Date": ["2026-08-01", "2026-08-02", "2026-08-03"],
        "Open": [100.0, np.nan, 105.0],
        "High": [105.0, np.nan, 108.0],
        "Low": [95.0, np.nan, 98.0],
        "Close": [101.0, np.nan, 106.0],
        "Volume": [1000, np.nan, 1200]
    })
    
    cleaned = validator.validate_and_clean(df)
    
    # Assert NaN on 2nd row was filled correctly from row 1 (forward fill)
    assert len(cleaned) == 3
    assert cleaned.loc[1, 'close'] == 101.0  # forward filled from index 0
    assert cleaned.loc[1, 'volume'] == 0.0   # volume filled with 0
