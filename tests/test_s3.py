from urllib.parse import parse_qs

import botocore
import pytest

from notifications_utils.s3 import (
    S3ObjectNotFound,
    s3_multipart_upload_abort,
    s3_multipart_upload_complete,
    s3_multipart_upload_create,
    s3_multipart_upload_part,
    s3download,
    s3upload,
)

contents = "some file data"
region = "eu-west-1"
bucket = "some_bucket"
location = "some_file_location"
content_type = "binary/octet-stream"
upload_id = "test-123-upload-id"
part_number = 23


def test_s3upload_save_file_to_bucket(mocker):
    mocked = mocker.patch("notifications_utils.s3.resource")
    s3upload(filedata=contents, region=region, bucket_name=bucket, file_location=location)
    mocked_put = mocked.return_value.Object.return_value.put
    mocked_put.assert_called_once_with(
        Body=contents,
        ServerSideEncryption="AES256",
        ContentType=content_type,
    )


def test_s3upload_save_file_to_bucket_with_contenttype(mocker):
    content_type = "image/png"
    mocked = mocker.patch("notifications_utils.s3.resource")
    s3upload(filedata=contents, region=region, bucket_name=bucket, file_location=location, content_type=content_type)
    mocked_put = mocked.return_value.Object.return_value.put
    mocked_put.assert_called_once_with(
        Body=contents,
        ServerSideEncryption="AES256",
        ContentType=content_type,
    )


def test_s3upload_raises_exception(app, mocker):
    mocked = mocker.patch("notifications_utils.s3.resource")
    response = {"Error": {"Code": 500}}
    exception = botocore.exceptions.ClientError(response, "Bad exception")
    mocked.return_value.Object.return_value.put.side_effect = exception
    with pytest.raises(botocore.exceptions.ClientError):
        s3upload(filedata=contents, region=region, bucket_name=bucket, file_location="location")


def test_s3upload_save_file_to_bucket_with_urlencoded_tags(mocker):
    mocked = mocker.patch("notifications_utils.s3.resource")
    s3upload(
        filedata=contents,
        region=region,
        bucket_name=bucket,
        file_location=location,
        tags={"a": "1/2", "b": "x y"},
    )
    mocked_put = mocked.return_value.Object.return_value.put

    # make sure tags were a urlencoded query string
    encoded_tags = mocked_put.call_args[1]["Tagging"]
    assert parse_qs(encoded_tags) == {"a": ["1/2"], "b": ["x y"]}


def test_s3upload_save_file_to_bucket_with_metadata(mocker):
    mocked = mocker.patch("notifications_utils.s3.resource")
    s3upload(
        filedata=contents,
        region=region,
        bucket_name=bucket,
        file_location=location,
        metadata={"status": "valid", "pages": "5"},
    )
    mocked_put = mocked.return_value.Object.return_value.put

    metadata = mocked_put.call_args[1]["Metadata"]
    assert metadata == {"status": "valid", "pages": "5"}


def test_s3download_gets_file(mocker):
    mocked = mocker.patch("notifications_utils.s3.resource")
    mocked_object = mocked.return_value.Object
    mocked_get = mocked.return_value.Object.return_value.get
    s3download("bucket", "location.file")
    mocked_object.assert_called_once_with("bucket", "location.file")
    mocked_get.assert_called_once_with()


def test_s3download_raises_on_error(mocker):
    mocked = mocker.patch("notifications_utils.s3.resource")
    mocked.return_value.Object.side_effect = botocore.exceptions.ClientError(
        {"Error": {"Code": 404}},
        "Bad exception",
    )

    with pytest.raises(S3ObjectNotFound):
        s3download("bucket", "location.file")


def test_s3_multipart_upload_create(mocker):
    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_create_multipart_upload = mocked_s3_client.return_value.create_multipart_upload

    s3_multipart_upload_create(bucket_name=bucket, file_location=location)

    mocked_create_multipart_upload.assert_called_once_with(
        Bucket=bucket,
        Key=location,
        ServerSideEncryption="AES256",
        ContentType=content_type,
    )


