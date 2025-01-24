# CHANGELOG

# 95.0.0

* Reverts 92.0.0 to restore new validation code
## 94.0.1

* Add `ruff.toml` to `MANIFEST.in`

## 94.0.0

* `version_tools.copy_config` will now copy `ruff.toml` instead of `pyproject.toml`. Apps should maintain their own `pyproject.toml`, if required
* Replaces `black` formatter with `ruff format`
* Upgrades `ruff` to version 0.9.2

## 93.2.1

* Replaces symlink at `./pyproject.toml` with a duplicate file

## 93.2.0

* logging: add verbose eventlet context to app.request logs if request_time is over a threshold

## 93.1.0

* Introduce `NOTIFY_LOG_LEVEL_HANDLERS` config variable for separate control of handler log level

## 93.0.0

* BREAKING CHANGE: logging: all contents of `logging/__init__.py` have been moved to `logging/flask.py` because they all assume a flask(-like) environment and this way we don't implicitly import all of flask etc. every time anything under `logging` is imported.
* Adds `request_cpu_time` to `app.request` logs when available.
* Adds ability to track eventlet's switching of greenlets and annotate `app.request` logs with useful metrics when the flask config parameter `NOTIFY_EVENTLET_STATS` is set and the newly provided function `account_greenlet_times` is installed as a greenlet trace hook.

## 92.1.1

* Bump minimum version of `jinja2` to 3.1.5

## 92.1.0

* RequestCache: add CacheResultWrapper to allow dynamic cache decisions

## 92.0.2

* Downgrade minimum version of `requests` to 2.32.3

## 92.0.1

* Bumps core dependencies to latest versions

## 92.0.0

* Restores old validation code so later utils changes can be added to api, admin etc.

## 91.1.2

* Adds rule N804 (invalid-first-argument-name-for-class-method) to linter config

## 91.1.1

* Remove hangul filler character from rendered emails

## 91.1.0

* bump all libs in requirements_for_test_common.in

## 91.0.4

* Don’t copy config when bumping utils version

## 91.0.3

* Fix validating supported international country codes for phone numbers without a leading "+" that look a bit like UK numbers

## 91.0.2

* Bumps requests to newer version

## 91.0.1

* Adds public utility method to check if a phonenumber is international (with correct handling for OFCOM TV numbers)
* Updates PhoneNumber.get_international_phone_info to return the correct info for OFCOM TV numbers

## 91.0.0

* BREAKING CHANGE: All standalone functions for validating, normalising and formatting phone numbers has been removed from notifications_utils/recipient_validation/phone_number.py, and are replaced and encapsualated entirely with a single `PhoneNumber` class. All code that relies on validation, normalisation or fomratting of a phone number must be re-written to use instances of `PhoneNumber` instead.

## 90.0.0

* Allow leading empty columns in CSV files
* Change second argument of `formatters.strip_all_whitespace` (this argument is not used in other apps)

## 89.2.0

* Use github API rather than fetching from their CDN in version_tools

## 89.1.0

* Change version_tools to a package that uses importlib to grab common reqs/config, rather than fetching common files from github. This repo's usage of those common files are now symlinks to the sources of truth found within notification_utils/version_tools/

## 89.0.1

* Raise an exception if we cant fetch remote github files in version_tools.py

## 89.0.0

* `requirements_for_test_common.txt` is now `requirements_for_test_common.in`. Apps should freeze this into a local requirements file for fully reproducible dependencies

## 88.1.1

* Bug fix: applies minor version bump of PhoneNumbers to v8.13.48 to apply a fix to the UG metadata which was causing validation to fail in error

## 88.1.0

* logging: slightly redesign filters behaviour to allow log-call-supplied request_id, span_id, user_id, service_id to be used if they are not available by normal means. Supply these manually for the streaming-response-closed log message.

## 88.0.1

* logging: don't use current_app in _log_response_closed

## 88.0.0

