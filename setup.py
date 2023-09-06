from setuptools import setup

# pip install --editable --user .

setup(
    name='ps2vcard',
    version='0.1',
    py_modules=['ps2vcard'],
    install_requires=['Click', 'vobject', 'transitions','bs4','lxml'],
    entry_points="""
        [console_scripts]
        ps2vcard=ps2vcard.cli:convert_all
        ps2vcard-old=ps2vcard.cli:convert_all_from_frameset
        ps2anki=ps2vcard.cli:convert_to_anki
        ps2amc=ps2vcard.cli:convert_to_amccsv
        psxls2amc=ps2vcard.cli:convert_xls_to_amccsv
    """
)
