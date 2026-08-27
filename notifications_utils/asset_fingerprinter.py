import hashlib
import pathlib
from collections.abc import MutableMapping


class AssetFingerprinter:
    """
    Get a unique hash for an asset file, so that it doesn't stay cached
    when it changes

    Usage:

        in the application
        template_data.asset_fingerprinter = AssetFingerprinter()

        where template data is how you pass variables to every template.

        in template.html:
        {{ asset_fingerprinter.get_url('stylesheets/application.css') }}

    * 'app/static' is assumed to be the root for all asset files
    """

    _cache: MutableMapping[str, str]
    _asset_root: str
    _filesystem_path: str

    def __init__(self, asset_root: str = "/static/", filesystem_path: str = "app/static/"):
        self._cache = {}
        self._asset_root = asset_root
        self._filesystem_path = filesystem_path

    def get_url(self, asset_path: str, with_querystring_hash: bool = True):
        if not with_querystring_hash:
            return self._asset_root + asset_path
        if asset_path not in self._cache:
            self._cache[asset_path] = (
                self._asset_root + asset_path + "?" + self.get_asset_fingerprint(self._filesystem_path + asset_path)
            )
        return self._cache[asset_path]

    def get_asset_fingerprint(self, asset_file_path: str) -> str:
        return hashlib.md5(self.get_asset_file_contents(asset_file_path)).hexdigest()

    def get_asset_file_contents(self, asset_file_path: str) -> bytes:
        return pathlib.Path(asset_file_path).read_bytes()


asset_fingerprinter: AssetFingerprinter = AssetFingerprinter()
