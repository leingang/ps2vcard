"""
HTML parser for Albert roster pages

Requires the vobject_ library to create and serialize vCards.
To get it, try `pip install vobject` from the command line,
or go to the web page referenced above and follow the
installation instructions.

.. _vobject: http://eventable.github.io/vobject/
"""

import csv
from collections import defaultdict
from functools import wraps
from html.parser import HTMLParser
from html.entities import entitydefs
import logging
import os
import re
import sys

from bs4 import BeautifulSoup
import click
from transitions import Machine
from transitions.core import MachineError
import vobject


def log_begin(f):
    """Log the beginning of a function call"""
    @wraps(f)
    def wrapper(*args, **kwds):
        logging.getLogger(f.__name__).info("begin")
        return f(*args, **kwds)
    return wrapper


def log_end(f):
    """Log the end of a function call"""
    @wraps(f)
    def wrapper(*args, **kwds):
        res = f(*args, **kwds)
        logging.getLogger(f.__name__).info("end")
        return res
    return wrapper

def add_logger(f):
    """Expose a logger object named 'logger'"""
    # a bit of sorcery; see https://stackoverflow.com/a/17862336/297797
    @wraps(f)
    def wrapper(*args, **kwds):
        logger = logging.getLogger(f.__name__)
        g = f.__globals__ 
        sentinel = object()

        oldvalue = g.get('logger', sentinel)
        g['logger'] = logger

        try:
            res = f(*args, **kwds)
        finally:
            if oldvalue is sentinel:
                del g['logger']
            else:
                g['logger'] = oldvalue
        return res
    return wrapper

def unpack_progplan(progplan):
    """unpack a `progplan` string into program and plan.

    >>> unpack_progplan("UA-Coll of Arts & Sci - \n\nUndecided")
    ['UA-Coll of Arts & Sci','Undecided']
    """
    return re.split(' - \n+', progplan)


class AlbertRosterFramesetParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.roster_frame = None

    def handle_starttag(self, tag, attrs):
        log = logging.getLogger("AlbertRosterFramesetParser.starttag")
        log.debug("tag: %s" % tag)
        log.debug("attrs: %s" % attrs)
        if self.roster_frame:
            return
        attr_dict = dict(attrs)
        log.debug("attr_dict: %s" % attr_dict)
        if ((tag == 'frame' or tag == 'iframe') and
                'name' in attr_dict and
                attr_dict['name'] == 'TargetContent'):
            self.roster_frame = os.path.join(self.base_dir, attr_dict['src'])
            self.subparser = AlbertRosterHtmlParser()
            self.subparser.base_dir = os.path.dirname(self.roster_frame)
            self.subparser.parse(self.roster_frame)

    def parse(self, infile):
        """parse an Albert Class Roster frameset HTML file
        for course and student information

        First looks for the TargetContent frame, then parses that with
        a AlbertRosterHtmlParser.

        Return a tuple `(course,students)`, where `course` is a dictionary
        of course (i.e., section) properties, and `students` is a list of
        vCards.
        """
        log = logging.getLogger("AlbertRosterFramesetParser.parse")
        log.debug('file: %s', infile)
        self.base_dir = os.path.dirname(infile)
        with open(infile, 'r') as f:
            data = f.read()
            # log.debug('data: %s',data)
            self.feed(data)
        return (self.subparser.course_data, self.subparser.student_vcards)


