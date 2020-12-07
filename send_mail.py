import csv
import mimetypes
import smtplib
import sys
import traceback
from email.message import EmailMessage
from email.utils import make_msgid
from os import read
from pathlib import Path
from string import Template
from typing import Dict, List

import click
import yaml


def setup_server(
    smtp_server: str,
    smtp_username: str,
    smtp_password: str,
    smtp_port: str,
    is_ssl: bool,
):
    if is_ssl:
        SMTP = smtplib.SMTP_SSL
    else:
        SMTP = smtplib.SMTP

    server = SMTP(smtp_server, smtp_port)
    server.login(smtp_username, smtp_password)
    return server


# def send(html_body: str, recipient: str, subject: str, sender_name: str, server):
#     pass


def make_message(
    recipient: str,
    html_template: str,
    subject_template: str,
    substitues: Dict,
    files: Dict,
    sender_name: str,
):
    # copy the files
    files_copy = dict(files)
    # Create the message
    msg = EmailMessage()
    msg["Subject"] = Template(subject_template).safe_substitute(**substitues)
    msg["To"] = recipient
    msg["From"] = sender_name
    msg.set_content("Please update your mail client to view this message\n")

    cid_dict = {}
    for key, value in files_copy.items():
        fpath = Path(value)
        if not fpath.is_file():
            click.echo(f"{value} is not a file. Skipping it.")
            continue

        # guess the mime type
        ctype, encoding = mimetypes.guess_type(fpath)
        if ctype is None or encoding is not None:
            # No guess could be made, or the file is encoded (compressed), so
            # use a generic bag-of-bits type.
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        files_copy[key] = {
            "content": fpath.read_bytes(),
            "maintype": maintype,
            "subtype": subtype,
        }

        cid = make_msgid()
        # save cid
        cid_dict[key] = cid
        substitues[key] = f"cid:{cid[1:-1]}"

    msg.add_alternative(
        Template(html_template).safe_substitute(**substitues), subtype="html"
    )

    for key, value in files_copy.items():
        msg.get_payload()[1].add_related(
            value["content"], value["maintype"], value["subtype"], cid=cid_dict[key]
        )

    return msg


# @click.command()
# @click.argument("data_csv", envvar="DATA_CSV", type=click.File("r"))
# def cli(
#     data_csv: click.File,
#     delimiter: str,
#     recipients_column: int,
#     mail_template: str,
#     mail_arg_column: int,
#     subject_template: str,
#     sender_name: str,
#     sender_email: str,
#     smtp_username: str,
#     smtp_server: str,
#     smtp_password: str,
#     is_ssl: bool,
# ):
#     if not smtp_username:
#         smtp_username = sender_email
#     click.echo(f"Connecting to SMTP server f{smtp_server}")
#     server = setup_server(smtp_server, smtp_username, smtp_password, is_ssl)
#     click.echo(f"Connected \n")

#     reader = csv.reader(data_csv.read(), delimiter=delimiter)
#     next(reader)  # skip header
#     for row in reader:
#         name = row[mail_arg_column]
#         email = row[recipients_column]
#         html_body = Template(mail_template).safe_substitute(name=name)
#         subject = Template(subject_template).safe_substitute(name=name)
#         try:
#             click.echo(f"Sending mail to [{name} <{email}>]")
#             send(html_body, email, subject, sender_name, server)
#         except Exception as ex:
#             click.echo(f"{ex}")


@click.command()
@click.option("-p", "password", envvar="SMTP_PASSWORD", required=True)
@click.argument("config_file", envvar="MAIL_CONFIG", type=click.File("r"))
def main(password: str, config_file: click.File):
    # load config
    try:
        config = yaml.safe_load(config_file.read())
    except yaml.YAMLError:
        click.echo(f"Failed to parse config file.")
        sys.exit(1)

    if not config["smtp_username"]:
        config["smtp_username"] = config["sender_email"]

    click.echo(f"Connecting to SMTP server {config['smtp_server']}")
    server = setup_server(
        config["smtp_server"],
        config["smtp_username"],
        password,
        config["smtp_port"],
        config["is_ssl"],
    )
    click.echo(f"Connected \n")

    with open(config["data_csv"], "r") as fp:
        reader = csv.reader(fp)
        next(reader)  # skip header

        for row in reader:
            name = row[config["name_column"]]
            email = row[config["recipients_column"]]
            html_template = config["html"]
            subject_template = config["subject"]
            subs = {k: row[v] for k, v in config["substitutes"].items()}
            try:
                click.echo(f"Sending mail to [{name} <{email}>]")
                msg = make_message(
                    email,
                    html_template,
                    subject_template,
                    subs,
                    config["files"],
                    config["sender_name"],
                )
                server.send_message(msg)
            except Exception as ex:
                click.echo(traceback.format_exc())


if __name__ == "__main__":
    main()
