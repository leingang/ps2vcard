#!/usr/bin/env python

from glob import glob
import os.path
from os.path import basename
from subprocess import check_call
from tempfile import TemporaryDirectory
import unittest


class TestPs2Vcard(unittest.TestCase):
    """Test the ps2vcard script.

    Parses the `Faculty_Center.html` frameset file (and referenced files)
    and produces vcards in a temporary.  Tests each against those in the
    "golden" directory

    TODO: add a --meld flag to overwrite generated files as golden files.
    Check for extra generated cards.
    """

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
            with open(newpath) as newfile, open(goldpath) as goldfile:
                newcard = newfile.read()
                goldcard = goldfile.read()
                self.assertMultiLineEqual(newcard, goldcard)


if __name__ == '__main__':
    unittest.main()
