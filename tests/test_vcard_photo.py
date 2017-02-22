#!/usr/bin/env python

import os
import os.path
import unittest
import urllib.request

import vobject


class TestVcardPhotoSerialize(unittest.TestCase):

    def setUp(self):
        self._dir = os.path.dirname(__file__)
        self.data_path = os.path.join(self._dir, 'data')
        self.golden_path = os.path.join(self._dir, 'golden')
        self.card = vobject.vCard()
        self.card.add('n')
        self.card.n.value = vobject.vcard.Name(family="Thecat", given="Felix")
        self.card.add('fn')
        self.card.fn.value = "Felix Thecat"
        self.photo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Felix_the_cat.svg/229px-Felix_the_cat.svg.png"  # noqa E501
        self.photo_path = os.path.join(self.data_path, 'felix-229.png')
        if not os.path.isfile(self.photo_path):
            urllib.request.urlretrieve(self.photo_url, self.photo_path)
        self.golden_filepath = os.path.join(self.golden_path, 'Felix.vcf')

    def test_serialize_plain(self):
        gold = '\r\n'.join(['BEGIN:VCARD', 'VERSION:3.0', 'FN:Felix Thecat',
                            'N:Thecat;Felix;;;', 'END:VCARD', ''])
        self.assertEqual(self.card.serialize(), gold)

    def test_add_photo_serialize_27(self):
        """add a photo and serialize (worked with the python 2.7 version)"""
        self.card.add('photo')
        with open(self.photo_path, 'rb') as f:
            self.card.photo.value = f.read()
        self.card.photo.encoding_param = "b"
        self.card.photo.type_param = "PNG"
        output = self.card.serialize()
        # with open('felix.vcf','w') as f:
        #     f.write(output)
        with open(self.golden_filepath, 'r', newline='\r\n') as f:
            expected_output = f.read()
        self.assertMultiLineEqual(output, expected_output)


if __name__ == '__main__':
    unittest.main()
