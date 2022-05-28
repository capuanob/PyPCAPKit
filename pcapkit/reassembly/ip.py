# -*- coding: utf-8 -*-
"""IP fragments reassembly

:mod:`pcapkit.reassembly.ipv4` contains
:class:`~pcapkit.reassembly.ipv4.IP_Reassembly`
only, which reconstructs fragmented IP packets back to
origin. The following algorithm implement is based on IP
reassembly procedure introduced in :rfc:`791`, using
``RCVBT`` (fragment receivedbit table). Though another
algorithm is explained in :rfc:`815`, replacing ``RCVBT``,
however, this implement still used the elder one.

Notations::

    FO    - Fragment Offset
    IHL   - Internet Header Length
    MF    - More Fragments flag
    TTL   - Time To Live
    NFB   - Number of Fragment Blocks
    TL    - Total Length
    TDL   - Total Data Length
    BUFID - Buffer Identifier
    RCVBT - Fragment Received Bit Table
    TLB   - Timer Lower Bound

Algorithm::

    DO {
        BUFID <- source|destination|protocol|identification;

        IF (FO = 0 AND MF = 0) {
            IF (buffer with BUFID is allocated) {
                flush all reassembly for this BUFID;
                Submit datagram to next step;
                DONE.
            }
        }

        IF (no buffer with BUFID is allocated) {
            allocate reassembly resources with BUFID;
            TIMER <- TLB;
            TDL <- 0;
            put data from fragment into data buffer with BUFID
                [from octet FO*8 to octet (TL-(IHL*4))+FO*8];
            set RCVBT bits [from FO to FO+((TL-(IHL*4)+7)/8)];
        }

        IF (MF = 0) {
            TDL <- TL-(IHL*4)+(FO*8)
        }

        IF (FO = 0) {
            put header in header buffer
        }

        IF (TDL # 0 AND all RCVBT bits [from 0 to (TDL+7)/8] are set) {
            TL <- TDL+(IHL*4)
            Submit datagram to next step;
            free all reassembly resources for this BUFID;
            DONE.
        }

        TIMER <- MAX(TIMER,TTL);

    } give up until (next fragment or timer expires);

    timer expires: {
        flush all reassembly with this BUFID;
        DONE.
    }

"""
from typing import TYPE_CHECKING, Generic, TypeVar

from pcapkit.corekit.infoclass import Info
from pcapkit.reassembly.reassembly import Reassembly

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address
    from typing import overload

    from typing_extensions import Literal

    from pcapkit.const.reg.ethertype import EtherType

__all__ = ['IP_Reassembly']

AT = TypeVar('AT', 'IPv4Address', 'IPv6Address')

###############################################################################
# Data Models
###############################################################################


class Packet(Info, Generic[AT]):
    """Data model for :term:`ipv4.packet` / :term:`ipv6.packet`."""

    #: Buffer ID.
    bufid: 'tuple[AT, AT, int, EtherType]'
    #: Original packet range number.
    num: 'int'
    #: Fragment offset.
    fo: 'int'
    #: Internet header length.
    ihl: 'int'
    #: More fragments flag.
    mf: 'bool'
    #: Total length, header includes.
    tl: 'int'
    #: Raw :obj:`bytes`  type header.
    header: 'bytes'
    #: Raw :obj:`bytearray` type payload.
    payload: 'bytearray'

    if TYPE_CHECKING:
        def __init__(self, bufid: 'tuple[AT, AT, int, EtherType]', num: 'int', fo: 'int', ihl: 'int', mf: 'bool', tl: 'int', header: 'bytes', payload: 'bytearray') -> 'None': ...  # pylint: disable=unused-argument, super-init-not-called, multiple-statements


class DatagramID(Info, Generic[AT]):
    """Data model for :term:`ipv4.datagram` / :term:`ipv6.datagram` original packet identifier."""

    #: Source address.
    src: 'AT'
    #: Destination address.
    dst: 'AT'
    #: IP protocol identifier.
    id: 'int'
    #: Payload protocol type.
    proto: 'EtherType'

    if TYPE_CHECKING:
        def __init__(self, src: 'AT', dst: 'AT', id: 'int', proto: 'EtherType') -> 'None': ...  # pylint: disable=unused-argument, super-init-not-called, multiple-statements


class Datagram(Info, Generic[AT]):
    """Data model for :term:`ipv4.datagram` / :term:`ipv6.datagram`."""

    #: Completed flag.
    completed: 'bool'
    #: Original packet identifier.
    id: 'DatagramID[AT]'
    #: Packet numbers.
    index: 'tuple[int, ...]'
    #: Initial IP header.
    header: 'bytes'
    #: Reassembled IP payload..
    payload: 'bytes | tuple[bytes, ...]'

    if TYPE_CHECKING:
        @overload
        def __init__(self, completed: 'Literal[True]', id: 'DatagramID[AT]', index: 'tuple[int, ...]', header: 'bytes', payload: 'bytes') -> 'None': ...# pylint: disable=unused-argument, super-init-not-called, multiple-statements

        @overload
        def __init__(self, completed: 'Literal[False]', id: 'DatagramID[AT]', index: 'tuple[int, ...]', header: 'bytes', payload: 'tuple[bytes, ...]') -> 'None': ...# pylint: disable=unused-argument, super-init-not-called, multiple-statements

        def __init__(self, completed: 'bool', id: 'DatagramID[AT]', index: 'tuple[int, ...]', header: 'bytes', payload: 'bytes | tuple[bytes, ...]') -> 'None': ...# pylint: disable=unused-argument, super-init-not-called, multiple-statements


