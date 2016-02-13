# @file SnowBall_comments_analysis_demo.py
# @brief analysis the topics at certain time in the SnowBall website

import ipdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(fdir)[0]
import sys 
sys.path.append(root)
from agares.engine.ag import (
    Analysis,
    ask_agares)


class SnowBallCommentsAnalysis(Analysis):
    """ 
    Analysis the topics at certain time in the SnowBall website
    """
    def __init__(self, name):
        super(SnowBallCommentsAnalysis, self).__init__(name)

    def perform_analysis(self, stocks, szTimeAxis, n_ahead):
        cmtfilepath = os.path.join(root, 'data', 'cmt', '2454158445')
        print cmtfilepath
        df_cmt = pd.read_csv(cmtfilepath, sep='%_%', encoding="utf-8", engine='python')
        print df_cmt

if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create an analysis class
    analysis = SnowBallCommentsAnalysis('SnowBall Comments Analysis')
    # set start and end datetime
    dt_start, dt_end = datetime(1997,1,1), datetime(2016,1,26)
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 80

    settings = {'pstocks': pstocks, 'analysis': analysis, 'dt_start': dt_start, 'dt_end': dt_end,
                'n_ahead': n_ahead}
    ask_agares(settings)