class AlbertRosterHtmlParser(HTMLParser, Machine):
    student_keys_dict = {
        'CLASS_ROSTER_VW_EMPLID': 'id',
        'SCC_PRFPRIMNMVW_NAME': 'name',
        'DERIVED_SSSMAIL_EMAIL_ADDR': 'email',
        'SCC_PREF_PHN_VW_PHONE': 'phone',
        'PROGPLAN': 'progplan',
        'PROGPLAN1': 'level',
        'PSXLATITEM_XLATLONGNAME': 'status'
    }
    course_keys_dict = {
        'DERIVED_SSR_FC_SSR_CLASSNAME_LONG': 'code',
        'DERIVED_SSR_FC_SSS_PAGE_KEYDESCR2': 'description',
        'DERIVED_SSR_FC_DESCR254': 'name',
        'MTG_INSTR$0': 'instructor',
        'MTG_SCHED$0': 'schedule',
        'MTG_LOC$0': 'room',
        'MTG_DATE$0': 'dates'
    }
    photo_key = 'win10divEMPL_PHOTO_EMPLOYEE_PHOTO'

    def __init__(self):
        self.course_data = defaultdict(dict)
        self.student_records = defaultdict(dict)
        HTMLParser.__init__(self)
        # parsing state variables
        self.current_key = ""
        self.current_index = 0
        self.data = ""
        self.data_dest = ''
        states = ['seeking_key',
                  'found_course_key', 'found_student_key',
                  'seeking_student_data', 'seeking_course_data',
                  'seeking_student_image']
        Machine.__init__(self, states=states, initial='seeking_key')
        # The transition and callbacks below create a flow equivalent to this:
        #
        # If, while in the state 'seeking_key', a starttag (HTML `element`)
        # is found,
        #
        #  1. `unpack_element` will store the elements data (tag name and
        #     attributes) as machine properties, plus perform some pattern
        #     matching to test on.
        #
        #  2. The condition `attr_is_course_key` will be checked.  If it fails,
        #     abort and go on to the next transition.
        #
        #  3. If it succeeds, transition to state `found_course_key`.
        #
        #  4. But before making the transition, execute `handle_course_key`.
        #     This stores a translation of the course key into something
        #     human-readable, to become a property of the course.
        #
        #  5. After making the transition, execute `cleanup_unpack_element`
        #     This just removes the properties instantiated by `unpack_element`
        #
        #  6. Once in state `found_course_key`, all other attributes will
        #     impotently transition from that state back to itself.
        #     This avoids an error that was caused by multiple attributes
        #     (`id` and `name`) having the same key as their attribute value.
        #
        #  7. Once all the attributes in a start tag are proceesed, the
        #     transition `finish_handling_attrs` will move from state
        #     `found_course_key` to `seeking_course_data`
        #
        #  The actual transition function can't be overridden, but the
        #  callbacks can, and they do all the work.
        self.add_transition(
            source='seeking_key',
            trigger='machine_handle_attr',
            prepare='unpack_element',
            conditions='attr_is_course_key',
            before=['store_key', 'handle_course_key'],
            dest='found_course_key',
            after='cleanup_unpack_element')
        self.add_transition(
            source='seeking_key',
            trigger='machine_handle_attr',
            conditions='attr_is_student_key',
            before='handle_student_key',
            dest='found_student_key',
            after='cleanup_unpack_element')
        self.add_transition(
            source='seeking_key',
            trigger='machine_handle_attr',
            conditions='found_photo_key',
            before='handle_photo_key',
            dest='seeking_student_image',
            after='cleanup_unpack_element')
        self.add_transition(
            source='seeking_student_image',
            trigger='machine_handle_attr',
            prepare='unpack_element',
            conditions='found_img_src',
            before='handle_img_src',
            dest='seeking_key',
            after='cleanup_unpack_element')
        for source in ['seeking_course_data', 'seeking_student_data']:
            self.add_transition(
                source=source,
                trigger='machine_handle_data',
                before='buffer_data',
                dest=source)
            self.add_transition(
                source=source,
                trigger='machine_handle_entityref',
                before='buffer_translated_entityref',
                dest=source)
        # one key needs some additional handling
        self.add_transition(
            source='seeking_course_data',
            trigger='machine_handle_endtag',
            conditions='key_is_course_description',
            before=['capture_course_data', 'unpack_course_description'],
            after='reset_buffers',
            dest='seeking_key')
        for subject in ['course', 'student']:
            source = 'seeking_%s_data' % subject
            self.add_transition(
                source=source,
                trigger='machine_handle_endtag',
                before='capture_%s_data' % subject,
                after='reset_buffers',
                dest='seeking_key')
            source = 'found_%s_key' % subject
            dest = 'seeking_%s_data' % subject
            self.add_transition(
                source=source,
                trigger='machine_handle_attr',
                dest=source
            )
            self.add_transition(
                source=source,
                trigger='finish_handling_attrs',
                dest=dest
            )
        # Ignore character data, entity references,
        # or end tags until we find a key.
        #
        # There is a ignore_invalid_transitions flag that can be set,
        # but Explicit is Better than Implicit.
        for trigger in ['machine_handle_data',
                        'machine_handle_entityref',
                        'machine_handle_endtag',
                        'finish_handling_attrs']:
            self.add_transition(trigger, 'seeking_key', 'seeking_key')
        self.add_transition('finish_handling_attrs',
                            'seeking_student_image',
                            'seeking_student_image')

    def unpack_element(self, tag, attr):
        self.tag_name = tag
        self.attr_name, self.attr_value = attr
        self.attr_value_match = re.match("([^$]*)\$(\d+)$", self.attr_value)

    def cleanup_unpack_element(self, tag, attr):
        del(self.tag_name, self.attr_name, self.attr_value,
            self.attr_value_match)

    def attr_is_course_key(self, tag, attr):
        return ((self.attr_name == 'id') and
                (self.attr_value in self.course_keys_dict))

    def store_key(self, tag, attr):
        self.albert_key = self.attr_value

    def handle_course_key(self, tag, attr):
        logging.debug("parsing id %s" % self.attr_value)
        self.current_key = self.course_keys_dict[self.attr_value]

    def attr_is_student_key(self, tag, attr):
        return (self.attr_name == 'id' and
                self.attr_value_match and
                self.attr_value_match.group(1) in self.student_keys_dict)

    def handle_student_key(self, tag, attr):
        self.current_key = self.student_keys_dict[
            self.attr_value_match.group(1)]
        self.current_index = int(self.attr_value_match.group(2))

    def found_photo_key(self, tag, attr):
        return (self.attr_name == 'id' and
                self.attr_value_match and
                self.attr_value_match.group(1) == self.photo_key)

    def handle_photo_key(self, tag, attr):
        self.current_index = int(self.attr_value_match.group(2))

    def found_img_src(self, tag, attr):
        return (self.tag_name == 'img' and self.attr_name == 'src')

    def handle_img_src(self, tag, attr):
        self.student_records[self.current_index][
            'photo'] = os.path.join(self.base_dir, self.attr_value)

    # This is the HTMLParser method.
    # But all the work is done by the Machine method.
    def handle_starttag(self, tag, attrs):
        log = logging.getLogger('AlbertRosterHtmlParser.handle_starttag')
        for attr in attrs:
            try:
                self.machine_handle_attr(tag, attr)
            except MachineError:
                log.error('current_key: %s' % self.current_key)
                log.error("tag: %s" % tag)
                log.error("attrs: %s" % attrs)
                raise
        self.finish_handling_attrs()

    def handle_data(self, data):
        self.machine_handle_data(data)

    def buffer_data(self, data):
        self.data += data

    def handle_charref(self, name):
        logging.debug("character ref: %s", name)

    def handle_entityref(self, name):
        # logging.debug("entity ref: %s",name)
        self.machine_handle_entityref(name)
        # if (self.state == 'SEEKING_DATA'):
        #     if (name in entitydefs):
        #         self.data += entitydefs[name]

    def buffer_translated_entityref(self, name):
        # possible KeyError if name is not in entitydefs
        # Either put into a conditional before the transition
        # or handle the exception properly
        self.data += entitydefs[name]

    def handle_endtag(self, tag):
        self.machine_handle_endtag()

    def capture_course_data(self):
        self.course_data[self.current_key] = self.data

    def capture_student_data(self):
        self.student_records[self.current_index][self.current_key] = self.data

    def key_is_course_description(self):
        return (self.albert_key in self.course_keys_dict and
                self.course_keys_dict[self.albert_key] == 'description')

    def unpack_course_description(self):
        """Unpack the course description string.

        The course description string looks like
        "Spring 2017 | Regular Academic Session | New York University | Undergraduate"

        """  # noqa: E501
        (term, session, org, level) = self.course_data[
            'description'].split(' | ')
        self.course_data['term'] = term
        self.course_data['session'] = session
        self.course_data['org'] = org
        self.course_data['level'] = level

    def reset_buffers(self):
        # better to del-ete them?
        self.albert_key = None
        self.current_index = 0
        self.current_key = ""
        self.data = ""

    def parse(self, file):
        """parse an Albert Class Roster HTML file
        for course and student information

        Return a tuple `(course,students)`, where `course` is a dictionary
        of course (i.e., section) properties, and `students` is a list of
        dictionaries of student properties.
        """
        self.base_dir = os.path.dirname(file)
        with open(file, 'r') as f:
            data = f.read()
            self.feed(data)
        self.student_vcards = []
        for (index, student) in self.student_records.items():
            self.student_vcards.append(
                self.student_to_vcard(student, self.course_data))
        return (self.course_data, self.student_vcards)

    def student_to_vcard(self, student, course):
        """convert a single student record to a vCard object."""
        card = vobject.vCard()
        # first and last names
        (family_name, given_names) = student['name'].split(',')
        card.add('n')
        card.n.value = vobject.vcard.Name(
            family=family_name, given=given_names)
        # full name
        card.add('fn')
        card.fn.value = "%s %s" % (given_names, family_name)
        # email
        card.add('email')
        card.email.value = student['email']
        card.email.type_param = 'INTERNET'
        # student info
        card.add('title').value = "Student"
        # could be working around a bug, but a list is expected here to avoid
        # ORG:N;e;w;Y;o;r;k;U; ... in the card.
        # while we are at it, we will unpack progplan
        # TODO: add to FSM
        (student_program, student_plan) = unpack_progplan(student['progplan'])
        card.add('org').value = [course['org'], student_program]
        card.add('X-NYU-PROGPLAN').value =\
            ' - '.join([student_program, student_plan])
        try:
            card.add('photo')
            with open(student['photo'], 'rb') as f:
                card.photo.value = f.read()
            card.photo.encoding_param = "b"
            card.photo.type_param = "JPEG"
        except KeyError:
            # no photo
            pass
        # course (use address book's "Related Names" fields)
        item = 'item1'
        card.add(item + '.X-ABLABEL').value = "course"
        card.add(item + '.X-ABRELATEDNAMES')\
            .value = course['code'] + ", " + course['term']
        return card


