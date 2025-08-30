"""Unit tests for geocoding utilities."""
import pytest
import requests
from unittest.mock import patch, Mock
from app.utils.geocoding import geocode_address, GeocodingError, format_distance


class TestGeocodeAddress:
    """Test cases for geocode_address function."""

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_success(self, mock_get):
        """Test successful geocoding of an address."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'lat': '40.7128',
                'lon': '-74.0060',
                'display_name': 'New York, NY, USA'
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("123 Main St, New York, NY")
        
        assert result == (40.7128, -74.0060)
        mock_get.assert_called_once()
        
        # Verify API call parameters
        call_args = mock_get.call_args
        assert call_args[1]['params']['q'] == "123 Main St, New York, NY"
        assert call_args[1]['params']['format'] == 'json'
        assert call_args[1]['params']['limit'] == 1

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_no_results(self, mock_get):
        """Test geocoding when no results are found."""
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Invalid Address 12345")
        
        assert result is None

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_network_error_with_retry(self, mock_get):
        """Test network error handling with successful retry."""
        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.json.return_value = [{'lat': '40.7128', 'lon': '-74.0060'}]
        mock_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            mock_response
        ]

        with patch('app.utils.geocoding.sleep'):  # Speed up test by mocking sleep
            result = geocode_address("123 Main St, New York, NY", max_retries=2)
        
        assert result == (40.7128, -74.0060)
        assert mock_get.call_count == 2

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_network_error_max_retries(self, mock_get):
        """Test network error handling when max retries exceeded."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with patch('app.utils.geocoding.sleep'):  # Speed up test
            with pytest.raises(GeocodingError) as exc_info:
                geocode_address("123 Main St, New York, NY", max_retries=2)
        
        assert "Failed to geocode address after 2 attempts" in str(exc_info.value)
        assert mock_get.call_count == 2

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_invalid_response_format(self, mock_get):
        """Test handling of invalid response format."""
        # Mock response with missing lat/lon
        mock_response = Mock()
        mock_response.json.return_value = [{'display_name': 'Some place'}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(GeocodingError) as exc_info:
            geocode_address("123 Main St, New York, NY")
        
        assert "Invalid response from geocoding service" in str(exc_info.value)

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_json_decode_error(self, mock_get):
        """Test handling of JSON decode errors."""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(GeocodingError) as exc_info:
            geocode_address("123 Main St, New York, NY")
        
        assert "Invalid response from geocoding service" in str(exc_info.value)

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(GeocodingError) as exc_info:
            geocode_address("123 Main St, New York, NY")
        
        assert "Failed to geocode address after 3 attempts" in str(exc_info.value)

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_timeout(self, mock_get):
        """Test handling of request timeouts."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        with patch('app.utils.geocoding.sleep'):
            with pytest.raises(GeocodingError) as exc_info:
                geocode_address("123 Main St, New York, NY", max_retries=1)
        
        assert "Failed to geocode address after 1 attempts" in str(exc_info.value)

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_unexpected_error_with_retry(self, mock_get):
        """Test handling of unexpected errors with retry."""
        # First call has unexpected error, second succeeds
        mock_response = Mock()
        mock_response.json.return_value = [{'lat': '40.7128', 'lon': '-74.0060'}]
        mock_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [
            Exception("Unexpected error"),
            mock_response
        ]

        with patch('app.utils.geocoding.sleep'):
            result = geocode_address("123 Main St, New York, NY", max_retries=2)
        
        assert result == (40.7128, -74.0060)
        assert mock_get.call_count == 2

    @patch('app.utils.geocoding.requests.get')
    def test_geocode_address_unexpected_error_max_retries(self, mock_get):
        """Test handling of unexpected errors when max retries exceeded."""
        mock_get.side_effect = Exception("Unexpected error")

        with patch('app.utils.geocoding.sleep'):
            with pytest.raises(GeocodingError) as exc_info:
                geocode_address("123 Main St, New York, NY", max_retries=2)
        
        assert "Unexpected error during geocoding" in str(exc_info.value)
        assert mock_get.call_count == 2

    def test_geocode_address_custom_retries_and_delay(self):
        """Test that custom max_retries and delay parameters are respected."""
        with patch('app.utils.geocoding.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
            
            with patch('app.utils.geocoding.sleep') as mock_sleep:
                with pytest.raises(GeocodingError):
                    geocode_address("123 Main St", max_retries=5, delay=2.0)
                
                assert mock_get.call_count == 5
                # Should have 4 sleep calls (retry attempts - 1)
                assert mock_sleep.call_count == 4
                mock_sleep.assert_called_with(2.0)

    def test_geocode_address_user_agent_header(self):
        """Test that proper User-Agent header is set."""
        with patch('app.utils.geocoding.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = [{'lat': '40.7128', 'lon': '-74.0060'}]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            geocode_address("123 Main St, New York, NY")
            
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert 'User-Agent' in headers
            assert 'Meutch-ItemLending' in headers['User-Agent']


class TestFormatDistance:
    """Test cases for format_distance function."""

    def test_format_distance_very_small(self):
        """Test formatting very small distances."""
        assert format_distance(0.05) == "< 0.1 mi"
        assert format_distance(0.09) == "< 0.1 mi"
        assert format_distance(0.0) == "< 0.1 mi"

    def test_format_distance_small(self):
        """Test formatting small distances."""
        assert format_distance(0.1) == "0.1 mi"
        assert format_distance(0.14) == "0.1 mi"  # Rounds down
        assert format_distance(0.15) == "0.1 mi"  # Python rounds to even (banker's rounding)
        assert format_distance(0.16) == "0.2 mi"  # Rounds up
        assert format_distance(0.9) == "0.9 mi"

    def test_format_distance_medium(self):
        """Test formatting medium distances."""
        assert format_distance(1.0) == "1.0 mi"
        assert format_distance(1.23) == "1.2 mi"
        assert format_distance(5.67) == "5.7 mi"
        assert format_distance(10.0) == "10.0 mi"

    def test_format_distance_large(self):
        """Test formatting large distances."""
        assert format_distance(25.8) == "25.8 mi"
        assert format_distance(100.0) == "100.0 mi"
        assert format_distance(999.9) == "999.9 mi"

    def test_format_distance_rounding(self):
        """Test distance rounding behavior."""
        assert format_distance(1.24) == "1.2 mi"  # Rounds down
        assert format_distance(1.25) == "1.2 mi"  # Python rounds to even
        assert format_distance(1.26) == "1.3 mi"  # Rounds up
        assert format_distance(1.35) == "1.4 mi"  # Python rounds to even

    def test_format_distance_edge_cases(self):
        """Test edge cases for distance formatting."""
        assert format_distance(0.099999) == "< 0.1 mi"
        assert format_distance(0.1000001) == "0.1 mi"
