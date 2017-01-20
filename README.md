ps2vcard
========

Convert Albert rosters to vCards

see docstring in ps2vcard.py

Installation
------------

First, create a virtual environment.  I like to put it in the user library
(`~/Library` on macs).

    $ virtualenv-2.7 ~/Library/virtualenvs/ps2vcard27
    $ . ~/Library/virtualenvs/ps2vcard27/bin/activate

Then install:

    (ps2vcard27)$ pip install --editable .

The executable will be installed as `~/Library/virtualenvs/ps2vcard27/bin/ps2vcard`.

TODO
----

Convert to Python 3.  Having trouble with getting photos saved.  See [issue](https://github.com/eventable/vobject/issues/59).