class Buffer(Info, Generic[AT]):
    """Data model for :term:`ipv4.buffer` / :term:`ipv6.buffer`."""

    #: Total data length.
    TDL: 'int'
    #: Fragment received bit table.
    RCVBT: 'bytearray'
    #: List of reassembled packets.
    index: 'list[int]'
    #: Header buffer.
    header: 'bytes'
    #: Data buffer, holes set to ``b'\x00'``.
    datagram: 'bytearray'

    if TYPE_CHECKING:
        def __init__(self, TDL: 'int', RCVBT: 'bytearray', index: 'list[int]', header: 'bytes', datagram: 'bytearray') -> 'None': ...  # pylint: disable=unused-argument, super-init-not-called, multiple-statements


###############################################################################
# Algorithm Implementation
###############################################################################


class IP_Reassembly(Reassembly[Packet[AT], Datagram[AT], tuple[AT, AT, 'int', 'EtherType'], Buffer[AT]], Generic[AT]):  # pylint: disable=abstract-method
    """Reassembly for IP payload."""

    ##########################################################################
    # Methods.
    ##########################################################################

    def reassembly(self, info: 'Packet[AT]') -> 'None':
        """Reassembly procedure.

        Arguments:
            info: info dict of packets to be reassembled

        """
        BUFID = info.bufid  # Buffer Identifier
        FO = info.fo        # Fragment Offset
        IHL = info.ihl      # Internet Header Length
        MF = info.mf        # More Fragments flag
        TL = info.tl        # Total Length

        # when non-fragmented (possibly discarded) packet received
        if not FO and not MF:
            if BUFID in self._buffer:
                self._dtgram.extend(
                    self.submit(self._buffer.pop(BUFID), bufid=BUFID)
                )
                return

        # initialise buffer with BUFID
        if BUFID not in self._buffer:
            self._buffer[BUFID] = Buffer(
                TDL=0,                              # Total Data Length
                RCVBT=bytearray(8191),              # Fragment Received Bit Table
                index=[],                           # index record
                header=b'' if FO else info.header,  # header buffer
                datagram=bytearray(65535),          # data buffer
            )
        else:
            # put header into header buffer
            if not FO:
                self._buffer[BUFID].__update__(header=info.header)

        # append packet index
        self._buffer[BUFID].index.append(info.num)

        # put data into data buffer
        start = FO
        stop = TL - IHL + FO
        self._buffer[BUFID].datagram[start:stop] = info.payload

        # set RCVBT bits (in 8 octets)
        start = FO // 8
        stop = FO // 8 + (TL - IHL + 7) // 8
        self._buffer[BUFID].RCVBT[start:stop] = b'\x01' * (stop - start + 1)

        # get total data length (header excludes)
        if not MF:
            TDL = TL - IHL + FO

        # when datagram is reassembled in whole
        start = 0
        stop = (TDL + 7) // 8
        if TDL and all(self._buffer[BUFID].RCVBT[start:stop]):
            self._dtgram.extend(
                self.submit(self._buffer.pop(BUFID), bufid=BUFID, checked=True)
            )

    def submit(self, buf: 'Buffer[AT]', *, bufid: 'tuple[AT, AT, int, EtherType]', checked: 'bool' = False) -> 'list[Datagram[AT]]':  # type: ignore[override] # pylint: disable=arguments-differ
        """Submit reassembled payload.

        Arguments:
            buf: buffer dict of reassembled packets

        Keyword Arguments:
            bufid: buffer identifier
            checked: buffer consistency checked flag

        Returns:
            Reassembled packets.

        """
        TDL = buf.TDL
        RCVBT = buf.RCVBT
        index = buf.index
        header = buf.header
        datagram = buf.datagram

        start = 0
        stop = (TDL + 7) // 8
        flag = checked or (TDL and all(RCVBT[start:stop]))
        # if datagram is not implemented
        if not flag and self._strflg:
            data = []  # type: list[bytes]
            byte = bytearray()
            # extract received payload
            for (bctr, bit) in enumerate(RCVBT):
                if bit:     # received bit
                    this = bctr * 8
                    that = this + 8
                    byte += datagram[this:that]
                else:       # missing bit
                    if byte:    # strip empty payload
                        data.append(bytes(byte))
                    byte = bytearray()
            # strip empty packets
            if data or header:
                packet = Datagram(
                    completed=False,
                    id=DatagramID(
                        src=bufid[0],
                        dst=bufid[1],
                        id=bufid[2],
                        proto=bufid[3],
                    ),
                    index=tuple(index),
                    header=header,
                    payload=tuple(data),
                )
        # if datagram is reassembled in whole
        else:
            payload = datagram[:TDL]
            packet = Datagram(  # type: ignore[call-overload]
                completed=True,
                id=DatagramID(
                    src=bufid[0],
                    dst=bufid[1],
                    id=bufid[2],
                    proto=bufid[3],
                ),
                index=tuple(index),
                header=header,
                packet=bytes(payload),
            )
        return [packet]
