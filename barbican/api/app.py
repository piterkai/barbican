# Copyright (c) 2013-2015 Rackspace, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
API application handler for Cloudkeep's Barbican
"""
import pecan

try:
    import newrelic.agent
    newrelic_loaded = True
except ImportError:
    newrelic_loaded = False

from oslo_log import log

from barbican.api.controllers import versions
from barbican.api import hooks
from barbican.common import config
from barbican import i18n as u
from barbican.model import repositories
from barbican import queue

CONF = config.CONF

if newrelic_loaded:
    newrelic.agent.initialize('/etc/newrelic/newrelic.ini')


def build_wsgi_app(controller=None, transactional=False):
    """WSGI application creation helper

    :param controller: Overrides default application controller
    :param transactional: Adds transaction hook for all requests
    """
    request_hooks = [hooks.JSONErrorHook()]
    if transactional:
        request_hooks.append(hooks.BarbicanTransactionHook())

    # Create WSGI app
    wsgi_app = pecan.Pecan(
        controller or versions.AVAILABLE_VERSIONS[versions.DEFAULT_VERSION](),
        hooks=request_hooks,
        force_canonical=False
    )
    return wsgi_app


def main_app(func):
    def _wrapper(global_config, **local_conf):
        # Queuing initialization
        queue.init(CONF, is_server_side=False)

        # Configure oslo logging and configuration services.
        log.setup(CONF, 'barbican')

        config.setup_remote_pydev_debug()

        # Initializing the database engine and session factory before the app
        # starts ensures we don't lose requests due to lazy initialiation of db
        # connections.
        repositories.setup_database_engine_and_factory()

        wsgi_app = func(global_config, **local_conf)

        if newrelic_loaded:
            wsgi_app = newrelic.agent.WSGIApplicationWrapper(wsgi_app)
        LOG = log.getLogger(__name__)
        LOG.info(u._LI('Barbican app created and initialized'))
        return wsgi_app
    return _wrapper


@main_app
def create_main_app_v1(global_config, **local_conf):
    """uWSGI factory method for the Barbican-API application."""
    # Setup app with transactional hook enabled
    return build_wsgi_app(versions.V1Controller(), transactional=True)


def create_admin_app(global_config, **local_conf):
    wsgi_app = pecan.make_app(versions.VersionsController())
    return wsgi_app


create_version_app = create_admin_app
