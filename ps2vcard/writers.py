import os
import csv
import logging


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