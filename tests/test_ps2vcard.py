#!/usr/bin/env python

import csv
from glob import glob
import os.path
from os.path import basename
from subprocess import check_call
from tempfile import TemporaryDirectory
import unittest

from jinja2 import Template


class TestPs2Vcard(unittest.TestCase):
    """Test the ps2vcard script.

    Parses the `Faculty_Center.html` frameset file (and referenced files)
    and produces vcards in a temporary.  Tests each against those in the
    "golden" directory.
    """

    def mock_pshtml(self):
        """ Mock up the Albert HTML file.

        This method is not a real test and doesn't need to be run often.
        It won't be discovered by running this module on the command line,
        or with `nose`.  To run it, execute

            $ python -m unittest test_ps2vcard.TestPs2Vcard.mock_pshtml

        on the command line.
        """
        dirname = 'Faculty Center_files'
        input_path = os.path.join('data', 'mock.csv')
        template_path = os.path.join('data', dirname, 'template.html')
        output_path = os.path.join(
            'data', dirname, 'SA_LEARNING_MANAGEMENT.SS_FACULTY.html')

        def fix(s):
            """fix up the student record for templating"""
            try:
                (url, query) = s['photo'].split('?')
                s['photo_filename'] = basename(url)
            except ValueError:
                pass
            s['Program and Plan'] = s['Program and Plan'].replace('\\n', '\n')
            return s
        with open(input_path) as f, open(template_path) as tf:
            t = Template(tf.read())
            students = [fix(student) for student in csv.DictReader(f)]
        with open(output_path, 'w') as f:
            f.write(t.render(students=students))
        self.assertTrue(os.path.exists(output_path))

    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.goldendir = os.path.join('golden', 'ps2vcard')
        self.input_path = os.path.join('data', 'Faculty Center.html')

    def test_ps2vcard(self):
        check_call([
            'ps2vcard', self.input_path, '--no-print', '--save',
            '--save-dir=%s' % self.tempdir.name
        ])
        for goldpath in glob(os.path.join(self.goldendir, '*.vcf')):
            newpath = os.path.join(self.tempdir.name, basename(goldpath))
            self.assertTrue(os.path.exists(newpath))
            with open(newpath) as newfile, open(goldpath) as goldfile:
                newcard = newfile.read()
                goldcard = goldfile.read()
                self.assertMultiLineEqual(newcard, goldcard)


if __name__ == '__main__':
    unittest.main()
