"""Simplify the connection to DS9 using SAMP.

This is a simplified interface to talking to DS9 with SAMP, and
assumes certain things, such as:

- a SAMP hub is running,
- the DS9 instance remains connected to it while the module is run,
- there is only one DS9 instance to talk to,
- connections with other SAMP capable clients is not needed,
- and commands are to be executed synchronously (i.e. each command is
  executed and acknowledged by DS9 before the next command is processed).

For more complex cases see the `DS9 SAMP documentation <https://sites.google.com/cfa.harvard.edu/saoimageds9/ds9-astropy>`_
and the `AstroPy SAMP module
<https://docs.astropy.org/en/stable/samp/>`_.

Please note that SAMP is not designed as a secure connection system,
and this module assumes that if a SAMP client supports ds9.set and
ds9.get methods then it is DS9 (or a valid DS9 emulator).

Simple usage
------------

The ds9samp.ds9samp routine is used to create a object that can control
the DS9 instance:

    import ds9samp
    with ds9samp.ds9samp() as ds9:
        ds9.set("frame delete all")
        ds9.set("url http://ds9.si.edu/download/data/img.fits")
        ds9.set("zscale")
        ds9.set("cmap viridis")

The get method will return a value (as a string, FITS HDUList, NumPy
array, or None if there is no response).

Syntax errors are displayed as a screen message (to stdout) but they
do not stop the connection. Lower-level errors - such as the DS9
instance being closed - will raise an error and this will exit the
context manager, and so the connection will be closed.

Direct access
-------------

The `ds9samp.start` routine will return an object that the user is
required to close, via `ds9samp.end`. The previous example can be
written as:

    import ds9samp
    ds9 = ds9samp.start()
    try:
        ds9.set("frame delete all")
        ds9.set("url http://ds9.si.edu/download/data/img.fits")
        ds9.set("zscale")
        ds9.set("cmap viridis")
    finally:
        ds9.end()

Sending images directly
-----------------------

It is possible to send DS9 the contents of a NumPy array directly
by using the `NumPy memmap
<https://numpy.org/doc/stable/reference/generated/numpy.memmap.html>`_
call to create a temporary file. This has been automated with the
`send_array` call. For example:

    import numpy as np
    import ds9samp
    # Create a rotated elliptical gaussian
    x0 = 2200
    x1 = 3510
    theta = 1.2
    ellip = 0.4
    fwhm = 400
    x1s, x0s = np.mgrid[3000:4001, 2000:2501]
    dx0 = (x0s - x0) * np.cos(theta) + (x1s - x1) * np.sin(theta)
    dx1 = (x1s - x1) * np.cos(theta) - (x0s - x0) * np.sin(theta)
    r2 = ((dx0 * (1 - ellip))**2  + dx1**2) / (fwhm * (1 - ellip))**2
    img = np.exp(-4 * np.log(2) * r2)
    # Send it to DS9
    with ds9samp.ds9samp() as ds9:
        ds9.send_array(img)
        ds9.set("cmap viridis")

For more complex cases the creation of the memmap-ed file should be
done manually, as described in the `DS9 example
<https://sites.google.com/cfa.harvard.edu/saoimageds9/ds9-astropy>`_.

3D data
^^^^^^^

3D data can be sent and retrieved with `send_array` and
`retrieve_array`. If the data should be treated as RGB, HLS, or HSV
data - that is, the third dimension has 3 elements representing

- red, green, and blue channels
- hue, lightness, and saturation
- hue, saturation, and value

then the `send_array` should be called setting the `cube` argument to
a value from the `Cube` enumeration; that is `Cube.RGB`, `Cube.HLS`,
or `Cube.HSV`.

FITS data
^^^^^^^^^

FITS data - as represented by AstroPy `FITS objects
<https://docs.astropy.org/en/stable/io/fits/index.html>`_ - can
also be sent and retrieved, as of version 0.0.7, using the
`send_fits` and `retrieve_fits` methods.

If a table is sent, then DS9 will select what columns to bin, although
the `bin command <https://ds9.si.edu/doc/ref/samp.html#bin>`_ can be
used to control the process. Attempts to retrieve a FITS file from
such a dataset will return an image, and not the underlying table.

Catalogs
--------

As of version 0.0.8, catalogs can be sent and retrieved using the
`send_cat` and `retrieve_cat` methods. The `send_cat` method
will send an AstroPy `Table <https://docs.astropy.org/en/stable/table/index.html>`_
or a `FITS table <https://docs.astropy.org/en/stable/io/fits/index.html>`_
to DS9, and `retrieve_cat` returns a `Table`.

Timeouts
--------

The default timeout for the set and get calls is 10 seconds, and this
can be changed by either setting the timeout attribute of the
connection, or by over-riding this value for a single call with the
timeout parameter for the get and set methods. Note that the timeout
must be an integer, and 0 is used to turn off the timeout.

For get calls it is suggested to set the timeout to 0 if the command
requires user interaction, such as selecting a location.

How to connect to a particular DS9 instance
-------------------------------------------

If there are multiple DS9 instances connected to the SAMP hub then
ds9samp.ds9samp or ds9samp.start must be called with the client
argument set to select the DS9 instance to talk to.

The ds9samp.list_ds9 routine returns a list of client names to use.
Unfortunately it's not immediately obvious how to map a client name to
a particular instance. One solution is to ask DS9 to display a window
with a command like

    % ds9samp_set "analysis message og {Selected window}" --name cl3 --timeout 0

(replacing cl3 by one of the values reported by list_samp).

The following will select the first DS9 instance and return the name
of the file the selected frame is displaying:

    import ds9samp
    clients = ds9samp.list_ds9()
    with ds9samp.ds9samp(client=clients[0]) as ds9:
        print(ds9.get("file"))

"""

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import importlib.metadata
import os
from pathlib import Path
import sys
import tempfile
from typing import Protocol
from urllib.parse import urlparse

