from ordered_set import OrderedSet

from notifications_utils.insensitive_dict import InsensitiveDict


class TemplateChange:
    def __init__(self, old_template, new_template):
        self.old_placeholders = InsensitiveDict.from_keys(old_template.placeholders)
        self.new_placeholders = InsensitiveDict.from_keys(new_template.placeholders)
        self.email_files_names = [email_file.filename for email_file in old_template.email_files] if hasattr(old_template, "email_files") else []

    @property
    def has_different_placeholders(self):
        return bool(self.new_placeholders.keys() ^ self.old_placeholders.keys())

    @property
    def placeholders_added(self):
        return OrderedSet(
            [self.new_placeholders.get(key) for key in self.new_placeholders.keys() - self.old_placeholders.keys()]
        )

    @property
    def placeholders_removed(self):
        return OrderedSet([self.placeholders_and_email_files_removed - self.email_files_removed])

    @property
    def placeholders_and_email_files_removed(self):
        return OrderedSet(
            [self.old_placeholders.get(key) for key in self.old_placeholders.keys() - self.new_placeholders.keys()]
        )

    @property
    def email_files_removed(self):
        return OrderedSet(
            [filename for filename in self.email_files_names if filename in self.placeholders_and_email_files_removed]
        )

    @property
    def is_breaking_change(self):
        return bool(self.placeholders_added or self.email_files_removed)
