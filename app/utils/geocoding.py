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

def build_address_string(street: str, city: str, state: str, zip_code: str, country: str) -> str:
    """
    Build a complete address string from individual components
    
    Args:
        street: Street address
        city: City name
        state: State or province
        zip_code: ZIP or postal code
        country: Country name
        
    Returns:
        Formatted address string
    """
    return f"{street}, {city}, {state} {zip_code}, {country}"

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

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    
    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point
        
    Returns:
        Distance in miles
    """
    import math
    
    # Convert latitude and longitude to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in miles
    r = 3956
    return r * c

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
    return f"{distance_miles:.1f} mi"


def sort_by_distance(items, reference_user, distance_fn, radius=None):
    """
    Sort items by distance from reference user.
    
    Args:
        items: List of items to sort
        reference_user: User to calculate distances from
        distance_fn: Function that takes (item, user) and returns distance in miles or None
        radius: Optional maximum distance in miles to include items
        
    Returns:
        List of items sorted by distance (closest first), with items beyond radius filtered out
    """
    if not reference_user.is_geocoded:
        # If reference user has no location, return original list
        return items
    
    # Calculate distances and filter by radius
    items_with_distance = []
    items_without_distance = []
    
    for item in items:
        distance = distance_fn(item, reference_user)
        if distance is None:
            items_without_distance.append(item)
        elif radius is None or distance <= radius:
            items_with_distance.append((item, distance))
    
    # Sort items with distance by distance (closest first)
    items_with_distance.sort(key=lambda x: x[1])
    
    # Return sorted items (with distance) + items without distance at the end
    return [item for item, _ in items_with_distance] + items_without_distance


def sort_items_by_owner_distance(items, reference_user):
    """
    Convenience function to sort items by their owner's distance from reference user.
    
    Args:
        items: List of Item objects to sort
        reference_user: User to calculate distances from
        
    Returns:
        List of items sorted by owner distance (closest first)
    """
    def item_owner_distance(item, user):
        """Calculate distance from item's owner to user."""
        if not (item.owner and item.owner.is_geocoded):
            return None
        return user.distance_to(item.owner)
    
    return sort_by_distance(items, reference_user, item_owner_distance)