"""
HTML parser for Albert roster pages

Requires the vobject_ library to create and serialize vCards.
To get it, try `pip install vobject` from the command line,
or go to the web page referenced above and follow the
installation instructions.

.. _vobject: http://eventable.github.io/vobject/
"""

import csv
import logging
import os
import sys

import click
from logdecorator import log_on_start, log_on_end

from .parsers.html import (
    AlbertRosterFramesetParser,
    AlbertRosterHtmlParser,
    AlbertRosterXlsParser,
)


FORMAT = "%(levelname)s:%(name)s#%(lineno)d|%(funcName)s: %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()


def _set_loglevel(*args):
    "Callback for a Click Option to set the logging level"
    (_, _, value) = args
    if value is not None:
        logging.getLogger().setLevel(value)


class VcardWriter(object):
    """Class to write a vCard to a file"""

    _name = "VcardWriter"

    def __init__(self, dirname=None):
        if dirname is None:
            dirname = os.getcwd()
        self.dirname = dirname

    def write(self, card, filename=None):
        """write a vcard to a file.

        If no `filename` is given, use the `card_file_name` method
        """
        if not os.path.exists(self.dirname):
            os.mkdir(self.dirname)
        if filename is None:
            filename = self.card_file_name(card)
        logging.getLogger(self._name + ".write").info("Saving %s", filename)
        with open(os.path.join(self.dirname, filename), "w") as f:
            f.write(card.serialize())

    def card_file_name(self, card):
        """construct a file name for a vCard.

        This one returns a sanitized form of the full name plus `.vcf`
        Warning: not guaranteed to be unique.
        """
        return "%s.vcf" % card.fn.value.replace(" ", "_")


class AmcCsvWriter(csv.DictWriter):
    """Class to write a list of students to a CSV file suitable for importing
    into auto-multiple-choice
    """

    fieldnames = [
        "Campus ID",  # N Number
        "surname",
        "name",  # given names
        "NetID",
        "email",  # NetID@nyu.edu
        "id",  # N Number with no N
    ]

    def __init__(
        self, csvfile, restval="", extrasaction="raise", dialect="excel", *args, **kwds
    ):
        # don't know how to pass the other keyword arguments...
        super().__init__(csvfile, fieldnames=self.fieldnames)

    def write(self, students):
        self.writeheader()
        for student in students:
            (email_localpart, domain) = student["Email Address"].split("@")
            (family_name, given_names) = student["Name"].split(",")
            try:
                row = {
                    "Campus ID": student["Campus ID"],
                    "surname": family_name,
                    "name": given_names,
                    "NetID": email_localpart,
                    "email": student["Email Address"],
                    "id": student["Campus ID"].replace("N", ""),
                }
            except:
                # debugging
                logging.error("student: %s", repr(student))
                raise
            self.writerow(row)


class VcardAmcCsvWriter(csv.DictWriter):
    """Class to write a list of student vCards to a CSV file suitable for
    importing into auto-multiple-choice
    """

    fieldnames = [
        "Campus ID",  # N Number
        "surname",
        "name",  # given names
        "NetID",
        "email",  # NetID@nyu.edu
        "id",  # N Number with no N
    ]

    def __init__(
        self, csvfile, restval="", extrasaction="raise", dialect="excel", *args, **kwds
    ):
        # don't know how to pass the other keyword arguments...
        super().__init__(csvfile, fieldnames=self.fieldnames)

    def write(self, students):
        self.writeheader()
        for student in students:
            (email_localpart, domain) = student.email.value.split("@")
            try:
                row = {
                    "Campus ID": student.x_nyu_nnumber.value,
                    "surname": student.n.value.family,
                    "name": student.n.value.given,
                    "NetID": email_localpart,
                    "email": student.email.value,
                    "id": student.x_nyu_nnumber.value.replace("N", ""),
                }
            except:
                # debugging
                logging.error("student: %s", repr(student))
                raise
            self.writerow(row)


