"""Unit tests for the bounding_box prefilter used ahead of Haversine checks."""

from app.utils.geocoding import bounding_box, calculate_distance


def test_bounding_box_contains_every_point_within_the_radius():
    """The box has to be a superset of the circle it approximates.

    It is applied in SQL ahead of the exact distance check, so a point it drops
    is a row the feed never gets to consider.
    """
    latitude, longitude = 40.7128, -74.0060  # NYC
    radius_miles = 20
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_miles)

    for latitude_step, longitude_step in ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7)):
        # Walk outward until the point falls outside the radius, checking that
        # everything closer than that stayed inside the box.
        multiplier = 0.0
        while True:
            multiplier += 0.001
            candidate_latitude = latitude + latitude_step * multiplier
            candidate_longitude = longitude + longitude_step * multiplier
            if (
                calculate_distance(latitude, longitude, candidate_latitude, candidate_longitude)
                > radius_miles
            ):
                break
            assert min_lat <= candidate_latitude <= max_lat
            assert min_lon <= candidate_longitude <= max_lon


def test_bounding_box_widens_longitude_at_higher_latitudes():
    """A degree of longitude covers less ground away from the equator."""
    _, _, equator_min_lon, equator_max_lon = bounding_box(0.0, 0.0, 20)
    _, _, arctic_min_lon, arctic_max_lon = bounding_box(70.0, 0.0, 20)

    assert (arctic_max_lon - arctic_min_lon) > (equator_max_lon - equator_min_lon)


def test_bounding_box_falls_back_to_the_full_longitude_range_near_the_pole():
    _, _, min_lon, max_lon = bounding_box(89.9, 0.0, 50)

    assert (min_lon, max_lon) == (-180.0, 180.0)


def test_bounding_box_falls_back_to_the_full_longitude_range_at_the_antimeridian():
    """Rather than splitting into two ranges, the box gives up on longitude."""
    _, _, min_lon, max_lon = bounding_box(0.0, 179.9, 50)

    assert (min_lon, max_lon) == (-180.0, 180.0)


def test_bounding_box_returns_none_without_coordinates_or_a_radius():
    assert bounding_box(None, -74.0060, 20) is None
    assert bounding_box(40.7128, None, 20) is None
    assert bounding_box(40.7128, -74.0060, None) is None
