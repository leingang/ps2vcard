#!/usr/bin/env python

import os.path
import tempfile
from subprocess import Popen,PIPE
import unittest

class TestPs2Amc(unittest.TestCase):

    def setUp(self):
        self.dirname = 'ps2amc'
        self.infile = os.path.join(self.dirname,'ps.csv')
        self.expected_outfile = os.path.join(self.dirname,'amc.csv')

    def test_ps2amc(self):
        with Popen(['ps2amc',self.infile],
                universal_newlines=True,stdout=PIPE).stdout as output,\
             open(self.expected_outfile) as expected_output:
            for expected_line in expected_output:
                line = output.readline()
                self.assertEqual(line,expected_line)

if __name__ == '__main__':
    unittest.main()