import numpy as np

from astropy import samp  # type: ignore
from astropy.io import fits  # type: ignore
from astropy.table import Table  # type: ignore


__all__ = ["Cube", "ds9samp", "list_ds9"]


VERSION = importlib.metadata.version("ds9samp")


class SupportsWriteTo(Protocol):
    """Represent objects with a writeto method.

    This is to represent astropy.io.fits objects.

    """

    # How best to mark the optional arguments?
    def writeto(
        self, fileobj, output_verify: str, overwrite: bool, checksum: bool
    ) -> None: ...


class Cube(Enum):
    """How should a 3D cube be treated by DS9."""

    RGB = 1
    "Data is stored in Red, Green, Blue order."

    HLS = 2
    "Data is stored in Hue, Lightness, Saturation order."

    HSV = 3
    "Data is stored in Hue, Saturation, Value order."


@dataclass(frozen=True)
class ImgInfo:
    """Metadata about the image."""

    dtype: np.dtype
    """The datatype."""
    shape: tuple[int, ...]
    """The size of the image. It is expected to be 2D or 3D."""


def add_color(txt):
    """Allow ANSI color escape codes unless NO_COLOR env var is set
    or sys.stderr is not a TTY.

    See https://no-color.org/

    Is it worth allowing these colors to be customized?
    """

    if not sys.stderr.isatty():
        return txt

    if os.getenv("NO_COLOR") is not None:
        return txt

    return f"\033[1;31m{txt}\033[0;0m"


def debug(msg: str) -> None:
    """Display the debug message.

    Parameters
    ----------
    msg
       The message to display

    See Also
    --------
    error, warning

    """

    # This should use the logging infrastructure but I want to see how
    # it ends up working out first.
    #
    lhs = add_color("DEBUG:")
    print(f"{lhs} {msg}")


def error(msg: str) -> None:
    """Display the error message.

    Parameters
    ----------
    msg
       The message to display

    See Also
    --------
    debug, warning

    Notes
    -----
    We could raise an error, but in loosely-coupled systems like
    DS9+SAMP we don't want to have to deal with catching exceptions,
    so we instead display a message and continue.

    """

    # This should use the logging infrastructure but I want to see how
    # it ends up working out first.
    #
    lhs = add_color("ERROR:")
    print(f"{lhs} {msg}")


def warning(msg: str) -> None:
    """Display the warning message.

    Parameters
    ----------
    msg
       The message to display

    See Also
    --------
    debug, error

    """

    # This should use the logging infrastructure but I want to see how
    # it ends up working out first.
    #
    lhs = add_color("WARNING:")
    print(f"{lhs} {msg}")


def read_array(path: str | Path, img: ImgInfo) -> np.ndarray:
    """Read in an array from a file."""

    fp = np.memmap(path, mode="r", dtype=img.dtype, shape=img.shape)
    return fp[:]