class AlbertRosterXlsParser(object):
    """Class to parse the `ps.xls` file downloaded from Albert"""

    @log_begin
    @log_end
    def parse(self, input_path):
        with open(input_path) as f:
            html = f.read()
        cards = []
        bs = BeautifulSoup(html, 'lxml')
        headers = [e.contents[0] for e in bs.find_all('th')]
        # logger.info('headers: %s',repr(headers))
        for row in bs('tr'):
            cells = row.find_all('td')
            if cells == []:
                continue
            cell_contents = [''.join(cell.contents) for cell in cells]
            student = dict(zip(headers, cell_contents))
            cards.append(self.student_to_vcard(student))
        return None, cards

    def student_to_vcard(self, student, course=None):
        """convert a single student record to a vCard object."""
        # This seems pretty similar to AlbertRosterHtmlParser.student_to_vcard,
        # with some dict keys changed.
        # Maybe refactor?
        if course is None:
            course = {}
        course['org'] = 'New York University'
        card = vobject.vCard()
        # first and last names
        try:
            (family_name, given_names) = student['Name'].split(',')
        except TypeError:
            logger.error("student['Name']: %s", student['Name'])
            raise
        card.add('n')
        card.n.value = vobject.vcard.Name(
            family=family_name, given=given_names)
        # full name
        card.add('fn')
        card.fn.value = "%s %s" % (given_names, family_name)
        # email
        card.add('email')
        card.email.value = student['Email Address']
        card.email.type_param = 'INTERNET'
        # student info
        card.add('title').value = "Student"
        (student_program, student_plan) \
            = unpack_progplan(student['Program and Plan'])
        card.add('org').value = [course['org'], student_program]
        card.add('X-NYU-PROGPLAN').value \
            = ' - '.join([student_program, student_plan])
        card.add('X-NYU-NNUMBER').value = student['Campus ID']
        # course (use address book's "Related Names" fields)
        item = 'item1'
        card.add(item + '.X-ABLABEL').value = "course"
        card.add(item + '.X-ABRELATEDNAMES')\
            .value = "%s %d - %03d" % (
                student['Subject'],
                int(student['Catalog']),
                int(student['Section']))
        return card