def set_loglevel(context, parameter, value):
    click.echo(f"{value=}")
    if value is None:
        value = logging.WARNING
    click.echo(f"Setting log level to {value}")
    logger.setLevel(value)


# Here begin the scripts
@click.command()
@click.option(
    "-d",
    "--debug",
    help="Show debugging statements",
    is_flag=True,
    flag_value=logging.DEBUG,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "-v",
    "--verbose",
    help="Be verbose",
    is_flag=True,
    flag_value=logging.INFO,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option("--save", is_flag=True, default=False, help="save vCards")
@click.option("--print/--no-print", "pprint", default=True, help="pretty-print vCards")
@click.argument("infile", metavar="FILE", default="Access Class Rosters.html")
@log_on_start(logging.DEBUG, "{callable.__name__:s} begin")
@log_on_end(logging.DEBUG, "{callable.__name__:s} end")
def convert_all(infile, save, pprint):
    """
    Process a roster downloaded from Albert and generate vCards

    Formerly Deprecated in favor of a frameset, but now we're back to this.

    To create the source file:

      * login to Albert, choose a course, and select "class roster"

      * select "view photos in list"

      * select "view all"

      * save this page, including the frames and photos.  In Chrome, use
        the "Webpage, complete" option when saving to do this.

      * change to the download directory and
        locate the roster file. It will probably be called
        "Access Class Rosters.html"

    Then run this script on that file.  You won't get any vCards saved without
    the --save option, though.

    Then you can import the cards into your address book.

    """
    parser = AlbertRosterHtmlParser()
    (course, students) = parser.parse(infile)
    logger.debug("course: %s", repr(course))
    logger.debug("students: %s", repr(students))
    writer = VcardWriter(dirname=os.getcwd())
    for card in students:
        if pprint:
            card.prettyPrint()
        if save:
            writer.write(card)


@click.command()
@click.option(
    "-d",
    "--debug",
    help="Show debugging statements",
    is_flag=True,
    flag_value=logging.DEBUG,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "-v",
    "--verbose",
    help="Be verbose",
    is_flag=True,
    flag_value=logging.INFO,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option("--save", is_flag=True, default=False, help="save vCards")
@click.option(
    "--save-dir",
    "save_dir",
    type=click.Path(),
    default=os.getcwd(),
    help="save vCards to this directory " + "(default: current directory)",
)
@click.option(
    "--print/--no-print",
    "pprint",
    is_flag=True,
    default=True,
    help="pretty-print vCards to standard output",
)
@click.argument(
    "infile",
    metavar="FILE",
    type=click.Path(exists=True),
    default="Access Class Rosters.html",
)
@log_on_start(logging.DEBUG, "{callable.__name__:s} begin")
@log_on_end(logging.DEBUG, "{callable.__name__:s} end")
def convert_all_from_frameset(infile, verbose, debug, save, save_dir, pprint):
    """Process a roster downloaded from Albert and generate vCards

    To create the source file:

      * login to Albert, choose a course, and select "class roster"

      * select "view photos in list"

      * select "view all"

      * save this page, including the frames and photos.  In Chrome, use
        the "Webpage, complete" option when saving to do this.

      * change to the download directory and locate the HTML file.  It will
        probably be called `Access Class Rosters.html` and have an accompanying
        directory `Access Class Rosters_files`.

      * Run this script on that html file.

    To save vCards, use the --save option.

    Then you can import the cards into your address book.
    """
    loglevel = (
        logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    )
    logging.basicConfig(level=loglevel)
    parser = AlbertRosterFramesetParser()
    (course, students) = parser.parse(infile)
    # logging.debug('students: %s',repr(students))
    # course info
    logger.debug("course: %s", repr(course))
    logger.debug("students: %s", repr(students))
    writer = VcardWriter(dirname=save_dir)
    for card in students:
        if pprint:
            card.prettyPrint()
        if save:
            writer.write(card)


@click.command()
@click.option(
    "-d",
    "--debug",
    help="Show debugging statements",
    is_flag=True,
    flag_value=logging.DEBUG,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "-v",
    "--verbose",
    help="Be verbose",
    is_flag=True,
    flag_value=logging.INFO,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "--save-dir",
    "save_dir",
    type=click.Path(),
    default=os.getcwd(),
    help="save images to this directory " + "(default: current directory)",
)
@click.argument(
    "infile",
    metavar="FILE",
    type=click.Path(exists=True),
    default="Access Class Rosters.html",
)
@log_on_start(logging.DEBUG, "{callable.__name__:s} begin")
@log_on_end(logging.DEBUG, "{callable.__name__:s} end")
def convert_to_anki(infile, verbose, debug, save_dir):
    """Process a roster downloaded from Albert and generate a set
    of image files with student names.  These files can be imported to Anki
    for making flashcards.

    To import:

    0. Get Anki
    1. Install the Media Import add-on:
       https://ankiweb.net/shared/info/1531997860
    2. import the files generated by this script.  They go into a deck named
       "Media Import"
    3. Rename "Media Import" to something useful
    4. Study.

    """
    # SOMEDAY: export an .apkg file or similar that can be imported easily.
    loglevel = (
        logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    )
    logging.basicConfig(level=loglevel)
    log = logging.getLogger("convert_to_anki")
    parser = AlbertRosterHtmlParser()
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    (course, students) = parser.parse(infile)
    for card in students:
        filename = os.path.join(save_dir, card.fn.value + ".jpg")
        with open(filename, "wb") as f:
            image = card.photo.value
            if not image == "":
                f.write(card.photo.value)
            else:
                log.warn("No photo found for student %s; skipping." % card.fn.value)


@click.command()
@click.option(
    "-d",
    "--debug",
    help="Show debugging statements",
    is_flag=True,
    flag_value=logging.DEBUG,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "-v",
    "--verbose",
    help="Be verbose",
    is_flag=True,
    flag_value=logging.INFO,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "--output",
    "outfile",
    type=click.File("wb"),
    default=sys.stdout,
    metavar="FILE",
    help="write to FILE (default: stdout)",
)
@click.argument(
    "infile", metavar="FILE", type=click.Path(exists=True), default="ps.csv"
)
@log_on_start(logging.DEBUG, "{callable.__name__:s} begin")
@log_on_end(logging.DEBUG, "{callable.__name__:s} end")
def convert_to_amccsv(infile, verbose, debug, outfile):
    """Process a CSV roster downloaded from Albert and generate a CSV file
    suitable for importing to auto-multiple-choice.

    Except, there's no such thing as a CSV roster downloaded from Albert.
    Albert sends an html file disguised as an excel file.

    See `convert_xls_to_amccsv`.
    """
    loglevel = (
        logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    )
    logger.setLevel(loglevel)
    with open(infile) as f:
        students = csv.DictReader(f)
        writer = AmcCsvWriter(outfile)
        writer.write(students)


@click.command()
@click.option(
    "-d",
    "--debug",
    help="Show debugging statements",
    is_flag=True,
    flag_value=logging.DEBUG,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "-v",
    "--verbose",
    help="Be verbose",
    is_flag=True,
    flag_value=logging.INFO,
    default=None,
    expose_value=False,
    callback=_set_loglevel,
)
@click.option(
    "--output",
    "outfile",
    type=click.File("wb"),
    default=sys.stdout,
    metavar="FILE",
    help="write to FILE (default: stdout)",
)
@click.argument(
    "infile", metavar="FILE", type=click.Path(exists=True), default="ps.csv"
)
@log_on_start(logging.DEBUG, "{callable.__name__:s} begin")
@log_on_end(logging.DEBUG, "{callable.__name__:s} end")
def convert_xls_to_amccsv(infile, loglevel, outfile):
    """Process an XLS roster downloaded from Albert and generate a CSV file
    suitable for importing to auto-multiple-choice.

    """
    parser = AlbertRosterXlsParser()
    (course, students) = parser.parse(infile)
    VcardAmcCsvWriter(outfile).write(students)
