import re
import os
from collections import defaultdict

from html.parser import HTMLParser
from html.entities import entitydefs

from bs4 import BeautifulSoup
from transitions import Machine
from transitions.core import MachineError
import vobject


import logging
from logdecorator import log_on_start, log_on_end

from ps2vcard.parsers import unpack_progplan


logger = logging.getLogger(__name__)


class AlbertRosterFramesetParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.roster_frame = None

    def handle_starttag(self, tag, attrs):
        logger.debug("tag: %s" % tag)
        logger.debug("attrs: %s" % attrs)
        if self.roster_frame:
            return
        attr_dict = dict(attrs)
        logger.debug("attr_dict: %s" % attr_dict)
        if (
            (tag == "frame" or tag == "iframe")
            and "name" in attr_dict
            and attr_dict["name"] == "TargetContent"
        ):
            self.roster_frame = os.path.join(self.base_dir, attr_dict["src"])
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
        logger.debug("file: %s", infile)
        self.base_dir = os.path.dirname(infile)
        with open(infile, "r") as f:
            data = f.read()
            # log.debug('data: %s',data)
            self.feed(data)
        return (self.subparser.course_data, self.subparser.student_vcards)


class AlbertRosterHtmlParser(HTMLParser, Machine):
    student_keys_dict = {
        "CLASS_ROSTER_VW_EMPLID": "id",
        "SCC_PRFPRIMNMVW_NAME": "name",
        "DERIVED_SSSMAIL_EMAIL_ADDR": "email",
        "SCC_PREF_PHN_VW_PHONE": "phone",
        "PROGPLAN": "progplan",
        "PROGPLAN1": "level",
        "PSXLATITEM_XLATLONGNAME": "status",
    }
    course_keys_dict = {
        "DERIVED_SSR_FC_SSR_CLASSNAME_LONG": "code",
        "DERIVED_SSR_FC_SSS_PAGE_KEYDESCR2": "description",
        "DERIVED_SSR_FC_DESCR254": "name",
        "MTG_INSTR$0": "instructor",
        "MTG_SCHED$0": "schedule",
        "MTG_LOC$0": "room",
        "MTG_DATE$0": "dates",
    }
    photo_key = "win10divEMPL_PHOTO_EMPLOYEE_PHOTO"

    def __init__(self):
        self.course_data = defaultdict(dict)
        self.student_records = defaultdict(dict)
        HTMLParser.__init__(self)
        # parsing state variables
        self.current_key = ""
        self.current_index = 0
        self.data = ""
        self.data_dest = ""
        states = [
            "seeking_key",
            "found_course_key",
            "found_student_key",
            "seeking_student_data",
            "seeking_course_data",
            "seeking_student_image",
        ]
        Machine.__init__(self, states=states, initial="seeking_key")
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
            source="seeking_key",
            trigger="machine_handle_attr",
            prepare="unpack_element",
            conditions="attr_is_course_key",
            before=["store_key", "handle_course_key"],
            dest="found_course_key",
            after="cleanup_unpack_element",
        )
        self.add_transition(
            source="seeking_key",
            trigger="machine_handle_attr",
            conditions="attr_is_student_key",
            before="handle_student_key",
            dest="found_student_key",
            after="cleanup_unpack_element",
        )
        self.add_transition(
            source="seeking_key",
            trigger="machine_handle_attr",
            conditions="found_photo_key",
            before="handle_photo_key",
            dest="seeking_student_image",
            after="cleanup_unpack_element",
        )
        self.add_transition(
            source="seeking_student_image",
            trigger="machine_handle_attr",
            prepare="unpack_element",
            conditions="found_img_src",
            before="handle_img_src",
            dest="seeking_key",
            after="cleanup_unpack_element",
        )
        for source in ["seeking_course_data", "seeking_student_data"]:
            self.add_transition(
                source=source,
                trigger="machine_handle_data",
                before="buffer_data",
                dest=source,
            )
            self.add_transition(
                source=source,
                trigger="machine_handle_entityref",
                before="buffer_translated_entityref",
                dest=source,
            )
        # one key needs some additional handling
        self.add_transition(
            source="seeking_course_data",
            trigger="machine_handle_endtag",
            conditions="key_is_course_description",
            before=["capture_course_data", "unpack_course_description"],
            after="reset_buffers",
            dest="seeking_key",
        )
        for subject in ["course", "student"]:
            source = "seeking_%s_data" % subject
            self.add_transition(
                source=source,
                trigger="machine_handle_endtag",
                before="capture_%s_data" % subject,
                after="reset_buffers",
                dest="seeking_key",
            )
            source = "found_%s_key" % subject
            dest = "seeking_%s_data" % subject
            self.add_transition(
                source=source, trigger="machine_handle_attr", dest=source
            )
            self.add_transition(
                source=source, trigger="finish_handling_attrs", dest=dest
            )
        # Ignore character data, entity references,
        # or end tags until we find a key.
        #
        # There is a ignore_invalid_transitions flag that can be set,
        # but Explicit is Better than Implicit.
        for trigger in [
            "machine_handle_data",
            "machine_handle_entityref",
            "machine_handle_endtag",
            "finish_handling_attrs",
        ]:
            self.add_transition(trigger, "seeking_key", "seeking_key")
        self.add_transition(
            "finish_handling_attrs", "seeking_student_image", "seeking_student_image"
        )

    def unpack_element(self, tag, attr):
        self.tag_name = tag
        self.attr_name, self.attr_value = attr
        self.attr_value_match = re.match("([^$]*)\$(\d+)$", self.attr_value)

    def cleanup_unpack_element(self, tag, attr):
        del (self.tag_name, self.attr_name, self.attr_value, self.attr_value_match)

    def attr_is_course_key(self, tag, attr):
        return (self.attr_name == "id") and (self.attr_value in self.course_keys_dict)

    def store_key(self, tag, attr):
        self.albert_key = self.attr_value

    def handle_course_key(self, tag, attr):
        logger.debug("parsing id %s" % self.attr_value)
        self.current_key = self.course_keys_dict[self.attr_value]

    def attr_is_student_key(self, tag, attr):
        return (
            self.attr_name == "id"
            and self.attr_value_match
            and self.attr_value_match.group(1) in self.student_keys_dict
        )

    def handle_student_key(self, tag, attr):
        self.current_key = self.student_keys_dict[self.attr_value_match.group(1)]
        self.current_index = int(self.attr_value_match.group(2))

    def found_photo_key(self, tag, attr):
        return (
            self.attr_name == "id"
            and self.attr_value_match
            and self.attr_value_match.group(1) == self.photo_key
        )

    def handle_photo_key(self, tag, attr):
        self.current_index = int(self.attr_value_match.group(2))

    def found_img_src(self, tag, attr):
        return self.tag_name == "img" and self.attr_name == "src"

    def handle_img_src(self, tag, attr):
        self.student_records[self.current_index]["photo"] = os.path.join(
            self.base_dir, self.attr_value
        )

    # This is the HTMLParser method.
    # But all the work is done by the Machine method.
    def handle_starttag(self, tag, attrs):
        log = logging.getLogger("AlbertRosterHtmlParser.handle_starttag")
        for attr in attrs:
            try:
                self.machine_handle_attr(tag, attr)
            except MachineError:
                log.error("current_key: %s" % self.current_key)
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
        return (
            self.albert_key in self.course_keys_dict
            and self.course_keys_dict[self.albert_key] == "description"
        )

    def unpack_course_description(self):
        """Unpack the course description string.

        The course description string looks like
        "Spring 2017 | Regular Academic Session | New York University | Undergraduate"

        """  # noqa: E501
        (term, session, org, level) = self.course_data["description"].split(" | ")
        self.course_data["term"] = term
        self.course_data["session"] = session
        self.course_data["org"] = org
        self.course_data["level"] = level

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
        with open(file, "r") as f:
            data = f.read()
            self.feed(data)
        self.student_vcards = []
        for index, student in self.student_records.items():
            self.student_vcards.append(self.student_to_vcard(student, self.course_data))
        return (self.course_data, self.student_vcards)

    def student_to_vcard(self, student, course):
        """convert a single student record to a vCard object."""
        card = vobject.vCard()
        # first and last names
        (family_name, given_names) = student["name"].split(",")
        card.add("n")
        card.n.value = vobject.vcard.Name(family=family_name, given=given_names)
        # full name
        card.add("fn")
        card.fn.value = "%s %s" % (given_names, family_name)
        # email
        card.add("email")
        card.email.value = student["email"]
        card.email.type_param = "INTERNET"
        # student info
        card.add("title").value = "Student"
        # could be working around a bug, but a list is expected here to avoid
        # ORG:N;e;w;Y;o;r;k;U; ... in the card.
        # while we are at it, we will unpack progplan
        # TODO: add to FSM
        (student_program, student_plan) = unpack_progplan(student["progplan"])
        card.add("org").value = [course["org"], student_program]
        card.add("X-NYU-PROGPLAN").value = " - ".join([student_program, student_plan])
        try:
            card.add("photo")
            with open(student["photo"], "rb") as f:
                card.photo.value = f.read()
            card.photo.encoding_param = "b"
            card.photo.type_param = "JPEG"
        except KeyError:
            # no photo
            pass
        # course (use address book's "Related Names" fields)
        item = "item1"
        card.add(item + ".X-ABLABEL").value = "course"
        card.add(item + ".X-ABRELATEDNAMES").value = (
            course["code"] + ", " + course["term"]
        )
        return card