def extract_url(
    url: str, img: ImgInfo | None
) -> str | np.ndarray | fits.HDUList | None:
    """Read in the URL and return the values.

    It relies on heuristics to determine the type of the data pointed
    to by the URL. Unfortunately this is currently underspecified.

    """

    res = urlparse(url)

    # We could also check that res.netloc == "localhost" but I do
    # not know if the tcl URL stack is guaranteed to use
    # localhost, so just assume it is local.
    #
    if res.scheme != "file":
        error(f"expected file url, not {url}")
        return None

    # Look at all the DS9 samp commands at
    # https://ds9.si.edu/doc/ref/samp.html
    # that have an example of "string url = ds9.get(string cmd):
    #
    #   command     suffix     encoding
    #   -------     ------     --------
    #   array       .arr       binary
    #   data        .dat.dat   ascii
    #   pixeltable  .pix.txt   ascii
    #   region      .reg.rgn   ascii
    #
    # Not included on this page are
    #
    #   command     suffix     encoding
    #   -------     ------     --------
    #   fits        .fits      FITS
    #
    #
    if any(res.path.endswith(f".{end}") for end in ["dat", "rgn", "txt"]):
        # What's the best encoding?
        with open(res.path, mode="rt", encoding="ascii") as fh:
            return fh.read()

    if res.path.endswith(".fits"):
        return fits.open(res.path)

    if res.path.endswith(".arr"):
        if img is None:
            error("Sent array but no image data")
            return None

        return read_array(res.path, img)

    error(f"Unable to determine contents of {url}")
    return None


