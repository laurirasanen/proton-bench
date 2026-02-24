#!/usr/bin/env python3
#
# GENERATED FILE, DO NOT EDIT
#
# SPDX-License-Identifier: MIT
#
from typing import Any, Callable, Generator, Tuple
from enum import IntEnum
from dataclasses import dataclass, field
try:
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum

import binascii
import itertools
import logging
import struct
import structlog
import time

# type aliases
s = str
i = int
u = int
x = int
t = int
o = int
n = int
f = float
h = int  # FIXME this should be a file-like object

logger = structlog.get_logger()


def hexlify(data):
    return binascii.hexlify(data, sep=" ", bytes_per_sep=4)


class ObjectId(int):
    def __repr__(self) -> str:
        return f"{self:#x}"


@dataclass
class MethodCall:
    name: str
    args: dict[str, Any]
    objects: dict[str, "Interface"] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class MessageHeader:
    object_id: ObjectId
    msglen: int
    opcode: int

    @classmethod
    def size(cls) -> int:
        return 16

    @classmethod
    def from_data(cls, data: bytes) -> "MessageHeader":
        object_id, msglen, opcode = struct.unpack("=QII", data[:cls.size()])
        return cls(ObjectId(object_id), msglen, opcode)

    @property
    def as_tuple(self) -> Tuple[int, int, int]:
        return self.object_id, self.msglen, self.opcode


@dataclass
class Context:
    objects: dict[str, "Interface"] = field(default_factory=dict)
    _callbacks: dict[str, dict[int, Callable]] = field(
        init=False,
        default_factory=lambda: { "register": {}, "unregister": {}}
    )
    _ids: Generator = field(init=False, default_factory=itertools.count)

    def register(self, object: "Interface") -> None:
        assert object.object_id not in self.objects
        logger.debug(f"registering object", interface=object.name, object_id=f"{object.object_id:#x}")
        self.objects[object.object_id] = object
        for cb in self._callbacks["register"].values():
            cb(object)

    def unregister(self, object: "Interface") -> None:
        assert object.object_id in self.objects
        logger.debug(f"unregistering object", interface=object.name, object=object, object_id=f"{object.object_id:#x}")
        del self.objects[object.object_id]
        for cb in self._callbacks["unregister"].values():
            cb(object)

    def connect(self, signal: str, callback: Callable) -> int:
        cbs = self._callbacks[signal]
        id = next(self._ids)
        cbs[id] = callback
        return id

    def disconnect(self, signal: str, id: int) -> None:
        del self._callbacks[signal][id]

    def dispatch(self, data: bytes) -> None:
        if len(data) < MessageHeader.size():
            return

        header = MessageHeader.from_data(data)
        object_id, opcode, msglen = header.object_id, header.opcode, header.msglen
        logger.debug(f"incoming packet ({msglen} bytes)", object_id=f"{object_id:x}", opcode=opcode, bytes=hexlify(data[:msglen]))

        try:
            dispatcher = self.objects[object_id]
        except KeyError:
            logger.error("Message from unknown object", object_id=f"{object_id:x}")
            return msglen

        try:
            logger.debug(f"incoming packet: dispatching", func=f"{dispatcher.name}.{dispatcher.incoming[opcode]}()", object=dispatcher)
        except KeyError:
            logger.error("Invalid opcode for object", object_id=f"{object_id:x}", opcode=opcode)
            return msglen
        consumed = dispatcher.dispatch(data, context=self)
        return consumed

    @classmethod
    def create(cls) -> "Context":
        o = cls()
        o.register(EiHandshake.create(object_id=0, version=1))
        return o


class InterfaceName(StrEnum):
    EI_HANDSHAKE = "ei_handshake"
    EI_CONNECTION = "ei_connection"
    EI_CALLBACK = "ei_callback"
    EI_PINGPONG = "ei_pingpong"
    EI_SEAT = "ei_seat"
    EI_DEVICE = "ei_device"
    EI_POINTER = "ei_pointer"
    EI_POINTER_ABSOLUTE = "ei_pointer_absolute"
    EI_SCROLL = "ei_scroll"
    EI_BUTTON = "ei_button"
    EI_KEYBOARD = "ei_keyboard"
    EI_TOUCHSCREEN = "ei_touchscreen"


