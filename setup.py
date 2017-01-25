from setuptools import setup

# pip install --editable --user .

setup(
    name='ps2vcard',
    version='0.1',
    py_modules=['ps2vcard'],
    install_requires=['Click','vobject','transitions'],
    entry_points="""
        [console_scripts]
        ps2vcard=ps2vcard:convert_all
    """
)