class Connection:
    """Store the DS9 connection.

    .. versionchanged:: 0.0.6
       Added the debug option.

    """

    def __init__(self, ds9: samp.SAMPIntegratedClient, client: str) -> None:
        self.ds9 = ds9
        self.client = client
        self.debug = False
        self.metadata = ds9.get_metadata(client)
        self.timeout = 10
        """Timeout, in seconds (must be an integer)."""

    def __str__(self) -> str:
        try:
            version = self.metadata["ds9.version"]
        except KeyError:
            version = "<unknown>"

        return f"Connection to DS9 {version} (client {self.client})"

    def get_raw(
        self, command: str, timeout: int | None = None
    ) -> dict[str, str] | None:
        """Call ds9.get for the given command and arguments.

        If the call fails then an error message is displayed (to
        stdout) and None is returned. This call will raise an error if
        there is a SAMP commmunication problem.

        .. versionadded:: 0.1.0

        Parameters
        ----------
        command
           The DS9 command to call, e.g. "cmap"
        timeout: optional
           Over-ride the default timeout setting. Use 0 to remove
           any timeout.

        Returns
        -------
        retval
           The dictionary represents the 'samp.result' field of the
           query, and may be empty. It will be None if there was an
           error with the call.

        See Also
        --------
        get

        """

        tout = self.timeout if timeout is None else timeout
        tout_str = str(int(tout))
        out = self.ds9.ecall_and_wait(
            self.client, "ds9.get", timeout=tout_str, cmd=command
        )

        if self.debug:
            # Can we display the output in a structured form?
            debug(f"ds9.get {command} timeout={tout_str}")
            debug(str(out))

        status = out["samp.status"]
        if status != "samp.ok":
            evals = out["samp.error"]
            try:
                emsg = f"DS9 reported: {evals['samp.errortxt']}"
            except KeyError:
                emsg = "Unknown DS9 error"

            if status == "samp.error":
                error(emsg)
                return None

            warning(emsg)

        return out["samp.result"]

    def get(
        self, command: str, timeout: int | None = None
    ) -> str | np.ndarray | fits.HDUList | None:
        """Call ds9.get for the given command and arguments.

        If the call fails then an error message is displayed (to
        stdout) and None is returned. This call will raise an error if
        there is a SAMP commmunication problem.

        .. versionchanged:: 0.0.6
           Commands that return data via a url (such as "data") will
           now return the contents of the url, rather than returning
           `None`.

        Parameters
        ----------
        command
           The DS9 command to call, e.g. "cmap"
        timeout: optional
           Over-ride the default timeout setting. Use 0 to remove
           any timeout.

        Returns
        -------
        retval
           The return value, as a string, or None if there was no
           return value.

        See Also
        --------
        get_raw, set

        """

        # The result is assumed to be one of:
        #  - the value field
        #  - the url field
        #  - otherwise we just return None
        #
        result = self.get_raw(command=command, timeout=timeout)
        if result is None:
            return None

        value = result.get("value")
        if value is not None:
            return value

        # We can probably assume that it's always a file on the
        # localhost, but add checks just in case.
        #
        url = result.get("url")
        if url is not None:
            if self.debug:
                debug(f"DS9 returned data in URL={url}")

            # In order to interpret the data from an array call
            # we need extra information. This would be easier if
            # it was sent in-band (i.e. as part of the response).
            # Are there other cases it is needed?
            #
            if command.startswith("array"):
                img = self.get_image_info(timeout=timeout)
                if img is None:
                    # Return an empty array
                    return np.zeros(0)

            else:
                img = None

            return extract_url(url, img=img)

        return None

    def get_image_info(self, timeout: int | None = None) -> ImgInfo | None:
        """Return information on the current image.

        Parameters
        ----------
        timeout: optional
           Over-ride the default timeout setting. Use 0 to remove
           any timeout.

        Returns
        -------
        img
           A structure describing the current image, or None if
           there is none.

        """

        # These values should convert, so do not try to improve the
        # error handling.
        #
        def convert(arg: str) -> int:
            result = self.get_raw(f"fits {arg}", timeout=timeout)
            if result is None:
                return 0

            value = result.get("value")
            if value is None:
                return 0

            return int(value)

        bitpix = convert("bitpix")
        nx = convert("width")
        ny = convert("height")
        nz = convert("depth")

        if nx == 0 or ny == 0:
            return None

        dtype = bitpix_to_dtype(bitpix)
        if dtype is None:
            if self.debug:
                debug(f"Unsupported BITPIX: {bitpix}")

            return None

        shape: tuple[int, ...]
        if nz > 1:
            shape = (nz, ny, nx)
        else:
            shape = (ny, nx)

        return ImgInfo(dtype, shape)

    def set(self, command: str, timeout: int | None = None) -> None:
        """Call ds9.set for the given command and arguments.

        If the call fails then an error message is displayed (to
        stdout). The assumption here is that ds9.set never returns any
        information. This call will raise an error if there is a SAMP
        commmunication problem.

        Parameters
        ----------
        command
           The DS9 command to call, e.g. "cmap viridis"
        timeout: optional
           Over-ride the default timeout setting. Use 0 to remove
           any timeout.

        See Also
        --------
        set

        """

        # Use ecall_and_wait to
        # - validate the message
        # - ensure it's been processed by DS9
        #
        # rather than sending the message and continuing before it has
        # been handled by DS9.
        #
        tout = self.timeout if timeout is None else timeout
        tout_str = str(int(tout))
        out = self.ds9.ecall_and_wait(
            self.client, "ds9.set", timeout=tout_str, cmd=command
        )

        if self.debug:
            # Can we display the output in a structured form?
            debug(f"ds9.set {command} timeout={tout_str}")
            debug(str(out))

        status = out["samp.status"]
        if status == "samp.ok":
            return

        evals = out["samp.error"]
        try:
            emsg = f"DS9 reported: {evals['samp.errortxt']}"
        except KeyError:
            emsg = "Unknown DS9 error"

        # Does DS9 support samp.warning?
        if status == "samp.warning":
            warning(emsg)
            return

        error(emsg)

    def send_array(
        self,
        img: np.ndarray,
        *,
        cube: Cube | None = None,
        mask: bool = False,
        timeout: int | None = None,
    ) -> None:
        """Send the array to DS9.

        This creates a temporary file to store the data,
        sends the data, and then deletes the file.

        .. versionchanged:: 0.0.6
           3D arrays can now be sent and the cube argument used to
           select what mode 3D data is interpreted as.

        .. versionchanged:: 0.0.5
           A DS9 frame will be created if needed. The mask argument
           has been added and optional arguments are now keyword-only
           arguments.

        .. versionadded:: 0.0.3

        Parameters
        ----------
        img:
           The 2D or 3D data to send.
        cube: optional
           If 3D data is sent in, should it be treated as RGB, HLS,
           or HSV format. Leave as None to treat as a generic cube.
        mask: optional
           Should the array be treated as a mask?
        timeout: optional
           The timeout, in seconds. If not set then use the
           default timeout value.

        See Also
        --------
        send_fits, retrieve_array

        Notes
        -----

        DS9 has limited support for all the varied number types, such
        as complex numbers or unsigned integers, so the code may
        either error out or choose a lossy conversion (e.g. unsigned
        to signed integers of the same size).

        This call provides access to the:

        - `array <https://ds9.si.edu/doc/ref/samp.html#array>`_,
        - `hlsarray <https://ds9.si.edu/doc/ref/samp.html#hlsarray>`_,
        - `hsvarray <https://ds9.si.edu/doc/ref/samp.html#hsvarray>`_,
        - and `rgbarray <https://ds9.si.edu/doc/ref/samp.html#rgbarray>`_

        commands.

        Examples
        --------

        Create an image of random values for a grid 500 pixels wide and
        200 pixels tall:

        >>> ds9 = ds9samp.start()
        >>> ivals = np.random.randn(200, 500)
        >>> ds9.send_array(ivals)
        >>> ds9samp.end(ds9)

        Send in a cube, change the scaling so that the full array
        range is shown, loop through the slices, and then stop and
        move to the first slice:

        >>> cube = np.arange(5 * 20 * 30).reshape(5, 30, 20)
        >>> minval = cube.min()
        >>> maxval = cube.max()
        >>> ds9.send_array(cube)
        >>> ds9.set(f"scale limits {minval} {maxval}")
        >>> ds9.set("cube play")
        >>> ds9.set("cube stop")
        >>> ds9.set("cube 1")

        """

        # Map between NumPy and DS9 storage fields.
        #
        # Hack in support for bool values
        if img.dtype.type == np.bool_:
            img = img.astype("int8")

        arr = np_to_array(img)

        # Validate the cube argument when given.
        #
        action = ""
        if cube is not None:
            if img.ndim != 3:
                raise ValueError("data must be 3D to set the cube argument")
            if img.shape[0] != 3:
                raise ValueError(
                    "z axis must have size 3 when cube argument is set"
                )

            match cube:
                case Cube.RGB:
                    action = "rgb"
                case Cube.HLS:
                    action = "hls"
                case Cube.HSV:
                    action = "hsv"

                case _:
                    raise ValueError(f"Invalid argument: cube={cube}")

        # Create a frame if necessary, since otherwise the ARRAY call
        # will fail.
        #
        if self.get("frame active") is None:
            self.set("frame new")

        with tempfile.NamedTemporaryFile(prefix="ds9samp", suffix=".arr") as fh:
            fp = np.memmap(fh, mode="w+", dtype=img.dtype, shape=img.shape)
            fp[:] = img
            fp.flush()

            # If given a RGB/HLS/HSV cube then create a frame. We
            # could try and check if we have one already, but it's not
            # clear how to do this, so always create it. If a user
            # wants to re-use the frame then they can try and do this
            # manually (probably by creating a FITS file and loading
            # that?).
            #
            if action != "":
                self.set(action, timeout=timeout)

            # Should this over-ride the filename as it is going to be
            # invalid as soon as this call ends? I am not sure that it
            # is possible.
            #
            cmd = f"{action}array "
            if mask:
                cmd += "mask "
            cmd += f" {fh.name}{arr}"
            self.set(cmd, timeout=timeout)

    def retrieve_array(
        self, *, timeout: int | None = None
    ) -> np.ndarray | None:
        """Get the current frame as a NumPy array.

        .. versionchanged:: 0.0.6
           3D arrays can now be returned.

        .. versionadded:: 0.0.5

        Parameters
        ----------
        timeout: optional
           The timeout, in seconds. If not set then use the
           default timeout value.

        See Also
        --------
        send_array, retrieve_fits

        Notes
        -----

        This call provides access to the `export array
        <https://ds9.si.edu/doc/ref/samp.html#export>`_ command.

        An alternative would be to get DS9 to create a FITS file and
        then read that in.

        Examples
        --------

        Smooth a 200 pixels wide by 500 pixels image of noise,
        retrieve the smoothed values, and use them to create a mask
        layer of the most-discrepant points:

        >>> ds9 = ds9samp.start()
        >>> ivals = np.random.randn(400, 300)
        >>> ds9.send_array(ivals)
        >>> ds9.set("cmap viridis")
        >>> ds9.set("smooth function tophat")
        >>> ds9.set("smooth radius 4")
        >>> ds9.set("smooth on")
        >>> svals = ds9.retrieve_array()
        >>> ds9.set("smooth off")
        >>> mvals = np.abs(svals) > 0.7
        >>> ds9.send_array(mvals, mask=True)
        >>> ds9samp.end(ds9)

        """

        # Get the data information before creating the temporary file.
        # Do we have to worry about WCS messing around with the units?
        #
        img = self.get_image_info(timeout=timeout)
        if img is None:
            # We could return an empty array, but is it worth it?
            error("DS9 appears to contain no data")
            return None

        with tempfile.NamedTemporaryFile(prefix="ds9samp", suffix=".arr") as fh:
            cmd = f"export array {fh.name} native"
            self.set(cmd, timeout=timeout)

            out = read_array(fh.name, img)

        return out

    def send_fits(
        self,
        data: SupportsWriteTo,
        *,
        mask: bool = False,
        timeout: int | None = None,
    ) -> None:
        """Send the FITS data to DS9.

        This creates a temporary file to store the data,
        sends the data, and then deletes the file.

        .. versionadded:: 0.0.7

        Parameters
        ----------
        data:
           The data to send. It can be a HDUList or an individual FITS
           extension.
        mask: optional
           Should the data be treated as a mask?
        timeout: optional
           The timeout, in seconds. If not set then use the
           default timeout value.

        See Also
        --------
        send_array, retrieve_fits

        Notes
        -----

        This call provides access to the `fits <https://ds9.si.edu/doc/ref/samp.html#fits>`_ call.

        The behaviour of DS9 will depend on the data, such as if it is
        a 2D or 2D image, or a table that can be automatically binned
        to an image.

        Invalid or missing metadata will be automatically converted by
        AstroPy, using the `fits+warn
        <https://docs.astropy.org/en/stable/io/fits/usage/verification.html#verification-options>`_
        verification option.

        """

        # We could try and validate the input argument but it's not
        # simple to do, so skip this step for now.
        #
        with tempfile.NamedTemporaryFile(
            prefix="ds9samp", suffix=".fits"
        ) as fh:
            # Correct any metadata. If this conversion causes a
            # problem for the user then they need to manually
            # replicate this code.
            #
            data.writeto(
                fh, output_verify="fix+warn", checksum=True, overwrite=True
            )

            # Should this over-ride the filename as it is going to be
            # invalid as soon as this call ends? I am not sure that it
            # is possible.
            #
            cmd = "fits "
            if mask:
                cmd += "mask "
            cmd += f" {fh.name}"
            self.set(cmd, timeout=timeout)

    def retrieve_fits(
        self, *, timeout: int | None = None
    ) -> fits.HDUList | None:
        """Get the current frame as a FITS dataset.

        .. versionadded:: 0.0.7

        Parameters
        ----------
        timeout: optional
           The timeout, in seconds. If not set then use the
           default timeout value.

        See Also
        --------
        send_fits, retrieve_array

        Notes
        -----

        This call provides access to the `fits
        <https://ds9.si.edu/doc/ref/samp.html#fits>`_ command.

        """

        # The result is assumed to be given by the url field.
        # Any other response is an error.
        #
        result = self.get_raw(command="fits", timeout=timeout)
        if result is None:
            return None

        url = result.get("url")
        if url is None:
            error("SAMP call returned unexpected data")
            return None

        res = urlparse(url)
        if res.scheme != "file":
            error(f"expected file url, not {url}")
            return None

        if not res.path.endswith(".fits"):
            warning("expected file url to end in .fits")

        return fits.open(res.path)

    def send_cat(
        self, data: Table | SupportsWriteTo, *, timeout: int | None = None
    ) -> None:
        """Send the catalog to DS9.

        This creates a temporary file to store the data as a FITS
        file, sends the data, and then deletes the file.

        .. versionadded:: 0.0.8

        Parameters
        ----------
        data:
           The data to send. It should be an AstroPy `Table` or
           contain a FITS table.
        timeout: optional
           The timeout, in seconds. If not set then use the
           default timeout value.

        See Also
        --------
        send_fits, retrieve_cat

        Notes
        -----

        This call provides access to the `catalog import fits
        <https://ds9.si.edu/doc/ref/samp.html#cat>`_ command.

        """

        # Limited validation of the input argument.
        #
        with tempfile.NamedTemporaryFile(
            prefix="ds9samp", suffix=".fits"
        ) as fh:
            try:
                # Is this a Table?
                data.write(fh, format="fits", overwrite=True)

            except AttributeError:
                # Is this a FITS object? Add some basic validation
                # checks.
                #
                if isinstance(data, fits.PrimaryHDU):
                    raise ValueError(
                        "data must be a table, not a PrimaryHDU"
                    ) from None

                try:
                    check = [
                        isinstance(elem, (fits.PrimaryHDU, fits.ImageHDU))
                        for elem in data
                    ]
                except TypeError:
                    # Assume not iterable
                    check = [False]

                if all(check):
                    raise ValueError(
                        "data mut be a table, not image(s)"
                    ) from None

                data.writeto(
                    fh, overwrite=True, output_verify="fix+warn", checksum=True
                )

            cmd = f"catalog import fits {fh.name}"
            self.set(cmd, timeout=timeout)

    def retrieve_cat(self, *, timeout: int | None = None) -> Table | None:
        """Retrive the current catalog.

        .. versionadded:: 0.0.8

        Parameters
        ----------
        timeout: optional
           The timeout, in seconds. If not set then use the
           default timeout value.

        See Also
        --------
        send_cat, retrieve_fits

        Notes
        -----

        This call provides access to the `catalog export
        <https://ds9.si.edu/doc/ref/samp.html#export>`_ command.

        """

        # Is this a sensible way to check if a catalog is present?
        #
        if self.get("catalog show") is None:
            return None

        with tempfile.NamedTemporaryFile(prefix="ds9samp", suffix=".rdb") as fh:
            # Format options are rdb and tsv. My inital tests with rdb
            # showed a mis-match between DS9 and AstroPy so go with
            # tsv.
            #
            cmd = f"catalog export tsv {fh.name}"
            self.set(cmd, timeout=timeout)

            tbl = Table.read(fh, format="ascii.csv", delimiter="\t")

        # We could return the Table or convert to FITS. Leave as a
        # table for now.
        #
        return tbl