@dataclass(eq=False)
class Interface:
    object_id: int
    version: int
    callbacks: dict[str, Callable] = field(init=False, default_factory=dict, repr=False)
    calllog: list[MethodCall] = field(init=False, default_factory=list, repr=False)
    name: str = field(default="<overridden by subclass>")
    incoming: dict[int, str] = field(default_factory=list, repr=False)
    outgoing: dict[int, str] = field(default_factory=list, repr=False)

    def format(self, *args, opcode: int, signature: str) -> bytes:
        encoding = ["=QII"]
        arguments = []
        for sig, arg in zip(signature, args):
            if sig in ["u"]:
                encoding.append("I")
            elif sig in ["i"]:
                encoding.append("i")
            elif sig in ["f"]:
                encoding.append("f")
            elif sig in ["n", "o", "t"]:
                encoding.append("Q")
            elif sig in ["x"]:
                encoding.append("q")
            elif sig in ["s"]:
                encoding.append("I")
                arguments.append(len(arg) + 1)
                slen = ((len(arg) + 1 + 3) // 4) * 4
                encoding.append(f"{slen}s")
                arg = arg.encode("utf8")
            elif sig in ["h"]:
                raise NotImplementedError("fd passing is not yet supported here")

            arguments.append(arg)

        format = "".join(encoding)
        length = struct.calcsize(format)
        header = MessageHeader(self.object_id, length, opcode)
        # logger.debug(f"Packing {encoding}: {arguments}")
        return struct.pack(format, *header.as_tuple, *arguments)

    def unpack(self, data, signature: str, names: list[str]) -> Tuple[int, dict[str, Any]]:
        encoding = ["=QII"]  # the header
        for sig in signature:
            if sig in ["u"]:
                encoding.append("I")
            elif sig in ["i"]:
                encoding.append("i")
            elif sig in ["f"]:
                encoding.append("f")
            elif sig in ["x"]:
                encoding.append("q")
            elif sig in ["n", "o", "t"]:
                encoding.append("Q")
            elif sig in ["s"]:
                length_so_far = struct.calcsize("".join(encoding))
                slen, = struct.unpack("I", data[length_so_far:length_so_far + 4])
                slen = ((slen + 3) // 4) * 4
                encoding.append(f"I{slen}s")
            elif sig in ["h"]:
                raise NotImplementedError("fd passing is not yet supported here")

        format = "".join(encoding)
        msglen = struct.calcsize(format)
        try:
            values = list(struct.unpack(format, data[:msglen]))
        except struct.error as e:
            logger.error(f"{e}", bytes=hexlify(data), length=len(data), encoding=format)
            raise e

        # logger.debug(f"unpacked {format} to {values}")

        results = []
        values = values[3:]  # drop id, length, opcode

        # we had to insert the string length into the format, filter the
        # value for that out again.
        for sig in signature:
            if sig in ["s"]:
                values.pop(0)
                s = values.pop(0)
                if not s:
                    s = None  # zero-length string is None
                else:
                    s = s.decode("utf8").rstrip("\x00")  # strip trailing zeroes
                results.append(s)
            else:
                results.append(values.pop(0))

        # First two values are object_id and len|opcode
        return (msglen, { name: value for name, value in zip(names, results) })

    def connect(self, event: str, callback: Callable):
        self.callbacks[event] = callback

    @classmethod
    def lookup(cls, name: str) -> "Interface":
        return {
            "ei_handshake": EiHandshake,
            "ei_connection": EiConnection,
            "ei_callback": EiCallback,
            "ei_pingpong": EiPingpong,
            "ei_seat": EiSeat,
            "ei_device": EiDevice,
            "ei_pointer": EiPointer,
            "ei_pointer_absolute": EiPointerAbsolute,
            "ei_scroll": EiScroll,
            "ei_button": EiButton,
            "ei_keyboard": EiKeyboard,
            "ei_touchscreen": EiTouchscreen,
        }[name]


@dataclass
class EiHandshake(Interface):
    class EiContextType(IntEnum):
        RECEIVER = 1
        SENDER = 2


    def HandshakeVersion(self, version: u) -> bytes:
        data = self.format(version, opcode=0, signature="u")
        logger.debug("composing message", oject=self, func="ei_handshake.handshake_version", args={"version": version, }, result=hexlify(data))
        return data

    def Finish(self) -> bytes:
        data = self.format(opcode=1, signature="")
        logger.debug("composing message", oject=self, func="ei_handshake.finish", args={}, result=hexlify(data))
        return data

    def ContextType(self, context_type: u) -> bytes:
        data = self.format(context_type, opcode=2, signature="u")
        logger.debug("composing message", oject=self, func="ei_handshake.context_type", args={"context_type": context_type, }, result=hexlify(data))
        return data

    def Name(self, name: s) -> bytes:
        data = self.format(name, opcode=3, signature="s")
        logger.debug("composing message", oject=self, func="ei_handshake.name", args={"name": name, }, result=hexlify(data))
        return data

    def InterfaceVersion(self, name: s, version: u) -> bytes:
        data = self.format(name, version, opcode=4, signature="su")
        logger.debug("composing message", oject=self, func="ei_handshake.interface_version", args={"name": name, "version": version, }, result=hexlify(data))
        return data

    def onHandshakeVersion(self, context: Context, version: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("HandshakeVersion", None)
        if cb is not None:
            if new_objects:
                cb(self, version, new_objects=new_objects)
            else:
                cb(self, version)

        m = MethodCall(name="HandshakeVersion", args={
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)


    def onInterfaceVersion(self, context: Context, name: s, version: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("InterfaceVersion", None)
        if cb is not None:
            if new_objects:
                cb(self, name, version, new_objects=new_objects)
            else:
                cb(self, name, version)

        m = MethodCall(name="InterfaceVersion", args={
            "name": name,
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)


    def onConnection(self, context: Context, serial: u, connection: n, version: u):
        new_objects = {
            "connection": EiConnection.create(connection, version),
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Connection", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, connection, version, new_objects=new_objects)
            else:
                cb(self, serial, connection, version)

        m = MethodCall(name="Connection", args={
            "serial": serial,
            "connection": connection,
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="HandshakeVersion", args=args)
            self.onHandshakeVersion(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="su", names=[
                    "name",
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="InterfaceVersion", args=args)
            self.onInterfaceVersion(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="unu", names=[
                    "serial",
                    "connection",
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="Connection", args=args)
            self.onConnection(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "handshake_version",
            1: "interface_version",
            2: "connection",
        }
        outgoing = {
            0: "handshake_version",
            1: "finish",
            2: "context_type",
            3: "name",
            4: "interface_version",
        }
        return cls(object_id=object_id, version=version, name="ei_handshake", incoming=incoming, outgoing=outgoing)


@dataclass
class EiConnection(Interface):
    class EiDisconnectReason(IntEnum):
        DISCONNECTED = 0
        ERROR = 1
        MODE = 2
        PROTOCOL = 3
        VALUE = 4
        TRANSPORT = 5


    def Sync(self, callback: n, version: u) -> bytes:
        data = self.format(callback, version, opcode=0, signature="nu")
        logger.debug("composing message", oject=self, func="ei_connection.sync", args={"callback": callback, "version": version, }, result=hexlify(data))
        return data

    def Disconnect(self) -> bytes:
        data = self.format(opcode=1, signature="")
        logger.debug("composing message", oject=self, func="ei_connection.disconnect", args={}, result=hexlify(data))
        return data

    def onDisconnected(self, context: Context, last_serial: u, reason: u, explanation: s):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Disconnected", None)
        if cb is not None:
            if new_objects:
                cb(self, last_serial, reason, explanation, new_objects=new_objects)
            else:
                cb(self, last_serial, reason, explanation)

        m = MethodCall(name="Disconnected", args={
            "last_serial": last_serial,
            "reason": reason,
            "explanation": explanation,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onSeat(self, context: Context, seat: n, version: u):
        new_objects = {
            "seat": EiSeat.create(seat, version),
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Seat", None)
        if cb is not None:
            if new_objects:
                cb(self, seat, version, new_objects=new_objects)
            else:
                cb(self, seat, version)

        m = MethodCall(name="Seat", args={
            "seat": seat,
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)


    def onInvalidObject(self, context: Context, last_serial: u, invalid_id: t):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("InvalidObject", None)
        if cb is not None:
            if new_objects:
                cb(self, last_serial, invalid_id, new_objects=new_objects)
            else:
                cb(self, last_serial, invalid_id)

        m = MethodCall(name="InvalidObject", args={
            "last_serial": last_serial,
            "invalid_id": invalid_id,
            }, objects=new_objects)
        self.calllog.append(m)


    def onPing(self, context: Context, ping: n, version: u):
        new_objects = {
            "ping": EiPingpong.create(ping, version),
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Ping", None)
        if cb is not None:
            if new_objects:
                cb(self, ping, version, new_objects=new_objects)
            else:
                cb(self, ping, version)

        m = MethodCall(name="Ping", args={
            "ping": ping,
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="uus", names=[
                    "last_serial",
                    "reason",
                    "explanation",
                    ])
            logger.debug("dispatching", object=self, func="Disconnected", args=args)
            self.onDisconnected(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="nu", names=[
                    "seat",
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="Seat", args=args)
            self.onSeat(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="ut", names=[
                    "last_serial",
                    "invalid_id",
                    ])
            logger.debug("dispatching", object=self, func="InvalidObject", args=args)
            self.onInvalidObject(context, **args)
        elif opcode == 3:
            consumed, args = self.unpack(data, signature="nu", names=[
                    "ping",
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="Ping", args=args)
            self.onPing(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "disconnected",
            1: "seat",
            2: "invalid_object",
            3: "ping",
        }
        outgoing = {
            0: "sync",
            1: "disconnect",
        }
        return cls(object_id=object_id, version=version, name="ei_connection", incoming=incoming, outgoing=outgoing)


@dataclass
class EiCallback(Interface):


    def onDone(self, context: Context, callback_data: t):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Done", None)
        if cb is not None:
            if new_objects:
                cb(self, callback_data, new_objects=new_objects)
            else:
                cb(self, callback_data)

        m = MethodCall(name="Done", args={
            "callback_data": callback_data,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="t", names=[
                    "callback_data",
                    ])
            logger.debug("dispatching", object=self, func="Done", args=args)
            self.onDone(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "done",
        }
        outgoing = {
        }
        return cls(object_id=object_id, version=version, name="ei_callback", incoming=incoming, outgoing=outgoing)


@dataclass
class EiPingpong(Interface):


    def Done(self, callback_data: t) -> bytes:
        data = self.format(callback_data, opcode=0, signature="t")
        logger.debug("composing message", oject=self, func="ei_pingpong.done", args={"callback_data": callback_data, }, result=hexlify(data))
        return data

    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
        }
        outgoing = {
            0: "done",
        }
        return cls(object_id=object_id, version=version, name="ei_pingpong", incoming=incoming, outgoing=outgoing)


@dataclass
class EiSeat(Interface):


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_seat.release", args={}, result=hexlify(data))
        return data

    def Bind(self, capabilities: t) -> bytes:
        data = self.format(capabilities, opcode=1, signature="t")
        logger.debug("composing message", oject=self, func="ei_seat.bind", args={"capabilities": capabilities, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onName(self, context: Context, name: s):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Name", None)
        if cb is not None:
            if new_objects:
                cb(self, name, new_objects=new_objects)
            else:
                cb(self, name)

        m = MethodCall(name="Name", args={
            "name": name,
            }, objects=new_objects)
        self.calllog.append(m)


    def onCapability(self, context: Context, mask: t, interface: s):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Capability", None)
        if cb is not None:
            if new_objects:
                cb(self, mask, interface, new_objects=new_objects)
            else:
                cb(self, mask, interface)

        m = MethodCall(name="Capability", args={
            "mask": mask,
            "interface": interface,
            }, objects=new_objects)
        self.calllog.append(m)


    def onDone(self, context: Context):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Done", None)
        if cb is not None:
            if new_objects:
                cb(self, new_objects=new_objects)
            else:
                cb(self)

        m = MethodCall(name="Done", args={
            }, objects=new_objects)
        self.calllog.append(m)


    def onDevice(self, context: Context, device: n, version: u):
        new_objects = {
            "device": EiDevice.create(device, version),
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Device", None)
        if cb is not None:
            if new_objects:
                cb(self, device, version, new_objects=new_objects)
            else:
                cb(self, device, version)

        m = MethodCall(name="Device", args={
            "device": device,
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="s", names=[
                    "name",
                    ])
            logger.debug("dispatching", object=self, func="Name", args=args)
            self.onName(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="ts", names=[
                    "mask",
                    "interface",
                    ])
            logger.debug("dispatching", object=self, func="Capability", args=args)
            self.onCapability(context, **args)
        elif opcode == 3:
            consumed, args = self.unpack(data, signature="", names=[
                    ])
            logger.debug("dispatching", object=self, func="Done", args=args)
            self.onDone(context, **args)
        elif opcode == 4:
            consumed, args = self.unpack(data, signature="nu", names=[
                    "device",
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="Device", args=args)
            self.onDevice(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "name",
            2: "capability",
            3: "done",
            4: "device",
        }
        outgoing = {
            0: "release",
            1: "bind",
        }
        return cls(object_id=object_id, version=version, name="ei_seat", incoming=incoming, outgoing=outgoing)


@dataclass
class EiDevice(Interface):
    class EiDeviceType(IntEnum):
        VIRTUAL = 1
        PHYSICAL = 2


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_device.release", args={}, result=hexlify(data))
        return data

    def StartEmulating(self, last_serial: u, sequence: u) -> bytes:
        data = self.format(last_serial, sequence, opcode=1, signature="uu")
        logger.debug("composing message", oject=self, func="ei_device.start_emulating", args={"last_serial": last_serial, "sequence": sequence, }, result=hexlify(data))
        return data

    def StopEmulating(self, last_serial: u) -> bytes:
        data = self.format(last_serial, opcode=2, signature="u")
        logger.debug("composing message", oject=self, func="ei_device.stop_emulating", args={"last_serial": last_serial, }, result=hexlify(data))
        return data

    def Frame(self, last_serial: u, timestamp: t) -> bytes:
        data = self.format(last_serial, timestamp, opcode=3, signature="ut")
        logger.debug("composing message", oject=self, func="ei_device.frame", args={"last_serial": last_serial, "timestamp": timestamp, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onName(self, context: Context, name: s):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Name", None)
        if cb is not None:
            if new_objects:
                cb(self, name, new_objects=new_objects)
            else:
                cb(self, name)

        m = MethodCall(name="Name", args={
            "name": name,
            }, objects=new_objects)
        self.calllog.append(m)


    def onDeviceType(self, context: Context, device_type: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("DeviceType", None)
        if cb is not None:
            if new_objects:
                cb(self, device_type, new_objects=new_objects)
            else:
                cb(self, device_type)

        m = MethodCall(name="DeviceType", args={
            "device_type": device_type,
            }, objects=new_objects)
        self.calllog.append(m)


    def onDimensions(self, context: Context, width: u, height: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Dimensions", None)
        if cb is not None:
            if new_objects:
                cb(self, width, height, new_objects=new_objects)
            else:
                cb(self, width, height)

        m = MethodCall(name="Dimensions", args={
            "width": width,
            "height": height,
            }, objects=new_objects)
        self.calllog.append(m)


    def onRegion(self, context: Context, offset_x: u, offset_y: u, width: u, hight: u, scale: f):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Region", None)
        if cb is not None:
            if new_objects:
                cb(self, offset_x, offset_y, width, hight, scale, new_objects=new_objects)
            else:
                cb(self, offset_x, offset_y, width, hight, scale)

        m = MethodCall(name="Region", args={
            "offset_x": offset_x,
            "offset_y": offset_y,
            "width": width,
            "hight": hight,
            "scale": scale,
            }, objects=new_objects)
        self.calllog.append(m)


    def onInterface(self, context: Context, object: n, interface_name: s, version: u):
        new_objects = {
            "object": Interface.lookup(interface_name).create(object, version),
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Interface", None)
        if cb is not None:
            if new_objects:
                cb(self, object, interface_name, version, new_objects=new_objects)
            else:
                cb(self, object, interface_name, version)

        m = MethodCall(name="Interface", args={
            "object": object,
            "interface_name": interface_name,
            "version": version,
            }, objects=new_objects)
        self.calllog.append(m)


    def onDone(self, context: Context):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Done", None)
        if cb is not None:
            if new_objects:
                cb(self, new_objects=new_objects)
            else:
                cb(self)

        m = MethodCall(name="Done", args={
            }, objects=new_objects)
        self.calllog.append(m)


    def onResumed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Resumed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Resumed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)


    def onPaused(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Paused", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Paused", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)


    def onStartEmulating(self, context: Context, serial: u, sequence: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("StartEmulating", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, sequence, new_objects=new_objects)
            else:
                cb(self, serial, sequence)

        m = MethodCall(name="StartEmulating", args={
            "serial": serial,
            "sequence": sequence,
            }, objects=new_objects)
        self.calllog.append(m)


    def onStopEmulating(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("StopEmulating", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="StopEmulating", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)


    def onFrame(self, context: Context, serial: u, timestamp: t):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Frame", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, timestamp, new_objects=new_objects)
            else:
                cb(self, serial, timestamp)

        m = MethodCall(name="Frame", args={
            "serial": serial,
            "timestamp": timestamp,
            }, objects=new_objects)
        self.calllog.append(m)


    def onRegionMappingId(self, context: Context, mapping_id: s):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("RegionMappingId", None)
        if cb is not None:
            if new_objects:
                cb(self, mapping_id, new_objects=new_objects)
            else:
                cb(self, mapping_id)

        m = MethodCall(name="RegionMappingId", args={
            "mapping_id": mapping_id,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="s", names=[
                    "name",
                    ])
            logger.debug("dispatching", object=self, func="Name", args=args)
            self.onName(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="u", names=[
                    "device_type",
                    ])
            logger.debug("dispatching", object=self, func="DeviceType", args=args)
            self.onDeviceType(context, **args)
        elif opcode == 3:
            consumed, args = self.unpack(data, signature="uu", names=[
                    "width",
                    "height",
                    ])
            logger.debug("dispatching", object=self, func="Dimensions", args=args)
            self.onDimensions(context, **args)
        elif opcode == 4:
            consumed, args = self.unpack(data, signature="uuuuf", names=[
                    "offset_x",
                    "offset_y",
                    "width",
                    "hight",
                    "scale",
                    ])
            logger.debug("dispatching", object=self, func="Region", args=args)
            self.onRegion(context, **args)
        elif opcode == 5:
            consumed, args = self.unpack(data, signature="nsu", names=[
                    "object",
                    "interface_name",
                    "version",
                    ])
            logger.debug("dispatching", object=self, func="Interface", args=args)
            self.onInterface(context, **args)
        elif opcode == 6:
            consumed, args = self.unpack(data, signature="", names=[
                    ])
            logger.debug("dispatching", object=self, func="Done", args=args)
            self.onDone(context, **args)
        elif opcode == 7:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Resumed", args=args)
            self.onResumed(context, **args)
        elif opcode == 8:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Paused", args=args)
            self.onPaused(context, **args)
        elif opcode == 9:
            consumed, args = self.unpack(data, signature="uu", names=[
                    "serial",
                    "sequence",
                    ])
            logger.debug("dispatching", object=self, func="StartEmulating", args=args)
            self.onStartEmulating(context, **args)
        elif opcode == 10:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="StopEmulating", args=args)
            self.onStopEmulating(context, **args)
        elif opcode == 11:
            consumed, args = self.unpack(data, signature="ut", names=[
                    "serial",
                    "timestamp",
                    ])
            logger.debug("dispatching", object=self, func="Frame", args=args)
            self.onFrame(context, **args)
        elif opcode == 12:
            consumed, args = self.unpack(data, signature="s", names=[
                    "mapping_id",
                    ])
            logger.debug("dispatching", object=self, func="RegionMappingId", args=args)
            self.onRegionMappingId(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "name",
            2: "device_type",
            3: "dimensions",
            4: "region",
            5: "interface",
            6: "done",
            7: "resumed",
            8: "paused",
            9: "start_emulating",
            10: "stop_emulating",
            11: "frame",
            12: "region_mapping_id",
        }
        outgoing = {
            0: "release",
            1: "start_emulating",
            2: "stop_emulating",
            3: "frame",
        }
        return cls(object_id=object_id, version=version, name="ei_device", incoming=incoming, outgoing=outgoing)


@dataclass
class EiPointer(Interface):


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_pointer.release", args={}, result=hexlify(data))
        return data

    def MotionRelative(self, x: f, y: f) -> bytes:
        data = self.format(x, y, opcode=1, signature="ff")
        logger.debug("composing message", oject=self, func="ei_pointer.motion_relative", args={"x": x, "y": y, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onMotionRelative(self, context: Context, x: f, y: f):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("MotionRelative", None)
        if cb is not None:
            if new_objects:
                cb(self, x, y, new_objects=new_objects)
            else:
                cb(self, x, y)

        m = MethodCall(name="MotionRelative", args={
            "x": x,
            "y": y,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="ff", names=[
                    "x",
                    "y",
                    ])
            logger.debug("dispatching", object=self, func="MotionRelative", args=args)
            self.onMotionRelative(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "motion_relative",
        }
        outgoing = {
            0: "release",
            1: "motion_relative",
        }
        return cls(object_id=object_id, version=version, name="ei_pointer", incoming=incoming, outgoing=outgoing)


@dataclass
class EiPointerAbsolute(Interface):


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_pointer_absolute.release", args={}, result=hexlify(data))
        return data

    def MotionAbsolute(self, x: f, y: f) -> bytes:
        data = self.format(x, y, opcode=1, signature="ff")
        logger.debug("composing message", oject=self, func="ei_pointer_absolute.motion_absolute", args={"x": x, "y": y, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onMotionAbsolute(self, context: Context, x: f, y: f):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("MotionAbsolute", None)
        if cb is not None:
            if new_objects:
                cb(self, x, y, new_objects=new_objects)
            else:
                cb(self, x, y)

        m = MethodCall(name="MotionAbsolute", args={
            "x": x,
            "y": y,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="ff", names=[
                    "x",
                    "y",
                    ])
            logger.debug("dispatching", object=self, func="MotionAbsolute", args=args)
            self.onMotionAbsolute(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "motion_absolute",
        }
        outgoing = {
            0: "release",
            1: "motion_absolute",
        }
        return cls(object_id=object_id, version=version, name="ei_pointer_absolute", incoming=incoming, outgoing=outgoing)


@dataclass
class EiScroll(Interface):


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_scroll.release", args={}, result=hexlify(data))
        return data

    def Scroll(self, x: f, y: f) -> bytes:
        data = self.format(x, y, opcode=1, signature="ff")
        logger.debug("composing message", oject=self, func="ei_scroll.scroll", args={"x": x, "y": y, }, result=hexlify(data))
        return data

    def ScrollDiscrete(self, x: i, y: i) -> bytes:
        data = self.format(x, y, opcode=2, signature="ii")
        logger.debug("composing message", oject=self, func="ei_scroll.scroll_discrete", args={"x": x, "y": y, }, result=hexlify(data))
        return data

    def ScrollStop(self, x: u, y: u, is_cancel: u) -> bytes:
        data = self.format(x, y, is_cancel, opcode=3, signature="uuu")
        logger.debug("composing message", oject=self, func="ei_scroll.scroll_stop", args={"x": x, "y": y, "is_cancel": is_cancel, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onScroll(self, context: Context, x: f, y: f):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Scroll", None)
        if cb is not None:
            if new_objects:
                cb(self, x, y, new_objects=new_objects)
            else:
                cb(self, x, y)

        m = MethodCall(name="Scroll", args={
            "x": x,
            "y": y,
            }, objects=new_objects)
        self.calllog.append(m)


    def onScrollDiscrete(self, context: Context, x: i, y: i):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("ScrollDiscrete", None)
        if cb is not None:
            if new_objects:
                cb(self, x, y, new_objects=new_objects)
            else:
                cb(self, x, y)

        m = MethodCall(name="ScrollDiscrete", args={
            "x": x,
            "y": y,
            }, objects=new_objects)
        self.calllog.append(m)


    def onScrollStop(self, context: Context, x: u, y: u, is_cancel: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("ScrollStop", None)
        if cb is not None:
            if new_objects:
                cb(self, x, y, is_cancel, new_objects=new_objects)
            else:
                cb(self, x, y, is_cancel)

        m = MethodCall(name="ScrollStop", args={
            "x": x,
            "y": y,
            "is_cancel": is_cancel,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="ff", names=[
                    "x",
                    "y",
                    ])
            logger.debug("dispatching", object=self, func="Scroll", args=args)
            self.onScroll(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="ii", names=[
                    "x",
                    "y",
                    ])
            logger.debug("dispatching", object=self, func="ScrollDiscrete", args=args)
            self.onScrollDiscrete(context, **args)
        elif opcode == 3:
            consumed, args = self.unpack(data, signature="uuu", names=[
                    "x",
                    "y",
                    "is_cancel",
                    ])
            logger.debug("dispatching", object=self, func="ScrollStop", args=args)
            self.onScrollStop(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "scroll",
            2: "scroll_discrete",
            3: "scroll_stop",
        }
        outgoing = {
            0: "release",
            1: "scroll",
            2: "scroll_discrete",
            3: "scroll_stop",
        }
        return cls(object_id=object_id, version=version, name="ei_scroll", incoming=incoming, outgoing=outgoing)


@dataclass
class EiButton(Interface):
    class EiButtonState(IntEnum):
        RELEASED = 0
        PRESS = 1


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_button.release", args={}, result=hexlify(data))
        return data

    def Button(self, button: u, state: u) -> bytes:
        data = self.format(button, state, opcode=1, signature="uu")
        logger.debug("composing message", oject=self, func="ei_button.button", args={"button": button, "state": state, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onButton(self, context: Context, button: u, state: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Button", None)
        if cb is not None:
            if new_objects:
                cb(self, button, state, new_objects=new_objects)
            else:
                cb(self, button, state)

        m = MethodCall(name="Button", args={
            "button": button,
            "state": state,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="uu", names=[
                    "button",
                    "state",
                    ])
            logger.debug("dispatching", object=self, func="Button", args=args)
            self.onButton(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "button",
        }
        outgoing = {
            0: "release",
            1: "button",
        }
        return cls(object_id=object_id, version=version, name="ei_button", incoming=incoming, outgoing=outgoing)


@dataclass
class EiKeyboard(Interface):
    class EiKeyState(IntEnum):
        RELEASED = 0
        PRESS = 1
    class EiKeymapType(IntEnum):
        XKB = 1


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_keyboard.release", args={}, result=hexlify(data))
        return data

    def Key(self, key: u, state: u) -> bytes:
        data = self.format(key, state, opcode=1, signature="uu")
        logger.debug("composing message", oject=self, func="ei_keyboard.key", args={"key": key, "state": state, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onKeymap(self, context: Context, keymap_type: u, size: u, keymap: h):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Keymap", None)
        if cb is not None:
            if new_objects:
                cb(self, keymap_type, size, keymap, new_objects=new_objects)
            else:
                cb(self, keymap_type, size, keymap)

        m = MethodCall(name="Keymap", args={
            "keymap_type": keymap_type,
            "size": size,
            "keymap": keymap,
            }, objects=new_objects)
        self.calllog.append(m)


    def onKey(self, context: Context, key: u, state: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Key", None)
        if cb is not None:
            if new_objects:
                cb(self, key, state, new_objects=new_objects)
            else:
                cb(self, key, state)

        m = MethodCall(name="Key", args={
            "key": key,
            "state": state,
            }, objects=new_objects)
        self.calllog.append(m)


    def onModifiers(self, context: Context, serial: u, depressed: u, locked: u, latched: u, group: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Modifiers", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, depressed, locked, latched, group, new_objects=new_objects)
            else:
                cb(self, serial, depressed, locked, latched, group)

        m = MethodCall(name="Modifiers", args={
            "serial": serial,
            "depressed": depressed,
            "locked": locked,
            "latched": latched,
            "group": group,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="uuh", names=[
                    "keymap_type",
                    "size",
                    "keymap",
                    ])
            logger.debug("dispatching", object=self, func="Keymap", args=args)
            self.onKeymap(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="uu", names=[
                    "key",
                    "state",
                    ])
            logger.debug("dispatching", object=self, func="Key", args=args)
            self.onKey(context, **args)
        elif opcode == 3:
            consumed, args = self.unpack(data, signature="uuuuu", names=[
                    "serial",
                    "depressed",
                    "locked",
                    "latched",
                    "group",
                    ])
            logger.debug("dispatching", object=self, func="Modifiers", args=args)
            self.onModifiers(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "keymap",
            2: "key",
            3: "modifiers",
        }
        outgoing = {
            0: "release",
            1: "key",
        }
        return cls(object_id=object_id, version=version, name="ei_keyboard", incoming=incoming, outgoing=outgoing)


@dataclass
class EiTouchscreen(Interface):


    def Release(self) -> bytes:
        data = self.format(opcode=0, signature="")
        logger.debug("composing message", oject=self, func="ei_touchscreen.release", args={}, result=hexlify(data))
        return data

    def Down(self, touchid: u, x: f, y: f) -> bytes:
        data = self.format(touchid, x, y, opcode=1, signature="uff")
        logger.debug("composing message", oject=self, func="ei_touchscreen.down", args={"touchid": touchid, "x": x, "y": y, }, result=hexlify(data))
        return data

    def Motion(self, touchid: u, x: f, y: f) -> bytes:
        data = self.format(touchid, x, y, opcode=2, signature="uff")
        logger.debug("composing message", oject=self, func="ei_touchscreen.motion", args={"touchid": touchid, "x": x, "y": y, }, result=hexlify(data))
        return data

    def Up(self, touchid: u) -> bytes:
        data = self.format(touchid, opcode=3, signature="u")
        logger.debug("composing message", oject=self, func="ei_touchscreen.up", args={"touchid": touchid, }, result=hexlify(data))
        return data

    def Cancel(self, touchid: u) -> bytes:
        data = self.format(touchid, opcode=4, signature="u")
        logger.debug("composing message", oject=self, func="ei_touchscreen.cancel", args={"touchid": touchid, }, result=hexlify(data))
        return data

    def onDestroyed(self, context: Context, serial: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Destroyed", None)
        if cb is not None:
            if new_objects:
                cb(self, serial, new_objects=new_objects)
            else:
                cb(self, serial)

        m = MethodCall(name="Destroyed", args={
            "serial": serial,
            }, objects=new_objects)
        self.calllog.append(m)

        context.unregister(self)

    def onDown(self, context: Context, touchid: u, x: f, y: f):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Down", None)
        if cb is not None:
            if new_objects:
                cb(self, touchid, x, y, new_objects=new_objects)
            else:
                cb(self, touchid, x, y)

        m = MethodCall(name="Down", args={
            "touchid": touchid,
            "x": x,
            "y": y,
            }, objects=new_objects)
        self.calllog.append(m)


    def onMotion(self, context: Context, touchid: u, x: f, y: f):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Motion", None)
        if cb is not None:
            if new_objects:
                cb(self, touchid, x, y, new_objects=new_objects)
            else:
                cb(self, touchid, x, y)

        m = MethodCall(name="Motion", args={
            "touchid": touchid,
            "x": x,
            "y": y,
            }, objects=new_objects)
        self.calllog.append(m)


    def onUp(self, context: Context, touchid: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Up", None)
        if cb is not None:
            if new_objects:
                cb(self, touchid, new_objects=new_objects)
            else:
                cb(self, touchid)

        m = MethodCall(name="Up", args={
            "touchid": touchid,
            }, objects=new_objects)
        self.calllog.append(m)


    def onCancel(self, context: Context, touchid: u):
        new_objects = {
        }

        for o in new_objects.values():
            context.register(o)

        cb = self.callbacks.get("Cancel", None)
        if cb is not None:
            if new_objects:
                cb(self, touchid, new_objects=new_objects)
            else:
                cb(self, touchid)

        m = MethodCall(name="Cancel", args={
            "touchid": touchid,
            }, objects=new_objects)
        self.calllog.append(m)


    def dispatch(self, data: bytes, context: Context) -> int:
        header = MessageHeader.from_data(data)
        object_id, opcode = header.object_id, header.opcode
        if False:
            pass
        elif opcode == 0:
            consumed, args = self.unpack(data, signature="u", names=[
                    "serial",
                    ])
            logger.debug("dispatching", object=self, func="Destroyed", args=args)
            self.onDestroyed(context, **args)
        elif opcode == 1:
            consumed, args = self.unpack(data, signature="uff", names=[
                    "touchid",
                    "x",
                    "y",
                    ])
            logger.debug("dispatching", object=self, func="Down", args=args)
            self.onDown(context, **args)
        elif opcode == 2:
            consumed, args = self.unpack(data, signature="uff", names=[
                    "touchid",
                    "x",
                    "y",
                    ])
            logger.debug("dispatching", object=self, func="Motion", args=args)
            self.onMotion(context, **args)
        elif opcode == 3:
            consumed, args = self.unpack(data, signature="u", names=[
                    "touchid",
                    ])
            logger.debug("dispatching", object=self, func="Up", args=args)
            self.onUp(context, **args)
        elif opcode == 4:
            consumed, args = self.unpack(data, signature="u", names=[
                    "touchid",
                    ])
            logger.debug("dispatching", object=self, func="Cancel", args=args)
            self.onCancel(context, **args)
        else:
            raise NotImplementedError(f"Invalid opcode {opcode}")

        return consumed

    @classmethod
    def create(cls, object_id: int, version: int):
        incoming = {
            0: "destroyed",
            1: "down",
            2: "motion",
            3: "up",
            4: "cancel",
        }
        outgoing = {
            0: "release",
            1: "down",
            2: "motion",
            3: "up",
            4: "cancel",
        }
        return cls(object_id=object_id, version=version, name="ei_touchscreen", incoming=incoming, outgoing=outgoing)


