import pytest

from notifications_utils.template_change import TemplateChange
from tests.test_base_template import ConcreteTemplate


@pytest.mark.parametrize(
    "old_template, new_template, should_differ",
    [
        (ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), False),
        (ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), ConcreteTemplate({"content": "((3)) ((2)) ((1))"}), False),
        (
            ConcreteTemplate({"content": "((1)) ((2)) ((3))"}),
            ConcreteTemplate({"content": "((1)) ((1)) ((2)) ((2)) ((3)) ((3))"}),
            False,
        ),
        (ConcreteTemplate({"content": "((1))"}), ConcreteTemplate({"content": "((1)) ((2))"}), True),
        (ConcreteTemplate({"content": "((1)) ((2))"}), ConcreteTemplate({"content": "((1))"}), True),
        (ConcreteTemplate({"content": "((a)) ((b))"}), ConcreteTemplate({"content": "((A)) (( B_ ))"}), False),
    ],
)
def test_checking_for_difference_between_templates(old_template, new_template, should_differ):
    assert TemplateChange(old_template, new_template).has_different_placeholders == should_differ


@pytest.mark.parametrize(
    "old_template, new_template, placeholders_added, is_breaking_change",
    [
        (
            ConcreteTemplate({"content": "((1)) ((2)) ((3))"}),
            ConcreteTemplate({"content": "((1)) ((2)) ((3))"}),
            set(),
            False,
        ),
        (
            ConcreteTemplate({"content": "((1)) ((2)) ((3))"}),
            ConcreteTemplate({"content": "((1)) ((1)) ((2)) ((2)) ((3)) ((3))"}),
            set(),
            False,
        ),
        (ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), ConcreteTemplate({"content": "((1))"}), set(), False),
        (ConcreteTemplate({"content": "((1))"}), ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), {"2", "3"}, True),
        (ConcreteTemplate({"content": "((a))"}), ConcreteTemplate({"content": "((A)) ((B)) ((C))"}), {"B", "C"}, True),
    ],
)
def test_placeholders_added(old_template, new_template, placeholders_added, is_breaking_change):
    template_change = TemplateChange(old_template, new_template)
    assert template_change.placeholders_added == placeholders_added
    assert template_change.is_breaking_change is is_breaking_change


@pytest.mark.parametrize(
    "old_template, new_template, placeholders_removed",
    [
        (ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), set()),
        (
            ConcreteTemplate({"content": "((1)) ((2)) ((3))"}),
            ConcreteTemplate({"content": "((1)) ((1)) ((2)) ((2)) ((3)) ((3))"}),
            set(),
        ),
        (ConcreteTemplate({"content": "((1))"}), ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), set()),
        (ConcreteTemplate({"content": "((1)) ((2)) ((3))"}), ConcreteTemplate({"content": "((1))"}), {"2", "3"}),
        (ConcreteTemplate({"content": "((a)) ((b)) ((c))"}), ConcreteTemplate({"content": "((A))"}), {"b", "c"}),
    ],
)
def test_placeholders_removed(old_template, new_template, placeholders_removed):
    assert TemplateChange(old_template, new_template).placeholders_removed == placeholders_removed


@pytest.mark.parametrize(
    "old_template, new_template, email_files_removed, is_breaking_change",
    [
        (
            ConcreteTemplate(
                {"content": "((1.pdf)) ((2)) ((3))", "email_files": [{"filename": "1.pdf", "retention_period": 26}]}
            ),
            ConcreteTemplate(
                {"content": "((1.pdf)) ((2)) ((3))", "email_files": [{"filename": "1.pdf", "retention_period": 26}]}
            ),
            set(),
            False,
        ),
        (
            ConcreteTemplate(
                {
                    "content": "((1)) ((2.pdf)) ((3))",
                    "email_files": [
                        {"filename": "2.pdf", "retention_period": 26},
                    ],
                }
            ),
            ConcreteTemplate(
                {
                    "content": "((1)) ((3))",
                    "email_files": [
                        {"filename": "2.pdf", "retention_period": 26},
                    ],
                }
            ),
            {"2.pdf"},
            True,
        ),
        (
            ConcreteTemplate(
                {
                    "content": "((1)) ((2.pdf)) ((3.pdf))",
                    "email_files": [
                        {"filename": "2.pdf", "retention_period": 26},
                        {"filename": "3.pdf", "retention_period": 26},
                    ],
                }
            ),
            ConcreteTemplate(
                {
                    "content": "((1)) ((4.pdf))",
                    "email_files": [
                        {"filename": "2.pdf", "retention_period": 26},
                        {"filename": "3.pdf", "retention_period": 26},
                    ],
                }
            ),
            {"2.pdf", "3.pdf"},
            True,
        ),
    ],
)
def test_email_files_removed(old_template, new_template, email_files_removed, is_breaking_change):
    template_change = TemplateChange(old_template, new_template)
    assert template_change.email_files_removed == email_files_removed
    assert template_change.is_breaking_change is is_breaking_change


def test_ordering_of_placeholders_is_preserved():
    before = ConcreteTemplate({"content": "((dog)) ((cat)) ((rat))"})
    after = ConcreteTemplate({"content": "((platypus)) ((echidna)) ((quokka))"})
    change = TemplateChange(before, after)
    assert change.placeholders_removed == ["dog", "cat", "rat"] == before.placeholders
    assert change.placeholders_added == ["platypus", "echidna", "quokka"] == after.placeholders