# From https://ds9.si.edu/doc/ref/file.html the array command says
#    xdim=value
#    ydim=value
#    zdim=value # default is a depth of 1
#    dim=value
#    dims=value
#    bitpix=[8|16|-16|32|64|-32|-64]
#    skip=value # must be even, most must be factor of 4
#    arch|endian=[big|bigendian|little|littleendian]
#
def np_to_array(img: np.ndarray) -> str:
    """Convert from NumPy data type to DS9 settings.

    Parameters
    ----------
    img
       The array to send. This must be 2D or 3D and not empty.

    Returns
    -------
    settings
       The settings needed by DS9 to decode the data.

    Notes
    -----
    This will error out if there is a problem, rather than just
    display a warning message, as this is expected to be used with a
    user-supplied array.

    """

    # For now restrict to 2D data only
    #
    opts = []
    match img.ndim:
        case 2:
            ny, nx = img.shape
            opts.extend([f"xdim={nx}", f"ydim={ny}"])

        case 3:
            nz, ny, nx = img.shape
            opts.extend([f"xdim={nx}", f"ydim={ny}", f"zdim={nz}"])

        case _:
            raise ValueError(f"img must be 2D or 3D, sent {img.ndim}D")

    if nx == 0 or ny == 0:
        raise ValueError("array appears to be empty")

    bpix = dtype_to_bitpix(img.dtype)
    opts.append(f"bitpix={bpix}")

    # Is this needed?
    match img.dtype.byteorder:
        case "<":
            opts.append("arch=little")
        case ">":
            opts.append("arch=big")
        case _:  # handle native and not-applicable
            pass

    out = ",".join(opts)
    return f"[{out}]"


