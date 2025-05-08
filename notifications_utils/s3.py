import urllib

import botocore
from boto3 import client, resource
from flask import current_app


def s3upload(
    filedata,
    region,
    bucket_name,
    file_location,
    content_type="binary/octet-stream",
    tags=None,
    metadata=None,
):
    _s3 = resource("s3")

    key = _s3.Object(bucket_name, file_location)

    put_args = {"Body": filedata, "ServerSideEncryption": "AES256", "ContentType": content_type}

    if tags:
        tags = urllib.parse.urlencode(tags)
        put_args["Tagging"] = tags

    if metadata:
        metadata = put_args["Metadata"] = metadata

    try:
        key.put(**put_args)
    except botocore.exceptions.ClientError as e:
        current_app.logger.error("Unable to upload file to S3 bucket %s", bucket_name)
        raise e


class S3ObjectNotFound(botocore.exceptions.ClientError):
    pass


def s3download(bucket_name, filename):
    try:
        s3 = resource("s3")
        key = s3.Object(bucket_name, filename)
        return key.get()["Body"]
    except botocore.exceptions.ClientError as error:
        raise S3ObjectNotFound(error.response, error.operation_name) from error


S3_MULTIPART_UPLOAD_MIN_PART_SIZE = 5 * 1024 * 1024  # 5MB minimum multi part upload size


def s3_multipart_upload_create(bucket_name, file_location, content_type="binary/octet-stream"):
    s3 = client("s3")

    args = {"Bucket": bucket_name, "Key": file_location, "ServerSideEncryption": "AES256", "ContentType": content_type}

    try:
        response = s3.create_multipart_upload(**args)
        return response
    except botocore.exceptions.ClientError as e:
        current_app.logger.error(
            "Unable to create multipart upload in S3 bucket %s for file %s", bucket_name, file_location
        )
        raise e


def s3_multipart_upload_part(part_number, bucket_name, filename, upload_id, data_bytes):
    s3 = client("s3")

    try:
        response = s3.upload_part(
            Bucket=bucket_name,
            Key=filename,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=data_bytes,
        )
        return response
    except botocore.exceptions.ClientError as e:
        current_app.logger.exception(
            "Unable to upload part %s in S3 bucket %s for file %s", part_number, bucket_name, filename
        )
        raise e


def s3_multipart_upload_complete(bucket_name, filename, upload_id, parts):
    s3 = client("s3")
    try:
        s3.complete_multipart_upload(
            Bucket=bucket_name,
            Key=filename,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
    except botocore.exceptions.ClientError as e:
        current_app.logger.exception(
            "Unable to complete multipart upload %s in S3 bucket %s for file %s", upload_id, bucket_name, filename
        )
        raise e


def s3_multipart_upload_abort(bucket_name, filename, upload_id):
    s3 = client("s3")

    try:
        s3.abort_multipart_upload(Bucket=bucket_name, Key=filename, UploadId=upload_id)
    except botocore.exceptions.ClientError as e:
        current_app.logger.exception(
            "Unable to abort multipart upload %s in S3 bucket %s for file %s", upload_id, bucket_name, filename
        )
        raise e