class AlbertRosterCsvParser(object):
    """Class to parse CSV files downloaded from Albert"""

    def student_to_vcard(student, course):
        """convert a single student dictionary to a vCard."""
        card = vobject.vCard()
        course['org'] = "New York University"
        (family_name, given_names) = student['Name'].split(',')
        card.add('n').value = vobject.vcard.Name(
            family=family_name, given=given_names)
        # full name
        card.add('fn').value = "%s %s" % (given_names, family_name)
        # email
        card.add('email')
        card.email.value = student['email']
        card.email.type_param = 'INTERNET'
        # student info
        card.add('title').value = "Student"
        (student_program, student_plan) = unpack_progplan(
            student['Program and Plan'])
        card.add('org').value = [course['org'], student_program]
        card.add('X-NYU-PROGPLAN').value =\
            ' - '.join([student_program, student_plan])
        card.add('X-NYU-NNUMBER').value = student['Campus ID']
        item = 'item1'
        card.add(item + '.X-ABLABEL').value = "course"
        card.add(item + '.X-ABRELATEDNAMES')\
            .value = "%s %d - %03d" % (
                student['Subject'],
                int(student['Catalog']),
                int(student['Section']))
        return card

    def parse(self, input_file):
        """parse an Albert Class Roster frame CSV file
        for course and student information

        Return a tuple `(course,students)`, where `course` is a dictionary
        of course (i.e., section) properties, and `students` is a list of
        dictionaries of student properties.
        """
        with open(input_file) as f:
            self.student_vcards = []
            self.course_data = {}
            for student in csv.DictReader(f):
                self.student_vcards.append(
                    self.student_to_vcard(student, self.course_data))
        return (self.course_data, self.student_vcards)