def test_s3_multipart_upload_create_with_content_type(mocker):
    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_create_multipart_upload = mocked_s3_client.return_value.create_multipart_upload

    s3_multipart_upload_create(bucket_name=bucket, file_location=location, content_type="text/csv")

    mocked_create_multipart_upload.assert_called_once_with(
        Bucket=bucket,
        Key=location,
        ServerSideEncryption="AES256",
        ContentType="text/csv",
    )


def test_s3_multipart_upload_create_failure(mocker, app_with_mocked_logger):
    response = {"Error": {"Code": 500}}
    exception = botocore.exceptions.ClientError(response, "Bad exception")

    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_instance = mocked_s3_client.return_value
    mocked_instance.create_multipart_upload.side_effect = exception

    with pytest.raises(botocore.exceptions.ClientError):
        s3_multipart_upload_create(bucket_name=bucket, file_location=location)

    mocked_instance.create_multipart_upload.assert_called_once()


def test_s3_multipart_upload_part(mocker):
    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_upload_part = mocked_s3_client.return_value.upload_part

    s3_multipart_upload_part(
        part_number=part_number, bucket_name=bucket, filename=location, upload_id=upload_id, data_bytes=contents
    )

    mocked_upload_part.assert_called_once_with(
        Bucket=bucket,
        Key=location,
        PartNumber=part_number,
        UploadId=upload_id,
        Body=contents,
    )


def test_s3_multipart_upload_part_failure(mocker, app_with_mocked_logger):
    response = {"Error": {"Code": 500}}
    exception = botocore.exceptions.ClientError(response, "Bad exception")

    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_instance = mocked_s3_client.return_value
    mocked_instance.upload_part.side_effect = exception

    with pytest.raises(botocore.exceptions.ClientError):
        s3_multipart_upload_part(
            part_number=part_number, bucket_name=bucket, filename=location, upload_id=upload_id, data_bytes=contents
        )

    mocked_instance.upload_part.assert_called_once()


def test_s3_multipart_upload_complete(mocker):
    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_complete_multipart_upload = mocked_s3_client.return_value.complete_multipart_upload

    s3_multipart_upload_complete(bucket_name=bucket, filename=location, upload_id=upload_id, parts=[])

    mocked_complete_multipart_upload.assert_called_once_with(
        Bucket=bucket,
        Key=location,
        MultipartUpload={"Parts": []},
        UploadId=upload_id,
    )


def test_s3_multipart_upload_complete_failure(mocker, app_with_mocked_logger):
    response = {"Error": {"Code": 500}}
    exception = botocore.exceptions.ClientError(response, "Bad exception")

    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_instance = mocked_s3_client.return_value
    mocked_instance.complete_multipart_upload.side_effect = exception

    with pytest.raises(botocore.exceptions.ClientError):
        s3_multipart_upload_complete(bucket_name=bucket, filename=location, upload_id=upload_id, parts=[])

    mocked_instance.complete_multipart_upload.assert_called_once()


def test_s3_multipart_upload_abort(mocker):
    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_abort_multipart_upload = mocked_s3_client.return_value.abort_multipart_upload

    s3_multipart_upload_abort(bucket_name=bucket, filename=location, upload_id=upload_id)

    mocked_abort_multipart_upload.assert_called_once_with(
        Bucket=bucket,
        Key=location,
        UploadId=upload_id,
    )


def test_s3_multipart_upload_abort_failure(mocker, app_with_mocked_logger):
    response = {"Error": {"Code": 500}}
    exception = botocore.exceptions.ClientError(response, "Bad exception")

    mocked_s3_client = mocker.patch("notifications_utils.s3.client")
    mocked_instance = mocked_s3_client.return_value
    mocked_instance.abort_multipart_upload.side_effect = exception

    with pytest.raises(botocore.exceptions.ClientError):
        s3_multipart_upload_abort(bucket_name=bucket, filename=location, upload_id=upload_id)

    mocked_instance.abort_multipart_upload.assert_called_once()
