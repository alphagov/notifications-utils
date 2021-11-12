# CHANGELOG

This is only used for recording changes for major version bumps.
More minor changes may optionally be recorded here too.

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
