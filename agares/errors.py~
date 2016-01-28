class QError(Exception):
    msg = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.message = str(self)
        

    def __str__(self):
        msg = self.msg.format(**self.kwargs)
        return msg

    __repr__ = __str__

class FileDoesNotExist(QError):
    msg = "File:{file} does not exist" 

class PeriodTypeError(QError):
    msg = "Period type does not exist"

class NotEnoughMoney(QError):
    msg = "Not enough money to continue. Need: {need_cash}, only have: {cash}."

class BidTooLow(QError):
    msg = "Your bid was too low for one board lot. Need: {need_cash}, you bid is {bid}"

class CanNotSplitShare(QError):
    msg = "You only have one share currently and can not be split.\n Try set ratio in sell() to 1."

