import os
import pandas as pd
import numpy as np
from agares.errors import PeriodTypeError, FileDoesNotExist

def parse_cst_filename(pstock):
    """
    Read information in candlestick data file name 

    Args:
	pstock: candlestick data file name (do NOT contain the path and the suffix '.csv')
		the 'p' in 'pstock' is short for 'period'
    Returns:
        ID: class StockID
        period: class PeriodInfo
    """
    t = pstock.split('-')
    if len(t) == 2:
	# get ID
        ID, period = StockID(t[0]), t[1]
	# check the type of period in file name
	Periods = ["1Minute", "5Minute", "15Minute", "30Minute", "60Minute", 
			"1Day", "1Week", "1Month"]
        if period not in Periods:
            raise PeriodTypeError
    else:
        assert False, "Candlestick File: {:s}.csv is not in the correct format <code.name-period>".format(pstock)
    return ID, period


class StockID(object):
    """ 
    StockInfo

    :ivar code: stock code
    :ivar name: stock name
    """
    def __init__(self, str_stock):
        info = str_stock.split('.')
        if len(info) == 2:
            self.code = info[0]
            self.name = info[1] 
        else:
            assert False

    def __str__(self):
        return "%s.%s" % (self.code, self.name)


class PStock(object):
    """ 
    stock with period information
    """
    def __init__(self, pstock, dt_start, dt_end, n_ahead):
	# .cst: to store candlestick data of different periods
	# .cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
	self.cst = {}
	# .missing_cst: similar to .cst, to store missing candlestick data of different period type
	# .missing_cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
	self.missing_cst = {}
	# read information in file name
        # .ID: class StockID, .period: class PeriodInfo
        self.ID, self.period = parse_cst_filename(pstock) 
	# load candlestick data in file <pstock>
	self.load_cst(pstock, dt_start, dt_end, n_ahead)

    def __str__(self):
        """ return string like '510300.300etf-1Minute'  """
        return "%s-%s" % (self.ID, self.period)


    def load_cst(self, pstock, dt_start, dt_end, n_ahead):	    
        """
	Load candlestick data

        Args:
	    pstock(str): period candlestick data filename
	    dt_start(datetime): start time
	    dt_end(datetime): end time
	Returns:
	    pd.DataFrame, i.e., candlestick data
  	"""
	_, period = parse_cst_filename(pstock) 
	try:
	    return self.cst[period]
	except KeyError:
	    fdir = os.path.split(os.path.realpath(__file__))[0]
        root = os.path.split(fdir)[0]
        datapath = os.path.join(root, 'data', 'cst')
        fname = os.path.join(datapath, pstock + ".csv")
        try:
	        cst_data = pd.read_csv(fname, index_col = 0, parse_dates = True, sep=',')
        except IOError:
            raise FileDoesNotExist(file = fname)
        else:
            # check whether we have the require data
            dt_start = pd.to_datetime(dt_start)
            dt_end = pd.to_datetime(dt_end)
            File_dt_start, File_dt_end = cst_data.index[0], cst_data.index[-1] 
            assert dt_start >= File_dt_start, \
	            "Candlestick Data do not exist before {0:s}".format(str(File_dt_start))
            assert dt_end <= File_dt_end, \
	            "Candlestick Data do not exist after {0:s}".format(str(File_dt_end))
            # start to select data
            index = np.arange(len(cst_data.index))
            select = index[(dt_start <= cst_data.index) & (cst_data.index <= dt_end)]	
            # add (n_head) extra data for strategy computation 
            assert select[0] >= n_ahead, \
	            "Not enough extra candlestick data. Try turn down variable: n_ahead."
            start_index = select[0] - n_ahead
            end_index = select[-1] + 1
            cst_data = cst_data.iloc[start_index: end_index]
            assert cst_data.index.is_unique
            # load data
            self.cst[period] = cst_data

