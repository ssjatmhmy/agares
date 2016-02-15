import pandas as pd
import tushare as ts

df = ts.get_stock_basics()
print(df['name'])
df['name'].to_csv('stock_name', index=False)
