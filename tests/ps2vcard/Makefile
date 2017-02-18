define MOCK_SCRIPT
import csv
import os.path
from os.path import basename
from jinja2 import Template

def fix(s):
    """fix up the student record for templating"""
    try:
        (url,query) = s['photo'].split('?')
        s['photo_filename'] = basename(url)
    except ValueError:
        pass
    s['Program and Plan'] = s['Program and Plan'].replace('\\n','\n')
    return s

students = []
dirname = 'Faculty Center_files'
with open('mock.csv','r') as f, open(os.path.join(dirname,'template.html'),'r') as tf:
    t = Template(tf.read())
    for student in csv.DictReader(f):
        students.append(fix(student))
with open(os.path.join(dirname,'SA_LEARNING_MANAGEMENT.SS_FACULTY.html'),'w') as f:
    f.write(t.render(students=students))
print("OK")
endef
export MOCK_SCRIPT

mock: ## Make mock input
	@python -c "$$MOCK_SCRIPT"

test:
	./test_ps2vcard.py
