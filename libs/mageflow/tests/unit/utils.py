import inspect


def sub_classes(cls: type):
    for t in cls.__subclasses__():
        if not inspect.isabstract(t):
            yield t
        yield from sub_classes(t)
