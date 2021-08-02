from math import isclose, pow

import pytest

from pyproj import transform
from notifications_utils.polygons import Polygons
from shapely.geometry.polygon import Polygon

HACKNEY_MARSHES = [
    [-0.038280487060546875, 51.55738264619775],
    [-0.03184318542480469, 51.553913882566754],
    [-0.023174285888671875, 51.55812972989382],
    [-0.023174285888671999, 51.55812972989999],
    [-0.029869079589843747, 51.56165153059717],
    [-0.038280487060546875, 51.55738264619775],
]
QUEEN_ELIZABETH_OLYMPIC_PARK = [
    [-0.016050338745117188, 51.555674980238805],
    [-0.026693344116210938, 51.54793631537473],
    [-0.017766952514648438, 51.53240164320126],
    [-0.006866455078125, 51.540036182553806],
    [-0.016050338745117188, 51.555674980238805]
]
ISLE_OF_DOGS = [
    [-0.03004074096679687, 51.50756719022885],
    [-0.029010772705078125, 51.491110246849814],
    [-0.014591217041015625, 51.484376148122536],
    [-0.0009441375732421874, 51.48774332180889],
    [-0.004291534423828125, 51.49709527744868],
    [-0.0040340423583984375, 51.505804230524056],
    [-0.03004074096679687, 51.50756719022885],
]
LEA_VALLEY = [
    # This is a box containing the River Lea, from Leamouth up to Tottenham
    [-0.0116729736328125, 51.50147667659363],
    [0.01682281494140625, 51.50810140697543],
    [-0.04978179931640625, 51.60266574567797],
    [-0.0775909423828125, 51.59648131678401],
    [-0.0116729736328125, 51.50147667659363],
]
SCOTLAND = [
    # This is basically a box around Scotland but with some finer detail
    # along the English border
    [-5.053710937499999, 54.226707764386695],
    [-3.0322265625, 55.015425940562984],
    [-2.900390625, 55.090943622278544],
    [-2.74658203125, 55.15376626853556],
    [-2.5927734375, 55.30413773740139],
    [-2.4169921874999996, 55.35413531021057],
    [-2.3291015625, 55.441479359140686],
    [-2.1752929687499996, 55.466399363938194],
    [-2.30712890625, 55.62799595426723],
    [-2.1533203125, 55.727110085045986],
    [-2.021484375, 55.801280971180454],
    [-0.263671875, 61.227957176677876],
    [-9.03076171875, 57.58655886615978],
    [-5.053710937499999, 54.226707764386695],
]
WHITECHAPEL_BUILDING = [
    [-0.07254838943481445, 51.514832001321224],
    [-0.07359981536865234, 51.51447145897536],
    [-0.07326722145080566, 51.514110913775795],
    [-0.07225871086120605, 51.51449148918058],
    [-0.07254838943481445, 51.514832001321224],
]


def close_enough(a, b):
    return isclose(a, b, rel_tol=0.001)  # Within 0.1% difference


@pytest.mark.parametrize('value, expected_exception, expected_exception_message', (
    ('a', TypeError, (
        'First argument to Polygons must be a list (not str)'
    )),
    (1, TypeError, (
        'First argument to Polygons must be a list (not int)'
    )),
    (Polygon(), TypeError, (
        'First argument to Polygons must be a list (not Polygon)'
    )),
    (['a'], ValueError, (
        'not enough values to unpack (expected 2, got 1)'
    )),
    ([1], TypeError, (
        '\'int\' object is not iterable'
    )),
))
def test_bad_types(value, expected_exception, expected_exception_message):
    with pytest.raises(expected_exception) as exception:
        Polygons(value)
    assert str(exception.value) == expected_exception_message


def test_can_be_initialised_with_instance_of_self():
    assert Polygons(Polygons([])).polygons == []


@pytest.mark.parametrize('polygons, expected_perimeter_length_km', (
    ([], 0),
    ([HACKNEY_MARSHES], 2.724),
    ([ISLE_OF_DOGS], 7.99),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], 10.71),
    ([SCOTLAND], 1_986),
))
def test_perimeter_length(polygons, expected_perimeter_length_km):
    perimeter_length_km = Polygons(polygons).perimeter_length / 1_000
    assert close_enough(
        perimeter_length_km,
        expected_perimeter_length_km,
    )


@pytest.mark.parametrize('polygons, expected_buffer_out_metres, expected_buffer_in_metres', (
    ([], 500, 500),
    ([HACKNEY_MARSHES], 503, 502),
    ([ISLE_OF_DOGS], 508, 506),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], 511, 507),
    ([SCOTLAND], 2486, 1873),
))
def test_buffer_distances(
    polygons,
    expected_buffer_out_metres,
    expected_buffer_in_metres,
):
    outward_metres = Polygons(polygons).buffer_outward_in_m
    inward_metres = Polygons(polygons).buffer_inward_in_m
    assert close_enough(
        outward_metres, expected_buffer_out_metres,
    )
    assert close_enough(
        inward_metres, expected_buffer_in_metres,
    )


