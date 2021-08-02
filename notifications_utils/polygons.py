import itertools

from shapely.geometry import (
    JOIN_STYLE,
    GeometryCollection,
    MultiPolygon,
    Polygon,
)
from shapely.ops import unary_union
from werkzeug.utils import cached_property


class Polygons():

    approx_metres_to_degree = 111_320
    approx_square_metres_to_square_degree = approx_metres_to_degree ** 2
    square_degrees_to_square_miles = (
        approx_square_metres_to_square_degree / (1000 * 1000) * 0.386102
    )

    # Estimated amount of bleed into neigbouring areas based on typical
    # range/separation of cell towers.
    approx_bleed_in_degrees = 1_500 / approx_metres_to_degree

    # Controls how much buffer to add for a shape of a given perimeter.
    # Smaller number means more buffering and a smoother shape. For
    # example `1000` means 1m of buffer for every 1km of perimeter, or
    # 20m of buffer for a 5km square. This gives us control over how
    # much we fill in very concave features like channels, harbours and
    # zawns.
    perimeter_to_buffer_ratio = 1000

    # Ratio of how much detail a shape of a given perimeter has once
    # simplified. Smaller number means less detail. For example `1000`
    # means that for a shape with a perimeter of 1000m, the simplified
    # line will never deviate more than 1m from the original.
    # Or for a 5km square, the line won’t deviate more than 20m. This
    # gives us approximate control over the total number of points.
    perimeter_to_simplification_ratio = 1_620

    # The threshold for removing very small areas from the map. These
    # areas are likely glitches in  the data where the shoreline hasn’t
    # been subtracted from the land properly
    minimum_area_size_square_metres = 6_500

    output_precision_in_decimal_places = 6

    def __init__(self, polygons):

        if not isinstance(polygons, (list, self.__class__)):
            raise TypeError(
                f'First argument to {self.__class__.__name__} must be a list '
                f'(not {type(polygons).__name__})'
            )

        self.polygons = [
            polygon if isinstance(polygon, Polygon) else Polygon(polygon)
            for polygon in polygons
        ]

    def __getitem__(self, index):
        return self.polygons[index]

    def __len__(self):
        return len(self.polygons)

    @cached_property
    def perimeter_length(self):
        '''
        Total distance around all polygons in degrees. Polygons may have
        larger perimeter for a number of reasons:
        - they have a larger area
        - they are more jagged or detailed, for example a rocky coastline
        - they are made up of lots of small polygons, rather than one
          large one
        '''
        return sum(
            polygon.length for polygon in self
        )

    @property
    def bounds(self):
        '''
        The bounds, of all polygons. In other words, the coordinates
        that would draw a box containing all the polygons.
        '''
        if not self.polygons:
            raise ValueError(
                f"Can't determine bounds of empty {self.__class__.__name__}"
            )
        all_min_x, all_min_y, all_max_x, all_max_y = zip(*(
            polygon.bounds for polygon in self
        ))
        return (
            min(all_min_x), min(all_min_y), max(all_max_x), max(all_max_y),
        )

    @cached_property
    def buffer_outward_in_degrees(self):
        '''
        Calculates the distance (in degrees) by which to buffer outwards
        when smoothing a given set of polygons. Larger and more complex
        polygons get a larger buffer.
        '''
        return (
            # If two areas are close enough that the distance between
            # them is less than the typical bleed of a cell
            # broadcast then this joins them together. The aim is to
            # reduce the total number of polygons in areas with many
            # small shapes like Orkney or the Isles of Scilly.
            self.approx_bleed_in_degrees / 3
        ) + (
            self.perimeter_length / self.perimeter_to_buffer_ratio
        )

    @cached_property
    def buffer_inward_in_degrees(self):
        '''
        Calculates the distance (in degrees) by which to buffer inwards
        when smoothing a given set of polygons. Larger and more complex
        polygons get a larger buffer, to negate the larger outwards
        buffer.
        '''
        return self.buffer_outward_in_degrees - (
            # We should leave the shape expanded by at least the
            # simplification tolerance in all places, so the
            # simplification never moves a point inside the original
            # shape. In practice half of the tolerance is enough to
            # acheive this.
            self.simplification_tolerance_in_degrees / 2
        )

    @cached_property
    def simplification_tolerance_in_degrees(self):
        '''
        Calculates a tolerance (in degrees) for how much a point can
        deviate from a line joining its two neighbours. Larger and more
        complex polygons get a wider tolerance, in order to keep the
        point count down. See also
        https://shapely.readthedocs.io/en/stable/manual.html#object.simplify
        '''
        return self.perimeter_length / self.perimeter_to_simplification_ratio

    @cached_property
    def smooth(self):
        '''
        Fills in areas which aren’t covered by the polygons, but would
        likely receive the broadcast anyway because of the bleed. This
        includes very convex areas like harbours, and places where two
        polygons are close to touching each other. By removing detail in
        these areas we can preserve it in places where it’s more
        relevant.
        '''
        buffered = [
            polygon.buffer(
                self.buffer_outward_in_degrees,
                resolution=4,
                join_style=JOIN_STYLE.round,
            )
            for polygon in self
        ]
        unioned = union_polygons(buffered)
        debuffered = [
            polygon.buffer(
                -1 * self.buffer_inward_in_degrees,
                resolution=1,
                join_style=JOIN_STYLE.bevel,
            )
            for polygon in unioned
        ]
        flattened = list(itertools.chain(*[
            flatten_polygons(polygon) for polygon in debuffered
        ]))
        return Polygons([
            polygon for polygon in flattened if (
                # The smoothing process creates some artifacts which can
                # be removed by ignoring polygons less than 1m² in area
                polygon.area > (1 / self.approx_square_metres_to_square_degree)
            )
        ])

    @cached_property
    def simplify(self):
        '''
        Reduces the number of points in a polygon. See
        https://shapely.readthedocs.io/en/stable/manual.html#object.simplify
        '''
        return Polygons([
            polygon.simplify(self.simplification_tolerance_in_degrees)
            for polygon in self
        ])

    def bleed_by(self, distance_in_degrees):
        '''
        Expands the area of each polygon to give an estimation of how
        far a broadcast would bleed into neighbouring areas.
        '''
        return Polygons(union_polygons([
            polygon.buffer(
                distance_in_degrees,
                resolution=4,
                join_style=JOIN_STYLE.round,
            )
            for polygon in self
        ]))

    @cached_property
    def remove_too_small(self):
        '''
        Filters out polygons below a certain area. Useful for removing
        artefacts from datasets that haven’t been cleaned up properly,
        often by trying to automatically subtract the shoreline from the
        land.
        '''
        return Polygons([
            polygon for polygon in self
            if (
                polygon.area * self.approx_square_metres_to_square_degree
            ) > (
                self.minimum_area_size_square_metres
            )
        ])

    @cached_property
    def as_coordinate_pairs_long_lat(self):
        '''
        For formats that specify coordinates in latitude/longitude
        order, for example leaflet.js.
        '''
        return [
            [[
                round(x, self.output_precision_in_decimal_places),
                round(y, self.output_precision_in_decimal_places),
            ] for x, y in polygon.exterior.coords]
            for polygon in self
        ]

    @cached_property
    def as_coordinate_pairs_lat_long(self):
        '''
        For formats that specify coordinates in latitude/longitude
        order, for example CAP XML.
        '''
        return [
            [[y, x] for x, y in coordinate_pairs]
            for coordinate_pairs in self.as_coordinate_pairs_long_lat
        ]

    @cached_property
    def point_count(self):
        '''
        Total number of points in all polygons.
        '''
        return len(list(itertools.chain(*self.as_coordinate_pairs_long_lat)))

    @property
    def estimated_area(self):
        '''
        Area of all polygons. Only an estimate because it does an
        approximate conversion of degrees to square miles for UK
        latitudes, rather than a projection.
        '''
        return sum(
            polygon.area for polygon in self
        ) * self.square_degrees_to_square_miles

    def ratio_of_intersection_with(self, polygons):
        '''
        Given another Polygons object, this works how much the two
        overlap, as a fraction of the area of this Polygons object.
        It assumes that neither of the objects already contain
        overlapping polygons.
        '''
        if self.estimated_area == 0:
            return 0
        return sum(
            intersection.area
            for intersection in self.intersection_with(polygons)
        ) * self.square_degrees_to_square_miles / self.estimated_area

    def intersection_with(self, polygons):
        for comparison in polygons:
            for polygon in self:
                yield polygon.intersection(comparison)

    def intersects(self, polygons):
        for comparison in polygons:
            for polygon in self:
                if polygon.intersects(comparison):
                    return True
        return False


def flatten_polygons(polygons):
    if isinstance(polygons, GeometryCollection):
        return []
    if isinstance(polygons, MultiPolygon):
        return [
            p for p in polygons
        ]
    else:
        return [polygons]


def union_polygons(polygons):
    return flatten_polygons(unary_union(polygons))