class VcardWriter(object):
    """Class to write a vCard to a file"""
    _name = 'VcardWriter'

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
        logging.getLogger(self._name + '.write').info("Saving %s", filename)
        with open(os.path.join(self.dirname, filename), 'w') as f:
            f.write(card.serialize())

    def card_file_name(self, card):
        """construct a file name for a vCard.

        This one returns a sanitized form of the full name plus `.vcf`
        Warning: not guaranteed to be unique.
        """
        return "%s.vcf" % card.fn.value.replace(' ', '_')


class AmcCsvWriter(csv.DictWriter):
    """Class to write a list of students to a CSV file suitable for importing
    into auto-multiple-choice
    """
    fieldnames = [
        'Campus ID',  # N Number
        'surname',
        'name',  # given names
        'NetID',
        'email',  # NetID@nyu.edu
        'id'  # N Number with no N
    ]

    def __init__(self, csvfile, restval='',
                 extrasaction='raise', dialect='excel', *args, **kwds):
        # don't know how to pass the other keyword arguments...
        super().__init__(csvfile, fieldnames=self.fieldnames)

    def write(self, students):
        self.writeheader()
        for student in students:
            (email_localpart, domain) = student['Email Address'].split('@')
            (family_name, given_names) = student['Name'].split(',')
            try:
                row = {
                    'Campus ID': student['Campus ID'],
                    'surname': family_name,
                    'name': given_names,
                    'NetID': email_localpart,
                    'email': student['Email Address'],
                    'id': student['Campus ID'].replace('N', '')
                }
            except:
                # debugging
                logging.error('student: %s', repr(student))
                raise
            self.writerow(row)


class VcardAmcCsvWriter(csv.DictWriter):
    """Class to write a list of student vCards to a CSV file suitable for
    importing into auto-multiple-choice
    """

    fieldnames = [
        'Campus ID',  # N Number
        'surname',
        'name',  # given names
        'NetID',
        'email',  # NetID@nyu.edu
        'id'  # N Number with no N
    ]

    def __init__(self, csvfile, restval='',
                 extrasaction='raise', dialect='excel', *args, **kwds):
        # don't know how to pass the other keyword arguments...
        super().__init__(csvfile, fieldnames=self.fieldnames)

    def write(self, students):
        self.writeheader()
        for student in students:
            (email_localpart, domain) = student.email.value.split('@')
            try:
                row = {
                    'Campus ID': student.x_nyu_nnumber.value,
                    'surname': student.n.value.family,
                    'name': student.n.value.given,
                    'NetID': email_localpart,
                    'email': student.email.value,
                    'id': student.x_nyu_nnumber.value.replace('N', '')
                }
            except:
                # debugging
                logging.error('student: %s', repr(student))
                raise
            self.writerow(row)


# Here begin the scripts
@click.command()
@click.option('--verbose', is_flag=True, default=False, help='be verbose')
@click.option('--debug', is_flag=True, default=False,
              help='show debugging statements')
@click.option('--save', is_flag=True, default=False, help='save vCards')
@click.option('--print/--no-print', 'pprint', default=True,
              help='pretty-print vCards')
@click.argument('infile', metavar='FILE',
                default='Access Class Rosters.html')
def convert_all(infile, verbose, debug, save, pprint):
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
    loglevel = logging.DEBUG if debug else (
        logging.INFO if verbose else logging.WARNING)
    logging.basicConfig(level=loglevel)
    parser = AlbertRosterHtmlParser()
    (course, students) = parser.parse(infile)
    logging.debug('course: %s', repr(course))
    logging.debug('students: %s', repr(students))
    writer = VcardWriter(dirname=os.getcwd())
    for card in students:
        if pprint:
            card.prettyPrint()
        if save:
            writer.write(card)


