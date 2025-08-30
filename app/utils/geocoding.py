"""
Geocoding utilities using Nominatim API
"""
import requests
import logging
from typing import Optional, Tuple
from time import sleep

logger = logging.getLogger(__name__)

class GeocodingError(Exception):
    """Custom exception for geocoding errors"""
    pass

def geocode_address(address: str, max_retries: int = 3, delay: float = 1.0) -> Optional[Tuple[float, float]]:
    """
    Geocode an address using Nominatim API
    
    Args:
        address: Full address string to geocode
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
        
    Returns:
        Tuple of (latitude, longitude) if successful, None if failed
        
    Raises:
        GeocodingError: If geocoding fails after all retries
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"
    
    # Parameters for the API request
    params = {
        'q': address,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1
    }
    
    # Headers to identify our application (Nominatim policy compliance)
    headers = {
        'User-Agent': 'Meutch-ItemLending/1.0 (https://meutch.com; item-lending-platform)'
    }
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Geocoding attempt {attempt + 1} for address: {address}")
            
            # Make the API request
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse the JSON response
            data = response.json()
            
            if not data:
                logger.warning(f"No results found for address: {address}")
                return None
            
            # Extract latitude and longitude from the first result
            result = data[0]
            lat = float(result['lat'])
            lon = float(result['lon'])
            
            logger.info(f"Successfully geocoded address: {address} -> ({lat}, {lon})")
            return (lat, lon)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during geocoding attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                sleep(delay)
                continue
            else:
                raise GeocodingError(f"Failed to geocode address after {max_retries} attempts: {e}")
                
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing geocoding response: {e}")
            raise GeocodingError(f"Invalid response from geocoding service: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error during geocoding: {e}")
            if attempt < max_retries - 1:
                sleep(delay)
                continue
            else:
                raise GeocodingError(f"Unexpected error during geocoding: {e}")
    
    return None

def format_distance(distance_miles: float) -> str:
    """
    Format distance for display
    
    Args:
        distance_miles: Distance in miles
        
    Returns:
        Formatted distance string (e.g., "2.3 mi", "0.1 mi")
    """
    if distance_miles < 0.1:
        return "< 0.1 mi"
    elif distance_miles < 1.0:
        return f"{distance_miles:.1f} mi"
    else:
        return f"{distance_miles:.1f} mi"
