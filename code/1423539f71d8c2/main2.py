import asyncio
import typing
from datetime import datetime

import aiostream
from camel_converter import to_snake
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse, ServerSentEvent

app = FastAPI(debug=True)

T = typing.TypeVar("T", bound=BaseModel)


class BaseEvent(BaseModel, typing.Generic[T]):
    data: T

    @classmethod
    @property
    def event_name(cls):
        return to_snake(cls.__name__)

    @classmethod
    def create(cls, data: T):
        return cls(data=data)


P = typing.ParamSpec("P")


def event_source():
    def decorator(
        func: typing.Callable[
            P,
            typing.AsyncGenerator[BaseEvent[T], BaseEvent[T]],
        ],
    ):
        async def wrapper(
            *args: typing.Any,
            **kwargs: typing.Any,
        ) -> typing.AsyncGenerator[ServerSentEvent, ServerSentEvent]:
            t = 0
            async for e in func(*args, **kwargs):
                yield ServerSentEvent(
                    event=e.__class__.event_name,
                    id=t,
                    data=e.data.model_dump_json(),
                )
                t += 1

        return wrapper

    return decorator


class EchoPayload(BaseModel):
    message: str
    created_at: datetime = Field(default_factory=datetime.now)


class Echo(BaseEvent[EchoPayload]):
    pass


@event_source()
async def echo_stream2(message: str):
    t = 0
    while True:
        await asyncio.sleep(1)
        yield Echo.create(
            EchoPayload(
                message=message,
            )
        )
        t += 1


@app.get("/sse2")
async def sse2(message: str):
    return EventSourceResponse(content=echo_stream2(message))


class ReverseEcho(BaseEvent[EchoPayload]):
    pass


@event_source()
async def echo_stream3(message: str):
    await asyncio.sleep(1)
    t = 0
    while True:
        await asyncio.sleep(1)
        yield ReverseEcho.create(
            EchoPayload(
                message=message[::-1],
            )
        )
        t += 1


@app.get("/sse3")
async def sse3(message: str):
    return EventSourceResponse(
        content=aiostream.stream.merge(
            echo_stream2(message),
            echo_stream3(message),
        )
    )