def dtype_to_bitpix(dtype: np.dtype) -> int:
    """Convert the data type to DS9/FITS BITPIX setting.

    Parameters
    ----------
    dtype
       The NumPy dtype of the array.

    Return
    ------
    bitpix
       The FITS BITPIX value used to represent the data. This may be a
       lossy conversion (e.g. unsigned to signed).

    Notes
    -----
    This will error out if there is a problem, rather than just
    display a warning message, as this is expected to be used with a
    user-supplied array.

    """

    # Not trying to be clever here. Can we just piggy back on astropy
    # instead?
    #
    size = dtype.itemsize
    if np.issubdtype(dtype, np.integer):
        # Unfortunately unsigned types are not going to be handled
        # well here for those elements with the MSB/LSB set. Should
        # we warn the user in this case or error out?
        #
        return size * 8

    if np.issubdtype(dtype, np.floating):
        return size * -8

    raise ValueError(f"Unsupported dtype: {dtype}")


def bitpix_to_dtype(bpix: int) -> np.dtype | None:
    """Convert the DS9/FITS BITPIX setting to a NumPy datatype.

    Notes
    -----
    As this is intended to be used with data sent by DS9, errors are
    not raised, and the routine just returns None.

    """

    match bpix:
        case -64:
            return np.dtype("float64")
        case -32:
            return np.dtype("float32")
        case -16:
            return np.dtype("float16")

        case 64:
            return np.dtype("int64")
        case 32:
            return np.dtype("int32")
        case 16:
            return np.dtype("int16")
        case 8:
            return np.dtype("int8")

        case _:
            return None


