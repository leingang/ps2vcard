#!/usr/bin/env python

import base64
import os
import vobject
import unittest
import urllib.request

class TestVcardPhotoSerialize(unittest.TestCase):

    def setUp(self):
        self.card=vobject.vCard()
        self.card.add('n')
        self.card.n.value=vobject.vcard.Name(family="Thecat",given="Felix")
        self.card.add('fn')
        self.card.fn.value="Felix Thecat"
        if not os.path.isfile("felix-229.png"):
            urllib.request.urlretrieve("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Felix_the_cat.svg/229px-Felix_the_cat.svg.png","felix-229.png")

    def test_serialize_plain(self):
        self.assertEqual(self.card.serialize(),"""BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Felix Thecat\r\nN:Thecat;Felix;;;\r\nEND:VCARD\r\n""")

    def test_add_photo_serialize_27(self):
        """add a photo and serialize (worked with the python 2.7 version)"""
        self.card.add('photo')
        with open("felix-229.png",'rb') as f:
            self.card.photo.value = f.read()
        self.card.photo.encoding_param = "b"
        self.card.photo.type_param = "PNG"
        output = self.card.serialize()
        # with open('felix.vcf','w') as f:
        #     f.write(output)
        with open('felix.vcf','r',newline='\r\n') as f:
            expected_output=f.read()
        self.assertEqual(output,expected_output)


if __name__ == '__main__':
    unittest.main()