@pytest.mark.parametrize('polygons, expected_area_before, expected_area_after', (
    # The smoothed area should always be slightly larger than the
    # original area
    ([], 0, 0),
    ([HACKNEY_MARSHES], 0.1734, 0.1738),
    ([ISLE_OF_DOGS], 1.551, 1.558),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], 1.724, 1.738),
    ([SCOTLAND], 76_565, 77_100),
))
def test_smoothing_and_area(
    polygons,
    expected_area_before,
    expected_area_after,
):
    SQUARE_MILES_TO_SQUARE_M = 1 / 3.86102e-7

    original_area = Polygons(polygons).estimated_area
    smoothed_area = Polygons(polygons).smooth.estimated_area

    expected_area_before_in_sq_m = expected_area_before * SQUARE_MILES_TO_SQUARE_M
    expected_area_after_in_sq_m = expected_area_after * SQUARE_MILES_TO_SQUARE_M

    assert close_enough(original_area, expected_area_before_in_sq_m)
    assert close_enough(smoothed_area, expected_area_after_in_sq_m)
    assert smoothed_area >= original_area


@pytest.mark.parametrize(
    'edge_length_in_m, expected_area_in_sq_m, expected_number_of_polygons_after_smoothing', (
        # Small polygons get erased by the smoothing process
        (1, 0.628, 0),
        (17, 181.5, 0),
        # This is the smallest polygon that will be preserved
        (40, 1004, 1),  # Tune this
        # Large polygons still result in a single polygon after smoothing
        (100_000, 6_349_128_887, 1),
    ),
)
def test_smoothing_doesnt_return_small_artifacts(
    edge_length_in_m,
    expected_area_in_sq_m,
    expected_number_of_polygons_after_smoothing,
):
    edge_length = edge_length_in_m / Polygons.approx_metres_to_degree
    x, y = HACKNEY_MARSHES[0]
    square = Polygons([[
        [x, y],                              # start at a given point in the UK
        [x + edge_length, y],                # go right 1 unit
        [x + edge_length, y - edge_length],  # go down 1 unit
        [x, y - edge_length],                # go left 1 unit
        [x, y],                              # go up 1 unit
    ]])
    assert close_enough(
        square.estimated_area,
        expected_area_in_sq_m,
    )
    assert len(square.smooth) == expected_number_of_polygons_after_smoothing


@pytest.mark.parametrize('polygons, expected_count_before, expected_count_after', (
    ([], 0, 0),
    ([HACKNEY_MARSHES], 1, 1),
    ([ISLE_OF_DOGS], 1, 1),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], 2, 2),
    ([HACKNEY_MARSHES, QUEEN_ELIZABETH_OLYMPIC_PARK], 2, 1),
    ([QUEEN_ELIZABETH_OLYMPIC_PARK, ISLE_OF_DOGS], 2, 2),
    ([HACKNEY_MARSHES, QUEEN_ELIZABETH_OLYMPIC_PARK, ISLE_OF_DOGS], 3, 2),
))
def test_smooth_joins_areas_in_close_proximity(
    polygons, expected_count_before, expected_count_after
):
    area_polygons = Polygons(polygons)
    assert len(area_polygons) == expected_count_before
    assert len(area_polygons.smooth) == expected_count_after


@pytest.mark.parametrize('polygons, expected_point_count_before, expected_point_count_after', (
    ([], 0, 0),
    ([HACKNEY_MARSHES], 6, 5),
    ([ISLE_OF_DOGS], 7, 7),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], 13, 12),
    ([SCOTLAND], 14, 12),
))
def test_simplify(
    polygons,
    expected_point_count_before,
    expected_point_count_after,
):
    area_polygons = Polygons(polygons)
    assert area_polygons.point_count == expected_point_count_before
    assert area_polygons.simplify.point_count == expected_point_count_after
    assert close_enough(
        area_polygons.estimated_area,
        area_polygons.simplify.estimated_area,
    )


@pytest.mark.parametrize('polygons, expected_area_before, expected_area_after', (
    ([], 0, 0),
    # For small areas the bleed is large relative to the size of the
    # original area
    ([HACKNEY_MARSHES], 0.1734, 4.41),
    ([ISLE_OF_DOGS], 1.551, 8.83),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], 1.725, 13.25),
    # For large areas the bleed is small relative to the size of the
    # original area
    ([SCOTLAND], 76_623, 77_750),
))
def test_bleed(
    polygons,
    expected_area_before,
    expected_area_after,
):

    SQUARE_MILES_TO_SQUARE_M = 1 / 3.86102e-7

    expected_area_after = SQUARE_MILES_TO_SQUARE_M * expected_area_after
    expected_area_before = SQUARE_MILES_TO_SQUARE_M * expected_area_before

    area_polygons = Polygons(polygons)
    assert close_enough(
        area_polygons.estimated_area,
        expected_area_before,
    )
    assert close_enough(
        area_polygons.bleed_by(Polygons.approx_bleed_in_m).estimated_area,
        expected_area_after,
    )