def start(
    name: str | None = None, desc: str | None = None, client: str | None = None
) -> Connection:
    """Set up the SAMP connection.

    This checks that a DS9 instance exists and is connected to
    the SAMP hub.

    Parameters
    ----------
    name: optional
       Override the default name.
    desc: optional
       Override the default description.
    client: optional
       The name of the DS9 client to use (only needed if multiple
       DS9 instances are connected to the hub).

    Returns
    -------
    connection
       Used to represent the DS9 SAMP connection.

    See Also
    --------
    ds9samp, end, list_ds9

    """

    name = "ds9samp" if name is None else name
    desc = "Client created by ds9samp" if desc is None else desc
    ds9 = samp.SAMPIntegratedClient(
        name=name, description=desc, metadata={"ds9samp.version": VERSION}
    )

    ds9.connect()

    # Is there a DS9 instance to connect to? Just because something
    # supports ds9.get does not mean it is DS9, so check that we
    # at least have the interfaces we need and assume that whoever
    # is on the other end is doing the right thing. This is not
    # a secure connection!
    #
    gkeys = ds9.get_subscribed_clients("ds9.get").keys()
    skeys = ds9.get_subscribed_clients("ds9.set").keys()
    names = set(gkeys) & set(skeys)

    if len(names) == 0:
        ds9.disconnect()
        raise OSError("Unable to find a SAMP client that supports ds9.get/set")

    # For now require a single connection, since it makes the
    # processing of calls a lot easier. Unfortunately there's no easy
    # way for a user to say "use this version", so they have to use
    # the actual client name (which they can get from the SAMP Hub).
    #
    #
    if client is not None:
        if client in names:
            clname = client
        else:
            ds9.disconnect()
            raise ValueError(f"client name {client} is not valid")

    else:
        if len(names) > 1:
            ds9.disconnect()
            raise OSError(
                "Unable to support multiple DS9 SAMP clients. Try setting the client parameter."
            )

        clname = names.pop()

    return Connection(ds9=ds9, client=clname)


