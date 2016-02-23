# @file new_extreme_strategy_demo.py
# @brief The new extreme strategy demo

import ipdb
from datetime import datetime
from talib import (MA, MACD)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(fdir)[0]
import sys
sys.path.append(root)
from agares.engine.ag import (
    Strategy,
    buy,
    sell,
    ask_agares)


class new_extreme_Strategy(Strategy):
    """ 
    The new extreme strategy on daily candlestick data.
    Buy an asset when close price rises above the highest price in last m days,
    and sell it when close price falls under the lowest price in last m days.
    """
    def __init__(self, name, m):
        super(new_extreme_Strategy, self).__init__(name)
        self.m = m

    @staticmethod
    def ExtremePrice(close, m):
        """
        Return highest and lowest prices of the last m timeunit.
        Note that both return variables (highest and lowest) start 
        from the (m+1)-th timeunit. The first m-th timeunit are np.nan

        Return:
            highest(np.ndarray)
            lowest(np.ndarray)
        """
        window = []
        highest = np.zeros(len(close)) 
        lowest = np.zeros(len(close)) 
        for i, price in enumerate(close):
            if i < m: 
                highest[i], lowest[i] = np.nan, np.nan # skip m timeunit.
                window.append(close[i])		
                continue 
            # note that both highest and lowest start from the (m+1)-th timeunit
            # the first m-th timeunit are np.nan
            highest[i] = np.max(window)
            lowest[i] = np.min(window)
            window.pop(0)
            window.append(close[i])
        return highest, lowest

    def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
        assert len(stocks) == 1, "This strategy allows only a daily candlestick data of one stock."
        code = next(iter(stocks))
        cst = stocks[code].cst # get candlestick data
        DataTimeAxis = cst['1Day'].index
        close = cst['1Day']['close'].values

        # ExtremePrice
        highest, lowest = self.ExtremePrice(close, self.m)

        # skip extra data
        TimeAxis = DataTimeAxis[n_ahead:]
        df_extreme = pd.DataFrame({'close': close[n_ahead:], 'highest': highest[n_ahead:], \
                                'lowest': lowest[n_ahead:]}, index = TimeAxis)

        #df_extreme.plot()
        #plt.show()
        hold_flag = 0
        for ticker in TimeAxis:
            # skip null value at the beginning
            if np.isnan(df_extreme.at[ticker, 'highest']) or np.isnan(df_extreme.at[ticker, 'lowest']):
                continue 
            # start trading
            price = cst['1Day'].at[ticker,'close']
            if (hold_flag == 0) and (df_extreme.at[ticker, 'close'] > df_extreme.at[ticker, 'highest']): 
                # quantity is the number of shares (unit: boardlot) you buy this time 
                quantity, _, _ = buy(code, price, str(ticker), ratio = 1) 
                hold_flag = 1
            if (hold_flag == 1) and (df_extreme.at[ticker, 'close'] < df_extreme.at[ticker, 'lowest']): 
                # sell all the shares bought last time
                sell(code, price, str(ticker), quantity) 
                hold_flag = 0


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create a trading strategy
    strategy = new_extreme_Strategy('The new extreme strategy no.1', 10)
    # set start and end datetime
    dt_start, dt_end = datetime(1997,1,1), datetime(2016,1,26)
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 80
    # capital:        Initial money for investment
    capital = 100000000
    # StampTaxRate:   Usually 0.001. Only charge when sell.
    #                 The program do not consider the fact that buying funds do not charge this tax.  
    #                 So set it to 0 if the 'pstocks' are ETF funds.
    StampTaxRate = 0.001
    # CommissionChargeRate:   Usually 2.5e-4. The fact that commission charge is at least 5 yuan has
    #                         been considered in the program.
    CommissionChargeRate = 2.5e-4
    # set to True if you would like to see the Plot of net value after the back-testing
    PlotNetValue = True

    settings = {'pstocks': pstocks, 'strategy': strategy, 'dt_start': dt_start, 'dt_end': dt_end,
                'n_ahead': n_ahead, 'capital': capital, 'StampTaxRate': StampTaxRate, 
                'CommissionChargeRate': CommissionChargeRate, 'PlotNetValue': PlotNetValue}
    ask_agares(settings)
