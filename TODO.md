TODO
====

Change interface to parse top level
-----------------------------------

I want to run this command in the directory that contains `Faculty Center.html`
and `Faculty Center_files` rather than in `Faculty Center_files.`

2017-01-27: This is done!

Move into `nyucutils`
---------------------

* Albert classes should be moved to `nyucutils.vendors.albert`
* functions that work with vCards should go to `nyucutils.vobjects`
* command-line applications should go to `nyucutils.applications`


Pandas
------

`parser.parse()` should (or could?) return `pandas.DataFrame`s

Anki
----

Add a module function to generate a directory suitable for importing into Anki.
It would contain the ID pictures, with file name equal to FN.

auto-multiple-choice
--------------------

Add a module function to generate the `AMC.csv` file
The only issue is storing the NYU Classes site_id
