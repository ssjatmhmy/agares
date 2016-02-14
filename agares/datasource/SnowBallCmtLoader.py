import pandas as pd
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(os.path.split(fdir)[0])[0]
import sys 
sys.path.append(root)

class SnowBallCmtLoader(object):
    def __init__(self):
        pass
        
    def load(self, date):
        fname = date+'.csv'
        cmtfilepath = os.path.join(root, 'data', 'SnowBall_cmt', fname)
        try:
            df_cmt = pd.read_csv(cmtfilepath, sep='%_%', encoding="utf-8", engine='python')
        except IOError:
            print('IOError: cmtdata of date {:s} does not exist. Please download the cmtdata first.'.format(date))
            return None
        else:
            return df_cmt
