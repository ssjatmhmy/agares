# User Guide of Agares

## What is it:
  Agares is a back-testing tool for Chinese stock market, which can be used to test investment strategies or verify theories. Unlike futures or other markets, Chinese stock marker carries out a T+1 system. The regulations in Chinese stock marker allows us to take our time instead of reacting promptly. Thus, agares is not for real-time trading; it is instead a analysis tool that might cost a lot of time to see whether 
an trading idea is reasonalbe by reviewing its performance in the pass.  
  The framework of agares is simple and flexible. Besides technical approaches and value investing theory, you can also try the algorithms in machine learning theory. For example, if you believe that market sentiment is helpful, you can deploy natural language processing algorithms on netizen comments to perform sentiment analysis.

## Dependencies:
see requirements.txt

## File Organization:
agares: source files  
data: data files for back-testing and analysis  
report: store back-testing reports  
strategy: deploy user's personalized strategies  


## How to use it:
### Download candlestick data
  Agares uses tushare to download candlestick data (often abbreviated as 'cst' in the code). To download new data, run the script in /agares/datasource/cst_loader.py. If you want to use your own data, put them in the 'data/cst' folder and make sure they can be read by the following code
  
        pandas.read_csv(fname, index_col = 0, parse_dates = True, sep=',')    
        
where fname is your data file name and should be of the form '(code.name-period).csv'. For daily candlestick data, they should at least contain the dates and the close price column 'close'.

### Test your trading strategy
  To use agares to test your trading strategy, you need to write a strategy file. A strategy file is a .py file that contains a subclass of Strategy class, in which a class function 

        def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
            """
            Args:
                stocks: {code(str): PStock, }, where class PStock has the following members for user

                    PStock.cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
                            to store candlestick data of different periods. 'cst' is short for 'candlestick'
                    PStock.missing_cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
                            similar to .cst, it stores the missing candlestick data of different period type.
                            The reason that cause the missing cst would be stock suspension or something else.
                    PStock.ID: class StockID, which has two member: .code(str) and .name(str)

                    Note that both .cst and .missing_cst contain n_ahead extra daily data (see the description of 
                    n_ahead).
                    
                szTimeAxis(pd.DateTimeIndex): Time axis of sz, from dt_start to dt_end.
                n_ahead(int): Number of extra daily data. We add extra daily data (before start date) for computing 
                                    indexes such as MA, MACD. These may help to avoid nan at the beginning of indexes.
            """

should be implemented. Your idea should be described in this class function by calling the buy() and sell() API functions under user-designed conditions at a certain datetime. If you have finished the above work, just call the API ask_agares() in the main program, and everything would be done. When you run a strategy file, a back-testing report would be generated according to those buy/sell functions.

### Note:
*The code does not require installation. So please deploy your strategy file in the 'strategy' folder so that the program can find the report/data file path. The generated report of your strategy would be in the 'report' folder.*
 
