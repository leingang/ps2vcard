ps2vcard
========

Convert Albert rosters to vCards

see docstring in ps2vcard.py

Requirements
------------

* vobject (version?)
* jinja2 (2.9.5) is used for test generation
* beautifulsoup4>=4.5.3
* lxml>=3.7.3

Installation
------------

First, create a virtual environment.  I like to put it in the user library
(`~/Library` on macs).

    $ virtualenv ~/Library/virtualenvs/ps2vcard
    $ . ~/Library/virtualenvs/ps2vcard/bin/activate

Then install:

    (ps2vcard)$ pip install --editable .

The executable will be installed as `~/Library/virtualenvs/ps2vcard/bin/ps2vcard`.
It can be executed in any environment.
