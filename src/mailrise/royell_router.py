"""
This is the YAML-based router for Mailrise.
"""

from functools import partial
from logging import Logger
import re
import typing as typ
import yaml

from apprise import NotifyType

from mailrise.config import ConfigFileLoader
from mailrise.router import AppriseNotification, EmailMessage, AppriseAsset
from mailrise.simple_router import (
    SimpleRouter, _parse_simple_key, _load_simple_sender, _parsercpt,
)
from mailrise.skeleton import _logger

APPRISE_ASSET = AppriseAsset(
    app_id='Mailrise',
    app_desc='Mailrise SMTP Notification Relay',
    app_url='https://mailrise.xyz',
    html_notify_map={
        NotifyType.INFO: '#2e6e99',
        NotifyType.SUCCESS: '#2e992e',
        NotifyType.WARNING: '#99972e',
        NotifyType.FAILURE: '#993a2e'
    },
    theme=None,
    default_extension='.png',
    image_url_mask='',
    image_url_logo='',
    image_path_mask='',
)


class RoyellRouter(SimpleRouter):  # pylint: disable=too-few-public-methods

    async def email_to_apprise(
        self, logger: Logger, email: EmailMessage, auth_data: typ.Any, **kwargs) \
            -> typ.AsyncGenerator[AppriseNotification, None]:
        for addr in email.to:
            try:
                rcpt = _parsercpt(addr)
            except ValueError:
                logger.error('Not a valid Mailrise address: %s', addr)
                continue
            sender = self.get_sender(rcpt.key)
            if sender is None:
                logger.error('Recipient is not configured: %s', addr)
                continue

            title = re.sub('/&nbsp;/', '', email.subject)
            mapping = {
                'subject': title,
                'from': email.from_,
                'body': email.body,
                'to': str(rcpt.key),
                'config': rcpt.key.as_configured(),
                'type': rcpt.notify_type
            }
            yield AppriseNotification(
                config=sender.config_yaml,
                config_format='yaml',
                title=sender.title_template.safe_substitute(mapping),
                body=sender.body_template.safe_substitute(mapping),
                # Use the configuration body format if specified.
                body_format=sender.body_format or email.body_format,
                notify_type=rcpt.notify_type,
                attachments=email.attachments,
                asset=APPRISE_ASSET,
            )


def load_from_yaml() -> RoyellRouter:
    """Load a simple router from the YAML configs node."""
    logger = _logger
    yml = yaml.load(
        '/etc/mailrise.conf', Loader=partial(ConfigFileLoader, logger=logger))
    if not isinstance(yml, dict):
        logger.critical('YAML root node is not a mapping')
        raise SystemExit(1)
    configs_node = yml.get('configs')
    if not isinstance(configs_node, dict):
        logger.critical('The configs node is not a YAML mapping')
        raise SystemExit(1)
    router = RoyellRouter(
        senders=[
            (_parse_simple_key(logger, key),
             _load_simple_sender(logger, key, config))
            for key, config in configs_node.items()]
    )
    if len(router.senders) < 1:
        logger.critical('No Apprise targets are configured')
        raise SystemExit(1)
    logger.info('Loaded configuration with %d recipient(s)', len(router.senders))
    return router


router = load_from_yaml()
