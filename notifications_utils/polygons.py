import itertools

from pyproj import CRS, Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from shapely.geometry import (
    JOIN_STYLE,
    GeometryCollection,
    MultiPolygon,
    Polygon,
)
from shapely.ops import unary_union
from werkzeug.utils import cached_property

transformers = {
    utm_code: {
        # WGS84 (World Geodetic System, 1984) is a standard which
        # defines the size and shape of the earth. Coordinates in the
        # data we get from ONS, and that we output as CAP XML are
        # expressed relative to the constants in WGS84.
        'from_wgs84': Transformer.from_crs('EPSG:4326', utm_code, always_xy=True),
        'to_wgs84': Transformer.from_crs(utm_code, 'EPSG:4326', always_xy=True),
    }
    for utm_code in {
        # These are the names of coordinate reference systems, which
        # provide mathemtical functions for transforming WGS84
        # coordinates to linear measures of distance across the earth’s
        # surface. The functions are different in different areas of the
        # earth because the earth is not a perfect sphere.
        # —
        # The UK, west to east
        'epsg:32629',  # Zone 29N: Between 12°W and 6°W, equator and 84°N
        'epsg:32630',  # Zone 30N: Between 6°W and 0°W, equator and 84°N
        'epsg:32631',  # Zone 31N: Between 0°E and 6°E, equator and 84°N
        # Santa Claus village (Finland)
        'epsg:32635',  # Zone 35N: Between 24°E and 30°E, equator and 84°N
    }
}