## API for writting a strategy file:
The following APIs are designed for writing a strategy. Before using them, you should 
import them from agares.engine.ag. There are some demos in the 'strategy' folder that 
might be helpful.

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

        def sell(code, price, datetime, quantity):
            """
            Args: 
                datetime(str): trading time
                quantity(int): the number of shares (unit: boardlot) you want to sell	
            """

        def ask_agares(settings):
            """
            Do all the required work. 
            If a strategy class instance is given, it will perform back-testing, including checking settings, 
            creating trading system, running the back-testing, and generating the report.
            If an analysis class instance is given, it will perform analysis.
            Note that one should NOT provide both strategy class instance and analysis instance at the same time.  
            
            Args: 
                settings: {name(str): setting, }. a dictionary that includes all settings that agares needs. The items 
                          are as follows:
                          
                Items for strategy:
                'pstocks': pstocks(list), list of candlestick data files, each item represents a period data of a 
                         interested stock. pstocks could contain multiple stock of multiple type of period.
                'strategy': strategy(class Strategy), a trading strategy. It should be a subclass instance of the 
                                  Strategy class.
                'dt_start': dt_start(datetime), start datetime
                'dt_end': dt_end(datetime), end datetime
                 'n_ahead': n_ahead(int), number of extra daily data for computation (ahead of start datatime). We 
                      add extra daily data (before start date) for computing indexes such as MA, MACD. These 
                                  may help to avoid nan at the beginning of indexes.
                'capital': capital(float), Initial money for investment.
                'StampTaxRate': StampTaxRate(float), Usually 0.001. Only charge when sell. The program do not consider 
                      the fact that buying funds do not charge this tax. So set it to 0 if the 'pstocks' 
                      are ETF funds.
                'CommissionChargeRate': CommissionChargeRate(float), Usually 2.5e-4. The fact that commission charge 
                        is at least 5 yuan has been considered in the program.
                'PlotNetValue': PlotNetValue(boolean), If True, a net value curve of the strategy will be drawn along 
                      with a scaled sz daily close price curve after the back-testing.
                'PlotEquity': PlotEquity(boolean), If True, a simple graph of equity curve will be drawn after the 
                    back-testing.
                'ReturnEquity': ReturnEquity(boolean), Set to True if you want agares to return the variable df_equity 
                      (pd.DataFrame), which can be used to draw equity curve. 
         
                Items for analysis:
                'pstocks': pstocks(list), list of candlestick data files, each item represents a period data of a 
                         interested stock. pstocks could contain multiple stock of multiple type of period.
                'analysis': analysis(class Analysis). It should be a subclass instance of the Analysis class.
                'dt_start': dt_start(datetime), start datetime
                'dt_end': dt_end(datetime), end datetime
                'n_ahead': n_ahead(int), number of extra daily data for computation (ahead of start datatime). We 
                      add extra daily data (before start date) for computing indexes such as MA, MACD. These 
                                  may help to avoid nan at the beginning of indexes.
            """

### Download comments from SnowBall website
  SnowBall is a well-known investment website in China. You can obtain comments from this website and perform analysis with natural language processing/machine learning algorithms. To download comment data (often abbreviated as 'cmt' in the code), run the script /agares/datasource/SnowBallCmtCrawler.py.
  
### Perform analysis
  Agares allows you to verify some ideas that does not directly involve trading. These ideas would be something involving using natural language processing/machine learning algorithms to process your self-download data. To do so, you need to write an analysis file. A analysis file is a .py file that contains a subclass of Analysis class, in which a class function 

         def perform_analysis(self, stocks, szTimeAxis, n_ahead):
            """
            Args:
                stocks: {code(str): PStock, }, where class PStock has the following members for user

                    PStock.cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
                            to store candlestick data of different periods. 'cst' is short for 'candlestick'
                    PStock.missing_cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
                            similar to .cst, it stores the missing candlestick data of different period type.
                            The reason that cause the missing cst would be stock suspension or something else.
                    PStock.ID: class StockID, which has two member: .code(str) and .name(str)

                    Note that both .cst and .missing_cst contain n_ahead extra daily data (see the description of 
                    n_ahead).
                    
                szTimeAxis(pd.DateTimeIndex): Time axis of sz, from dt_start to dt_end.
                n_ahead(int): Number of extra daily data. We add extra daily data (before start date) for computing 
                                    indexes such as MA, MACD. These may help to avoid nan at the beginning of indexes.
            """

should be implemented. Similar to the strategy file, the cst data is available for your algorithm. However, the buy() and sell() API functions will be ignored and the back-testing report will not be generated. If you have implemented the required subclass, call the API ask_agares() in the main program.

### Note:
*Please deploy your analysis file in the 'analysis' folder.*
 
## API for writting an analysis file:
The API ask_agares() is the only indispensable API for an analysis file. Before using it, you should import it from agares.engine.ag. There are some demos in the 'analysis' folder that might be helpful.

If you want to use the comment data from the SnowBall website, agares has a loader class for you. Here is an example to show how to use it:

        from agares.datasource.SnowBallCmtLoader import SnowBallCmtLoader
        SBLoader = SnowBallCmtLoader()
        df_cmt = SBLoader.load('2016-02-14')
        print(df_cmt)
        
Make sure you have download the SnowBall cmt data before you load the data. If you have not download the data yet, use the script /agares/datasource/SnowBallCmtCrawler.py to do so.












