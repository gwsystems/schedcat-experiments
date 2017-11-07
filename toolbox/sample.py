
def value_range(start, max, step):
    x  =  start
    while x <= max:
        yield x
        x += step
