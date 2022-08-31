#!/usr/bin/env python
"""
TITLE:  mumblelistener
AUTHOR: Ranomier (ranomier@fragomat.net), F4EXB (f4exb06@gmail.com)
DESC:   A bot that streams audio from a Mumble server to host audio.
"""

import argparse
import sys
import os
import subprocess
from threading import Thread
import time
import logging
import json
import collections

import audioop
import pymumble_py3 as pymumble
import pyaudio

from pulseaudio import PulseAudioHandler

__version__ = "0.1.0"

logging.basicConfig(format="%(asctime)s %(levelname).1s [%(threadName)s] %(funcName)s: %(message)s", level=logging.INFO)
LOG = logging.getLogger("Mumblelistener")


class Status(collections.UserList):
    """Thread status handler"""

    def __init__(self, runner_obj):
        self.__runner_obj = runner_obj
        self.scheme = collections.namedtuple("thread_info", ("name", "alive"))
        super().__init__(self.__gather_status())

    def __gather_status(self):
        """Gather status"""
        result = []
        for meta in self.__runner_obj.values():
            result.append(self.scheme(meta["process"].name, meta["process"].is_alive()))
        return result

    def __repr__(self):
        repr_str = ""
        for status in self:
            repr_str += f"[{status.name}] alive: {status.alive} "
        return repr_str


class Runner(collections.UserDict):
    """Runs a list of threads"""

    def __init__(self, run_dict, args_dict=None):
        self.is_ready = False
        if run_dict is not None:
            super().__init__(run_dict)
            self.change_args(args_dict)
            self.run()

    def change_args(self, args_dict):
        """Copy arguments"""
        for name, value in self.items():
            if name in args_dict:
                value["args"] = args_dict[name]["args"]
                value["kwargs"] = args_dict[name]["kwargs"]
            else:
                value["args"] = None
                value["kwargs"] = None

    def run(self):
        """Spawns threads"""
        for name, cdict in self.items():
            LOG.info("generating process")
            # fmt: off
            cdict["process"] = Thread(
                name=name,
                target=cdict["func"],
                args=cdict["args"],
                kwargs=cdict["kwargs"]
            )
            # fmt: on
            LOG.info("starting process")
            cdict["process"].daemon = True
            cdict["process"].start()
            LOG.info("%s started", name)
        LOG.info("all done")
        self.is_ready = True

    def status(self):
        """Return a status"""
        if self.is_ready:
            return Status(self)
        return []

    def stop(self, name=""):
        """Stop and exit"""
        raise NotImplementedError("Sorry")


class MumbleRunner(Runner):
    """A threads runner for Mumble"""

    def __init__(self, mumble_object, config, args_dict):
        self.mumble = mumble_object
        self.config = config
        super().__init__(self._config(), args_dict)

    def _config(self):
        """Initial configuration"""
        raise NotImplementedError("please inherit and implement")