@click.command()
@click.option('--verbose', is_flag=True, default=False, help='be verbose')
@click.option('--debug', is_flag=True, default=False,
              help='show debugging statements')
@click.option('--save', is_flag=True, default=False, help='save vCards')
@click.option('--save-dir', 'save_dir', type=click.Path(), default=os.getcwd(),
              help='save vCards to this directory ' +
                   '(default: current directory)')
@click.option('--print/--no-print', 'pprint', is_flag=True, default=True,
              help='pretty-print vCards to standard output')
@click.argument('infile', metavar='FILE', type=click.Path(exists=True),
                default='Access Class Rosters.html')
@log_begin
@log_end
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
    loglevel = logging.DEBUG if debug else (
        logging.INFO if verbose else logging.WARNING)
    logging.basicConfig(level=loglevel)
    log = logging.getLogger('convert_all_from_frameset')
    parser = AlbertRosterFramesetParser()
    (course, students) = parser.parse(infile)
    # logging.debug('students: %s',repr(students))
    # course info
    log.debug('course: %s', repr(course))
    log.debug('students: %s', repr(students))
    writer = VcardWriter(dirname=save_dir)
    for card in students:
        if pprint:
            card.prettyPrint()
        if save:
            writer.write(card)


@click.command()
@click.option('--verbose', is_flag=True, default=False, help='be verbose')
@click.option('--debug', is_flag=True, default=False,
              help='show debugging statements')
@click.option('--save-dir', 'save_dir', type=click.Path(), default=os.getcwd(),
              help='save images to this directory ' +
                   '(default: current directory)')
@click.argument('infile', metavar='FILE', type=click.Path(exists=True),
                default='Access Class Rosters.html')
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
    loglevel = logging.DEBUG if debug else (
        logging.INFO if verbose else logging.WARNING)
    logging.basicConfig(level=loglevel)
    log = logging.getLogger('convert_to_anki')
    parser = AlbertRosterHtmlParser()
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    (course, students) = parser.parse(infile)
    for card in students:
        filename = os.path.join(save_dir, card.fn.value + '.jpg')
        with open(filename, 'wb') as f:
            image = card.photo.value
            if not image == '':
                f.write(card.photo.value)
            else:
                log.warn('No photo found for student %s; skipping.' %
                         card.fn.value)


@click.command()
@click.option('--verbose', is_flag=True, default=False, help='be verbose')
@click.option('--debug', is_flag=True, default=False,
              help='show debugging statements')
@click.option('--output', 'outfile', type=click.File('wb'), default=sys.stdout,
              metavar='FILE', help='write to FILE (default: stdout)'
              )
@click.argument('infile', metavar='FILE', type=click.Path(exists=True),
                default='ps.csv')
@log_begin
@log_end
def convert_to_amccsv(infile, verbose, debug, outfile):
    """Process a CSV roster downloaded from Albert and generate a CSV file
    suitable for importing to auto-multiple-choice.

    Except, there's no such thing as a CSV roster downloaded from Albert.
    Albert sends an html file disguised as an excel file.

    See `convert_xls_to_amccsv`.
    """
    loglevel = logging.DEBUG if debug else (
        logging.INFO if verbose else logging.WARNING)
    logging.basicConfig(level=loglevel)
    with open(infile) as f:
        students = csv.DictReader(f)
        writer = AmcCsvWriter(outfile)
        writer.write(students)


def set_loglevel(context, parameter, value):
    if value is None:
        value = logging.WARNING
    logging.basicConfig(level=value)


@click.command()
@click.option('--verbose', 'loglevel', flag_value=logging.INFO,
              help='be verbose')
@click.option('--debug', 'loglevel', flag_value=logging.DEBUG,
              callback=set_loglevel,
              help='show debugging statements')
@click.option('--output', 'outfile', type=click.File('wb'), default=sys.stdout,
              metavar='FILE', help='write to FILE (default: stdout)')
@click.argument('infile', metavar='FILE', type=click.Path(exists=True),
                default='ps.csv')
@log_begin
@log_end
def convert_xls_to_amccsv(infile, loglevel, outfile):
    """Process an XLS roster downloaded from Albert and generate a CSV file
    suitable for importing to auto-multiple-choice.

    """
    parser = AlbertRosterXlsParser()
    (course, students) = parser.parse(infile)
    VcardAmcCsvWriter(outfile).write(students)
