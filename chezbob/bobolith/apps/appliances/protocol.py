import json
from typing import Protocol, Type

from bidict import bidict
from django.conf import settings


class MessageHeader:
    __slots__ = ['message_type', 'version']

    version: int
    message_type: str

    def __init__(self, message_type, version=None):
        self.message_type = message_type
        if version is None:
            self.version = settings.BOBOLITH_PROTOCOL_VERSION

    def to_json(self):
        return {
            'version': self.version,
            'message_type': self.message_type,
        }


class Message(Protocol):
    header: MessageHeader

    def __init__(self, header=None, **kwargs):
        ...


MESSAGE_TYPES: bidict[str, Type[Message]] = bidict({
    # 'header': MessageHeader
})


def message_mixin(message_type: str) -> Type[Message]:
    class MessageMixin(Message):
        __slots__ = ['header']

        header: MessageHeader

        def __init__(self, header=None, **kwargs):
            super().__init__(header, **kwargs)

            if header is None:
                self.header = MessageHeader(message_type=message_type)

            for key, value in kwargs.items():
                setattr(self, key, value)

        def __init_subclass__(cls, **kwargs):
            if cls not in MESSAGE_TYPES.inverse:
                MESSAGE_TYPES[message_type] = cls

        def to_json(self):
            return {slot: getattr(self, slot)
                    for slot in self.__slots__
                    if hasattr(self, slot)}

    return MessageMixin


class PingMessage(message_mixin('ping')):
    __slots__ = ['ping']

    ping: str


class PongMessage(message_mixin('pong')):
    __slots__ = ['pong']

    pong: str


def _encode(o):
    if o.__class__ in MESSAGE_TYPES.inverse:
        return o.to_json()
    else:
        raise TypeError(f'Object of type {o.__class__.__name__} '
                        f'is not JSON serializable')


def _decode(json_dict):
    if 'header' not in json_dict:
        return json_dict
    content = dict(json_dict)
    header_content = content.pop('header')
    if type(header_content) is not dict or \
            'message_type' not in header_content or \
            header_content['message_type'] not in MESSAGE_TYPES:
        # This is a non-message dict, just return it.
        return json_dict
    header = MessageHeader(**header_content)

    klass = MESSAGE_TYPES[header.message_type]
    msg = klass(header=header, **content)

    return msg


MessageEncoder = json.JSONEncoder(default=_encode)
MessageDecoder = json.JSONDecoder(object_hook=_decode)
