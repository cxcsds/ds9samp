# Changes for ds9samp

## Version 0.1.1 - 2025-11-05

Minor additions to the documentation on installation and how to
select from multiple running DS9 instances.

## Version 0.1.0 - 2025-02-06

Add the `get_raw` routine which does not try to read in the data
stored in the URL response. Improved the handling of data from the
DATA, PIXELTABLE, and REGION commands (when used with `get`) by
returning a FITS HDUList or NumPy array instead of a string. Added the
`get_image_info` method to return basic information about the current
image.

Let's try ruff for linting and code formatting.

## Version 0.0.8 - 2025-01-30

Added the `send_cat` and `retrieve_cat` methods to allow you to
send and retrieve catalogs. Catalogs can be sent as AstroPy
[tables](https://docs.astropy.org/en/stable/table/index.html) or
[FITS tables](https://docs.astropy.org/en/stable/io/fits/index.html).

Cleaned up code introduced in version 0.0.7. There should be no
functional change, but the code just looks better.

## Version 0.0.7 - 2025-01-29

Added the `send_fits` and `retrieve_fits` methods to allow you to
directly work with [AstroPy FITS
objects](https://docs.astropy.org/en/stable/io/fits/index.html).

The `ds9samp_list` tool has gained the `--verbose` flag, which displays
the metadata for each DS9 instance that it finds.

## Version 0.0.6 - 2025-01-28

The `send_array` and `retrieve_array` methods can now handle 3D arrays
as well as 2D ones. Data in RGB, HLS, or HSV format is identified by
setting the `cube` argument in `send_array` to one of: `Cube.RGB`,
`Cube.HLS`, or `Cube.HSV`.

Commands which return data via a url, such as "data", will now return
the contents of this file, rather than returning `None` (this is only
valid for `get` calls).

The ds9 connection has now gained a debug field which can be set to
`True` to display the SAMP return value for each `set` or `get` call.

## Version 0.0.5 - 2025-01-27

Added the `retrieve_array` method, which saves the current frame to a
temporary file and then reads the data as a NumPy array.

The `send_array` method will create a new frame if needed (otherwise
the call to load the array data will fail). The mask argument should
be set to True if the array should be treated as a mask for the
frame. It now requires optional arguments to be explicitly named
(i.e. keyword only).

## Version 0.0.4 - 2025-01-27

The command-line tools now include the package version number when
reporting an error. For example:

    % ds9samp_list
    # ds9samp_list (0.0.4): ERROR Unable to find a running SAMP Hub.

## Version 0.0.3 - 2025-01-24

Added the `send_array` method to allow users to send a NumPy array
directly to DS9. Added this
[changelog](https://github.com/cxcsds/ds9samp/blob/main/CHANGELOG.md).

## Version 0.0.2 - 2025-01-17

A documentation release:

- added a note about the
[astropy-samp-ds9](https://pypi.org/project/astropy-samp-ds9/) Python
version that was released at essentially the same time as `ds9samp`;

- added links to some of the tools and systems we talk about;

- and additions and improvements to the README.

## Version 0.0.1 - 2024-12-20

Initial version.
