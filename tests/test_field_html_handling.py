import pytest

from notifications_utils.field import Field


@pytest.mark.parametrize(
    "content, values, expected_escaped, expected_passthrough",
    [
        (
            "string <em>with</em> html",
            {},
            "string &lt;em&gt;with&lt;/em&gt; html",
            "string <em>with</em> html",
        ),
        (
            "string ((<em>with</em>)) html",
            {},
            "string <span class='placeholder'>&#40;&#40;&lt;em&gt;with&lt;/em&gt;&#41;&#41;</span> html",
            "string <span class='placeholder'>&#40;&#40;<em>with</em>&#41;&#41;</span> html",
        ),
        (
            "string ((placeholder)) html",
            {"placeholder": "<em>without</em>"},
            "string &lt;em&gt;without&lt;/em&gt; html",
            "string <em>without</em> html",
        ),
        (
            "string ((<em>conditional</em>??<em>placeholder</em>)) html",
            {},
            (
                "string "
                "<span class='placeholder-conditional'>"
                "&#40;&#40;&lt;em&gt;conditional&lt;/em&gt;??</span>"
                "&lt;em&gt;placeholder&lt;/em&gt;&#41;&#41; "
                "html"
            ),
            (
                "string "
                "<span class='placeholder-conditional'>"
                "&#40;&#40;<em>conditional</em>??</span>"
                "<em>placeholder</em>&#41;&#41; "
                "html"
            ),
        ),
        (
            "string ((conditional??<em>placeholder</em>)) html",
            {"conditional": True},
            "string &lt;em&gt;placeholder&lt;/em&gt; html",
            "string <em>placeholder</em> html",
        ),
        (
            "string & entity",
            {},
            "string &amp; entity",
            "string & entity",
        ),
    ],
)
def test_field_handles_html(content, values, expected_escaped, expected_passthrough):
    assert str(Field(content, values)) == expected_escaped
    assert str(Field(content, values, html="escape")) == expected_escaped
    assert str(Field(content, values, html="passthrough")) == expected_passthrough
