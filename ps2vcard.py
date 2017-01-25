"""
HTML parser for Albert roster pages

Requires the vobject_ library
to create and serialize vCards. To get it, try `pip install vobject` from the command line,
or go to the web page referenced above and follow the installation instructions.

.. _vobject: http://eventable.github.io/vobject/
"""

import base64
import click
from collections import defaultdict
from html.parser import HTMLParser
from html.entities import entitydefs
import logging
import re
from transitions import Machine,logger
from transitions.core import MachineError
import vobject

class AlbertHTMLParser(HTMLParser,Machine):
    student_keys_dict={
    'CLASS_ROSTER_VW_EMPLID'     : 'id',
    'SCC_PRFPRIMNMVW_NAME'       : 'name',
    'DERIVED_SSSMAIL_EMAIL_ADDR' : 'email',
    'SCC_PREF_PHN_VW_PHONE'      : 'phone',
    'PROGPLAN'                   : 'progplan',
    'PROGPLAN1'                  : 'level',
    'PSXLATITEM_XLATLONGNAME'    : 'status'
    }
    course_keys_dict={
    'DERIVED_SSR_FC_SSR_CLASSNAME_LONG' : 'code',
    'DERIVED_SSR_FC_SSS_PAGE_KEYDESCR2' : 'description',
    'DERIVED_SSR_FC_DESCR254'           : 'name',
    'MTG_INSTR$0'                       : 'instructor',
    'MTG_SCHED$0'                       : 'schedule',
    'MTG_LOC$0'                         : 'room',
    'MTG_DATE$0'                        : 'dates'
    }
    photo_key='win0divEMPL_PHOTO_EMPLOYEE_PHOTO'

    def __init__(self):
        self.course_data=defaultdict(dict)
        self.student_records=defaultdict(dict)
        HTMLParser.__init__(self)
        # parsing state variables
        self.current_key=""
        self.current_index=0
        self.data=""
        self.data_dest=''
        states=['seeking_key',
            'found_course_key','found_student_key',
            'seeking_student_data','seeking_course_data',
            'seeking_student_image']
        Machine.__init__(self,states=states,initial='seeking_key')
        # The transition and callbacks below create a flow equivalent to this:
        #
        # If, while in the state 'seeking_key', a starttag (HTML `element`)
        # is found,
        #
        #  1. `unpack_element` will store the elements data (tag name and attributes)
        #     as machine properties, plus perform some pattern matching to test on.
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
        #  6. Once in state `found_course_key`, all other attrivutes will
        #     impotently transition from that state back to itself.
        #     This avoids an error that was caused by multiple attributes
        #     (`id` and `name`) having the same key as their attribute value.
        #
        #  7. Once all the attributes in a start tag are proceesed, the transition
        #     `finish_handling_attrs` will move from state `found_course_key`
        #     to `seeking_course_data`
        #
        #  The actual transition function can't be overridden, but the callbacks
        #  can, and they do all the work.
        self.add_transition(
            source='seeking_key',
            trigger='machine_handle_attr',
            prepare='unpack_element',
            conditions='attr_is_course_key',
            before='handle_course_key',
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
        for source in ['seeking_course_data','seeking_student_data']:
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
        for subject in ['course','student']:
            source='seeking_%s_data' % subject
            self.add_transition(
                source=source,
                trigger='machine_handle_endtag',
                before='capture_%s_data' % subject,
                after='reset_buffers',
                dest='seeking_key')
            source='found_%s_key' % subject
            dest='seeking_%s_data' % subject
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
        # Ignore character data, entity references, or end tags until we find a key.
        #
        # There is a ignore_invalid_transitions flag that can be set,
        # but Explicit is Better than Implicit.
        for trigger in ['machine_handle_data','machine_handle_entityref','machine_handle_endtag',
            'finish_handling_attrs']:
            self.add_transition(trigger,'seeking_key','seeking_key')
        self.add_transition('finish_handling_attrs','seeking_student_image','seeking_student_image')

    def unpack_element(self,tag,attr):
        self.tag_name=tag
        self.attr_name,self.attr_value = attr
        self.attr_value_match=re.match("([^$]*)\$(\d+)$",self.attr_value)

    def cleanup_unpack_element(self,tag,attr):
        del self.tag_name, self.attr_name, self.attr_value, self.attr_value_match

    def attr_is_course_key(self,tag,attr):
        return (self.attr_name == 'id') and (self.attr_value in self.course_keys_dict)

    def handle_course_key(self,tag,attr):
        logging.debug("parsing id %s" % self.attr_value)
        self.current_key=self.course_keys_dict[self.attr_value]

    def attr_is_student_key(self,tag,attr):
        return (self.attr_name == 'id'
            and self.attr_value_match
            and self.attr_value_match.group(1) in self.student_keys_dict)

    def handle_student_key(self,tag,attr):
        self.current_key = self.student_keys_dict[self.attr_value_match.group(1)]
        self.current_index = int(self.attr_value_match.group(2))

    def found_photo_key(self,tag,attr):
        return (self.attr_name == 'id'
            and self.attr_value_match
            and self.attr_value_match.group(1) == self.photo_key)

    def handle_photo_key(self,tag,attr):
        self.current_index = int(self.attr_value_match.group(2))

    def found_img_src(self,tag,attr):
        return (self.tag_name == 'img' and self.attr_name == 'src')

    def handle_img_src(self,tag,attr):
        self.student_records[self.current_index]['photo'] = self.attr_value

    # This is the HTMLParser method.
    # But all the work is done by the Machine method.
    def handle_starttag(self,tag,attrs):
        log=logging.getLogger('AlbertHTMLParser.handle_starttag')
        for attr in attrs:
            try:
                self.machine_handle_attr(tag,attr)
            except MachineError:
                log.error('current_key: %s' % self.current_key)
                log.error("tag: %s" % tag)
                log.error("attrs: %s" % attrs)
                raise
        self.finish_handling_attrs()

    def handle_data(self,data):
        self.machine_handle_data(data)

    def buffer_data(self,data):
        self.data += data

    def handle_charref(self,name):
        logging.debug("character ref: %s",name)

    def handle_entityref(self,name):
        # logging.debug("entity ref: %s",name)
        self.machine_handle_entityref(name)
        # if (self.state == 'SEEKING_DATA'):
        #     if (name in entitydefs):
        #         self.data += entitydefs[name]

    def buffer_translated_entityref(self,name):
        # possible KeyError if name is not in entitydefs
        # Either put into a conditional before the transition
        # or handle the exception properly
        self.data += entitydefs[name]

    def handle_endtag(self,tag):
        self.machine_handle_endtag()

    def capture_course_data(self):
        self.course_data[self.current_key] = self.data

    def capture_student_data(self):
        self.student_records[self.current_index][self.current_key] = self.data

    def reset_buffers(self):
        # better to del-ete them?
        self.current_index=0
        self.current_key=""
        self.data=""

    def parse(self,file):
        """parse an Albert HTML file for course and student information

        Return a tuple `(course,students)`, where `course` is a dictionary
        of course (i.e., section) properties, and `students` is a list of
        dictionaries of student properties.
        """
        # TODO: consider returning a pandas.DataFrame
        with open(file,'r') as f:
            data = f.read()
            self.feed(data)
        return (self.course_data,self.student_records)

def student_to_vcard(student,org,course,term):
    """convert a single student record to a vCard object."""
    card = vobject.vCard()
    # first and last names
    (family_name,given_names) = student['name'].split(',')
    card.add('n')
    card.n.value = vobject.vcard.Name(family=family_name,given=given_names)
    # full name
    card.add('fn')
    card.fn.value="%s %s" % (given_names,family_name)
    # email
    card.add('email')
    card.email.value=student['email']
    card.email.type_param='INTERNET'
    # student info
    card.add('title').value = "Student"
    card.add('org').value = org
    try:
        card.add('photo')
        with open(student['photo'],'rb') as f:
            card.photo.value = f.read()
        card.photo.encoding_param = "b"
        card.photo.type_param = "JPEG"
    except KeyError:
        # no photo
        pass
    # course (use address book's "Related Names" fields)
    item = 'item1'
    card.add(item + '.X-ABLABEL').value="course"
    card.add(item + '.X-ABRELATEDNAMES').value=course['code'] + ", " + term
    return card

def write_vcard(card,filename=None):
    """write a vcard to a file.

    If no `filename` is given, use a sanitized form of the full name, with
    extension `.vcf`
    """
    #filename=student['name'].replace(',','_').replace(' ','_') + '.vcf'
    if filename is None:
        filename="%s.vcf" % card.fn.value.replace(' ','_')
    logging.getLogger('write_vcard').info("Saving %s",filename)
    with open(filename,'w') as f:
        f.write(card.serialize())

# Here begins the script
@click.command()
@click.option('--verbose',is_flag=True,default=False,help='be verbose')
@click.option('--debug',is_flag=True,default=False,help='show debugging statements')
@click.option('--save',is_flag=True,default=False,help='save vCards')
@click.option('--print','pprint',is_flag=True,default=True,help='pretty-print vCards')
@click.argument('infile',metavar='FILE',default='SA_LEARNING_MANAGEMENT.SS_FACULTY.html')
def convert_all(infile,verbose,debug,save,pprint):
    """
    Process a roster downloaded from Albert and generate vCards

    To create the source file:

      * login to Albert, choose a course, and select "class roster"

      * select "view photos in list"

      * select "view all"

      * save this page, including the frames and photos.  In Chrome, use
        the "Webpage, complete" option when saving to do this.

      * change to the created directory (it will likely end in `_files`) and locate the roster file.
        It will probably be called "SA_LEARNING_MANAGEMENT.SS_CLASS_ROSTER.html"

    Then run this script on that file.  You won't get any vCards saved without
    the --save option, though.

    Then you can import the cards into your address book.

    """
    loglevel = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    logging.basicConfig(level=loglevel)
    parser=AlbertHTMLParser()
    (course,students)=parser.parse(infile)
    # logging.debug('students: %s',repr(students))

    # course info
    # logging.debug('course: %s',repr(course))
    # TODO: fix this so that they are also `course` keys.
    (term,session,org,level) = course['description'].split(' | ')

    for key in students:
        student = students[key]
        card=student_to_vcard(student,org,course,term)
        if pprint:
            card.prettyPrint()
        if save:
            write_vcard(card)