class AlbertRosterXlsParser(object):
    """Class to parse the `ps.xls` file downloaded from Albert"""

    @log_on_start(logging.DEBUG, "{callable.__name__:s} begin")
    @log_on_end(logging.DEBUG, "{callable.__name__:s} end")
    def parse(self, input_path):
        with open(input_path) as f:
            html = f.read()
        cards = []
        bs = BeautifulSoup(html, "lxml")
        headers = [e.contents[0] for e in bs.find_all("th")]
        logger.info("headers: %s", repr(headers))
        for row in bs("tr"):
            cells = row.find_all("td")
            if cells == []:
                continue
            cell_contents = [
                "".join(filter(lambda x: str(x) == x, cell.contents)) for cell in cells
            ]  # needs to be a list of strings
            student = dict(zip(headers, cell_contents))
            logger.info("student: %s", repr(student))
            cards.append(self.student_to_vcard(student))
        return None, cards

    def student_to_vcard(self, student, course=None):
        """convert a single student record to a vCard object."""
        # This seems pretty similar to AlbertRosterHtmlParser.student_to_vcard,
        # with some dict keys changed.
        # Maybe refactor?
        if course is None:
            course = {}
        course["org"] = "New York University"
        card = vobject.vCard()
        # first and last names
        try:
            (family_name, given_names) = student["Name"].split(",")
        except TypeError:
            logger.error("student['Name']: %s", student["Name"])
            raise
        card.add("n")
        card.n.value = vobject.vcard.Name(family=family_name, given=given_names)
        # full name
        card.add("fn")
        card.fn.value = "%s %s" % (given_names, family_name)
        # email
        card.add("email")
        card.email.value = student["Email Address"]
        card.email.type_param = "INTERNET"
        # student info
        card.add("title").value = "Student"
        (student_program, student_plan) = unpack_progplan(student["Program and Plan"])
        card.add("org").value = [course["org"], student_program]
        card.add("X-NYU-PROGPLAN").value = " - ".join([student_program, student_plan])
        card.add("X-NYU-NNUMBER").value = student["Campus ID"]
        # course (use address book's "Related Names" fields)
        item = "item1"
        card.add(item + ".X-ABLABEL").value = "course"
        card.add(item + ".X-ABRELATEDNAMES").value = "%s %d - %03d" % (
            student["Subject"],
            int(student["Catalog"]),
            int(student["Section"]),
        )
        return card
