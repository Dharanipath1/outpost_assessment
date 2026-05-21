__version__ = "0.0.1"

import sys
try:
	from . import payment
	sys.modules["payment"] = payment
except ImportError:
	pass



