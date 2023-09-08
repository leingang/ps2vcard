import re

def unpack_progplan(progplan):
    """unpack a `progplan` string into program and plan.

    >>> unpack_progplan("UA-Coll of Arts & Sci - \n\nUndecided")
    ['UA-Coll of Arts & Sci','Undecided']
    """
    return re.split(" - \n+", progplan)