def end(connection: Connection) -> None:
    """Stop the connection to the DS9 hub.

    This does not close the hub or the DS9 instance.

    Parameters
    ----------
    connection
       The DS9 connection.

    See Also
    --------
    ds9samp, start

    """

    connection.ds9.disconnect()


@contextmanager
def ds9samp(
    name: str | None = None, desc: str | None = None, client: str | None = None
) -> Connection:
    """Set up the SAMP connection.

    This checks that a DS9 instance exists and is connected to
    the SAMP hub. The connection will be automatically closed
    when used as a context manager.

    Parameters
    ----------
    name: optional
       Override the default name.
    desc: optional
       Override the default description.
    client: optional
       The name of the DS9 client to use (only needed if multiple
       DS9 instances are connected to the hub).

    Returns
    -------
    connection
       Used to represent the DS9 SAMP connection.

    See Also
    --------
    end, list_ds9, start

    """

    conn = start(name=name, desc=desc, client=client)
    try:
        yield conn
    finally:
        end(conn)


def list_ds9() -> list[str]:
    """Return the SAMP client names of all the SAMP-connected DS9s.

    This is only needed when ds9samp errors out because there are
    multiple SAMP clients available. This routine lets a user find out
    what names can be used for the client argument.

    See Also
    --------
    ds9samp, start

    """

    temp = samp.SAMPIntegratedClient(
        name="ds9samp-list",
        description="Identify DS9 clients",
        metadata={"ds9samp-list.version": VERSION},
    )
    temp.connect()
    try:
        gkeys = temp.get_subscribed_clients("ds9.get").keys()
        skeys = temp.get_subscribed_clients("ds9.set").keys()
    finally:
        temp.disconnect()

    keys = set(gkeys) & set(skeys)
    return sorted(keys)
