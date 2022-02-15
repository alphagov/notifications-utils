# CHANGELOG

This is only used for recording changes for major version bumps.
More minor changes may optionally be recorded here too.

## 54.0.0

* remove the `column` argument from recipients.validate_phone_number`,
  `recipients.validate_uk_phone_number`,
  `recipients.try_validate_and_format_phone_number` and
  `recipients.validate_email_address` (no consuming code uses this
  argument)
* remove `recipients.validate_recipient` (consuming code already uses
  `recipients.validate_phone_number`,
  `recipients.validate_email_address` or
  `postal_address.PostalAddress(…).valid` instead)

## 53.0.0

* `notifications_utils.columns.Columns` has moved to
  `notifications_utils.insensitive_dict.InsensitiveDict`
* `notifications_utils.columns.Rows` has moved to
  `notifications_utils.recipients.Rows`
* `notifications_utils.columns.Cell` has moved to
  `notifications_utils.recipients.Cell`

## 52.0.0

* Deprecate the following unused `redis_client` functions:
  - `redis_client.increment_hash_value`
  - `redis_client.decrement_hash_value`
  - `redis_client.get_all_from_hash`
  - `redis_client.set_hash_and_expire`
  - `redis_client.expire`

## 51.3.1

* Bump govuk-bank-holidays to cache holidays for next year.

## 51.3.0

* Log exception and stacktrace when Celery tasks fail.

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
