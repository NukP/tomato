import sys
import os
import subprocess
import textwrap
from pathlib import Path
from datetime import datetime, timezone
from importlib import metadata

import argparse
import logging
import psutil
import zmq
import appdirs
import yaml
import toml

sys.path += sys.modules["tomato"].__path__

from tomato import tomato, ketchup, _version


__version__ = _version.get_versions()["version"]
VERSION = __version__
DEFAULT_TOMATO_PORT = 1234
logger = logging.getLogger(__name__)


def set_loglevel(loglevel: int):
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def run_tomato():
    dirs = appdirs.AppDirs("tomato", "dgbowl", version=VERSION)
    config_dir = dirs.user_config_dir
    data_dir = dirs.user_data_dir
    log_dir = dirs.user_log_dir

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s version {VERSION}",
    )

    verbose = argparse.ArgumentParser(add_help=False)

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    status = subparsers.add_parser("status")
    status.set_defaults(func=tomato.status)

    start = subparsers.add_parser("start")
    start.set_defaults(func=tomato.start)

    stop = subparsers.add_parser("stop")
    stop.set_defaults(func=tomato.stop)

    init = subparsers.add_parser("init")
    init.set_defaults(func=tomato.init)

    reload = subparsers.add_parser("reload")
    reload.set_defaults(func=tomato.reload)

    pipeline = subparsers.add_parser("pipeline")
    pipparsers = pipeline.add_subparsers(dest="subsubcommand", required=True)

    pip_load = pipparsers.add_parser("load")
    pip_load.set_defaults(func=tomato.pipeline_load)
    pip_load.add_argument("pipeline")
    pip_load.add_argument("sampleid")

    pip_eject = pipparsers.add_parser("eject")
    pip_eject.set_defaults(func=tomato.pipeline_eject)
    pip_eject.add_argument("pipeline")

    pip_ready = pipparsers.add_parser("ready")
    pip_ready.set_defaults(func=tomato.pipeline_ready)
    pip_ready.add_argument("pipeline")

    for p in [parser, verbose]:
        p.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Increase verbosity of tomato daemon by one level.",
        )
        p.add_argument(
            "--quiet",
            "-q",
            action="count",
            default=0,
            help="Decrease verbosity of tomato daemon by one level.",
        )

    for p in [start, stop, init, status, reload, pip_load, pip_eject, pip_ready]:
        p.add_argument(
            "--port",
            "-p",
            help="Port number of tomato's reply socket",
            default=DEFAULT_TOMATO_PORT,
        )
        p.add_argument(
            "--timeout",
            help="Timeout for the tomato command, in milliseconds",
            type=int,
            default=3000,
        )
        p.add_argument(
            "--appdir",
            "-A",
            help="Settings directory for tomato",
            default=config_dir,
        )
        p.add_argument(
            "--datadir",
            "-D",
            help="Data directory for tomato",
            default=data_dir,
        )
        p.add_argument(
            "--logdir",
            "-L",
            help="Log directory for tomato",
            default=data_dir,
        )

    # parse subparser args
    args, extras = parser.parse_known_args()
    # parse extras for verbose tags
    args, extras = verbose.parse_known_args(extras, args)

    verbosity = min(max((2 + args.verbose - args.quiet) * 10, 10), 50)
    set_loglevel(verbosity)

    context = zmq.Context()
    if "func" in args:
        ret = args.func(**vars(args), context=context, verbosity=verbosity)
        print(yaml.dump(ret.dict()))


def run_ketchup():
    dirs = appdirs.AppDirs("tomato", "dgbowl", version=VERSION)
    config_dir = dirs.user_config_dir
    data_dir = dirs.user_data_dir

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s version {VERSION}",
    )

    verbose = argparse.ArgumentParser(add_help=False)

    for p in [parser, verbose]:
        p.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Increase verbosity by one level.",
        )
        p.add_argument(
            "--quiet",
            "-q",
            action="count",
            default=0,
            help="Decrease verbosity by one level.",
        )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    submit = subparsers.add_parser("submit")
    submit.add_argument(
        "payload",
        help="File containing the payload to be submitted to tomato.",
        default=None,
    )
    submit.add_argument(
        "-j",
        "--jobname",
        help="Set the job name of the submitted job to?",
        default=None,
    )
    submit.set_defaults(func=ketchup.submit)

    status = subparsers.add_parser("status")
    status.add_argument(
        "jobids",
        nargs="*",
        help=(
            "The jobid(s) of the requested job(s), "
            "defaults to the status of the whole queue."
        ),
        type=int,
        default=None,
    )
    status.set_defaults(func=ketchup.status)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument(
        "jobid",
        help="The jobid of the job to be cancelled.",
        type=int,
        default=None,
    )
    cancel.set_defaults(func=ketchup.cancel)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument(
        "jobid", help="The jobid of the job to be snapshotted.", default=None
    )
    snapshot.set_defaults(func=ketchup.snapshot)

    search = subparsers.add_parser("search")
    search.add_argument(
        "jobname",
        help="The jobname of the searched job.",
        default=None,
    )
    search.add_argument(
        "-c",
        "--complete",
        action="store_true",
        default=False,
        help="Search also in completed jobs.",
    )
    search.set_defaults(func=ketchup.search)

    for p in [submit, status, cancel, snapshot, search]:
        p.add_argument(
            "--port",
            "-p",
            help="Port number of tomato's reply socket",
            default=DEFAULT_TOMATO_PORT,
        )
        p.add_argument(
            "--timeout",
            help="Timeout for the ketchup command, in milliseconds",
            type=int,
            default=3000,
        )
        p.add_argument(
            "--appdir",
            help="Settings directory for tomato",
            default=config_dir,
        )
        p.add_argument(
            "--datadir",
            help="Data directory for tomato",
            default=data_dir,
        )

    args, extras = parser.parse_known_args()
    args, extras = verbose.parse_known_args(extras, args)

    verbosity = args.verbose - args.quiet
    set_loglevel(verbosity)

    if "func" in args:
        context = zmq.Context()
        status = tomato.status(**vars(args), context=context)
        if not status.success:
            print(yaml.dump(status.dict()))
        else:
            ret = args.func(
                **vars(args), verbosity=verbosity, context=context, status=status
            )
            print(yaml.dump(ret.dict()))