@pytest.mark.parametrize('bleed_distance_in_m, expected_area_before, expected_area_after', (
    (0, 1.551, 1.551),
    (500, 1.551, 3.390),
    (5000, 1.551, 46.48),
))
def test_custom_bleed(
    bleed_distance_in_m,
    expected_area_before,
    expected_area_after,
):

    SQUARE_MILES_TO_SQUARE_M = 1 / 3.86102e-7
    expected_area_after = SQUARE_MILES_TO_SQUARE_M * expected_area_after
    expected_area_before = SQUARE_MILES_TO_SQUARE_M * expected_area_before

    area_polygons = Polygons([ISLE_OF_DOGS])
    assert close_enough(
        area_polygons.estimated_area,
        expected_area_before,
    )
    assert close_enough(
        area_polygons.bleed_by(bleed_distance_in_m).estimated_area,
        expected_area_after,
    )


def test_remove_areas_too_small():
    hackney_marshes_and_wcb = Polygons([HACKNEY_MARSHES, WHITECHAPEL_BUILDING])
    hackney_marshes = Polygons([HACKNEY_MARSHES])
    assert len(hackney_marshes_and_wcb) == 2
    assert len(hackney_marshes_and_wcb.remove_too_small) == 1
    assert (
        hackney_marshes_and_wcb.remove_too_small.estimated_area,
        hackney_marshes_and_wcb.remove_too_small.perimeter_length,
    ) == (
        hackney_marshes.estimated_area,
        hackney_marshes.perimeter_length,
    )


def test_empty_bounds():
    with pytest.raises(ValueError) as exception:
        Polygons([]).bounds
    assert str(exception.value) == "Can't determine bounds of empty Polygons"


@pytest.mark.parametrize('polygons, expected_bounds', (
    ([ISLE_OF_DOGS], (
        -0.034327, 51.4849, 0.002541, 51.507,
    )),
    ([HACKNEY_MARSHES, ISLE_OF_DOGS], (
        -0.052144, 51.4849, 0.013096, 51.561,
    )),
    ([SCOTLAND], (
        -9.030761, 54.2913, -0.263671, 61.227,
    )),
))
def test_bounds(polygons, expected_bounds):
    min_x, min_y, max_x, max_y = Polygons(polygons).bounds
    expected_min_x, expected_min_y, expected_max_x, expected_max_y = expected_bounds
    assert close_enough(min_x, expected_min_x)
    assert close_enough(min_y, expected_min_y)
    assert close_enough(max_x, expected_max_x)
    assert close_enough(max_y, expected_max_y)


@pytest.mark.parametrize('polygons_1, polygons_2, expected_intersection_percentage', (
    # Hackney Marshes is a small part of the Lea Valley
    ([LEA_VALLEY], [HACKNEY_MARSHES], 1.865),
    # … and the Lea Valley wholey contains Hackney Marshes
    ([HACKNEY_MARSHES], [LEA_VALLEY], 100),
    # Isle of Dogs is a wholey separate area from Hackney Marshes
    ([ISLE_OF_DOGS], [HACKNEY_MARSHES], 0),
    # A small part of the Isle of Dogs overlaps with the Lea Valley…
    ([LEA_VALLEY], [ISLE_OF_DOGS], 1.187),
    # …but as a proportion of the area of the Isle of Dogs, the overlap
    # is larger
    ([ISLE_OF_DOGS], [LEA_VALLEY], 7.115),
    # Ratio is always 0 if one or both polygons are empty
    ([ISLE_OF_DOGS], [], 0),
    ([], [ISLE_OF_DOGS], 0),
    ([], [], 0),
))
def test_intersection_ratio(polygons_1, polygons_2, expected_intersection_percentage):
    percentage = Polygons(polygons_1).ratio_of_intersection_with(Polygons(polygons_2)) * 100
    assert close_enough(percentage, expected_intersection_percentage)
    assert Polygons(polygons_1).intersects(Polygons(polygons_2)) is bool(expected_intersection_percentage)


def test_precision():
    assert Polygons([HACKNEY_MARSHES]).as_coordinate_pairs_lat_long[0][0] == [
        # Note up to 6 decimal places
        51.557383, -0.03828
    ]
    assert Polygons([HACKNEY_MARSHES]).as_coordinate_pairs_long_lat[0][0] == [
        # Same points, reversed polarity
        -0.03828, 51.557383
    ]

    precision = pow(10, -Polygons.output_precision_in_decimal_places)

    assert precision == 0.000001
    assert close_enough(
        precision * Polygons.approx_metres_to_degree,
        0.1113  # Our coordinates are accurate to about 0.1m
    )
