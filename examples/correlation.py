# -*- coding: utf-8 -*-
import sys

from gor.middleware import TornadoGor

"""
Stores prometheus counters and provides an interface to push metrics with custom labels
"""

TOKEN_NAME = 'JSESSIONID'


class Tokens:
    def __init__(self):
        self.tokens = {}

    def get_token_value(self, name, original_value):
        """
        Retrieves the latest observed value for the specified token, original_value pair.
        :param name: The name of the token to look for.
        :param original_value: The value of the token in the original response gathered during the recording
        :return value: the value of the token in the last replayed sample of an epmty string
        :return err: 0 if the new value of the token was found, 1 if the token has not been found
        """
        if name in self.tokens:
            if original_value in self.tokens[name]:
                return self.tokens[name][original_value], 0
            elif None in self.tokens[name]:
                return self.tokens[name][None], 0
        return "", 1

    def observe_token_value(self, name, observed_value, original_value=None):
        """
        Observe a new value for the specified token, optionally the original token value observed when recording
        can be specified for correlation
        :param name: The name of the observed token
        :param observed_value: The value of the observed token
        :param original_value: (Optional) the original_value of the token
        """
        if observed_value is None and original_value is None:
            return
        if name not in self.tokens:
            self.tokens[name] = {}
        self.tokens[name][original_value] = observed_value


def log(msg):
    """
    Logging to STDERR as STDOUT and STDIN used for data transfer
    @type msg: str or byte string
    @param msg: Message to log to STDERR
    """
    try:
        msg = str(msg) + '\n'
    except:
        pass
    sys.stderr.write(msg)
    sys.stderr.flush()


def on_request(proxy, msg, **kwargs):
    tokens = kwargs['tokens']
    # TODO: modify token if necessary
    proxy.on('response', on_response, idx=msg.id, req=msg, tokens=tokens)
    log("Processing Request: {}".format(msg.id))

    # Modify the token
    request_cookie = proxy.http_cookie(msg.http, TOKEN_NAME)
    if request_cookie is not None:
        updated_token, _ = tokens.get_token_value(TOKEN_NAME, request_cookie)
        log("Modifying {} Cookie from {} to {}".format(TOKEN_NAME, request_cookie, updated_token))
        new_msg = msg
        new_msg.http = proxy.set_http_cookie(msg.http, TOKEN_NAME, updated_token)
        return new_msg


def on_response(proxy, msg, **kwargs):
    tokens = kwargs['tokens']
    proxy.on('replay', on_replay, idx=kwargs['req'].id, req=kwargs['req'], resp=msg, tokens=tokens)


def on_replay(proxy, msg, **kwargs):
    tokens = kwargs['tokens']

    # Look for tokens to be saved in the Set-Cookie of the response
    request_cookie = proxy.http_cookie(kwargs['req'].http, TOKEN_NAME)
    original_response_cookie = proxy.http_cookie(kwargs['resp'].http, TOKEN_NAME, header_name='Set-Cookie')
    replayed_response_cookie = proxy.http_cookie(msg.http, TOKEN_NAME, header_name='Set-Cookie')
    tokens.observe_token_value(TOKEN_NAME, replayed_response_cookie, original_response_cookie)

    # Debug
    log("Replayed Response")
    log("Request ID: {}".format(msg.id))
    log("Request Cookie: {} ".format(request_cookie))
    log("Original Response Set-Cookie: {} ".format(original_response_cookie))
    log("Replayed Response Set-Cookie: {} ".format(replayed_response_cookie))

    # Check Status consistency between original response and replay
    replay_status = proxy.http_status(msg.http)
    resp_status = proxy.http_status(kwargs['resp'].http)
    if replay_status != resp_status:
        log('replay status [%s] diffs from response status [%s]\n' % (replay_status, resp_status))
    else:
        log('replay status is same as response status\n')
    # log('Received Response {}'.format(msg.http))


if __name__ == '__main__':
    toks = Tokens()
    proxy = TornadoGor()
    proxy.setup_prometheus(enable=True, port=8000)
    log('Starting Proxy')
    proxy.on('request', on_request, tokens=toks)
    proxy.run()
