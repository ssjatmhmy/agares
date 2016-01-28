import os

class Output(object):
    def __init__(self, root, fname):
	try:
	    self._reportfile = open(os.path.join(root, fname), 'wt')
	except IOError:
	    self._reportfile = None
	    print "IOError: report file will not be created."
    	    pass
	# write blank lines so that the front lines are left for the most useful results
	self._reportfile.write(' '*100000 + '\n')

    def printsf(self, statement):
        """
        Print statement on screen and write it into reportfile
	Args:
	    statement(str)
	"""
	print statement
	if self._reportfile:
	    self._reportfile.write(statement+'\n') 

    def seek(self, offset):
	if self._reportfile:
	    self._reportfile.seek(offset)	

    def close(self):
	if self._reportfile:
	    self._reportfile.close()
	
