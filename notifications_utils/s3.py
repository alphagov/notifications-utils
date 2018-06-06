import urllib

import botocore
from boto3 import resource
from flask import current_app


def s3upload(filedata, region, bucket_name, file_location, content_type='binary/octet-stream', tags=None):
    _s3 = resource('s3')

    key = _s3.Object(bucket_name, file_location)

    put_args = {
        'Body': filedata,
        'ServerSideEncryption': 'AES256',
        'ContentType': content_type
    }

    if tags:
        tags = urllib.parse.urlencode(tags)
        put_args['Tagging'] = tags

    try:
        key.put(**put_args)
    except botocore.exceptions.ClientError as e:
        current_app.logger.error(
            "Unable to upload file to S3 bucket {}".format(bucket_name)
        )
        raise e


class S3ObjectNotFound(botocore.exceptions.ClientError):
    pass


def s3download(bucket_name, filename):
    try:
        s3 = resource('s3')
        key = s3.Object(bucket_name, filename)
        return key.get()['Body']
    except botocore.exceptions.ClientError as error:
        raise S3ObjectNotFound(error.response, error.operation_name)