class Audio(MumbleRunner):
    """Audio input/output"""

    def _config(self):
        self.stream_out = None
        self.out_running = None
        self.out_volume = 1
        self.in_users = {}
        self.receive_ts = None
        self.ptt_on_command = None
        self.ptt_off_command = None
        self.ptt_running = None
        """Initial configuration"""
        if not self.__init_audio():
            return None
        # fmt: off
        return {
            "output": {
                "func": self.__output_loop,
                "process": None
            },
            "ptt": {
                "func": self.__ptt_loop,
                "process": None
            },
        }
        # fmt: on

    def __init_audio(self):
        pa = pyaudio.PyAudio()
        pulse = None
        input_device_names, output_device_names = self.__scan_devices(pa)
        chunk_size = int(pymumble.constants.PYMUMBLE_SAMPLERATE * self.config["args"].packet_length)
        # Output audio
        if pulse is None and self.config["output_pulse_name"]:
            pulse = PulseAudioHandler("mumblestream")
        pyaudio_output_index = self.__get_pyaudio_output_index(output_device_names)
        if pyaudio_output_index is None:
            LOG.error("cannot find PyAudio output device")
            return False
        self.stream_out = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=pymumble.constants.PYMUMBLE_SAMPLERATE,
            output=True,
            frames_per_buffer=chunk_size,
            output_device_index=pyaudio_output_index,
        )
        LOG.debug("output stream opened")
        if self.config["output_pulse_name"] is not None:  # redirect output from mumblestream with pulseaudio
            self.__move_output_pulseaudio(pulse, self.config["output_pulse_name"])
        # All OK
        return True

    @staticmethod
    def __scan_devices(pa):
        """Scan audio devices handled by PyAudio"""
        info = pa.get_host_api_info_by_index(0)
        numdevices = info.get("deviceCount")
        input_device_names = {}
        output_device_names = {}
        for i in range(0, numdevices):
            if pa.get_device_info_by_host_api_device_index(0, i).get("maxInputChannels") > 0:
                device_info = pa.get_device_info_by_host_api_device_index(0, i)
                input_device_names[device_info["name"]] = device_info["index"]
            if pa.get_device_info_by_host_api_device_index(0, i).get("maxOutputChannels") > 0:
                device_info = pa.get_device_info_by_host_api_device_index(0, i)
                output_device_names[device_info["name"]] = device_info["index"]
        LOG.debug("input: %s", input_device_names)
        LOG.debug("output: %s", output_device_names)
        return input_device_names, output_device_names

    def __get_pyaudio_output_index(self, output_device_names):
        """Returns the PyAudio index of output device or None if no default"""
        if self.config["output_pulse_name"] is not None:
            pyaudio_name = "pulse"
        else:
            pyaudio_name = self.config.get("output_pyaudio_name", "default")
        return output_device_names.get(pyaudio_name)

    def __move_output_pulseaudio(self, pulse, output_pulse_name):
        """Moves the output to the given pulseaudio device"""
        pulse_sink_index = pulse.get_sink_index(output_pulse_name)
        pulse_sink_input_index = pulse.get_own_sink_input_index()
        if pulse_sink_index is None or pulse_sink_input_index is None:
            LOG.warning("cannot move pulseaudio sink input %d to sink %d", pulse_sink_input_index, pulse_sink_index)
        else:
            try:
                pulse.move_sink_input(pulse_sink_input_index, pulse_sink_index)
                LOG.debug("moved pulseaudio sink input %d to sink %d", pulse_sink_input_index, pulse_sink_index)
            except Exception as ex:
                LOG.error("exception assigning pulseaudio sink: %s", ex)

    def __output_loop(self):
        """Output process"""
        self.out_volume = self.config["audio_output_volume"]
        self.ptt_on_command = " ".join(self.config["ptt_on_command"]) if self.config["ptt_command_support"] else None
        self.ptt_off_command = " ".join(self.config["ptt_off_command"]) if self.config["ptt_command_support"] else None
        self.out_running = True
        try:
            while self.out_running:
                sound_frag = None
                for user_session_id in list(self.mumble.users):
                    user = self.mumble.users[user_session_id]
                    user_name = user["name"]
                    if user.sound.is_sound():
                        if self.config["ptt_command_support"] and self.receive_ts is None:
                            run_ptt_on_command = subprocess.run(self.ptt_on_command, shell=True, check=True)
                            LOG.debug("PTT on exited with code %d", run_ptt_on_command.returncode)
                        if user_name not in self.in_users:
                            LOG.debug("start receiving audio from %s", user_name)
                            self.in_users[user_name] = 0
                        self.receive_ts = time.time()
                        self.in_users[user_name] = self.receive_ts
                        if sound_frag is None:
                            sound_frag = user.sound.get_sound().pcm
                        else:
                            sound_frag = audioop.add(sound_frag, user.sound.get_sound().pcm, 2)
                    else:
                        if user_name in self.in_users and time.time() > self.in_users[user_name] + 0.5:
                            LOG.debug("stop receiving audio from %s", user_name)
                            self.in_users.pop(user_name)
                if sound_frag is not None:
                    self.stream_out.write(sound_frag)
                time.sleep(0.005)
        finally:
            LOG.debug("terminating")
            self.stream_out.close()
            LOG.debug("output stream closed")
        return True

    def __ptt_loop(self):
        """PTT process"""
        self.ptt_running = True
        while self.ptt_running:
            if self.config["ptt_command_support"] and self.receive_ts is not None and time.time() > self.receive_ts + 1:
                run_ptt_off_command = subprocess.run(self.ptt_off_command, shell=True, check=True)
                LOG.debug("PTT off exited with code %d", run_ptt_off_command.returncode)
                self.receive_ts = None
            time.sleep(0.1)
        return True

    def stop(self, name=""):
        """Stop the runnin threads"""
        self.out_running = False
        self.ptt_running = False


class AudioPipe(MumbleRunner):
    """Audio pipe"""

    def _config(self):
        """Initial configuration"""
        # fmt: off
        return {
            "PipeOutput": {
                "func": self.__output_loop,
                "process": None
            },
            "PipePTT": {
                "func": self.__ptt_loop,
                "process": None
            },
        }
        # fmt: on

    def __output_loop(self, _):
        """Output process"""
        return None

    def __ptt_loop(self):
        """PTT process"""
        return None

    def stop(self, name=""):
        """Stop the runnin threads"""


