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
    The new extreme strategy with risk control and position management (PM) on daily candlestick data.
    state 0: Prepare to buy some asset with a proportion of your cash. This proportion is called
    first position.
    state 1: Buy an asset with first position when the close price rises above the highest price 
             in last m days. If the loss of this part of money reach certain ratio, sell it; 
             otherwise wait until you have a small amount of floating profits. Then enter state 2.
    state 2: Sell all when you lose all your floating profits or when the close price falls under 
             the lowest price in last m days.
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

        # set position management and Risk control parameters
        # the proportion of your current cash for the first investment (if you earn
        # some profits, you would invest the rest of the cash).
        first_position = 0.25
        # stop_loss: stop out when your loss of 1th position reach this proportion 
        stop_loss = 0.04
        # lock_profit: if your floating earn of 1th position reach this proportion,
        #              enter state 2: sell all at a proper time that before you 
        #              lose the profits.
        lock_profit = 0.03

        # start
        start_flag = 0
        state_flag = 0
        for ticker in TimeAxis:
            # skip null value at the beginning
            if np.isnan(df_extreme.at[ticker, 'highest']) or np.isnan(df_extreme.at[ticker, 'lowest']):
                continue 
            # start trading
            price = cst['1Day'].at[ticker,'close']
            if (state_flag == 0) and (df_extreme.at[ticker, 'close'] > df_extreme.at[ticker, 'highest']): 
                # quantity is the number of shares (unit: boardlot) you buy this time 
                # record quantity1
                quantity1, _, _ = buy(code, price, str(ticker), ratio = first_position) 
                price1 = price # record the first buying price
                state_flag = 1
            if state_flag ==1:
                floating_earn_rate = (price - price1)/price1
                if floating_earn_rate <= -stop_loss:
                    # stop out
                    sell(code, price, str(ticker), quantity1)
                    state_flag = 0
                elif floating_earn_rate >= lock_profit:
                    # enter state 2: lock in profits
                    # record quantity2
                    quantity2, _, _ = buy(code, price, str(ticker), ratio = 1) 
                    price2 = first_position * price1 + (1-first_position) * price
                    state_flag = 2
                else: # just wait
                    pass
            if state_flag == 2:
                if (price < price2) or (df_extreme.at[ticker, 'close'] < df_extreme.at[ticker, 'lowest']): 
                    # sell all the shares bought last time
                    sell(code, price, str(ticker), quantity1 + quantity2) 
                    state_flag = 0


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create a trading strategy
    strategy = new_extreme_Strategy('The new extreme strategy with PM', 10)
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
