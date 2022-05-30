# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""decorator functions

:mod:`pcapkit.utilities.decorators` contains several useful
decorators, including :func:`~pcapkit.utilities.decorators.seekset`
and :func:`~pcapkit.utilities.decorators.beholder`.

"""
import functools
import io
import os
import traceback
from typing import TYPE_CHECKING, cast

from pcapkit.utilities.logging import logger

if TYPE_CHECKING:
    from typing import Callable, TypeVar, Optional
    from pcapkit.protocols.protocol import Protocol

    from typing_extensions import ParamSpec, Concatenate

    P = ParamSpec('P')
    R = TypeVar('R')

__all__ = ['seekset', 'beholder']


def seekset(func: 'Callable[Concatenate[Protocol, P], R]') -> 'Callable[P, R]':
    """Read file from start then set back to original.

    Important:
        This decorator function is designed for decorating *class methods*.

    The decorator will keep the current offset of :attr:`self._file`, then
    call the decorated function. Afterwards, it will rewind the  offset of
    :attr:`self._file` to the original and returns the return value from
    the decorated function.

    Note:
        The decorated function should have following signature::

            func(self, *args, **kw)

    See Also:
        :meth:`pcapkit.protocols.protocol.Protocol._read_packet`

    :meta decorator:
    """
    @functools.wraps(func)
    def seekcur(*args: 'P.args', **kw: 'P.kwargs') -> 'R':
        # extract self object
        self = cast('Protocol', args[0])

        # move file pointer
        seek_cur = self._file.tell()
        self._file.seek(self._seekset, os.SEEK_SET)

        # call method
        return_ = func(*args, **kw)

        # reset file pointer
        self._file.seek(seek_cur, os.SEEK_SET)
        return return_
    return seekcur


def beholder(func: 'Callable[Concatenate[Protocol, int, Optional[int], P], R]') -> 'Callable[P, R]':
    """Behold extraction procedure.

    Important:
        This decorator function is designed for decorating *class methods*.

    This decorate first keep the current offset of
    :attr:`self._file <pcapkit.protocols.protocol.Protocol._file>`, then
    try to call the decorated function. Should any exception raised, it will
    re-parse the :attr:`self._file <pcapkit.protocols.protocol.Protocol._file>`
    as :class:`~pcapkit.protocols.misc.raw.Raw` protocol.

    Note:
        The decorated function should have following signature::

            func(self, proto, length, *args, **kwargs)

    See Also:
        :meth:`pcapkit.protocols.protocol.Protocol._decode_next_layer`

    :meta decorator:
    """
    @functools.wraps(func)
    def behold(*args: 'P.args', **kwargs: 'P.kwargs') -> 'R':
        # extract self object & args
        self = cast('Protocol', args[0])
        length = cast('int', args[2])

        # record file pointer
        seek_cur = self._file.tell()
        try:
            # call method
            return func(*args, **kwargs)
        except Exception as exc:
            from pcapkit.protocols.misc.raw import Raw  # pylint: disable=import-outside-toplevel
            error = traceback.format_exc(limit=1).strip().rsplit(os.linesep, maxsplit=1)[-1]
            # error = traceback.format_exc()

            # log error
            logger.error(error, exc_info=exc)

            self._file.seek(seek_cur, os.SEEK_SET)
            next_ = Raw(io.BytesIO(self._read_fileng(length)), length, error=error)
            return cast('R', next_)
    return behold
