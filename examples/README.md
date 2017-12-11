# GoReplay Python Middleware

This is an example implementation of a GoReplay middleware based on [https://github.com/amyangfei/GorMW](https://github.com/amyangfei/GorMW). The is extension includes a Prometheus exporter that can be used to track the 
replayed traffic and APIs for token correlation logic.

## Exposing metrics

The plugin exposes metrics in the following format using a Bucket for replayed responses and applying labels for HTTP methog (e.g. GET, POST), HTTP Status (e.g. 200, 404, 500 (hopefully not) ) and HTTP path (e.g. /home, 
/console). 
``` 
responses_latency_bucket{http_method="GET",http_path="/console",http_status="200",le="1.0"} 0.0 responses_latency_bucket{http_method="GET",http_path="/console",http_status="200",le="2.5"} 0.0 
responses_latency_bucket{http_method="GET",http_path="/console",http_status="200",le="5.0"} 230.0 responses_latency_bucket{http_method="GET",http_path="/console",http_status="200",le="7.5"} 565.0 
responses_latency_bucket{http_method="GET",http_path="/console",http_status="200",le="10.0"} 649.0 responses_latency_bucket{http_method="GET",http_path="/console",http_status="200",le="+Inf"} 727.0 
responses_latency_count{http_method="GET",http_path="/console",http_status="200"} 727.0 responses_latency_sum{http_method="GET",http_path="/console",http_status="200"} 4631.674593999971 
```

##  Token Correlation

Token correlation is still a WIP, currently we have implemented two API, namely `observe_token_value` which should be used when a replayed response is received to save the new value of a Token (e.g. a new value for the 
JSESSIONID) and the `get_token_value` which should be used when modifying requests to inject the observed token. We are currently facing an issue with the asynchronous nature of GoReplay which makes it hard to correlate requests 
when the target system slows down, the issue is tracked [here](https://github.com/buger/gor/issues/154) 

The main problem we are facing is the Open Loop asynchronous nature of GoReplay which might cause problems to the correlation when the system against we are replaying the recorded traffic is slower than the original one. 
In such a case the following sequence of events might occur. 

The recorded sequence of events looks like: 
![Record](https://github.com/GiovanniPaoloGibilisco/GorMW/blob/master/docs/record.png)

While the replay looks like:
![Record](https://github.com/GiovanniPaoloGibilisco/GorMW/blob/master/docs/replay.png)

In this case the server is not quick enough to send the response to the first request (the one that allows the creation of the JSESSIONID) so the second request is still using the same JSESSIONID used in the recording which is not valid for the target system

An example can of such ha behavior on a real system can be observed in this [Gist](https://gist.github.com/GiovanniPaoloGibilisco/cbee0dcacf7d5549d7691b4754f7016d) obtained with the sample echo middleware enriched with timestamps taken when the request is submitted to the middleware from GoReplay
In particular request `ef46234f491d96fd9822ee0906b77ea0534c6717` took about 2 seconds to complete on the original system while it took more than 5 seconds during the replay. 
Since subsequent requests are forwarded to the middleware in an asynchronous way they can not be modified using content of the replayed response for that request which is available only later on. 
 

## Installation 
This middleware implementation depends on the python library for GoReplay and the python 
client for prometheus that can be installed by: 

```
    $ pip install prometheus_client
    $ git clone https://github.com/amyangfei/GorMW
    $ cd GorMW && python setup.py install 

``` 

## Running 
You can launch GoReplay using the middleware like this: 

```
# INPUT_FILE Should be a valid recording containing both requests and responses. 
# OUTPUT Sould be you desired http output server (e.g. http://localhost:8000) 
# MIDDLEWARE should be the executable used to launch the middleware

MIDDLEWARE=middleware_wrapper.sh 
sudo ./goreplay --input-file $INPUT_FILE --input-file-loop --output-http=$OUTPUT --middleware $MIDDLEWARE --prettify-http --output-http-track-response 
```