def prepare_mumble(host, user, password="", certfile=None, codec_profile="audio", bandwidth=96000, channel=None):
    """Will configure the pymumble object and return it"""

    try:
        mumble = pymumble.Mumble(host, user, certfile=certfile, password=password)
    except Exception as ex:
        LOG.error("cannot commect to %s: %s", host, ex)
        return None

    mumble.set_application_string(f"mumblestream ({__version__})")
    mumble.set_codec_profile(codec_profile)
    mumble.set_receive_sound(1)  # Enable receiving sound from mumble server
    mumble.start()
    mumble.is_ready()
    mumble.set_bandwidth(bandwidth)
    if channel:
        try:
            mumble.channels.find_by_name(channel).move_in()
        except pymumble.channels.UnknownChannelError as ex:
            LOG.warning("tried to connect to channel: '%s' exception %s", channel, ex)
            LOG.info("Available Channels:")
            LOG.info(mumble.channels)
            return None
    return mumble


def get_config(args):
    """Get parameters from the optional config file"""
    config = {}

    if args.config_path is not None and os.path.exists(args.config_path):
        with open(args.config_path) as f:
            configdata = json.load(f)
    else:
        configdata = {}

    config["audio_output_volume"] = configdata.get("audio_output_volume", 1)
    config["output_pyaudio_name"] = configdata.get("output_pyaudio_name", "default")
    config["output_pulse_name"] = configdata.get("output_pulse_name")
    config["ptt_on_command"] = configdata.get("ptt_on_command")
    config["ptt_off_command"] = configdata.get("ptt_off_command")
    config["ptt_command_support"] = not (config["ptt_on_command"] is None or config["ptt_off_command"] is None)
    config["logging_level"] = configdata.get("logging_level", "warning")
    return config


def main(preserve_thread=True):
    """swallows parameter. TODO: move functionality away"""
    parser = argparse.ArgumentParser(description="Alsa input to mumble")
    # fmt: off
    parser.add_argument("-H", "--host", dest="host", type=str, required=True,
                        help="A hostame of a mumble server")
    parser.add_argument("-u", "--user", dest="user", type=str, required=True,
                        help="Username you wish, Default=mumble")
    parser.add_argument("-p", "--password", dest="password", type=str, default="",
                        help="Password if server requires one")
    parser.add_argument("-s", "--setpacketlength", dest="packet_length", type=int, default=pymumble.constants.PYMUMBLE_AUDIO_PER_PACKET,
                        help="Length of audio packet in seconds. Lower values mean less delay. Default 0.02 WARNING:Lower values could be unstable")
    parser.add_argument("-b", "--bandwidth", dest="bandwidth", type=int, default=48000,
                        help="Bandwith of the bot (in bytes/s). Default=96000")
    parser.add_argument("-c", "--certificate", dest="certfile", type=str, default=None,
                        help="Path to an optional openssl certificate file")
    parser.add_argument("-C", "--channel", dest="channel", type=str, default=None,
                        help="Channel name as string")
    parser.add_argument("-f", "--fifo", dest="fifo_path", type=str, default=None,
                        help="Read from FIFO (EXPERMENTAL)")
    parser.add_argument("--config", dest="config_path", type=str, default="listener.json",
                        help="Configuration file")
    # fmt: on
    args = parser.parse_args()
    config = get_config(args)
    config["args"] = args

    log_level = logging.getLevelName(config["logging_level"].upper())
    LOG.setLevel(log_level)

    mumble = prepare_mumble(args.host, args.user, args.password, args.certfile, "audio", args.bandwidth, args.channel)

    if mumble is None:
        LOG.critical("cannot connect to Mumble server or channel")
        return 1

    # fmt: off
    if args.fifo_path:
        audio = AudioPipe(
            mumble,
            config,
            {
                "output": {
                    "args": (args.packet_length,),
                    "kwargs": None
                },
                "ptt": {
                    "args": [],
                    "kwargs": None
                },
            },
        )
    else:
        audio = Audio(
            mumble,
            config,
            {
                "output": {
                    "args": [],
                    "kwargs": None
                },
                "ptt": {
                    "args": [],
                    "kwargs": None
                },
            }
        )
    # fmt: on
    if preserve_thread:
        while True:
            try:
                LOG.info(audio.status())
                time.sleep(60)
            except KeyboardInterrupt:
                LOG.info("terminating")
                audio.stop()
                time.sleep(1)
                return 0
            except Exception as ex:
                LOG.error("exception %s", ex)
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
