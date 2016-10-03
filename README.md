# pymumble-abot
This is a bot that streams your ALSA output into Mumble. It uses the [pymumble library](https://github.com/azlux/pymumble).

## Features
* Set bandwidth in bytes/s. Default is 50000 bytes/s

## Todos
* Add ability to use certificates

## Dependencies
### Python libraries
* opuslib (Opus codec)
* protobuf-py3 (Google Protocol Buffers)
* pyaudio (PortAudio)

## Installation
### Method 1: Install on Linux with virtualenv
Login as a user; do not execute the following commands as root :)

	virtualenv ~/python-for-pymumble-abot
	source ~/python-for-pymumble-abot/bin/activate

	pip install opuslib google protobuf-py3 pyaudio
	cd

	git clone git@github.com:ranomier/pymumble-abot.git
	cd pymumble-abot
	git submodule init
	git submodule update

Now you can run your own bot :)

## Usage
First you need to activate your Python environment:
	source ~/python-for-pymumble-abot/bin/activate

Then you can run your bot:
	cd ~/pymumble-abot
	./abot.py --host hostname_of_server -u "choose_username" -p "your_password"

Be aware that most Mumble servers do not allow spaces or other special characters for user names.

## Bandwidth
The bot uses TCP mode which causes some (more) overhead in bandwidth compared to UDP mode. Note, that all Mumble bots do that; but keep that in mind when you set the bitrate on your server.

So when you set your bot to 96000 bytes/s it will use ~120000 bytes/s.