* Removes `template.EmailPreviewTemplate` (only used in admin app)

## 87.1.0

* logging: don't calculate_content_length() for after_request logs of streaming responses - this caused attempted streaming responses to be eagerly consumed, negating the point of streaming responses. Instead emit the after_request log when status code and header is returned and a separate log message when a streaming response is closed.

## 87.0.0

* Reintroduce changes to `AntivirusClient` and `ZendeskClient` from 83.0.0

## 86.2.0

* Adds `asset_fingerprinter.AssetFingerprinter` to replace the versions duplicated across our frontend apps

## 86.1.0

* Add `EventletTimeoutMiddleware`

# 86.0.0

* BREAKING CHANGE: The `Phonenumber` class now accepts a flag `allow_landline`, which defaults to False. This changes the previous default behaviour, allowing landlines.

## 85.0.0

* Removes `SerialisedModel.ALLOWED_PROPERTIES` in favour of annotations syntax

## 84.3.0

* Reverts 84.1.0

## 84.2.0

* The Zendesk client takes a new optional argument, `user_created_at` which populates a new field on the Notify Zendesk form if provided.

## 84.1.1

* Remove GIR 0AA from valid postcodes

## 84.1.0

* Bump versions of common test dependencies (run `make bootstrap` to copy these into your app)

## 84.0.0

* `AntivirusClient` and `ZendeskClient` have returned to their behaviour as of 82.x.x to allow the 83.0.1 fix to go out to apps without the required changes.

# 83.0.1

* Updates phone_numbers to 8.13.45 to apply a fix to the metadata for phone numbers that was discovered causing a subset of valid Jersey numbers to be incorrectly invalidated

## 83.0.0

* `AntivirusClient` and `ZendeskClient` are no longer thread-safe because they now use persistent requests sessions. Thread-local instances should be used in place of any global instances in any situations where threading is liable to be used
* `AntivirusClient` and `ZendeskClient` have had their `init_app(...)` methods removed as this is an awkward pattern to use for initializing thread-local instances. It is recommended to use `LazyLocalGetter` to construct new instances on-demand, passing configuration parameters via the constructor arguments in a `factory` function.

## 82.7.0

* Add `expected_type` mechanism to `LazyLocalGetter`

# 82.6.1

* Adds validation check to `PhoneNumber` so that it returns the expected error message `TOO_SHORT` if an empty string is passed. This has caused issues with users of the v2 API getting inconsistent error messages

## 82.6.0

* Add `LazyLocalGetter` class for lazily-initialized context-local resources

## 82.5.0

* Add support for validation of UK landlines for services with sms_to_uk_landlines enabled using CSV flow

## 82.4.0

* Add support for sending SMS to more international numbers. Sending to Eritrea, Wallis and Futuna, Niue, Kiribati, and Tokelau is now supported.

## 82.3.0
* Extends the validation logic for the `PhoneNumber` class to disallow premium rate numbers

## 82.2.1

* Add fix to recipient_validation/phone_number.py to raise correct error if a service tries to send to an international number without that permission

## 82.2.0
* Add `unsubscribe_link` argument to email templates

## 82.1.2
* Write updated version number to `requirements.txt` if no `requirements.in` file found

## 82.1.1
*  Fix the way we log the request_size. Accessing the data at this point can trigger a validation error early and cause a 500 error

## 82.1.0
*  Adds new logging fields to request logging. Namely environment_name, request_size and response_size

## 82.0.0

* Change `PostalAddress` to add `has_no_fixed_abode_address` method. No fixed abode addresses are now considered invalid.

