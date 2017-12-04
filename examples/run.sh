#!/bin/bash
## Usage: ./replay.sh

OUTPUT="http://192.168.100.123:8000"
MIDDLEWARE="./middleware_wrapper.sh"
#MIDDLEWARE="./middleware_echo.py"
INPUT_FILE="filtered_0.gor"

#sudo ./goreplay --input-file $INPUT_FILE --output-file="dev/debug.gor" --prettify-http  &> test.log
#sudo ./goreplay --input-file $INPUT_FILE --output-file="dev/debug.gor" --middleware $MIDDLEWARE --prettify-http  > test.out 2> test.err
sudo ./goreplay --input-file $INPUT_FILE --input-file-loop --output-http=$OUTPUT --middleware $MIDDLEWARE --prettify-http --output-http-track-response  > test.out
