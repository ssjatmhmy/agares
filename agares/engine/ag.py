import ipdb
from datetime import datetime
from agares.engine.execute_unit import ExecuteUnit
import matplotlib.pyplot as plt
from abc import ABCMeta, abstractmethod
import pandas as pd

# global
ag_simulator = None

def create_trading_system(strategy, pstocks, dt_start, dt_end, n_ahead, settings = {}):
    """
    Args:
    	pstocks([str,]): list of candlestick data files, each item represents \             
                         a period data of a interested stock
    	dt_start(str): start datetime
    	dt_end(str): end datetime
    """
    global ag_simulator
    ag_simulator = ExecuteUnit(pstocks, dt_start, dt_end, n_ahead)
    ag_simulator.add_strategy(strategy, settings)


def run():
    ag_simulator.run()


def buy(code, price, datetime, **kargs):
    """
    Args: 
	kargs(optional): You have two choices, position or ratio (both within (0,1])
			 Below are some detail descriptions.

        		 position(float): the proportion of the capital that you would like to bid. 	
		                          Note that the capital is the initial money amount and is 
		                          a contant once set at the beginning.
			 ratio(float): the proportion of the current cash that you would like to bid. 	
			               Note that the current cash is the money in your account and 
				       would vary during the back test.
    Return:
	quantity(int): the number of shares (unit: boardlot) you buy this time
    """
    if kargs.has_key('ratio'):
	quantity = ag_simulator.buy_ratio(code, price, datetime, ratio = kargs['ratio'])  
    elif kargs.has_key('position'):   
        quantity = ag_simulator.buy_position(code, price, datetime, position = kargs['position']) 
    else:
	print "Warning: ratio/position not given in buy(). Using default: position = 1."
	quantity = ag_simulator.buy_position(code, price, datetime, position = 1) 
    ag_simulator.trading_stocks.add(code)
    return quantity


def sell(code, price, datetime, quantity):
    """
    Args: 
        datetime(str): trading time
        quantity(int): the number of shares (unit: boardlot) you want to sell	
    """
    ag_simulator.sell(code, price, datetime, quantity)
    ag_simulator.trading_stocks.add(code)


def report(ReturnEquity = False, PlotEquity = False, PlotNetValue = False):
    """
    Args:
	ReturnEquity(boolean): set to True if you want to return the variable 
                            df_equity(pd.DataFrame), which can be used to draw
			    equity curve. 
	PlotEquity(boolean): If True, a simple graph of equity curve will be drawn.
	PlotNetValue(boolean): If True, a net value curve of the strategy will be 
			       drawn along with a scaled sz daily close price curve.
    """
    df_equity = ag_simulator.report()
    if ReturnEquity:
        return df_equity
    if PlotEquity: # plot equity
        df_equity['equity'].plot()
    	print "Plot of equity curve is shown."
    	plt.show()
    if PlotNetValue:
	init_equity = df_equity['equity'].values[0]
	init_sz = df_equity['sz'].values[0]
	net_value = df_equity['equity'].values/float(init_equity)
	scaled_sz = df_equity['sz'].values/float(init_sz)
	df_nv = pd.DataFrame({'Net value': net_value, 'scaled sz': scaled_sz}, index = df_equity.index)
	df_nv.plot()
	print "Plot of net value curve is shown."
	plt.show()
	


class Strategy(object):
    """
    Base class of strategy
    """
    __metaclass__ = ABCMeta

    def __init__(self, name):
	self.name = name

    @abstractmethod
    def compute_trading_points(self, cst, actual_ahead):
	"""
	Args:
            cst(pd.DataFrame): The variable name 'cst' is short for 'candlestick'
            actual_ahead(int): Number of extra daily data. We add extra daily data 
                        (before start date) for computing indexes such as MA, MACD. 
			These may help to avoid nan at the beginning of indexes.
			It can be set at the main program (var: n_ahead). However, 
			it would be smaller than you set because of lack of data.
			That's why we use a different variable name from that of main
			program.
	"""
	pass