## 81.1.1
*  Adds condition to validation to allow TV Numbers (https://www.ofcom.org.uk/phones-and-broadband/phone-numbers/numbers-for-drama/) for UK mobiles

## 81.1.0
* introduce new validation class - `PhoneNumber`, that we will use for services that want to send sms
to landline (and in the future this new code can be extended for all phone number validation)
* in this new class, we use `phonenumbers` library for validating phone numbers, instead of our custom valdiation code


## 81.0.0

* BREAKING CHANGE: The constructor for `notification_utils.recipient_validation.errors.InvalidPhoneError`
  - When raising InvalidPhoneError, instead of supplying a custom message, you must create an error by supplying a code from the `InvalidPhoneError.Codes` enum
* `InvalidPhoneError.code` will contain this machine-readable code for an exception if you need to examine it later
* `InvalidPhoneError.get_legacy_v2_api_error_message` returns a historical error message for use on the public v2 api

## 80.0.1

* Reduces minimum required Gunicorn version for compatibility

## 80.0.0

* Copies additional config files from utils into repos
* Renames `version_tools.copy_pyproject_yaml` to `version_tools.copy_config`

## 79.0.1

* Update the `send_ticket_to_zendesk` method of the ZendeskClient to return the ID of the ticket that was created.

## 79.0.0

* Switches on Pyupgrade and a bunch of other more opinionated linting rules

## 78.2.0

* Bumped minimum versions of select subdependencies

## 78.1.0

* Restrict postcodes to valid UK postcode zones

## 78.0.0

* BREAKING CHANGE: recipient validation code has all been moved into separate files in a shared folder. Functionality is unchanged.
  - Email address validation can be found in `notifications_utils.recipient_validation.email_address`
  - Phone number validation can be found in `notifications_utils.recipient_validation.phone_number`
  - Postal address validation can be found in `notifications_utils.recipient_validation.postal_address`
* BREAKING CHANGE: InvalidPhoneError and InvalidAddressError no longer extend InvalidEmailError.
  - if you wish to handle all recipient validation errors, please use `notifications_utils.recipient_validation.errors.InvalidRecipientError`

## 77.2.1

* Change redis delete behaviour to error, rather than end up with stale data, if Redis is unavailable.

## 77.2.0

* `NotifyTask`: include pid and other structured fields in completion log messages

## 77.1.1

* Fix how `version_tools.copy_pyproject_toml` discovers the current version of notifications-utils

## 77.1.0

* Add `version_tools.copy_pyproject_toml` to share linter config between apps

## 77.0.0

* Breaking change to the Zendesk Client. The `ticket_categories` argument has been replaced with a `notify_task_type` argument, and it now populates
  a different Zendesk form.

## 76.1.0

* Remove `check_proxy_header_before_request` from request_helper.py since this was only used when apps
  were deployed on the PaaS.

## 76.0.2

* linting changes

## 76.0.1

* Reject Gibraltar’s postcode (`GX11 1AA) when validating postal addresses

## 76.0.0

* Remove use of `NOTIFY_RUNTIME_PLATFORM` and `NOTIFY_LOG_PATH` flask config parameters, which no longer did anything. Technically this only affects users if the consumed the paramter themselves and relied on utils code setting default values for them.

## 75.2.0

* Add `InsensitiveSet` class (behaves like a normal set, but with uniqueness determined by normalised values)

## 75.1.1

* Don't set `statsd_host` in `set_gunicorn_defaults` - not all apps have statsd.

## 75.1.0

* Split `logging.formatting` submodule out of `logging` module. All components should remain
  accessible via the `logging` module, so this shouldn't affect existing code.
* Introduce `gunicorn_defaults` module.

## 75.0.0

* BREAKING CHANGE: notifications_utils/clients/encryption/encryption_client has been removed. It
  has been replaced with notifications_utils/clients/signing/signing_client. This is because
  the encyrption_client was not using encryption. It was just signing the contents of the string.

## 74.12.3

* Add structured time_taken log to celery logs

## 74.12.2

* Fix use of hyphen in phone number validation error

## 74.12.1

* email template: use the new crown and associated styling

## 74.12.0

* Remove celery.* structured logging for now. It can return when we have more certainty over what values it will log or can rule out that it is ever given sensitive values.

## 74.11.0

* Add option to ignore list of web paths from request logging. Defaults to /_status and /metrics.
* Add new fields to web request log messages (user_agent, host, path)

## 74.9.1

* logging: set celery.worker.strategy logging to WARNING to prevent sensitive information being logged

## 74.9.0

* logging: also attach handlers etc. to celery.worker and celery.redirected

## 74.8.1

* Always hide barcodes when printing a letter - not only when adding a NOTIFY tag

## 74.8.0

* NotifyRequest: generate own span_id if none provided in headers

## 74.7.0

* Include onwards request headers in AntivirusClient requests

## 74.6.0

* Include parent_span_id in request logs
* Include span_id in all logs when available

## 74.5.0

* Include remote_addr in request logs
* NotifyRequest: handle trace ids when not handed X-B3-TraceId by paas

## 74.4.0

* Reverts the 'single session' change from 74.1.0, which may be causing us some connection errors.

## 74.3.0

* Add `decrby` method to the RedisClient

## 74.2.0

* Change logging's date formatting to include microseconds

## 74.1.0

* remove the geojson dependency (another emergency alerts module)
* reuse a single session for all antivirus/zendesk requests to get http keepalive advantages

## 74.0.0

Removes Emergency-Alerts-related code

* the `polygons` module has been removed
* `template.BroadcastPreviewTemplate` and `template.BroadcastMessageTemplate` have been removed

## 73.2.1

* Fix utils packaging to allow access to subpackages again.

## 73.2.0

* Adds a `include_notify_tag` parameter to `LetterPrintTemplate` so that bilingual letters can disable the NOTIFY tag on the English pages of a letter.

## 73.1.3

* Add compatibility with Python 3.11 and 3.12

## 73.1.2

* Change how utils is packaged to exclude tests.

## 73.1.1

* SKIPPED VERSION - NO RELEASE.

## 73.1.0

* Adds request logging to flask apps.
* Adds `RestrictedAny` family of testing utilities to new `testing.comparisons` submodule.

## 73.0.0

* Removes `LetterImageTemplate`. This has been moved to admin, as that is the only app using it.

## 72.2.0

* Render Welsh language templated letter, with page numbers footer and name of the month in Welsh
* Recognise placeholders from letter_welsh_content and letter_welsh_subject fields


## 72.1.0

* Change the email template to use a HTML5 doctype and add a 'hidden' attribute to the preheader

## 72.0.0

* Remove the deprecated `from_address` param from EmailPreviewTemplate (it's been unused for six years)

## 71.0.0

* Remove support for Markdown-style links in letters `[label](https://example.url)`

## 70.0.6

* Fix QR code rendering for old-style syntax `[QR]()`

## 70.0.5

* Ensure UUIDs in Redis cache keys are always lowercase

## 70.0.4

* Update the commit message auto-generated by `make bump-utils` (in app repos) to be copy/pastable via eg vim commit message editing.

## 70.0.3

* Remove empty table cell from 'branding only' branding HTML to fix bug with JAWS screen reader

## 70.0.2

* Update sanitising of SMS content to include more obscure whitespace

## 70.0.0

* InvalidPhoneError messages have been updated. The new error messages are more user friendly.

## 69.0.0

* Remove old syntax for QR codes in letters (only `QR: http://example.com` will work now)

## 68.0.1

* Fix a bug with some HTML getting injected into QR codes

## 68.0.0

* Update return value of `BaseLetterTemplate.has_qr_code_with_too_much_data` from `bool` to `Optional[QrCodeTooLong]`.

## 67.0.0

* Add `has_qr_code_with_too_much_data` property to letter templates.
* Update RecipientCSV to detect and throw errors when rows generate QR codes with too much data in them. Anything using RecipientCSV to process letters will need to check for and report on the row-level property `qr_code_too_long`.

## 66.1.0

* Add a simpler syntax for QR codes in letters (QR: http://example.com)

## 66.0.2

* Style the QR code placeholder so it looks better when the placeholder text is long

## 66.0.1

* Use HTML-encoded parenthesis (`(` and `)`) when rendering template content with placeholders.
* Bump `phonenumbers` to `>= 8.13.8`.

## 66.0.0

* Switch from PyPDF2 to pypdf, and bump to version 3.9.0. This addresses an infinite loop vulnerability in PDF processing (https://nvd.nist.gov/vuln/detail/CVE-2023-36464).

## 65.2.0

* Update international billing rates for text messages to latest values from MMG.

## 65.1.0

* Add a few more mappings to the list of countries for postage

## 65.0.0

* Remove automatic formatting from JSONFormatter. Any log messages using `{}` to inject strings should be converted
  to "old-style" log messages using %s and passing variables as arguments to the log function. Do not eagerly
  interpolate the string (eg "log: {}" % ("string") - let Python's logging module do this itself. This is to provide
  compatability with Sentry. Add the "G" rule to Ruff's checks to enforce this.
* Removes `CustomLogFormatter` altogether, as its only purpose was the auto-formatting as above.

## 64.2.0

* `LetterImageTemplate` now adds a hidden element marking the first page of any attachment

## 64.1.0

* `RequestCache` now stores items in Redis for 28 days by default (2419200 seconds instead
  of 7 days or 604800 seconds)

## 64.0.0

* Remove the `postage` argument from `LetterImageTemplate` in favour of getting `postage`
  from the `template` `dict` (can still be overridden by setting `template_instance.postage`)
* The `page_count` argument of `LetterImageTemplate` is now optional until the template is
  rendered (calling `str(template)`)

## 63.4.0

* Allow subheadings via markdown for emails using `##`.

## 63.3.0

* Only log a warning and no longer raise an error if creating a Zendesk ticket fails because the user is suspended.

## 63.2.0

* `LetterImageTemplate.page_count` is now a property which can be overriden by subclasses
* New attributes and properties on `BaseLetterTemplate` (and its subclasses):
  - `max_page_count`
  - `max_sheet_count`
  - `too_many_pages` (requires subclasses to implement `page_count`)

## 63.1.0

* argument `image_url` to `LetterImageTemplate` is now optional unless calling `str(LetterImageTemplate(…))`

# 63.0.0

* Remove the `technical_ticket` parameter from NotifySupportTicket; replace with an optional `notify_ticket_type`
  that takes a NotifyTicketType enum value. If provided, this will maintain the existing behaviour where tickets are
  tagged as technical/non-technical on creation. If omitted, then tickets will have no ticket type, which may help
  us have a clearer process around triaging tickets.

## 62.4.0

* Add `class="page--first"` and `class="page--last"` to the first and last
  pages (respectively) of letters rendered with `LetterImageTemplate`

## 62.3.1

* Change `logger.exception` to `logger.warning` for log formatting error.

## 62.3.0

* Adds support for Chinese character sets in letters

## 62.2.1

* Injects the celery task ID into logging output if no requestId is present.

## 62.2.0

* Add odd/even class to letter pages

## 62.1.0

* Allow extra logging filters to be passed into `notifications_utils.logging.init_app`.
* Add a `UserIdFilter` to automatically inject the user_id to flask request logs.

## 62.0.1

* Include the country for normalised BFPO lines.

## 62.0.0

* Updated PostalAddress to parse BFPO addresses. Any validation done on PostalAddresses should be update to report on the new error property `has_invalid_country_for_bfpo_address`.

## 61.2.0

* Adds `redis_client.get_lock` which returns a redis lock object (or a stub lock if redis is not enabled). See https://redis-py.readthedocs.io/en/v4.4.2/lock.html for functionality.

## 61.1.0

* Adds a method to the ZendeskClient to add a comment to a pre-existing ticket, including adding attachments.

## 61.0.0

* Provide our own cache file for bank holidays data, which will help us keep it up-to-date. This is a breaking change
  as any apps pulling in utils should now use notifications_utils.bank_holidays.BankHolidays rather than
  govuk_bank_holidays.bank_holidays.BankHolidays directly.

## 60.1.0

* Add `letter_timings.is_dvla_working_day`
* Add `letter_timings.is_royal_mail_working_day`
* Add `letter_timings.get_dvla_working_day_offset_by`
* Add `letter_timings.get_previous_dvla_working_day`
* Add `letter_timings.get_royal_mail_working_day_offset_by`
* Add `letter_timings.get_previous_royal_mail_working_day`

## 60.0.0

* Bump pyproj to be version 3.4.1  or greater. This changes the ESPG codes to be upper case, which affects the how
  `Polygons` class transforms data.

## 59.3.0

* Add tooling to bump utils version in apps

## 59.2.0

* Add support for creating redis cache keys for a specific notification type.

## 59.1.0

* Add synonyms for sending letters to the Canary Islands

## 59.0.0

* Remove `Template.encoding` (very unlikely to be used anywhere)

## 58.1.0

* add a `message_as_html` parameter to `NotifySupportTicket` to enable creating tickets containing HTML (eg links).

## 58.0.0

* replace `brand_name` with `brand_alt_text` in HTMLEmailTemplate to more accurately reflect its purpose

## 57.1.0

* Do not log to file when `NOTIFY_RUNTIME_PLATFORM` is set to `ecs`

## 57.0.0

* Breaking changes to `field.Field`:

  - The `html` argument must now be `escape` or `passthrough`. `strip` is no longer
    valid
  - The default value of the `html` argument is now `escape` not `strip`

* Removal of `formatters.strip_html`:

## 56.0.0

* Breaking: upgrade PyPDF2 to version 2.0.0. You will need to:

  - Change error class imports from `pypdf2.utils` to `pypdf2.errors`.
  - Run the tests and make changes based on the deprecation warnings.

## 55.2.0

* Links in previews of text messages and emergency alerts now have the correct CSS
  classes added automatically
* URLs in previews of text messages and emergency alerts will now become links even
  if they don’t have `http://` or `https://` at the start

## 55.1.7

* Move some functions and variable from the `notifications_utils.formatters` module to
  the `notifications_utils.markdown` and `notifications_utils` modules. None of our
  apps are directly importing the functions and variables which have moved.

## 55.1.4

* Downgrade min version of boto3 due to incompatibility with awscli-cwlogs dependency.

## 55.1.3

* Unpin most dependencies and remove redundant ones (no action required).

## 55.1.1

* Bump shapely to 1.8.0 to support Mac M1 installation of geos.

## 55.1.0

* Added "delete_by_pattern" wrapper to RequestCache decorator group.

## 55.0.0

* Shortened "delete_cache_keys_by_pattern" to "delete_by_pattern".
* "delete_by_pattern" has a new "raise_exception" parameter (default False).

## 54.1.0

* Add should_validate flag to `notifications_utils.recipients.RecipientCSV`. Defaults to `True`.

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

## 47.0.0

* Breaking: remove `create_ticket` method from ZendeskClient

# 46.1.0

* Extract ticket formatting from ZendeskClient into NotifySupportTicket

# 46.0.0

* Revert 45.0.0 (pyproj dependency won't install on PaaS)

# 45.0.0

* Use cartesian coordinate system for polygon geometry

# 44.5.1

* Split out separate too_late_to_cancel_letter function to allow reuse

# 44.5.0

* Add `intersects` method to Polygons

# 44.4.1

* Detect optional placeholders with brackets in their text

# 44.4.0

* Allow Zendesk tickets to be create with internal notes

# 44.3.1

* Round coordinates to 5 decimal places

# 44.3.0

* Add methods to get the bounds and overlap of polygons

# 44.2.1

* Normalise international numbers when formatting

## Prior versions

Changelog not recorded - please see pull requests on github.
