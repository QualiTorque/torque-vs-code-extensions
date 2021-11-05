import argparse
import logging

logging.basicConfig(filename="torque_ls.log", level=logging.INFO, filemode="w")

from .torque_server import torque_ls


def add_arguments(parser):
    parser.description = "A torque language server"

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
        torque_ls.start_tcp(args.host, args.port)
    else:
        torque_ls.start_io()


if __name__ == '__main__':
    main()
