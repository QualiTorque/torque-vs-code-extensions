import argparse
import logging

logging.basicConfig(filename="colony_ls.log", level=logging.DEBUG, filemode="w")

from .server import colony_server


def add_arguments(parser):
    parser.description = "simple colony server example"

    parser.add_argument(
        "--tcp", action="store_true",
        help="Use TCP server instead of stdio"
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Bind to this address"
    )
    parser.add_argument(
        "--port", type=int, default=2087,
        help="Bind to this port"
    )


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()

    if args.tcp:
        colony_server.start_tcp(args.host, args.port)
    else:
        colony_server.start_io()


if __name__ == '__main__':
    main()
