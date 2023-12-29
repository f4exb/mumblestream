# Mumblestream / Mumblelistener
A bot that streams host audio to/from a Mumble server.

The bot uses PortAudio which works together with Jack, ALSA, OSS, PulseAudio, WASAPI, and more. It can also assign Pulseaudio devices at startup.

It uses the [pymumble library](https://github.com/azlux/pymumble).

It is a fork of [pymumble-abot](https://github.com/ranomier/pymumble-abot).

## Features
* Set bandwidth in bytes/s. Default is 48000 bytes/s
* Ability to use certificates
* See ./mumblestream.py --help

## Bugs and Features
* See https://github.com/f4exb/mumblestream/issues

## Dependencies
### Python libraries
See requirements.txt:
* opuslib (Opus codec)
* pyaudio (PortAudio)
* pulsectl (Pulseaudio)
* pymumble
* numpy

## Installation
### Prerequisites (Ubuntu/Debian)
    sudo apt install python3-dev portaudio19-dev

### Install on Linux with virtualenv
Login as a user; do not execute the following commands as root :) of course... but always worth to mention.

    cd
	git clone https://github.com/f4exb/mumblestream.git
	cd mumblestream

	python -m venv venv
	source venv/bin/activate

	pip install -r requirements.txt


# Mumblestream

## Configuration file

You will need a configuration file to further customize your `mumblestream` instance. However this file is not mandatory as all parameters are optional. It is in the form of a JSON file with the following parameters defined as keys:

- `vox_silence_time`: Time in seconds of detected silence before streaming stops. Default: 3
- `audio_threshold`: Audio detected above this level will be streamed. Default: 1000
- `audio_output_volume`: Volume factor applied to audio coming from Mumble. Default: 1
- `input_pyaudio_name`: PyAudio input device name. Default "default"
- `input_pulse_name`: Optional pulseaudio device name to reroute the input from
- `output_pyaudio_name`: PyAudio output device name. Default "default"
- `output_pulse_name`: Optional pulseaudio device name to reroute the output to
- `output_disable`: Set it to an integer value different of zero to disable audio output. Default 0 (false)
- `ptt_on_command`: Optional command to execute to turn host PTT on when receiving audio from Mumble. It is in the form of a list of command followed by its arguments
- `ptt_off_command`: Optional command to execute to turn host PTT off when audio from Mumble has finished. It is in the form of a list of command followed by its arguments
- `logging_level`: Set Python logging module to this level. Can be "critial", "error", "warning", "info" or "debug". Default "warning".

Both `ptt_on_command` and `ptt_off_command` parameters are required for the PTT feature to be engaged.

You will find an example `sampleconfig.json` file in this repository

## Typical usage

First you need to activate your Python environment

    cd ~/mumblestream
    source venv/bin/activate

Then you can run your bot:

	./mumblestream.py -H [your host] -u [your user] -p [your password] -C [target channel] -c [path to .pem certificate]

Be aware that most Mumble servers do not allow spaces or other special characters for user names.
Also a certificate is usually mandatory (see "Certificate" section next)

## Bandwidth
The bot uses TCP mode which causes some (more) overhead in bandwidth compared to UDP mode. Note, that all Mumble bots do that; but keep that in mind when you set the bitrate on your server. Expect a ~25% increase.

For example when you set your bot to 96000 bytes/s it will use ~120000 bytes/s.

## Certificate
Export your certificate from the Mumble client with the "Certificate wizard". Then convert it with openssl:

			openssl pkcs12 -in cert_from_mumble.p12 -out cert_for_abot.pem -nodes

To use it, tell abot the path with the --certificate|-c option.

# Mumblelistener

This bot specializes in listening to a Mumble channel and send the audio to an audio output device on the host. Conversely to `mumblestream` it mixes the input of all sources when with `mumblestream` only one source has the control of the output device at a time.

It has a reduced set of controls compared to `mumblestream` since the audio input from the host is not handled. It can handle PTT control so that it can serve the audio mix on a radio channel.

## Configuration file

- `output_pyaudio_name`: PyAudio output device name. Default "default"
- `output_pulse_name`: Optional pulseaudio device name to reroute the output to
- `ptt_on_command`: Optional command to execute to turn host PTT on when receiving audio from Mumble. It is in the form of a list of command followed by its arguments
- `ptt_off_command`: Optional command to execute to turn host PTT off when audio from Mumble has finished. It is in the form of a list of command followed by its arguments
- `logging_level`: Set Python logging module to this level. Can be "critial", "error", "warning", "info" or "debug". Default "warning".

Both `ptt_on_command` and `ptt_off_command` parameters are required for the PTT feature to be engaged.

You will find an example `samplelistener.json` file in this repository. The default configuration file is `listener.json` in the current directory and can be changed with the `--config` option.

## Typical usage

First you need to activate your Python environment

    cd ~/mumblestream
    source venv/bin/activate

Then you can run your bot:

	./mumblelistener.py -H [your host] -u [your user] -p [your password] -C [target channel] -c [path to .pem certificate]

Be aware that most Mumble servers do not allow spaces or other special characters for user names.
Also a certificate is usually mandatory (see "Certificate" section next)

Report to the "Certificate" section above to obtain the certification file.
