[![PyPI version](https://badge.fury.io/py/ds9samp.svg)](https://badge.fury.io/py/ds9samp)

# DS9 and Python

[DS9](https://ds9.si.edu/) can be controlled with XPA and
[SAMP](https://www.ivoa.net/documents/SAMP/). The AstroPy project
provides a
[SAMP interface](https://docs.astropy.org/en/stable/samp/index.html),
so it can be used to
[control DS9](https://sites.google.com/cfa.harvard.edu/saoimageds9/ds9-astropy).
However, using the SAMP interface is likely to be annoying,
so can we make something a bit more user friendly?

There is also the
[astropy-samp-ds9](https://pypi.org/project/astropy-samp-ds9/)
Python package that should be reviewed to see if it better meets
your needs.

## Installation

The package is available [on PyPI](https://pypi.org/project/ds9samp/)
and so can be installed with commands like

    pip install ds9samp

or

    uv pip install ds9samp

## Usage

The aim is to support the "simple" case where

- DS9 has been started,
- and is connected to a SAMP hub (probably its own),
- the DS9 instance is not going to be closed down during processing,
- the code is only going to talk to a single DS9 instance
  (ideally only one DS9 is connected to the SAMP hub to make things
   easier),
- and each call is made synchronously, that is the response from
  DS9 is waited for before finishing the call.

If any of these conditions do not hold then the [DS9 SAMP
examples](https://sites.google.com/cfa.harvard.edu/saoimageds9/ds9-astropy)
and the [AstroPy SAMP
module](https://docs.astropy.org/en/stable/samp/) pages should be
read.

### Security warning

Note that there is no expectation of security in this module; the
connections to DS9 depend on the SAMP protocol, and in fact there is
no guarantee that a DS9 instance is actually being talked to. All
that is checked is that the SAMP client supports the "ds9.get" and
"ds9.set" SAMP message names.

### Expected use

The code is written as a "context manager", to make sure the
connection is cleaned up, and it expected to be used something like:

```python
from ds9samp import ds9samp

with ds9samp() as ds9:

    # At this point use
    #    ds9.set("...")
    #    ds9.get("...")
    # to send messages to and from the DS9 instance.
    #
```

If there are any syntax errors in the DS9 commands then a message is
printed to the stdout channel. An exception is not raised as this
would exit the context manager, and so close the connection, which
would not be useful for the expected work flow.

Exceptions will be raised if there are "low-level" SAMP problems,
such as the DS9 instance or the SAMP hub closing down.

### Timeouts

The default timeout for calls is 10 seconds. This can be changed
either by setting the `timeout` parameter for the `get` and `set`
calls, or by setting the `timeout` attribute of the `ds9samp`
object. Note that the timeout value is an integer, and should be 0 or
greater.

```python
import ds9samp

with ds9samp.ds9samp() as ds9:
    # Reduce the timeout to 1 second
    ds9.timeout = 1

    ...

    # Remove the timeout
    ds9.timeout = 0

    ...

    # Over-ride the timeout value
    ds9.set("cmap viridis", timeout=4)
```

### Direct access

If direct access is needed - for example you are using a Python
notebook and need the connection to last longer than a single cell -
then you can use the `start` and `end` routines directly. For
example:

```python
import ds9samp

ds9 = ds9samp.start()
try:
    old_dir = ds9.get("cd")
    ds9.set("cd /tmp/")
    ...

finally:
    ds9samp.end(ds9)
```

### Direct access to the SAMP connection

This module is a very-small wrapper around the AstroPy SAMP
code. The `ds9` attribute of the object returned by either
`ds9samp.ds9samp` or `ds9samp.start` is a
[SampIntegratedClient](https://docs.astropy.org/en/stable/api/astropy.samp.SAMPIntegratedClient.html)
if you feel the need to use it.

The `client` attribute gives the name of the DS9 instance, as set by
the SAMP hub, and the `metadata` attribute is a dictionary of the
metadata reported by the DS9 instance. For example:

```python
from ds9samp import ds9samp
with ds9samp() as ds9:
    print(f"DS9 client = {ds9.client}")
    print(ds9.metadata["samp.name"])
    print(ds9.metadata["ds9.version"])
```

can display

```
DS9 client = c1
ds9
8.6
```

### Command-line tools

The module comes with three command-line tools:

- `ds9samp_get`
- `ds9samp_set`
- `ds9samp_list`

The get and set tools allow you to make a single `ds9.get` or
`ds9.set` call, and the last one is useful if there are multiple
DS9 instances connected to the SAMP hub.

If the tools error out then the output message will include some
colorized text (in red), unless

- the [NO_COLOR environment variable](https://no-color.org/) is set,
- or the output is not a TTY (e.g. it is being piped to a file).

#### ds9samp_get

```
% ds9samp_get --help
usage: ds9samp_get [options] command

Send a single command to DS9 via SAMP and print out any response.

Examples:

    % ds9samp_get scale
    linear
    % ds9samp_get 'frame all'
    1 3
    % ds9samp_get 'frame frameno'
    3

positional arguments:
  command

options:
  -h, --help            show this help message and exit
  -n CLIENT, --name CLIENT
                        Name of DS9 client in the SAMP hub
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout in seconds (integer, use 0 to disable)
  --version             show program's version number and exit
  --debug               Provide debugging output
```

As examples:

```
% ds9samp_get cmap
grey
% ds9samp_get 'frame frameno'
2
% ds9samp_get 'frame all'
1 2
```

#### ds9samp_set

```
% ds9samp_set --help
usage: ds9samp_set [options] command

Send one or more commands to DS9 via SAMP. If the command begins
with @ then it assumed to be a text file, with one command per line.

Any command errors will cause screen output but will not stop
running any remaining commands.

Examples:

    % ds9samp_set 'frame frameno 2'
    % ds9samp_set @commands
    % ds9samp_set 'frame delete all\nframe new'

positional arguments:
  command

options:
  -h, --help            show this help message and exit
  -n CLIENT, --name CLIENT
                        Name of DS9 client in the SAMP hub
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout in seconds (integer, use 0 to disable)
  --version             show program's version number and exit
  --debug               Provide debugging output
```

As examples:

```
% ds9samp_set 'cmap viridis'
% ds9samp_set 'frame delete all\nframe new'
```

#### ds9samp_list

```
% ds9samp_list --help
usage: ds9samp_list [options]

Display the names of the DS9 clients attached to the SAMP hub.

Examples:

    % ds9samp_list
    There is one DS9 client: c1
    % ds9samp_list
    There are 2 DS9 clients: c1 c56

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
  --verbose   report the metadata from each client
```

As an example:

```
% ds9samp_list
# ds9samp_list: ERROR Unable to find a running SAMP Hub.
% ds9 &
% ds9samp_list
There is one DS9 client: c1
% ds9 -title another-ds9 &
% ds9samp_list
There are 2 DS9 clients: c1 c3
% ds9samp_list --verbose
There are 2 DS9 clients: c1 c3

* client c1
  samp.name  ds9
  home.page  http://ds9.si.edu/
  ds9.version 8.6
  samp.icon.url http://ds9.si.edu/sun.png
  author.email ds9help@cfa.harvard.edu
  samp.description.text SAOImageDS9 is an astronomical visualization application
  samp.documentation.url http://ds9.si.edu/doc/ref/index.html
  author.name William Joye
  author.affiliation Smithsonian Astrophysical Observatory

* client c3
  samp.name  another-ds9
  home.page  http://ds9.si.edu/
  ds9.version 8.6
  samp.icon.url http://ds9.si.edu/sun.png
  author.email ds9help@cfa.harvard.edu
  samp.description.text SAOImageDS9 is an astronomical visualization application
  samp.documentation.url http://ds9.si.edu/doc/ref/index.html
  author.name William Joye
  author.affiliation Smithsonian Astrophysical Observatory

```

## What happens if there are multiple DS9 instances?

A call to `ds9samp` or `start` can error out with the message:

```
OSError: Unable to support multiple DS9 SAMP clients. Try setting the client parameter.
```

In this case there are multiple DS9 instances connected to the SAMP hub.
If the hub can be queried then the "client name" for the DS9 instance
to use can be found, otherwise the ds9samp_list script can be used:

```
There are 2 DS9 clients: c1 c4
```

Unfortunately there's no easy way to tell which is which. You can try
something like

```
% ds9samp_set "analysis message ok {Selected window}" --name c4 --timeout 0
```

(chose one of the names from the output above) as it should display
a pop up window centered on the DS9 instance.

### From Python

Both `ds9samp.ds9samp` and `ds9samp.start` accept an optional `client`
argument, which should be set to the name of the DS9 instance you want
to connect to. For example, the following will select the **first**
DS9 instance in the list (it uses `ds9samp.list_ds9` to identify the
names of the DS9 instances):

    import ds9samp
    clients = ds9samp.list_ds9()
    with ds9samp.ds9samp(client=clients[0]) as ds9:
        do_something_awesome(ds9)

### Using the scripts

The `ds9samp_get` and `ds9samp_set` commands accept a `--name` argument
which accepts the client name reported by `ds9samp_list`.

## Examples

Some of these examples are based on the examples in the
[DS9+Astropy
page](https://sites.google.com/cfa.harvard.edu/saoimageds9/ds9-astropy).

### RGB Images

This is the same as the "RGB Images" section, with several
simplifications:

 - the "client name" of the DS9 application does not need to be
   specified, as this is handled for you
 - the timeout can be set once, rather than each call
 - since this interface is for DS9, and not a generic SAMP-enabled
   tool, we can hide some parts of the SAMP interface,
 - the connection is automatically closed for us.

```python
from ds9samp import ds9samp

with ds9samp() as ds9:
    ds9.timeout = 10  # this is the default setting
    ds9.set("rgb")
    ds9.set("rgb red")
    ds9.set("url http://ds9.si.edu/download/data/673nmos.fits")
    ds9.set("zscale")
    ds9.set("rgb green")
    ds9.set("url http://ds9.si.edu/download/data/656nmos.fits")
    ds9.set("zscale")
    ds9.set("rgb blue")
    ds9.set("url http://ds9.si.edu/download/data/502nmos.fits")
    ds9.set("zscale")
    ds9.set("rotate 270")
    ds9.set("zoom to fit")
```

### 3D Data Cube

This will create a file called `3d.gif` in the current working
directory (rather than the directory whre ds9 was started):

```python
from pathlib import Path

from ds9samp import ds9samp

this_dir = Path().resolve()

with ds9samp() as ds9:
    ds9.set("frame delete all")
    ds9.set(f"cd {this_dir}")
    ds9.set("3d")
    ds9.set("url http://ds9.si.edu/download/data/image3d.fits")
    ds9.set("cmap viridis")
    ds9.set("movie 3d gif 3d.gif number 10 az from -90 az to 90 el from 45 el to 45 zoom from 4 zoom to 4 oscillate 1")
```

### Imexam

Note that the timeout for the `imexam wcs icrs` is set to 0 so that
it does not fail because the user has taken too long to select a
position.

```python
from ds9samp import ds9samp

with ds9samp() as ds9:
    ds9.set("url http://ds9.si.edu/download/data/img.fits")
    ds9.set("zscale")

    print("Click anwhere in the image")
    coord = ds9.get("imexam wcs icrs", timeout=0)
    x, y = [float(c) for c in coord.split()]
    print(f" -> '{coord}'")
    print(f" -> x={x}  y={y}")

    # Extract pixel data around this location, using a box size of 0.7
    # arcseconds.
    #
    size = 0.7 / 3600
    vals = ds9.get("data wcs {x} {y} {size:.5f} {size:.5f} no")
    print("Data values:")
    print(vals)
```

If a `get` call returns a value then it is returned as a string, and
the format depends on the command, in this case a pair of
space-separated coordinates, for `imexam`. The return value for `data`
depends on the last argument (in this case `no`, which means the pixel
coordinates are included).

An example output of this is:

```
Click anwhere in the image
 -> '202.4845615 47.1919416'
 -> x=202.4845615  y=47.1919416
Data values:
202.4843826,47.1918298 = 20
202.4845067,47.1919821 = 33
202.4844518,47.1920227 = 23
202.4843373,47.1920259 = 21
202.4844422,47.1918671 = 24
202.4843325,47.1919481 = 21
202.4843874,47.1919076 = 21
202.4843277,47.1918703 = 20
202.4845615,47.1919416 = 68
202.4842181,47.1919514 = 22
202.4842729,47.1919109 = 22
202.4843970,47.1920632 = 19
202.4845019,47.1919043 = 34
202.4842777,47.1919887 = 21
202.4844470,47.1919449 = 24
202.4843922,47.1919854 = 21


```

### Sending a NumPy array

Version 0.0.3 added the `send_array` call, which will create a
temporary file and use that to send a NumPy array to DS9. As an
example, view this 2D elliptical gaussian:

```python
import numpy as np
import ds9samp

# Create a rotated elliptical gaussian
x0 = 2200
x1 = 3510
theta = 1.2
ellip = 0.4
fwhm = 400

# The grid is x=2000...2500 and y=3000...4000 (inclusive).
#
x1s, x0s = np.mgrid[3000:4001, 2000:2501]

# Create the "delta" values
dx0 = (x0s - x0) * np.cos(theta) + (x1s - x1) * np.sin(theta)
dx1 = (x1s - x1) * np.cos(theta) - (x0s - x0) * np.sin(theta)

# Create the gaussian image
r2 = ((dx0 * (1 - ellip))**2  + dx1**2) / (fwhm * (1 - ellip))**2
img = np.exp(-4 * np.log(2) * r2)

# Send it to DS9
with ds9samp.ds9samp() as ds9:
    ds9.send_array(img)
    ds9.set("cmap viridis")
```

### Retrieving a NumPy array

Version 0.0.5 added the `retrieve_array` call, which will return a
NumPy array from the selected DS9 frame. As an example, we lightly
smooth - using DS9 - an array and return it:

```python
import numpy as np
import ds9samp

orig = np.random.randn(300, 400)

# Send it to DS9
with ds9samp.ds9samp() as ds9:
    ds9.send_array(orig)
    ds9.set("cmap gray")
    ds9.set("smooth function gaussian")
    ds9.set("smooth radius 3")

    # The color map and scaling do not change the retrieved values
    smoothed = ds9.retrieve_array()

    # Turn off the smoothing
    ds9.set("smooth off")

    # Identify the most-discrepant points in the smoothed image
    discrepant = np.abs(smoothed) > 3

    # Add it as a mask
    ds9.send_array(discrepant, mask=True)
```
