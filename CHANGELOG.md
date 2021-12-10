# CHANGELOG

This is only used for recording changes for major version bumps.
More minor changes may optionally be recorded here too.

## 51.2.1

* Revert 51.2.0.

## 51.2.0

* Timeout processing CSVs to avoid timing out downstream requests

This only affects the Admin app, which should ideally rescue the exception,
but just letting it propagate is also acceptable as it's similar to the
current behaviour where we timeout in CloudFront.

## 51.1.0

* Make processing of spreadsheets with many empty columns more efficient

## 51.0.0

* Initial argument to `RecipientCSV` renamed from `whitelist` to
  `guestlist`, in other words consuming code should call
  `RecipientCSV(guestlist=['test@example.com'])`
* `RecipientCSV.whitelist` property renamed to `RecipientCSV.guestlist`

## 50.0.0

* Make icon in `broadcast_preview_template.jinja2` an inline SVG
  (requires changes to the CSS of consumer code)

## 49.1.0

* Add `ttl_in_seconds` argument to `RequestCache.set` to let users specify
a custom TTL

## 49.0.0

* `Polygons` must now be called with either `shapely.Polygon` objects and
a valid Coordinate Reference System code for `utm_crs` or a list of
lists of coordinates in degrees

## 48.2.0

* Enable Celery argument checking for apply_async.
* Remove redundant "kwargs" handling code for Celery Request ID
tracing.

## 48.1.0

* Add new NotifyCelery base class as a drop in replacement to
DRY-up the "app/celery/celery.py" file we have in many apps.

## 48.0.0

* Rename `normalise_lines` to `get_lines_with_normalised_whitespace`
* Rename `strip_whitespace` to `strip_all_whitespace`
* Remove `OBSCURE_WHITESPACE` variable (appears unused in other apps)
* Remove `multiple_spaces_in_a_row` variable (appears unused in other apps)
* Remove `normalise_line` function (appears unused in other apps)

## Prior versions

Changelog not recorded - please see pull requests on github.
