class Error(BaseException):
    def __init__(self,*args,**kwargs):
        super(Error, self).__init__(*args,**kwargs)
        self.msg = args[0]
        self.origin_exception = kwargs.get('origin',None)

    def str(self):
        sb = [str(self.msg)]
        if self.origin_exception:
            sb.append(f'caused by: {self.origin_exception}')
        return '; '.join(sb)
