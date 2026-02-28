import os
import pprint
import importlib
import pathlib
import socket
import structlog
import logging
from functools import reduce


from util.libei_bindings import *


logger = structlog.get_logger()
min_log_level = logging.INFO  # change for debugging eis
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(min_log_level))


def VERSION_V(v):
    """Noop function that helps with grepping for hardcoded version numbers"""
    return v


def time_micro():
    return int(time.time() * 1_000_000)


@dataclass
class InputClient:
    sock: socket.socket
    context: Context
    connection: Optional[EiConnection] = None
    interface_versions: dict[str, int] = field(init=False, default_factory=dict)
    seats: list[EiSeat] = field(init=False, default_factory=list)
    devices: list[EiDevice] = field(init=False, default_factory=list)
    object_ids: Generator[int, None, None] = field(
        init=False, default_factory=lambda: itertools.count(3)
    )
    _data: bytes = field(init=False, default_factory=bytes)
    pointer_absolute: Optional[EiPointerAbsolute] = None
    button: Optional[EiButton] = None
    keyboard: Optional[EiKeyboard] = None

    def connect(self):
        # drain any messages
        self.dispatch()

        # Establish our connection
        setup = self.handshake
        self.send(setup.HandshakeVersion(VERSION_V(1)))
        self.send(setup.ContextType(EiHandshake.EiContextType.SENDER))
        self.send(setup.Name("vkd3d-bench"))
        for interface in [
            InterfaceName.EI_CONNECTION,
            InterfaceName.EI_CALLBACK,
            InterfaceName.EI_DEVICE,
            InterfaceName.EI_PINGPONG,
            InterfaceName.EI_POINTER,
            InterfaceName.EI_POINTER_ABSOLUTE,
            InterfaceName.EI_KEYBOARD,
            InterfaceName.EI_SEAT,
            InterfaceName.EI_TOUCHSCREEN,
            InterfaceName.EI_SCROLL,
            InterfaceName.EI_BUTTON,
        ]:
            self.send(setup.InterfaceVersion(interface, VERSION_V(1)))

        self.send(setup.Finish())
        self.wait_for_seat()
        seat = self.seats[0]
        self.send(
            seat.Bind(
                seat.bind_mask(
                    [
                        InterfaceName.EI_POINTER,
                        InterfaceName.EI_POINTER_ABSOLUTE,
                        InterfaceName.EI_BUTTON,
                        InterfaceName.EI_SCROLL,
                    ]
                )
            )
        )
        self.wait_for_device()
        self.wait_for_pointer()
        assert self.devices[0].name == "Gamescope Virtual Input", (
            f"Unexpected device name {self.devices[0].name}"
        )
        self.dispatch()

    def disconnect(self):
        if self.connection is not None:
            logger.info("disconnecting")
            self.send(self.devices[0].Release())
            self.send(self.seats[0].Release())
            self.send(self.connection.Disconnect())
            self.dispatch()

    def pointer_motion_absolute(self, x: f, y: f):
        assert self.pointer_absolute is not None
        assert self.devices[0].ready is True
        logger.info(f"Sending abs ptr [{x}, {y}]")
        self.send(self.pointer_absolute.MotionAbsolute(x, y))
        self.send(self.devices[0].Frame(self.devices[0].serial, time_micro()))
        self.dispatch()

    # see linux/input-event-codes.h
    def mouse_button(self, butt: u, hold_time=0):
        assert self.button is not None
        assert self.devices[0].ready is True
        logger.info(f"Sending mouse button {butt}")
        self.send(self.button.Button(butt, EiButton.EiButtonState.PRESS))
        self.send(self.devices[0].Frame(self.devices[0].serial, time_micro()))
        self.dispatch()
        if hold_time > 0:
            self.sleep(hold_time)
        self.send(self.button.Button(butt, EiButton.EiButtonState.RELEASED))
        self.send(self.devices[0].Frame(self.devices[0].serial, time_micro()))
        self.dispatch()

    # see linux/input-event-codes.h
    def keyboard_key(self, key: u, hold_time=0):
        assert self.keyboard is not None
        assert self.devices[0].ready is True
        logger.info(f"Sending keyboard key {key}")
        self.send(self.keyboard.Key(key, EiKeyboard.EiKeyState.PRESS))
        self.send(self.devices[0].Frame(self.devices[0].serial, time_micro()))
        self.dispatch()
        if hold_time > 0:
            self.sleep(hold_time)
        self.send(self.keyboard.Key(key, EiKeyboard.EiKeyState.RELEASED))
        self.send(self.devices[0].Frame(self.devices[0].serial, time_micro()))
        self.dispatch()

    @property
    def data(self) -> bytes:
        return self._data

    def send(self, msg: bytes) -> None:
        logger.debug(f"sending {len(msg)} bytes", bytes=hexlify(msg))
        self.sock.sendmsg([msg])

    def find_objects_by_interface(self, interface: str) -> list[Interface]:
        return [o for o in self.context.objects.values() if o.name == interface]

    def callback_roundtrip(self) -> bool:
        assert self.connection is not None

        cb = EiCallback.create(next(self.object_ids), VERSION_V(1))
        self.context.register(cb)
        self.send(self.connection.Sync(cb.object_id, cb.version))

        return self.wait_for(
            lambda: cb not in self.find_objects_by_interface(InterfaceName.EI_CALLBACK)
        )

    @property
    def handshake(self) -> EiHandshake:
        setup = self.context.objects[0]
        assert isinstance(setup, EiHandshake)
        return setup

    def wait_for_seat(self, timeout=2) -> bool:
        def seat_is_done():
            return self.seats and [
                call for call in self.seats[0].calllog if call.name == "Done"
            ]

        return self.wait_for(seat_is_done, timeout)

    def wait_for_device(self, timeout=2) -> bool:
        def device_is_done():
            return self.devices and self.devices[0].ready is True

        return self.wait_for(device_is_done, timeout)

    def wait_for_connection(self, timeout=2) -> bool:
        return self.wait_for(lambda: self.connection is not None, timeout)

    def wait_for_pointer(self, timeout=2) -> bool:
        return self.wait_for(lambda: self.pointer_absolute is not None, timeout)

    def wait_for(self, callable, timeout=2) -> bool:
        expire = time.time() + timeout
        while not callable():
            self.dispatch()
            if time.time() > expire:
                raise "wait_for timed out"
            time.sleep(0.01)

        return True

    def seat_fill_capability_masks(self, seat: EiSeat):
        """
        Set up the seat to fill the interface masks for each Capability
        and add the bind_mask() helper function to compile a mask
        from interface names.
        """

        def seat_cap(seat, mask, intf_name):
            seat.interface_masks[intf_name] = mask

        seat.interface_masks = {}
        seat.connect("Capability", seat_cap)

        def bind_mask(interfaces: list[InterfaceName]) -> int:
            return reduce(
                lambda mask, v: mask | v,
                [seat.interface_masks[i] for i in interfaces],
                0,
            )

        seat.bind_mask = bind_mask

    def device_register(self, device: EiDevice):
        # not sure these are correct but seems to work...

        def on_resumed(device, serial):
            device.serial = serial
            # this should not be sent twice
            if device.starting is not True:
                device.starting = True
                device.sequence += 1
                self.send(device.StartEmulating(serial, device.sequence))
                self.dispatch()

        def on_start_emu(device, serial, sequence):
            device.serial = serial
            device.sequence = sequence
            device.ready = True
            device.starting = False

        def on_stop_emu(device, serial):
            device.serial = serial
            device.ready = False
            device.starting = False

        def on_name(device, name):
            device.name = name
            device.ready = True

        device.serial = None
        device.sequence = 0
        device.ready = False
        device.starting = False
        device.connect("Resumed", on_resumed)
        device.connect("StartEmulating", on_start_emu)
        device.connect("StopEmulating", on_stop_emu)
        device.connect("Name", on_name)

    # use this instead of time.sleep if need to keep socket alive
    def sleep(self, duration):
        expire = time.time() + duration
        while time.time() < expire:
            self.dispatch()

    def recv(self) -> bytes:
        try:
            data = self.sock.recv(1024)
            while data:
                self._data += data
                data = self.sock.recv(1024)
        except (BlockingIOError, ConnectionResetError):
            pass
        return self.data

    def dispatch(self, timeout=0.1) -> None:
        if not self.data:
            expire = time.time() + timeout
            while not self.recv():
                now = time.time()
                if now >= expire:
                    break
                time.sleep(min(0.01, expire - now))
                if now >= expire:
                    break

        while self.data:
            logger.debug("data pending dispatch: ", bytes=hexlify(self.data[:64]))
            header = MessageHeader.from_data(self.data)
            logger.debug("dispatching message: ", header=header)
            consumed = self.context.dispatch(self.data)
            if consumed == 0:
                break
            self.pop(consumed)

    def pop(self, count: int) -> None:
        self._data = self._data[count:]

    @classmethod
    def create(cls):
        runtime_dir = os.getenv("XDG_RUNTIME_DIR")
        if runtime_dir is None:
            runtime_dir = "/run/user/1000"
            logger.warn(f"XDG_RUNTIME_DIR unset, assume {runtime_dir}")
        runtime_dir = os.path.abspath(runtime_dir)

        socket_path = os.getenv("LIBEI_SOCKET")
        if socket_path is None:
            socket_path = "gamescope-0-ei"
            logger.warn(f"LIBEI_SOCKET unset, assume {socket_path}")
        socket_path = os.path.join(runtime_dir, socket_path)

        logger.info(f"waiting for {socket_path}")
        while not os.path.exists(socket_path):
            time.sleep(1)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_NONBLOCK)

        logger.info(f"connecting to {socket_path}")
        for _ in range(3):
            try:
                sock.connect(socket_path)
                break
            except ConnectionRefusedError:
                time.sleep(1)
        else:
            raise "Failed to connect to EIS"

        ctx = Context.create()
        ei = cls(sock=sock, context=ctx)

        # callback for new objects
        def register_cb(interface: Interface) -> None:
            logger.debug(interface)
            if isinstance(interface, EiConnection):
                assert ei.connection is None
                ei.connection = interface

                # Automatic ping/pong handler
                def ping(conn, id, version, new_objects={}):
                    pingpong = new_objects["ping"]
                    try:
                        ei.send(pingpong.Done(0))
                    except BrokenPipeError:
                        pass

                ei.connection.connect("Ping", ping)

            elif isinstance(interface, EiSeat):
                assert interface not in ei.seats

                seat = interface
                ei.seat_fill_capability_masks(seat)
                ei.seats.append(seat)

            elif isinstance(interface, EiDevice):
                assert interface not in ei.devices
                ei.device_register(interface)
                ei.devices.append(interface)

            elif isinstance(interface, EiPointerAbsolute):
                ei.pointer_absolute = interface

            elif isinstance(interface, EiButton):
                ei.button = interface

            elif isinstance(interface, EiKeyboard):
                ei.keyboard = interface

        def unregister_cb(interface: Interface) -> None:
            if interface == ei.connection:
                assert ei.connection is not None
                ei.connection = None
            elif interface in ei.seats:
                ei.seats.remove(interface)
            elif interface in ei.devices:
                ei.devices.remove(interface)
            elif interface == ei.pointer_absolute:
                ei.pointer_absolute = None
            elif interface == ei.button:
                ei.button = None
            elif interface == ei.keyboard:
                ei.keyboard = None

        ctx.connect("register", register_cb)
        ctx.connect("unregister", unregister_cb)

        return ei
