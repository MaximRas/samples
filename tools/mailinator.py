import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import allure
import requests
from selenium.common.exceptions import TimeoutException

import consts
from tools import config
from tools import generate_id_from_time
from tools.client import ApiClient
from tools.types import EmailType
from tools.types import IdIntType
from tools.types import UrlType

log = logging.getLogger(__name__)


class NoMailException(Exception):
    pass


SUBJECT_USER_ADDED_TO_COMPANY = 'You have been added to the company.'
SUBJECT_REMOVED_FROM_COMPANY = 'You have been removed from the company.'
SUBJECT_FORGOT_PASSWORD = 'Metapix Cloud | Forgot Password'


@dataclass
class MailinatorMessage:
    subject: str
    author: str
    id: IdIntType

    def __str__(self):
        return f'Message "{self.subject}" author:"{self.author}"'


def resend_confirmation_email(client: ApiClient, email: str) -> None:
    log.info(f'Resend confirmation email for {email}')
    client.request(
        'post',
        f'/{consts.SERVICE_AUTH_MANAGER}/auth/resend-confirmation-email',
        data={'login': email},
        expected_code=200,
    )


class Inbox:
    MAILINATOR = 'https://MAILINATOR.com/api/v2/'
    dom = 'metapixteam.testinator.com'

    def __init__(self, env=None, iname=None, email=None):
        self._requests_timeout = tuple(config.user_config['requests_timeout'])
        self._auth_header = {'Authorization': config.user_config["mailinator"]["token"]}
        self._env = env
        self._iname = iname
        self._new_inboxes = []  # workaround to open verification links of users created thr web ui
        if email:
            self._iname = email.replace(f"@{self.dom}", "")

    def __str__(self):
        return f'Inbox iname={self.iname}'

    @property
    def iname(self):
        return self._iname

    @property
    def email(self) -> EmailType:
        return EmailType(f'{self.iname}@{self.dom}')

    @property
    def inbox_url(self):
        return Inbox.MAILINATOR + f'domains/{self.dom}/inboxes/{self.iname}'

    def fetch_inbox(self) -> list[MailinatorMessage]:
        log.debug(f'Fetching inbox "{self.iname}"')
        resp = requests.get(self.inbox_url, headers=self._auth_header, timeout=self._requests_timeout)
        resp.raise_for_status()
        content = json.loads(resp.text)
        for msg in content["msgs"]:
            log.debug(f"Found message: {msg}")
        return [
            MailinatorMessage(
                id=msg['id'],
                author=msg['from'],
                subject=msg['subject'],
            )
            for msg in content["msgs"]
        ]

    def fetch_mail(self, id, part_id=0, entity="body") -> str:
        log.debug(f'Reading message "{id}" from box {self.iname}')
        url = f'{self.inbox_url}/messages/{id}'
        resp = requests.get(url, headers=self._auth_header, timeout=self._requests_timeout)
        resp.raise_for_status()
        resp = json.loads(resp.text)
        return resp['parts'][part_id][entity]

    def delete_message(self, msg: MailinatorMessage):
        log.warning(f'Delete {msg} from box {self.iname}')
        url = f'{self.inbox_url}/messages/{msg.id}'
        resp = requests.delete(url, headers=self._auth_header, timeout=self._requests_timeout)
        resp.raise_for_status()

    def find_message_by_subject(
            self,
            subject: str,
            timeout: int = 10,
    ) -> MailinatorMessage:
        log.info(f'Wait for message with subject: {subject}')
        st_time = time.time()
        while time.time() - st_time < timeout:
            for msg in self.fetch_inbox():
                if msg.subject == subject:
                    return msg
                log.warning(f'Subject mismatch: {msg}')
            time.sleep(5)
        raise NoMailException(subject)

    @property
    def messages_count(self) -> int:
        count = len(self.fetch_inbox())
        log.info(f'{self} messages count: {count}')
        return count

    def wait_any_message(self, waiter):
        try:
            waiter.until(lambda x: self.messages_count > 0)
        except TimeoutException as exc:
            raise NoMailException from exc

    def wait_new_message(self, waiter, message_count_before, timeout: int = 15):
        waiter(timeout=timeout, poll_frequency=3).until(
            lambda x: self.messages_count > message_count_before,
        )

    def clear(self):
        with allure.step(f'Deleting all messages in {self}'):
            log.info(f'Deleting all messages in {self}')
            for msg in self.fetch_inbox():
                self.delete_message(msg)
            resp = requests.delete(self.inbox_url, headers=self._auth_header, timeout=self._requests_timeout)
            resp.raise_for_status()

    def create_new(self, email: Optional[EmailType] = None):
        if email:
            kwargs = {'email': EmailType(email)}
        else:
            kwargs = {'iname': generate_id_from_time()}
        with allure.step(f'Create new inbox {kwargs}'):
            log.info(f'Create new inbox with {kwargs}')
            inbox = self.__class__(**kwargs)
            self._new_inboxes.append(inbox)
            return inbox

    def get_registration_link(
            self,
            timeout: int = 60,
            delete_message: bool = True,
    ) -> UrlType:
        log.info(f"Looking for verification code for {self.email}")
        verification_mail = self.find_message_by_subject(subject=SUBJECT_USER_ADDED_TO_COMPANY, timeout=timeout)
        verification_msg = self.fetch_mail(verification_mail.id)
        try:
            link = re.findall('please use the following link: (http[^">]+)', verification_msg)[0]
        except IndexError as exc:
            raise RuntimeError(f'There is no registration link: {verification_msg}') from exc
        log.info(f"Verification link: {link}")
        if delete_message:
            self.delete_message(verification_mail)
        return link

    def get_confirmation_code(self) -> str:
        """ Get confirmation code to reset password """
        # TODO: rename
        with allure.step(f"Looking for confirmation code for {self.email}"):
            log.info(f"Looking for confirmation code for {self.email}")
            mail = self.find_message_by_subject(subject=SUBJECT_FORGOT_PASSWORD)
            msg = self.fetch_mail(mail.id)
            code = re.findall(r"code is (\d+)\b", msg)[0]
            log.info(f"Verification code: {code}")
            self.delete_message(mail)
        return code
