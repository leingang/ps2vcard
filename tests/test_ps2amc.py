#!/usr/bin/env python

import csv
import os.path
from subprocess import Popen, PIPE
import unittest

from jinja2 import Template


class TestPs2Amc(unittest.TestCase):

    def setUp(self):
        self._dir = os.path.dirname(__file__)
        self.data_path = os.path.join(self._dir, 'data')
        self.golden_path = os.path.join(self._dir, 'golden')
        self.infile = os.path.join(self.data_path, 'ps.csv')
        self.inxlspath = os.path.join(self.data_path, 'ps.xls')
        self.expected_outfile = os.path.join(self.golden_path, 'amc.csv')

    def mock_psxls(self):
        """ Mock up the ps.xls file.

        This method is not a real test and doesn't need to be run often.
        It won't be discovered by running this module on the command line,
        or with `nose`.  To run it, execute

            $ python -m unittest test_ps2amc.TestPs2Amc.mock_psxls

        on the command line.
        """
        input_path = os.path.join(self.data_path, 'mock.csv')
        template_path = os.path.join(self.data_path, 'psxlst.html')
        output_path = os.path.join(self.data_path, 'ps.xls')

        def fix(s):
            s['Program and Plan'] \
                = s['Program and Plan'].replace('\\n\\n', '\n\r')
            return s

        with open(input_path) as data_fh, open(template_path) as template_fh:
            template = Template(template_fh.read())
            students = [fix(student) for student in csv.DictReader(data_fh)]
        with open(output_path, 'w') as output_fh:
            output_fh.write(template.render(students=students))
        self.assertTrue(os.path.exists(output_path))

    def mock_pscsv(self):
        """ Mock up the ps.csv file.

        This method is not a real test and doesn't need to be run often.
        It won't be discovered by running this module on the command line,
        or with `nose`.  To run it, execute

            $ python -m unittest test_ps2amc.TestPs2Amc.mock_pscsv

        on the command line.
        """
        # csvfix order -f 2,3,5,9,10,11,12,13,14,15,16,17,18 mock.csv > ps.csv
        input_path = os.path.join(self.data_path, 'mock.csv')
        output_path = os.path.join(self.data_path, 'ps.csv')
        fields = [2, 3, 5, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
        with open(input_path) as infile, open(output_path, 'w') as outfile:
            writer = csv.writer(outfile)
            for line in csv.reader(infile):
                writer.writerow([line[field - 1] for field in fields])
        self.assertTrue(os.path.exists(output_path))

    def test_ps2amc(self):
        with Popen(['ps2amc', self.infile],
                   universal_newlines=True, stdout=PIPE).stdout as output,\
                open(self.expected_outfile) as expected_output:
            for expected_line in expected_output:
                line = output.readline()
                self.assertEqual(line, expected_line)

    def test_psxls2amc(self):
        with Popen(['psxls2amc', self.inxlspath],
                   universal_newlines=True, stdout=PIPE).stdout as output,\
                open(self.expected_outfile) as expected_output:
            for expected_line in expected_output:
                line = output.readline()
                self.assertEqual(line, expected_line)


if __name__ == '__main__':
    unittest.main()
