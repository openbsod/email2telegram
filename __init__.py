#!env python3

from imaplib import IMAP4, IMAP4_SSL
from email.parser import Parser as Email_Parser
from email.header import decode_header
from http.client import HTTPSConnection
from urllib.parse import quote_plus
from datetime import datetime
import socket
import html

now = datetime.now()
time_stamp = "{}-{}-{} {}:{}:{}".format(now.year, now.month, now.day, now.hour, now.minute, now.second)

try:
    from settings import mail, bot, db, recipients, silent_hours
except ImportError:
    mail = None
    bot = None
    db = None
    silent_hours = []
    recipients = list()
    print("{}: No settings file found!".format(time_stamp))
    exit(1)

# :IMAP4

email_parser = Email_Parser()


def connect() -> IMAP4_SSL:
    try:
        imap = IMAP4_SSL(mail.server, mail.port)
        imap.login(mail.login, mail.password)
        imap.select("INBOX")
        return imap
    except socket.gaierror:
        print("{}: Error: Unable to connect with server {}:{}.".format(time_stamp, mail.server, mail.port))
        exit(1)
    except IMAP4.error as e:
        print("{}: Error: Unable to connect with server. {}".format(time_stamp, e))
        exit(1)
    except Exception as e:
        print("{}: Unknown error.\n{}".format(time_stamp, e))
        exit(1)


def decode(header):
    """

    :param header: bytes - encoded email header
    :return: str - human-readable header.
    """
    if header is None:
        return ''
    result = []
    heads = decode_header(header)
    for raw_header in heads:
        header, encoding = raw_header
        if type(header) is str:
            result.append(header)
        else:
            if encoding is None:
                encoding = "utf-8"
            result.append(header.decode(encoding))
    return " ".join(result)


def parse_mail(rawdata: bytes):
    """
    :param rawdata: bytes - email-encoded letter
    :return: dict - dictionary in human-readable format.
    """
    parsed_message = dict()
    message = rawdata.decode(errors='ignore')
    message = email_parser.parsestr(message, True)
    #    if 'referece' not in message:
    parsed_message['from'] = html.escape(decode(message['from']))
    parsed_message['to'] = decode(message['to'])
    parsed_message['cc'] = decode(message['cc'])
    parsed_message['references'] = decode(message['references'])
    parsed_message['subj'] = decode(message['subject'])
    parsed_message['date'] = decode(message['date'])
    return parsed_message


def send_data(data: dict):
    """

    :param data: dic - dictionary with processed headers
    :return: bool
    """
    message_text = "<b>New email!</b>\n" \
                   "<code>Sender: {from}\n" \
                   "Topic: {subj}\n" \
                   "Date: {date}</code>\n" \
                   "#piter-ix #email".format(**data)

    result = False
    if datetime.now().hour in silent_hours:
        is_silent = 1
    else:
        is_silent = 0

    for r in recipients:
        query_string = "chat_id={chat_id}&text={text}&disable_notification={is_silent}".format(
            chat_id=r['id'],
            text=quote_plus(message_text),
            is_silent=is_silent
        )

        url = 'https://{domain}/bot{token}/sendMessage?{qs}&parse_mode=html'.format(
            domain=bot.domain,
            token=bot.token,
            qs=query_string
        )

        http_client = HTTPSConnection(bot.domain, '443')
        http_client.request("GET", url)
        http_res = http_client.getresponse()
        result = (http_res.status == 200) or result

    # if API returned 200 - set email as readed.
    return result


def run():
    imap = connect()
    status, mails = imap.search(
        None,
        "UNSEEN"
    )
    #       '(OR (OR CC "dva@example.tld" TO "dva@example.tld") (OR CC support@example.tld TO support@example.tld))'
    # '(OR (OR CC "dva@example.tld" TO "dva@example.tld") (OR CC support@example.tld TO support@example.tld))'
    #    )

    from_filter = ["*@*"]
    to_filter = ["noc@example.tld"]

    for uid in mails[0].split(b' '):
        if uid != b'':
            status, result = imap.fetch(uid, '(RFC822)')
            data, flags = result
            req, message = data
            msg = parse_mail(message)

            from_matches = [s for s in from_filter if s in msg["from"]]
            to_matches = [s for s in to_filter if s in msg["to"]]
            to_cc = [s for s in to_filter if s in msg["cc"]]
            to_matches = to_matches + to_cc

            if to_matches and not from_matches:
                if not send_data(msg):
                    imap.store(uid, '-FLAGS', '\Seen')
        else:
            # print("Nothing to do.")
            pass


if __name__ == "__main__":
    run()
