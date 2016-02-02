import os

class Output(object):
    def __init__(self, root, fname):
	try:
	    self._reportfile = open(os.path.join(root, fname), 'wt')
	    self.ReportFileExist = True
	except IOError:
	    self.ReportFileExist = False
	    print "IOError: Report file can not be created."
	    pass
	else:
	    # write blank lines so that the front lines are left for the most useful results
	    self._reportfile.write(' '*100000 + '\n')

    def report(self, statement):
        """
        Print statement on screen and write it into reportfile

	Args:
	    statement(str)
	"""
	print statement
	if self.ReportFileExist:
	    self._reportfile.write(statement+'\n') 

    def seek(self, offset):
	if self.ReportFileExist:
	    self._reportfile.seek(offset)	

    def close(self):
	if self.ReportFileExist:
	    self._reportfile.close()

    def account(self, shares, cash):
	"""
	Print current equity in the account

	Args:
	    shares: {code(str): quantity(int), }
	    cash: float
	"""	
	if shares:
            self.report("shares: ")
	    self.report("code" + " "*10 + "quantity (Board Lot)")
	    for code in shares.keys():
	        self.report("{0: ^14}{1:d} ".format(code, shares[code]))
	self.report("cash: {:.2f}".format(cash))

	
