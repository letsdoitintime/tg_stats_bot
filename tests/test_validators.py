"""Tests for validation utilities."""

import pytest
from tgstats.utils.validators import (
    parse_boolean_argument,
    validate_chat_id,
    validate_user_id,
    validate_date_string,
    validate_timezone,
    validate_page_number,
    validate_per_page,
    validate_retention_days,
)
from tgstats.core.exceptions import ValidationError


class TestParseBooleanArgument:
    """Tests for parse_boolean_argument function."""

    def test_parse_on_values(self):
        """Test parsing 'on' values."""
        for value in ["on", "true", "1", "yes", "enabled", "enable", "ON", "TRUE"]:
            assert parse_boolean_argument(value) is True

    def test_parse_off_values(self):
        """Test parsing 'off' values."""
        for value in ["off", "false", "0", "no", "disabled", "disable", "OFF", "FALSE"]:
            assert parse_boolean_argument(value) is False

    def test_parse_invalid_value(self):
        """Test parsing invalid value raises ValidationError."""
        with pytest.raises(ValidationError):
            parse_boolean_argument("invalid")

    def test_parse_none(self):
        """Test parsing None raises ValidationError."""
        with pytest.raises(ValidationError):
            parse_boolean_argument(None)


class TestValidateChatId:
    """Tests for validate_chat_id function."""

    def test_validate_valid_chat_id(self):
        """Test validating valid chat ID."""
        assert validate_chat_id(-1001234567890) == -1001234567890
        assert validate_chat_id("123456") == 123456

    def test_validate_invalid_chat_id(self):
        """Test validating invalid chat ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_chat_id("invalid")
        with pytest.raises(ValidationError):
            validate_chat_id(None)


class TestValidateUserId:
    """Tests for validate_user_id function."""

    def test_validate_valid_user_id(self):
        """Test validating valid user ID."""
        assert validate_user_id(123456789) == 123456789
        assert validate_user_id("987654321") == 987654321

    def test_validate_invalid_user_id(self):
        """Test validating invalid user ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_user_id("invalid")


class TestValidateDateString:
    """Tests for validate_date_string function."""

    def test_validate_valid_date(self):
        """Test validating valid date string."""
        assert validate_date_string("2025-01-15") == "2025-01-15"
        assert validate_date_string("2024-12-31") == "2024-12-31"

    def test_validate_invalid_date_format(self):
        """Test validating invalid date format raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_date_string("15-01-2025")
        with pytest.raises(ValidationError):
            validate_date_string("2025/01/15")
        with pytest.raises(ValidationError):
            validate_date_string("invalid")

    def test_validate_invalid_date_value(self):
        """Test validating invalid date value raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_date_string("2025-13-01")  # Invalid month
        with pytest.raises(ValidationError):
            validate_date_string("2025-01-32")  # Invalid day


class TestValidateTimezone:
    """Tests for validate_timezone function."""

    def test_validate_valid_timezone(self):
        """Test validating valid timezone."""
        assert validate_timezone("UTC") == "UTC"
        assert validate_timezone("America/New_York") == "America/New_York"
        assert validate_timezone("Europe/Sofia") == "Europe/Sofia"

    def test_validate_invalid_timezone(self):
        """Test validating invalid timezone raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_timezone("Invalid/Timezone")


class TestValidatePageNumber:
    """Tests for validate_page_number function."""

    def test_validate_valid_page(self):
        """Test validating valid page number."""
        assert validate_page_number(1) == 1
        assert validate_page_number("5") == 5
        assert validate_page_number(100) == 100

    def test_validate_invalid_page(self):
        """Test validating invalid page number raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_page_number(0)
        with pytest.raises(ValidationError):
            validate_page_number(-1)
        with pytest.raises(ValidationError):
            validate_page_number("invalid")


class TestValidatePerPage:
    """Tests for validate_per_page function."""

    def test_validate_valid_per_page(self):
        """Test validating valid per_page value."""
        assert validate_per_page(10) == 10
        assert validate_per_page("25") == 25
        assert validate_per_page(100) == 100

    def test_validate_per_page_out_of_range(self):
        """Test validating per_page out of range raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_per_page(0)
        with pytest.raises(ValidationError):
            validate_per_page(101)
        with pytest.raises(ValidationError):
            validate_per_page(-5)

    def test_validate_invalid_per_page(self):
        """Test validating invalid per_page raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_per_page("invalid")


class TestValidateRetentionDays:
    """Tests for validate_retention_days function."""

    def test_validate_valid_retention_days(self):
        """Test validating valid retention days."""
        assert validate_retention_days(30) == 30
        assert validate_retention_days("90") == 90
        assert validate_retention_days(365) == 365

    def test_validate_retention_days_out_of_range(self):
        """Test validating retention days out of range raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_retention_days(0)
        with pytest.raises(ValidationError):
            validate_retention_days(-1)
        with pytest.raises(ValidationError):
            validate_retention_days(3651)  # More than 10 years

    def test_validate_invalid_retention_days(self):
        """Test validating invalid retention days raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_retention_days("invalid")
