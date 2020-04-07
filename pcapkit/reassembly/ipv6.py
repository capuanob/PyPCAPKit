# -*- coding: utf-8 -*-
"""IPv6 fragments reassembly

:mod:`pcapkit.reassembly.ipv6` contains
:class:`~pcapkit.reassembly.ipv6.IPv6_Reassembly`
only, which reconstructs fragmented IPv6 packets back to
origin. The following algorithm implement is based on IP
reassembly procedure introduced in :rfc:`791`, using
``RCVBT`` (fragment receivedbit table). Though another
algorithm is explained in :rfc:`815`, replacing ``RCVBT``,
however, this implement still used the elder one.

Notations::

    FO    - Fragment Offset
    IHL   - Internet Header Length
    MF    - More Fragments Flag
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
from pcapkit.reassembly.ip import IP_Reassembly


__all__ = ['IPv6_Reassembly']


class IPv6_Reassembly(IP_Reassembly):
    """Reassembly for IPv6 payload.

    Example:
        >>> from pcapkit.reassembly import IPv6_Reassembly
        # Initialise instance:
        >>> ipv6_reassembly = IPv6_Reassembly()
        # Call reassembly:
        >>> ipv6_reassembly(packet_dict)
        # Fetch result:
        >>> result = ipv6_reassembly.datagram

    Attributes:
        name (str): protocol of current packet
        count (int): total number of reassembled packets
        datagram (tuple): reassembled datagram, which structure may vary
            according to its protocol
        protocol (str): protocol of current reassembly object

        _strflg (bool): strict mode flag
        _buffer (dict): buffer field
        _dtgram (tuple): reassembled datagram

    Methods:
        reassembly: perform the reassembly procedure
        submit: submit reassembled payload
        fetch: fetch datagram
        index: return datagram index
        run: run automatically

    .. glossary::

        packet
            Data structure for **IPv6 datagram reassembly**
            (:meth:`~pcapkit.reassembly.ipv6.IPv6_Reassembly.reassembly`) is as following:

            .. productionlist:: ipv6.packet

               packet_dict = dict(
                 bufid = tuple(
                     ipv6.src,                   # source IP address
                     ipv6.dst,                   # destination IP address
                     ipv6.label,                 # label
                     ipv6_frag.next,             # next header field in IPv6 Fragment Header
                 ),
                 num = frame.number,             # original packet range number
                 fo = ipv6_frag.offset,          # fragment offset
                 ihl = ipv6.hdr_len,             # header length, only headers before IPv6-Frag
                 mf = ipv6_frag.mf,              # more fragment flag
                 tl = ipv6.len,                  # total length, header includes
                 header = ipv6.header,           # raw bytearray type header before IPv6-Frag
                 payload = ipv6.payload,         # raw bytearray type payload after IPv6-Frag
               )

        datagram
            Data structure for **reassembled IPv6 datagram** (element from
            :attr:`~pcapkit.reassembly.ipv6.IPv6_Reassembly.datagram` *tuple*)
            is as following:

            .. productionlist:: ipv6.datagram

               (tuple) datagram
                |--> (dict) data
                |     |--> 'NotImplemented' : (bool) True --> implemented
                |     |--> 'index' : (tuple) packet numbers
                |     |               |--> (int) original packet range number
                |     |--> 'packet' : (Optional[bytes]) reassembled IPv6 packet
                |--> (dict) data
                |     |--> 'NotImplemented' : (bool) False --> not implemented
                |     |--> 'index' : (tuple) packet numbers
                |     |               |--> (int) original packet range number
                |     |--> 'header' : (Optional[bytes]) IPv6 header
                |     |--> 'payload' : (Optional[tuple]) partially reassembled IPv6 payload
                |                       |--> (Optional[bytes]) IPv4 payload fragment
                |--> (dict) data ...

        buffer
            Data structure for internal buffering when performing reassembly algorithms
            (:attr:`~pcapkit.reassembly.ipv6.IPv6_Reassembly._buffer`) is as following:

            .. productionlist:: ipv6.buffer

               (dict) buffer --> memory buffer for reassembly
                |--> (tuple) BUFID : (dict)
                |     |--> ipv6.src       |
                |     |--> ipc6.dst       |
                |     |--> ipv6.label     |
                |     |--> ipv6_frag.next |
                |                         |--> 'TDL' : (int) total data length
                |                         |--> RCVBT : (bytearray) fragment received bit table
                |                         |             |--> (bytes) b\x00' not received
                |                         |             |--> (bytes) b\x01' received
                |                         |             |--> (bytes) ...
                |                         |--> 'index' : (list) list of reassembled packets
                |                         |               |--> (int) packet range number
                |                         |--> 'header' : (bytearray) header buffer
                |                         |--> 'datagram' : (bytearray) data buffer, holes set to b'\x00'
                |--> (tuple) BUFID ...

    """
    ##########################################################################
    # Properties.
    ##########################################################################

    @property
    def name(self):
        """Protocol of current packet."""
        return 'Internet Protocol version 6'

    @property
    def protocol(self):
        """Protocol of current reassembly object."""
        return 'IPv6'
