import csv

import vobject

from ps2vcard.parsers import unpack_progplan


class AlbertRosterCsvParser(object):
    """Class to parse CSV files downloaded from Albert"""

    def student_to_vcard(student, course):
        """convert a single student dictionary to a vCard."""
        card = vobject.vCard()
        course["org"] = "New York University"
        (family_name, given_names) = student["Name"].split(",")
        card.add("n").value = vobject.vcard.Name(family=family_name, given=given_names)
        # full name
        card.add("fn").value = "%s %s" % (given_names, family_name)
        # email
        card.add("email")
        card.email.value = student["email"]
        card.email.type_param = "INTERNET"
        # student info
        card.add("title").value = "Student"
        (student_program, student_plan) = unpack_progplan(student["Program and Plan"])
        card.add("org").value = [course["org"], student_program]
        card.add("X-NYU-PROGPLAN").value = " - ".join([student_program, student_plan])
        card.add("X-NYU-NNUMBER").value = student["Campus ID"]
        item = "item1"
        card.add(item + ".X-ABLABEL").value = "course"
        card.add(item + ".X-ABRELATEDNAMES").value = "%s %d - %03d" % (
            student["Subject"],
            int(student["Catalog"]),
            int(student["Section"]),
        )
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
                    self.student_to_vcard(student, self.course_data)
                )
        return (self.course_data, self.student_vcards)
