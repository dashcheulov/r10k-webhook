import pytest
from urllib.request import urlopen
from urllib.error import HTTPError
from r10kwebhook import webserver


def test_api():
    class Handlers(object):

        @webserver.path('/test')
        def test(self, data):
            return 'test'

    # websrv = webserver.WebServer()
    # websrv.register_handlers(Handlers())
    # try:
    #     assert urlopen('http://localhost:8088/test').read().decode() == 'test'
    #     with pytest.raises(HTTPError) as excinfo:
    #         urlopen('http://localhost:8088/other').read().decode()
    #     assert str(excinfo.value) == 'HTTP Error 404: Not Found'
    # finally:
    #     websrv.stop()