class Polygons():

    # Estimated amount of bleed into neigbouring areas based on typical
    # range/separation of cell towers.
    approx_bleed_in_m = 1_500

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

    def __init__(self, polygons, utm_crs=None):

        if not isinstance(polygons, list):
            raise TypeError(
                f'First argument to {self.__class__.__name__} must be a list '
                f'(not {type(polygons).__name__})'
            )

        self.polygons = polygons
        self.utm_crs = utm_crs

        if self.utm_crs:
            if utm_crs not in transformers:
                raise ValueError(
                    f'Could not find {self.utm_crs} in expected coordinate '
                    f'systems (are the coordinates in longitude/latitude '
                    f'order?)'
                )
        else:
            for polygon in self:
                if isinstance(polygon, Polygon):
                    raise TypeError(
                        f'Can’t initiate with {Polygon.__name__} objects and no CRS'
                    )
                if not isinstance(polygon, list):
                    raise TypeError(
                        f'Can’t make {Polygon.__name__} from {type(polygon).__name__} `{polygon}`'
                    )

    @cached_property
    def transform_from_wgs84(self):
        return transformers[self.utm_crs]['from_wgs84']

    @cached_property
    def transform_to_wgs84(self):
        return transformers[self.utm_crs]['to_wgs84']

    @cached_property
    def utm_polygons(self):

        if all(
            isinstance(polygon, Polygon) for polygon in self
        ):
            # These polygons already have UTM coordinates
            return self

        if not self.polygons:
            return Polygons([])

        if not self.utm_crs:
            shapely_polygons = MultiPolygon([Polygon(p) for p in self])
            utm_crs_list = query_utm_crs_info(
                datum_name="WGS 84",
                area_of_interest=AreaOfInterest(
                    *shapely_polygons.bounds
                ),
            )
            if not utm_crs_list:
                raise ValueError(
                    f'Could not find coordinates '
                    f'{shapely_polygons.bounds} anywhere on the '
                    f'surface of the earth (are they in '
                    f'in WGS84 format?)'
                )
            self.utm_crs = str(CRS.from_epsg(utm_crs_list[0].code))

        return Polygons(
            [
                self._polygon_from_wgs84_coords(polygon) for polygon in self
            ],
            utm_crs=self.utm_crs,
        )

    def _polygon_from_wgs84_coords(self, coords):
        return Polygon(
            self.transform_coords(
                coords,
                transformer=self.transform_from_wgs84,
            )
        )

    @staticmethod
    def transform_coords(coords, transformer):
        return [
            list(transformer.transform(x, y)) for x, y in coords
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
            polygon.length for polygon in self.utm_polygons
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
            polygon.bounds for polygon in self.utm_polygons
        ))

        min_x_wgs84, min_y_wgs84 = self.transform_to_wgs84.transform(
            min(all_min_x), min(all_min_y),
        )
        max_x_wgs84, max_y_wgs84 = self.transform_to_wgs84.transform(
            max(all_max_x), max(all_max_y),
        )

        return (
            min_x_wgs84, min_y_wgs84, max_x_wgs84, max_y_wgs84,
        )

    @cached_property
    def buffer_outward_in_m(self):
        '''
        Calculates the distance (in metres) by which to buffer outwards
        when smoothing a given set of polygons. Larger and more complex
        polygons get a larger buffer.
        '''
        return (
            # If two areas are close enough that the distance between
            # them is less than the typical bleed of a cell
            # broadcast then this joins them together. The aim is to
            # reduce the total number of polygons in areas with many
            # small shapes like Orkney or the Isles of Scilly.
            self.approx_bleed_in_m / 3
        ) + (
            self.perimeter_length / self.perimeter_to_buffer_ratio
        )

    @cached_property
    def buffer_inward_in_m(self):
        '''
        Calculates the distance (in metres) by which to buffer inwards
        when smoothing a given set of polygons. Larger and more complex
        polygons get a larger buffer, to negate the larger outwards
        buffer.
        '''
        return self.buffer_outward_in_m - (
            # We should leave the shape expanded by at least the
            # simplification tolerance in all places, so the
            # simplification never moves a point inside the original
            # shape. In practice half of the tolerance is enough to
            # acheive this.
            self.simplification_tolerance_in_m / 2
        ) - (
            # This reduces the inward buffer by an additional fixed
            # ammount. This helps ensure we bound very small polygons
            # entirely, while not making a significant difference to
            # large polygons.
            15
        )

    @cached_property
    def simplification_tolerance_in_m(self):
        '''
        Calculates a tolerance (in metres) for how much a point can
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
        return self.bleed_by(
            self.buffer_outward_in_m
        ).bleed_by(
            -1 * self.buffer_inward_in_m
        ).remove_smaller_than(
            area_in_square_metres=1
        )

    @cached_property
    def simplify(self):
        '''
        Reduces the number of points in a polygon. See
        https://shapely.readthedocs.io/en/stable/manual.html#object.simplify
        '''
        return Polygons([
            polygon.simplify(self.simplification_tolerance_in_m)
            for polygon in self.utm_polygons
        ], utm_crs=self.utm_crs)

    def bleed_by(self, distance_in_m):
        '''
        Expands the area of each polygon to give an estimation of how
        far a broadcast would bleed into neighbouring areas.
        '''
        return Polygons(union_polygons([
            polygon.buffer(
                distance_in_m,
                resolution=4,
                join_style=JOIN_STYLE.round,
            )
            for polygon in self.utm_polygons
        ]), utm_crs=self.utm_crs)

    @cached_property
    def remove_too_small(self):
        '''
        Filters out polygons below a certain area. Useful for removing
        artefacts from datasets that haven’t been cleaned up properly,
        often by trying to automatically subtract the shoreline from the
        land.
        '''
        return self.remove_smaller_than(self.minimum_area_size_square_metres)

    def remove_smaller_than(self, area_in_square_metres):
        return Polygons([
            polygon for polygon in self.utm_polygons
            if polygon.area > area_in_square_metres
        ], utm_crs=self.utm_crs)

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
            ] for x, y in coords]
            for coords in self.as_wgs84_coordinates
        ]

    @property
    def as_wgs84_coordinates(self):
        if all(isinstance(polygon, list) for polygon in self):
            return self.polygons
        return [
            self.transform_coords(
                polygon.exterior.coords,
                transformer=self.transform_to_wgs84,
            )
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
        return sum(polygon.area for polygon in self.utm_polygons)

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
        ) / self.estimated_area

    def intersection_with(self, polygons):
        for comparison in polygons.utm_polygons:
            for polygon in self.utm_polygons:
                yield polygon.intersection(comparison)

    def intersects(self, polygons):
        for comparison in polygons.utm_polygons:
            for polygon in self.utm_polygons:
                if polygon.intersects(comparison):
                    return True
        return False


def flatten_polygons(polygons):
    if isinstance(polygons, GeometryCollection):
        return []
    if isinstance(polygons, MultiPolygon):
        return [
            p for p in polygons.geoms
        ]
    else:
        return [polygons]


def union_polygons(polygons):
    return flatten_polygons(unary_union(polygons))
