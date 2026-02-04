from flask import current_app

def patch_kombu_sqs_send_message_group_id_for_standard():
    try:
        from kombu.transport.SQS import Channel as SQSChannel
        from kombu.transport.SQS import AsyncMessage, dumps
    except Exception:
        return

    if getattr(SQSChannel, "_notify_patched_group_id_standard", False):
        return

    def _put(self, queue, message, **kwargs):
        q_url = self._new_queue(queue)

        send_kwargs = {"QueueUrl": q_url}

        if "properties" in message:
            props = message["properties"]

            # keep kombu behaviour for MessageAttributes
            if "message_attributes" in props:
                send_kwargs["MessageAttributes"] = props.pop("message_attributes")

            # OUR FIX: always pass MessageGroupId if present (standard queues)
            group_id = props.get("MessageGroupId")
            if group_id:
                current_app.logger.info("***Fair queue group_id: %s***", group_id)
                send_kwargs["MessageGroupId"] = group_id

            # keep DelaySeconds behaviour (standard queues use this)
            delay = props.get("DelaySeconds")
            if delay is not None:
                send_kwargs["DelaySeconds"] = delay

        if self.sqs_base64_encoding:
            body = AsyncMessage().encode(dumps(message))
        else:
            body = dumps(message)
        send_kwargs["MessageBody"] = body

        c = self.sqs(queue=self.canonical_queue_name(queue))
        if message.get("redelivered"):
            c.change_message_visibility(
                QueueUrl=q_url,
                ReceiptHandle=message["properties"]["delivery_tag"],
                VisibilityTimeout=self.wait_time_seconds,
            )
        else:
            c.send_message(**send_kwargs)

    SQSChannel._put = _put
    SQSChannel._notify_patched_group_id_standard = True
