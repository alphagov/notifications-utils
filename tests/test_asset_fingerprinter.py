from notifications_utils.asset_fingerprinter import AssetFingerprinter


class TestAssetFingerprint:
    def test_url_format(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = b"""
            body {
                font-family: nta;
            }
        """
        asset_fingerprinter = AssetFingerprinter(asset_root="/suppliers/static/")
        assert (
            asset_fingerprinter.get_url("application.css")
            == "/suppliers/static/application.css?418e6f4a6cdf1142e45c072ed3e1c90a"
        )
        assert (
            asset_fingerprinter.get_url("application-ie6.css")
            == "/suppliers/static/application-ie6.css?418e6f4a6cdf1142e45c072ed3e1c90a"
        )

    def test_building_file_path(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = b"""
            document.write('Hello world!');
        """
        fingerprinter = AssetFingerprinter()
        fingerprinter.get_url("javascripts/application.js")
        fingerprinter.get_asset_file_contents.assert_called_with("app/static/javascripts/application.js")

    def test_hashes_are_consistent(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = b"""
            body {
                font-family: nta;
            }
        """
        asset_fingerprinter = AssetFingerprinter()
        assert asset_fingerprinter.get_asset_fingerprint(
            "application.css"
        ) == asset_fingerprinter.get_asset_fingerprint("same_contents.css")

    def test_hashes_are_different_for_different_files(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        asset_fingerprinter = AssetFingerprinter()
        get_file_content_mock.return_value = b"""
            body {
                font-family: nta;
            }
        """
        css_hash = asset_fingerprinter.get_asset_fingerprint("application.css")
        get_file_content_mock.return_value = b"""
            document.write('Hello world!');
        """
        js_hash = asset_fingerprinter.get_asset_fingerprint("application.js")
        assert js_hash != css_hash

    def test_gets_fingerprint_from_cache(self, mocker):
        get_file_content_mock = mocker.patch.object(AssetFingerprinter, "get_asset_file_contents")
        get_file_content_mock.return_value = b"""
            body {
                font-family: nta;
            }
        """
        fingerprinter = AssetFingerprinter()
        assert fingerprinter.get_url("application.css") == "/static/application.css?418e6f4a6cdf1142e45c072ed3e1c90a"
        fingerprinter._cache["application.css"] = "a1a1a1"
        assert fingerprinter.get_url("application.css") == "a1a1a1"
        fingerprinter.get_asset_file_contents.assert_called_once_with("app/static/application.css")

    def test_without_hash_if_requested(self, mocker):
        fingerprinter = AssetFingerprinter()
        assert (
            fingerprinter.get_url(
                "application.css",
                with_querystring_hash=False,
            )
            == "/static/application.css"
        )
        assert fingerprinter._cache == {}


class TestAssetFingerprintWithUnicode:
    def test_can_read_self(self):
        "Ralph’s apostrophe is a string containing a unicode character"
        AssetFingerprinter(filesystem_path="tests/").get_url("test_asset_fingerprinter.py")
